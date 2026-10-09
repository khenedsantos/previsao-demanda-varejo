"""Compara A/N/A solicitado (incluindo fallback) com Seasonal Naive, sem novos ajustes."""

import json
from pathlib import Path
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.forecasting.backtesting import export_frame,fold_stability,records,SEGMENT_KEYS,SUMMARY_LEVELS,peak_working_set_bytes
from src.forecasting.ets import PRIMARY_MODEL
from src.forecasting.ets_benchmark import phase4_inputs
from src.forecasting.statistical_backtesting import write_json
from src.ingestion.source_manifest import ROOT,sha256_file
from src.segmentation.operational_profile import json_ready
from src.validation.forecast_metrics import create_metric_tables,DIMENSION_TYPES,metrics_from_arrays


REFERENCE="seasonal_naive"
PAIR_KEYS=["level",*DIMENSION_TYPES]
ERROR_METRICS=["mae","rmse","wape"]
EXTRA_LEVELS={"series_abc":["store_id","product_id","abc_class"],
              "series_xyz":["store_id","product_id","xyz_class"]}
TIE_ATOL=1e-12
TIE_RTOL=1e-10


def frame_records(frame):
    return json_ready(frame.astype(object).where(frame.notna(),None).to_dict("records"))


def pair_metrics(metrics):
    reference=metrics.loc[metrics.model.eq(REFERENCE)].drop(columns="model")
    challenger=metrics.loc[metrics.model.eq(PRIMARY_MODEL)].drop(columns="model")
    if len(reference)!=len(challenger):
        raise ValueError("Cobertura desigual dos modelos.")
    pairs=reference.merge(challenger,on=PAIR_KEYS,suffixes=("_seasonal_naive","_ets"),validate="one_to_one",how="outer",indicator=True)
    if not pairs["_merge"].eq("both").all():
        raise ValueError("Chaves não pareadas entre os modelos.")
    pairs=pairs.drop(columns="_merge")
    for column in ["n_forecasts","actual_sum","n_series","n_products","n_folds","n_series_folds"]:
        left=pairs[f"{column}_seasonal_naive"].to_numpy(dtype=float)
        right=pairs[f"{column}_ets"].to_numpy(dtype=float)
        if not np.allclose(left,right,rtol=1e-12,atol=1e-12):
            raise ValueError(f"Denominador/cobertura divergente: {column}")
        pairs[column]=pairs[f"{column}_seasonal_naive"]
        pairs=pairs.drop(columns=[f"{column}_seasonal_naive",f"{column}_ets"])
    pairs["undefined_percentage_metrics"]=pairs.actual_sum.eq(0)
    pairs=pairs.drop(columns=["undefined_percentage_metrics_seasonal_naive","undefined_percentage_metrics_ets"])
    for metric in ERROR_METRICS:
        baseline=pairs[f"{metric}_seasonal_naive"].to_numpy(dtype=float)
        ets=pairs[f"{metric}_ets"].to_numpy(dtype=float)
        valid=np.isfinite(baseline)&np.isfinite(ets)
        improvement=np.full(len(pairs),np.nan)
        np.divide(baseline-ets,baseline,out=improvement,where=valid&(baseline>0))
        pairs[f"improvement_{metric}"]=improvement
        tie=np.isclose(baseline,ets,rtol=TIE_RTOL,atol=TIE_ATOL)
        pairs[f"winner_{metric}"]=np.where(~valid,"undefined",np.where(tie,"tie",np.where(ets<baseline,"ets","seasonal_naive")))
    pairs["bias_change"]=pairs.bias_ets-pairs.bias_seasonal_naive
    return pairs.sort_values(PAIR_KEYS,na_position="last").reset_index(drop=True)


def win_rate_tables(pairs):
    rows=[]
    for source,level,dimension in [("series","global",None),("series_abc","abc","abc_class"),("series_xyz","xyz","xyz_class")]:
        frame=pairs.loc[pairs.level.eq(source)]
        groups=[("ALL",frame)] if dimension is None else frame.groupby(dimension,observed=True,sort=True)
        for label,part in groups:
            for metric in ["mae","wape"]:
                counts=part[f"winner_{metric}"].value_counts()
                valid=int(len(part)-counts.get("undefined",0))
                row={"level":level,"segment":label,"metric":metric,"n_series_cases":len(part),"valid_cases":valid,
                     "undefined_cases":int(counts.get("undefined",0)),"min_folds":int(part.n_folds.min()),"max_folds":int(part.n_folds.max())}
                for label_name in ["ets","seasonal_naive","tie"]:
                    row[f"{label_name}_count"]=int(counts.get(label_name,0))
                    row[f"{label_name}_rate"]=row[f"{label_name}_count"]/valid if valid else None
                rows.append(row)
    return pd.DataFrame(rows)


def materiality_table(pairs):
    series=pairs.loc[pairs.level.eq("series")]
    rows=[]
    for metric in ["mae","rmse","wape"]:
        values=series[f"improvement_{metric}"].dropna()
        row={"metric":metric,"total_series":len(series),"valid_series":len(values),"undefined_reference":len(series)-len(values),
             "p25":values.quantile(.25),"median":values.median(),"p75":values.quantile(.75),"positive_fraction":values.gt(0).mean()}
        for threshold in [.01,.05,.10]:
            label=f"{int(threshold*100):02d}"
            row[f"improvement_ge_{label}"]=values.ge(threshold).mean()
            row[f"decline_le_minus_{label}"]=values.le(-threshold).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def hybrid_choices(segment_fold_pairs):
    """Análise predefinida: mínimo dois folds passados; nunca olha o erro do fold escolhido."""
    choices=[]
    for (abc,xyz),group in segment_fold_pairs.groupby(["abc_class","xyz_class"],observed=True,sort=True):
        for fold in sorted(group.fold_id.unique()):
            previous=group.loc[group.fold_id<fold]
            selected=REFERENCE
            reason="insufficient_completed_folds"
            if len(previous)>=2:
                consistent=previous.improvement_wape.gt(0).all() and previous.improvement_rmse.ge(0).all()
                bias_ok=abs(previous.error_sum_ets.sum())<=abs(previous.error_sum_seasonal_naive.sum())+TIE_ATOL
                reason="past_error_not_consistent" if not consistent else "past_absolute_bias_worse"
                if consistent and bias_ok:
                    selected=PRIMARY_MODEL
                    reason="past_error_and_bias_qualify"
            choices.append({"fold_id":int(fold),"abc_class":abc,"xyz_class":xyz,"model_used":selected,
                            "completed_folds":len(previous),"reason":reason})
    return pd.DataFrame(choices)


def evaluate_hybrid(connection,choices,forecast_paths,segments_path):
    connection.register("hybrid_choices",choices)
    all_actual,all_forecast,rows=[],[],[]
    for fold in sorted(choices.fold_id.unique()):
        arrays=connection.execute("""
            SELECT f.actual,f.forecast FROM read_parquet(?,union_by_name=true) f
            JOIN read_parquet(?) s USING(store_id,product_id,fold_id,forecast_origin)
            JOIN hybrid_choices p USING(fold_id,abc_class,xyz_class)
            WHERE f.model=p.model_used AND f.fold_id=?
            ORDER BY f.store_id,f.product_id,f.target_date
        """,[[str(p) for p in forecast_paths],str(segments_path),int(fold)]).fetchnumpy()
        if len(arrays["actual"])!=350000:
            raise ValueError("Cobertura da análise híbrida divergente.")
        rows.append({"level":"fold","fold_id":int(fold),**metrics_from_arrays(arrays["actual"],arrays["forecast"])})
        all_actual.append(arrays["actual"])
        all_forecast.append(arrays["forecast"])
    rows.append({"level":"global","fold_id":None,**metrics_from_arrays(np.concatenate(all_actual),np.concatenate(all_forecast))})
    connection.unregister("hybrid_choices")
    return pd.DataFrame(rows)


def select_statistical_examples(pairs,fallback_keys):
    current=pairs.loc[pairs.level.eq("series_fold")&pairs.fold_id.eq(4)].copy()
    rules=[
        ("ETS_GAIN_AX",current.abc_class.eq("A")&current.xyz_class.eq("X")&current.improvement_wape.gt(0),"improvement_wape",False),
        ("ETS_LOSS_AX",current.abc_class.eq("A")&current.xyz_class.eq("X")&current.improvement_wape.lt(0),"improvement_wape",True),
        ("ETS_GAIN_AZ",current.abc_class.eq("A")&current.xyz_class.eq("Z")&current.improvement_wape.gt(0),"improvement_wape",False),
        ("ETS_REDUCES_UNDER",current.bias_seasonal_naive.lt(0)&current.bias_ets.le(0)&current.bias_change.gt(0),"bias_change",False),
        ("ETS_INCREASES_UNDER",current.bias_ets.lt(0)&current.bias_change.lt(0),"bias_change",True),
        ("SEASONAL_NAIVE_SUPERIOR",current.improvement_wape.lt(0),"improvement_wape",True),
    ]
    selected=[]
    for rule,mask,metric,ascending in rules:
        eligible=current.loc[mask]
        if not eligible.empty:
            row=eligible.sort_values([metric,"store_id","product_id"],ascending=[ascending,True,True]).iloc[0].to_dict()
            selected.append({"selection_rule":rule,"selection_metric":metric,**row})
    if len(fallback_keys):
        key=fallback_keys.sort_values(["fold_id","store_id","product_id"],ascending=[False,True,True]).iloc[0]
        row=pairs.loc[pairs.level.eq("series_fold")&pairs.fold_id.eq(key.fold_id)&pairs.store_id.eq(key.store_id)&pairs.product_id.eq(key.product_id)].iloc[0].to_dict()
        selected.append({"selection_rule":"FALLBACK_LATEST_ORIGIN","selection_metric":"latest_fold_then_ids",**row})
    return pd.DataFrame(selected)


def diagnostic_tables(connection,forecast_path,segments_path):
    connection.execute("""CREATE TEMP TABLE diagnostic_forecasts AS
        SELECT f.*,s.abc_class,s.xyz_class,s.stockout_exposure,s.censoring_risk_flag
        FROM read_parquet(?) f JOIN read_parquet(?) s USING(store_id,product_id,fold_id,forecast_origin)
    """,[str(forecast_path),str(segments_path)])
    outputs=[]
    dimensions={"fold_id":"INTEGER","abc_class":"VARCHAR","xyz_class":"VARCHAR","stockout_exposure":"VARCHAR","censoring_risk_flag":"BOOLEAN"}
    for level,cols in [("global",[]),("fold",["fold_id"]),("abc",["abc_class"]),("xyz",["xyz_class"]),
                      ("abc_xyz",["abc_class","xyz_class"]),("stockout_exposure",["stockout_exposure"]),("censoring_risk_flag",["censoring_risk_flag"])]:
        keys=", ".join(name if name in cols else f"NULL::{kind} AS {name}" for name,kind in dimensions.items())
        group_by=" GROUP BY "+", ".join(cols) if cols else ""
        query=f"""SELECT '{level}' AS level,{keys},count(*) AS n_forecasts,
            count(*) FILTER(WHERE horizon_step=1) AS n_fits,
            count(*) FILTER(WHERE horizon_step=1 AND fallback_flag) AS fallback_fits,
            count(*) FILTER(WHERE negative_clipped) AS clipped_forecasts,
            count(DISTINCT (store_id,product_id,fold_id)) FILTER(WHERE negative_clipped) AS clipped_fits,
            min(forecast_unclipped) FILTER(WHERE negative_clipped) AS minimum_unclipped,
            avg(-forecast_unclipped) FILTER(WHERE negative_clipped) AS mean_clip_magnitude,
            sum(-forecast_unclipped) FILTER(WHERE negative_clipped) AS total_upward_projection
            FROM diagnostic_forecasts{group_by}"""
        outputs.extend(records(connection,query))
    diagnostics=pd.DataFrame(outputs)
    diagnostics["fallback_rate"]=diagnostics.fallback_fits/diagnostics.n_fits
    diagnostics["clipping_rate"]=diagnostics.clipped_forecasts/diagnostics.n_forecasts
    reasons=connection.execute("""SELECT fold_id,fallback_reason,count(*) AS n_fits
        FROM diagnostic_forecasts WHERE horizon_step=1 AND fallback_flag GROUP BY ALL ORDER BY ALL""").df()
    fallback_keys=connection.execute("""SELECT store_id,product_id,fold_id FROM diagnostic_forecasts
        WHERE horizon_step=1 AND fallback_flag ORDER BY fold_id,store_id,product_id""").df()
    return diagnostics,reasons,fallback_keys


def run_comparison(root=ROOT):
    root=Path(root)
    started=perf_counter()
    phase4=phase4_inputs(root)
    folder=root / "data/outputs/statistical_forecasting"
    forecast_path=root / "data/processed/mart_forecast_statistical.parquet"
    population=json.loads((folder / "population_performance.json").read_text(encoding="utf-8"))
    if sha256_file(forecast_path)!=population["forecast_sha256"]:
        raise ValueError("Forecast populacional diferente do resultado registrado.")
    forecasts=[root / phase4["artifacts"]["forecasts"]["path"],forecast_path]
    segments=root / phase4["artifacts"]["fold_segments"]["path"]
    temp=root / ".tmp/statistical_comparison"
    temp.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(config={"threads":1,"memory_limit":"768MB","temp_directory":str(temp),"max_temp_directory_size":"2GB"}) as connection:
        connection.execute("SET enable_progress_bar=false")
        create_metric_tables(connection,forecasts,segments,models=[REFERENCE,PRIMARY_MODEL],extra_levels=EXTRA_LEVELS)
        metric_rows=records(connection,"SELECT * FROM metrics WHERE level NOT LIKE 'series%' ORDER BY level,model,fold_id,abc_class,xyz_class,stockout_exposure,censoring_risk_flag")
        long_metrics=connection.execute("SELECT * FROM metrics ORDER BY level,model,fold_id,store_id,product_id,abc_class,xyz_class").df()
        for table in ["atomic_metrics","metric_sums","metrics"]:
            connection.execute(f"DROP TABLE {table}")
        pairs=pair_metrics(long_metrics)
        del long_metrics
        paired_path=root / "data/processed/mart_model_comparison.parquet"
        export_frame(pairs,paired_path)
        wins=win_rate_tables(pairs)
        materiality=materiality_table(pairs)
        stability=fold_stability(pd.DataFrame([r for r in metric_rows if r["level"]=="fold" or r["level"].endswith("_fold")]))
        diagnostics,reasons,fallback_keys=diagnostic_tables(connection,forecast_path,segments)
        examples=select_statistical_examples(pairs,fallback_keys)
        choices=hybrid_choices(pairs.loc[pairs.level.eq("abc_xyz_fold")])
        hybrid=evaluate_hybrid(connection,choices,forecasts,segments)
        series=pairs.loc[pairs.level.eq("series")]
        bias=[]
        for suffix,model in [("seasonal_naive",REFERENCE),("ets",PRIMARY_MODEL)]:
            values=series[f"bias_{suffix}"]
            percentages=series[f"bias_pct_{suffix}"]
            bias.append({"model":model,"n_series":len(series),"negative_bias_series":int(values.lt(0).sum()),
                "negative_bias_fraction":float(values.lt(0).mean()),"bias_quantiles":values.quantile([.05,.25,.5,.75,.95]).tolist(),
                "bias_pct_quantiles":percentages.quantile([.05,.25,.5,.75,.95]).tolist(),"undefined_bias_pct":int(percentages.isna().sum())})
        denominators=[]
        for level in ["series","series_fold"]:
            part=pairs.loc[pairs.level.eq(level)]
            denominators.append({"level":level,"n_pairs":len(part),"zero_denominator_pairs":int(part.actual_sum.eq(0).sum()),
                "minimum_positive_actual_sum":part.loc[part.actual_sum.gt(0),"actual_sum"].min(),
                "zero_reference_mae":int(part.mae_seasonal_naive.eq(0).sum()),"undefined_improvement_wape":int(part.improvement_wape.isna().sum())})
        compact_pairs=pairs.loc[~pairs.level.str.startswith("series")].copy()
        connection.register("example_keys",examples[["selection_rule","store_id","product_id","fold_id","forecast_origin"]])
        example_forecasts=connection.execute("""SELECT e.selection_rule,f.* FROM read_parquet(?,union_by_name=true) f
            JOIN example_keys e USING(store_id,product_id,fold_id,forecast_origin)
            WHERE f.model IN ('seasonal_naive','ets_ana') ORDER BY e.selection_rule,f.model,f.target_date""",[[str(p) for p in forecasts]]).df()
        example_actuals=connection.execute("""SELECT e.selection_rule,cast(r.dt AS DATE) AS dt,r.sale_amount,r.stock_hour6_22_cnt
            FROM read_parquet(?) r JOIN example_keys e USING(store_id,product_id)
            WHERE cast(r.dt AS DATE) BETWEEN e.forecast_origin-INTERVAL 14 DAY AND e.forecast_origin+INTERVAL 6 DAY
            ORDER BY e.selection_rule,dt""",[str(root / "data/raw/train.parquet")]).df()
    artifact_paths={"forecasts":forecast_path,"comparison":paired_path}
    tables={"win_rates":wins,"materiality":materiality,"fold_stability":stability,"fit_diagnostics":diagnostics,
        "fallback_reasons":reasons,"hybrid_choices":choices,"hybrid_metrics":hybrid,
        "example_selection":examples,"example_forecasts":example_forecasts,"example_actuals":example_actuals}
    for name,frame in tables.items():
        path=folder / f"{name}.parquet"
        export_frame(frame,path)
        artifact_paths[name]=path
    fold_pairs=compact_pairs.loc[compact_pairs.level.eq("fold")]
    summary={"source_split":"train","target":"sale_amount","target_interpretation":"venda observada normalizada",
        "analysis_view":"prospective","reference":REFERENCE,"challenger":PRIMARY_MODEL,"folds":phase4["folds"],
        "source":phase4["source"],"phase4_summary_sha256":sha256_file(root / "data/outputs/forecasting_baselines/summary.json"),
        "benchmark_sha256":sha256_file(folder / "benchmark.json"),"n_requested_fits":population["n_fits"],
        "n_forecasts_per_model":1400000,"metrics":[r for r in metric_rows if r["level"] in SUMMARY_LEVELS],
        "fold_segment_metrics":metric_rows,"comparisons":frame_records(compact_pairs),"bias_distribution":bias,
        "denominator_diagnostics":json_ready(denominators),"win_rates":frame_records(wins),"materiality":frame_records(materiality),
        "fit_diagnostics":frame_records(diagnostics),"fallback_reasons":frame_records(reasons),
        "fold_wins":{metric:fold_pairs[f"winner_{metric}"].value_counts().to_dict() for metric in ERROR_METRICS},
        "hybrid_metrics":frame_records(hybrid),"hybrid_rule":"minimum_two_completed_folds; all_previous_WAPE_wins; no_previous_RMSE_loss; pooled_absolute_bias_not_worse",
        "hybrid_analysis_only":True,"examples":frame_records(examples),
        "win_rate_segment_definition":"series x prospective class, aggregating only folds where that class was known; counts across classes may overlap",
        "tie_tolerance":{"atol":TIE_ATOL,"rtol":TIE_RTOL},
        "reproduction_scope":"contracts, hashes, baseline consistency and small-sample fits; no second population fit requested",
        "artifacts":{name:{"path":path.relative_to(root).as_posix(),"sha256":sha256_file(path),"rows":pq.ParquetFile(path).metadata.num_rows}
            for name,path in artifact_paths.items()}}
    write_json(folder / "summary.json",json_ready(summary))
    elapsed=perf_counter()-started
    performance={"comparison_seconds":elapsed,"comparison_peak_working_set_bytes":peak_working_set_bytes(),
        "population_plus_comparison_seconds":population["population_seconds"]+elapsed,
        "total_fit_seconds":population["fit_seconds"],"overhead_population_plus_comparison_seconds":population["population_overhead_seconds"]+elapsed,
        "parquet_bytes":sum(path.stat().st_size for path in artifact_paths.values()),
        "scope":"population and comparison, excluding later report/notebook; no second population fit"}
    write_json(folder / "comparison_performance.json",performance)
    print(f"Comparação concluída em {elapsed:.2f}s; {len(pairs)} pares de métricas; nenhum novo ajuste.",flush=True)
    return summary,performance
