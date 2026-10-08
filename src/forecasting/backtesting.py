"""Rolling-origin de sete dias com segmentação refeita em cada corte de train."""

from datetime import timedelta
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.features.demand_profile import TRAIN_START,TRAIN_END,prepare_tables
from src.forecasting.baselines import HORIZON,create_predictions
from src.ingestion.source_manifest import ROOT,load_manifest,project_paths,sha256_file,verify_file
from src.segmentation.abc import classify_products
from src.segmentation.xyz import fit_thresholds,classify_series,WEEKLY_CV,PATTERN
from src.segmentation.stockout_exposure import fit_exposure_thresholds,classify_exposure
from src.segmentation.operational_profile import combine_dimensions,json_ready
from src.validation.forecast_metrics import create_metric_tables,relative_improvement


N_FOLDS=4
SEGMENT_KEYS=["abc_class","xyz_class","stockout_exposure","censoring_risk_flag"]
SUMMARY_LEVELS=["global","fold","abc","xyz","stockout_exposure","censoring_risk_flag","abc_xyz"]


def make_folds():
    first_test=TRAIN_END-timedelta(days=N_FOLDS*HORIZON-1)
    folds=[]
    for index in range(N_FOLDS):
        origin=first_test+timedelta(days=index*HORIZON)
        cutoff=origin-timedelta(days=1)
        folds.append({"fold_id":index+1,"forecast_origin":origin,"cutoff_date":cutoff,
                      "history_start":TRAIN_START,"history_end":cutoff,
                      "history_days":(origin-TRAIN_START).days,
                      "test_start":origin,"test_end":origin+timedelta(days=HORIZON-1)})
    return folds


def compute_fold(train_path,fold,temporary):
    """Não lê marts finais. Segmentar e prever ocorrem antes de juntar os actuals."""
    temporary=Path(temporary)
    temporary.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(config={"threads":1,"memory_limit":"1GB","temp_directory":str(temporary),
                                "max_temp_directory_size":"2GB"}) as connection:
        connection.execute("SET enable_progress_bar=false")
        prepare_tables(connection,Path(train_path),as_of=fold["cutoff_date"])
        profile=connection.execute("SELECT * FROM profile ORDER BY store_id,product_id").df()
        abc=classify_products(connection.execute("""
            SELECT product_id,sum(sale_amount) AS normalized_sales_total,
                   count(DISTINCT store_id) AS associated_series
            FROM train GROUP BY product_id ORDER BY product_id
        """).df())
        xyz_thresholds=fit_thresholds(profile)
        exposure_thresholds=fit_exposure_thresholds(profile)
        xyz=classify_series(profile,xyz_thresholds)
        exposure=classify_exposure(profile,exposure_thresholds)
        operational=combine_dimensions(profile,abc,xyz,exposure)
        snapshot=operational[["store_id","product_id","source_split","n_days",*SEGMENT_KEYS,"xyz_reason",
                              "mean_demand","zero_ratio","stockout_rate",WEEKLY_CV,PATTERN]].copy()
        snapshot["fold_id"]=fold["fold_id"]
        snapshot["forecast_origin"]=fold["forecast_origin"]
        snapshot["cutoff_date"]=fold["cutoff_date"]
        abc["fold_id"]=fold["fold_id"]
        abc["forecast_origin"]=fold["forecast_origin"]
        abc["cutoff_date"]=fold["cutoff_date"]
        create_predictions(connection,fold["forecast_origin"])
        expected=len(profile)*HORIZON*2
        grain=connection.execute("SELECT count(*),count(DISTINCT (store_id,product_id,forecast_origin,target_date,model)) FROM predictions").fetchone()
        if grain!=(expected,expected):
            raise ValueError("Cobertura/chave das previsões divergente.")
        # Actuals do horizonte entram somente para medir erro após a previsão estar pronta.
        connection.execute("""
            CREATE TEMP TABLE evaluated AS
            SELECT p.*,a.sale_amount AS actual,p.forecast-a.sale_amount AS error,?::INTEGER AS fold_id
            FROM predictions p JOIN read_parquet(?) a
              ON p.store_id=a.store_id AND p.product_id=a.product_id AND p.target_date=cast(a.dt AS DATE)
        """,[fold["fold_id"],str(train_path)])
        if connection.execute("SELECT count(*) FROM evaluated").fetchone()[0]!=expected:
            raise ValueError("Actuals faltantes ou duplicados no horizonte de train.")
        forecasts=connection.execute("""
            SELECT store_id,product_id,fold_id,forecast_origin,cutoff_date,target_date,horizon_step,
                   model,source_observation_date,actual,forecast,error
            FROM evaluated ORDER BY store_id,product_id,model,target_date
        """).to_arrow_table()
    details={**fold,"n_series":len(profile),"xyz_thresholds":xyz_thresholds,"exposure_thresholds":exposure_thresholds,
             "xyz_counts":snapshot.xyz_class.value_counts().sort_index().to_dict(),
             "abc_product_counts":abc.abc_class.value_counts().sort_index().to_dict(),
             "exposure_counts":snapshot.stockout_exposure.value_counts().sort_index().to_dict(),
             "censoring_risk_count":int(snapshot.censoring_risk_flag.sum()),
             "undefined_pattern_count":int(profile[PATTERN].isna().sum()),
             "no_stockout_history_count":int(profile.stockout_rate.eq(0).sum()),
             "complete_weeks":sorted(profile.complete_weeks.unique().tolist())}
    return forecasts,snapshot,abc,details


def export_frame(frame,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary,index=False,engine="pyarrow",compression="zstd",row_group_size=65536)
    temporary.replace(path)


def records(connection,query):
    cursor=connection.execute(query)
    names=[c[0] for c in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def comparisons(metric_rows):
    # Níveis consolidados, sem inventar melhoria percentual para bias com sinal.
    frame=pd.DataFrame(metric_rows)
    keys=["level","fold_id","forecast_origin",*SEGMENT_KEYS]
    pairs=frame.loc[frame.model.eq("naive")].merge(frame.loc[frame.model.eq("seasonal_naive")],
                                                  on=keys,suffixes=("_naive","_seasonal"),validate="one_to_one")
    result=[]
    for row in pairs.to_dict("records"):
        base={key:row[key] for key in keys}
        base["actual_sum"]=row["actual_sum_naive"]
        for metric in ["mae","rmse","wape"]:
            naive,seasonal=row[f"{metric}_naive"],row[f"{metric}_seasonal"]
            result.append({**base,"metric":metric,"naive":naive,"seasonal_naive":seasonal,
                           "relative_improvement":relative_improvement(naive,seasonal)})
    return pd.DataFrame(result)


def fold_stability(fold_metrics):
    frame=fold_metrics.copy()
    frame["level"]=frame.level.str.replace("_fold","",regex=False).replace({"fold":"global"})
    keys=["level","model",*SEGMENT_KEYS]
    rows=[]
    for key,group in frame.groupby(keys,dropna=False,sort=True):
        row=dict(zip(keys,key))
        row["n_folds"]=len(group)
        for metric in ["mae","rmse","wape","bias","bias_pct"]:
            values=group[metric].dropna()
            mean=values.mean()
            row.update({f"{metric}_valid_folds":len(values),f"{metric}_mean":mean,
                        f"{metric}_std":values.std(ddof=1),f"{metric}_min":values.min(),f"{metric}_max":values.max()})
            if metric in {"mae","rmse","wape"}:
                row[f"{metric}_cv"]=values.std(ddof=1)/mean if mean>0 else None
        rows.append(row)
    return pd.DataFrame(rows)


def select_examples(series_fold,last_fold):
    current=series_fold.loc[series_fold.fold_id.eq(last_fold)].copy()
    seasonal=current.loc[current.model.eq("seasonal_naive")]
    rules=[
        ("SN_BEST_AX",(seasonal.abc_class=="A")&(seasonal.xyz_class=="X")&seasonal.wape.notna(),"wape",True),
        ("SN_WORST_AX",(seasonal.abc_class=="A")&(seasonal.xyz_class=="X")&seasonal.wape.notna(),"wape",False),
        ("SN_MOST_UNDER_AZ",(seasonal.abc_class=="A")&(seasonal.xyz_class=="Z")&(seasonal.bias<0),"bias",True),
        ("SN_HIGH_EXPOSURE_HIGH_ERROR",(seasonal.stockout_exposure=="HIGH")&seasonal.wape.notna(),"wape",False),
        ("SN_CENSOR_STRONG_UNDER",seasonal.censoring_risk_flag.eq(True)&(seasonal.bias<0),"bias",True),
    ]
    chosen=[]
    for name,mask,metric,ascending in rules:
        eligible=seasonal.loc[mask]
        if not eligible.empty:
            row=eligible.sort_values([metric,"store_id","product_id"],ascending=[ascending,True,True]).iloc[0].to_dict()
            chosen.append({"selection_rule":name,"selection_metric":metric,**row})
    naive=current.loc[current.model.eq("naive"),["store_id","product_id","wape"]].rename(columns={"wape":"naive_wape"})
    paired=seasonal.merge(naive,on=["store_id","product_id"],validate="one_to_one")
    paired["seasonal_minus_naive_wape"]=paired.wape-paired.naive_wape
    eligible=paired.loc[paired.seasonal_minus_naive_wape>0]
    if not eligible.empty:
        row=eligible.sort_values(["seasonal_minus_naive_wape","store_id","product_id"],ascending=[False,True,True]).iloc[0].to_dict()
        chosen.append({"selection_rule":"NAIVE_BEATS_SEASONAL","selection_metric":"seasonal_minus_naive_wape",**row})
    return pd.DataFrame(chosen)


def peak_working_set_bytes():
    if os.name!="nt":
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
            ["PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage",
             "QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage"]]
    counters=Counters()
    counters.cb=ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
    query=ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not query(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        return None
    return int(counters.PeakWorkingSetSize)


def run_backtest(root=ROOT):
    started=perf_counter()
    root=Path(root)
    _,paths=project_paths(root)
    manifest=load_manifest(root)
    train_entry=next(e for e in manifest["files"] if e["role"]=="train")
    train_path=paths["raw"] / "train.parquet"
    verify_file(train_path,train_entry)
    output=paths["outputs"] / "forecasting_baselines"
    output.mkdir(parents=True,exist_ok=True)
    paths["processed"].mkdir(parents=True,exist_ok=True)
    forecast_path=paths["processed"] / "mart_forecast_baselines.parquet"
    temporary_forecasts=forecast_path.with_suffix(".parquet.tmp")
    snapshots,product_classes,fold_details,fold_times=[],[],[],[]
    writer=None
    try:
        for fold in make_folds():
            fold_started=perf_counter()
            print(f"Fold {fold['fold_id']}: histórico até {fold['cutoff_date']}; teste {fold['test_start']} a {fold['test_end']}",flush=True)
            predictions,snapshot,abc,details=compute_fold(train_path,fold,root / ".tmp/forecasting_baselines")
            if writer is None:
                writer=pq.ParquetWriter(temporary_forecasts,predictions.schema,compression="zstd",version="2.6")
            writer.write_table(predictions,row_group_size=65536)
            snapshots.append(snapshot)
            product_classes.append(abc)
            fold_details.append(details)
            fold_times.append({"fold_id":fold["fold_id"],"seconds":perf_counter()-fold_started})
            del predictions
    finally:
        if writer is not None:
            writer.close()
    temporary_forecasts.replace(forecast_path)
    segments=pd.concat(snapshots,ignore_index=True).sort_values(["fold_id","store_id","product_id"])
    segment_path=output / "fold_segments.parquet"
    export_frame(segments,segment_path)
    abc_path=output / "fold_product_abc.parquet"
    export_frame(pd.concat(product_classes,ignore_index=True).sort_values(["fold_id","abc_rank"]),abc_path)
    print("Consolidando métricas, melhorias relativas, bias e estabilidade...",flush=True)
    with duckdb.connect(config={"threads":1,"memory_limit":"1GB"}) as connection:
        connection.execute("SET enable_progress_bar=false")
        create_metric_tables(connection,forecast_path,segment_path)
        metric_path=paths["processed"] / "mart_forecast_metrics.parquet"
        table=connection.execute("""SELECT * FROM metrics ORDER BY level,model,fold_id,store_id,product_id,
            abc_class,xyz_class,stockout_exposure,censoring_risk_flag""").to_arrow_table()
        pq.write_table(table,metric_path,compression="zstd",version="2.6",row_group_size=65536)
        del table
        summary_metrics=records(connection,"SELECT * FROM metrics WHERE level NOT IN ('series','series_fold') ORDER BY level,model,fold_id,abc_class,xyz_class,stockout_exposure,censoring_risk_flag")
        compact=[r for r in summary_metrics if r["level"] in SUMMARY_LEVELS]
        improvements=comparisons(compact)
        stability=fold_stability(pd.DataFrame([r for r in summary_metrics if r["level"]=="fold" or r["level"].endswith("_fold")]))
        series_fold=connection.execute("SELECT * FROM metrics WHERE level='series_fold' ORDER BY fold_id,model,store_id,product_id").df()
        examples=select_examples(series_fold,N_FOLDS)
        del series_fold
        connection.register("example_keys",examples[["selection_rule","store_id","product_id","fold_id","forecast_origin"]])
        example_forecasts=connection.execute("""
            SELECT e.selection_rule,f.* FROM read_parquet(?) f JOIN example_keys e
            USING(store_id,product_id,fold_id,forecast_origin)
            ORDER BY e.selection_rule,f.model,f.target_date
        """,[str(forecast_path)]).df()
        example_actuals=connection.execute("""
            SELECT e.selection_rule,cast(r.dt AS DATE) AS dt,r.sale_amount,r.stock_hour6_22_cnt
            FROM read_parquet(?) r JOIN example_keys e USING(store_id,product_id)
            WHERE cast(r.dt AS DATE) BETWEEN e.forecast_origin-INTERVAL 14 DAY AND e.forecast_origin+INTERVAL 6 DAY
            ORDER BY e.selection_rule,dt
        """,[str(train_path)]).df()
        bias_distribution=records(connection,"""
            SELECT model,count(*) AS n_series,count(*) FILTER(WHERE bias<0) AS underforecast_series,
                   count(*) FILTER(WHERE bias>0) AS overforecast_series,
                   quantile_cont(bias,[.01,.05,.25,.5,.75,.95,.99]) AS bias_quantiles,
                   quantile_cont(bias_pct,[.01,.05,.25,.5,.75,.95,.99]) AS bias_pct_quantiles,
                   count(*) FILTER(WHERE bias_pct IS NULL) AS undefined_bias_pct
            FROM metrics WHERE level='series' GROUP BY model ORDER BY model
        """)
        denominator_diagnostics=records(connection,"""
            WITH limits AS (
                SELECT level,model,quantile_cont(actual_sum,.05) FILTER(WHERE actual_sum>0) AS positive_p05
                FROM metrics WHERE level IN ('series','series_fold') GROUP BY level,model
            )
            SELECT m.level,m.model,count(*) AS n_cases,count(*) FILTER(WHERE actual_sum=0) AS undefined_wape_cases,
                   min(actual_sum) AS min_actual_sum,median(actual_sum) AS median_actual_sum,
                   min(actual_sum) FILTER(WHERE actual_sum>0) AS min_positive_actual_sum,
                   any_value(positive_p05) AS positive_p05,
                   count(*) FILTER(WHERE actual_sum>0 AND actual_sum<=positive_p05) AS low_scale_cases,
                   median(wape) FILTER(WHERE actual_sum>0 AND actual_sum<=positive_p05) AS low_scale_median_wape,
                   max(wape) FILTER(WHERE actual_sum>0 AND actual_sum<=positive_p05) AS low_scale_max_wape
            FROM metrics m JOIN limits l USING(level,model) GROUP BY m.level,m.model ORDER BY m.level,m.model
        """)
    auxiliaries={"relative_improvement":improvements,"fold_stability":stability,"example_selection":examples,
                 "example_forecasts":example_forecasts,"example_actuals":example_actuals}
    artifact_paths={"forecasts":forecast_path,"metrics":metric_path,"fold_segments":segment_path,"fold_product_abc":abc_path}
    for name,frame in auxiliaries.items():
        path=output / f"{name}.parquet"
        export_frame(frame,path)
        artifact_paths[name]=path
    global_metrics=[r for r in compact if r["level"]=="global"]
    reference=min(global_metrics,key=lambda row:(row["wape"],row["model"]))["model"]
    summary={"source_split":"train","target":"sale_amount","target_interpretation":"venda observada normalizada",
             "analysis_view":"prospective","forecast_origin_definition":"first_target_day_before_observing_sales",
             "horizon_days":HORIZON,"folds":fold_details,"n_series":len(segments)//N_FOLDS,
             "n_forecasts":pq.ParquetFile(forecast_path).metadata.num_rows,
             "source":{"path":"data/raw/train.parquet","sha256":train_entry["sha256"],"revision":manifest["source_revision"]},
             "metrics":compact,"fold_segment_metrics":summary_metrics,
             "bias_distribution":bias_distribution,"denominator_diagnostics":denominator_diagnostics,
             "reference_baseline":reference,"selection_criterion":"lowest_pooled_global_wape; MAE/RMSE/bias/fold_stability_reported_as_tradeoffs",
             "examples":examples.to_dict("records"),
             "runtime":{"python":sys.version.split()[0],**{name:version(name) for name in ["duckdb","pandas","numpy","pyarrow"]}},
             "artifacts":{name:{"path":path.relative_to(root).as_posix(),"sha256":sha256_file(path),
                                "rows":pq.ParquetFile(path).metadata.num_rows} for name,path in artifact_paths.items()}}
    summary=json_ready(summary)
    (output / "summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    performance={"pipeline_seconds":perf_counter()-started,"fold_times":fold_times,
                 "process_peak_working_set_bytes":peak_working_set_bytes(),"duckdb_memory_limit":"1GB",
                 "parquet_bytes":sum(p.stat().st_size for p in artifact_paths.values()),
                 "summary_bytes":(output / "summary.json").stat().st_size,
                 "measurement_scope":"current_process; pipeline includes source verification and tabular outputs, excludes notebook/report",
                 "reproducibility_note":"timing and process memory are telemetry, excluded from deterministic hashes"}
    (output / "performance.json").write_text(json.dumps(performance,indent=2)+"\n",encoding="utf-8")
    print(f"Concluído: {summary['n_forecasts']} previsões; referência {reference}; {performance['pipeline_seconds']:.1f}s.",flush=True)
    return summary,performance
