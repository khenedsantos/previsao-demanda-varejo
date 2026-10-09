"""Perfis pós-backtest em 25/06: dois sinais separados, sem score ou lost sales."""

import json
from pathlib import Path
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.features.demand_profile import TRAIN_END
from src.forecasting.backtesting import export_frame,make_folds,peak_working_set_bytes
from src.forecasting.statistical_backtesting import write_json
from src.ingestion.source_manifest import ROOT,load_manifest,sha256_file
from src.segmentation.operational_profile import validate_profile_scope,json_ready
from src.validation.forecast_uncertainty import KEYS,error_aggregation,attach_bias_persistence,metric_correlations,descriptive_thresholds


DIMENSIONS=["abc_class","xyz_class","stockout_exposure","censoring_risk_flag","demand_observation_risk_cell"]
RISK_CELLS=["NEITHER","UNDERFORECAST_ONLY","CENSORING_ONLY","CENSORING_AND_UNDERFORECAST"]
UNCERTAINTY_METRICS=["error_std","rmse","p90_absolute_error","p95_absolute_error"]
MIN_MATRIX_SERIES=100


def verified_inputs(root):
    specs={"phase5":("statistical_forecasting","forecasts"),
           "phase3":("segmentation","operational_profile"),"phase2":("demand_understanding","profile")}
    manifest=load_manifest(root)
    train=next(x for x in manifest["files"] if x["role"]=="train")
    inputs,metadata={},{}
    for label,(folder,artifact) in specs.items():
        path=root / "data/outputs" / folder / "summary.json"
        summary=json.loads(path.read_text(encoding="utf-8"))
        if summary["source_split"]!="train" or summary["source"]["path"]!="data/raw/train.parquet" or summary["source"]["sha256"]!=train["sha256"]:
            raise ValueError("Proveniência deve corresponder exclusivamente ao train congelado.")
        if label=="phase5":
            if summary["challenger"]!="ets_ana" or summary["analysis_view"]!="prospective":
                raise ValueError("Exige o ETS aprovado e backtest prospectivo da Fase 5.")
            if [(f["forecast_origin"],f["cutoff_date"]) for f in summary["folds"]]!=[
                (str(f["forecast_origin"]),str(f["cutoff_date"])) for f in make_folds()]:
                raise ValueError("Folds diferentes do protocolo aprovado.")
        elif summary["as_of"]!=str(TRAIN_END):
            raise ValueError("Perfil operacional deve ter corte em 25/06/2024.")
        item=summary["artifacts"][artifact]
        artifact_path=(root / item["path"]).resolve()
        if not artifact_path.is_relative_to((root / "data/processed").resolve()):
            raise ValueError("Input fora dos marts processados autorizados.")
        if sha256_file(artifact_path)!=item["sha256"]:
            raise ValueError(f"Input alterado: {label}")
        inputs[label]=artifact_path
        metadata[label]={"summary_path":path.relative_to(root).as_posix(),"summary_sha256":sha256_file(path),**item}
    return inputs,metadata,{"path":"data/raw/train.parquet","sha256":train["sha256"],"revision":manifest["source_revision"]}


def validate_observations(connection):
    row=connection.execute("""SELECT count(*),count(DISTINCT (store_id,product_id)),
        count(DISTINCT (store_id,product_id,fold_id,target_date)),
        count(*) FILTER(WHERE NOT isfinite(actual) OR actual<0 OR NOT isfinite(forecast) OR forecast<0
          OR NOT isfinite(error) OR abs(error-(forecast-actual))>1e-12
          OR model!='ets_ana' OR model_requested!='ets_ana'
          OR target_date<DATE '2024-05-29' OR target_date>DATE '2024-06-25'
          OR cutoff_date!=forecast_origin-1 OR date_diff('day',forecast_origin,target_date) NOT BETWEEN 0 AND 6)
        FROM observations""").fetchone()
    if row!=(1400000,50000,1400000,0):
        raise ValueError(f"Cobertura/grão/valores do ETS inválidos: {row}")
    windows=connection.execute("""SELECT fold_id,forecast_origin,cutoff_date,count(*)
        FROM observations GROUP BY ALL ORDER BY fold_id""").fetchall()
    if windows!=[(f["fold_id"],f["forecast_origin"],f["cutoff_date"],350000) for f in make_folds()]:
        raise ValueError("Janelas do backtest divergentes.")


def risk_cells(censoring,persistent):
    if pd.isna(censoring).any() or pd.isna(persistent).any():
        raise ValueError("Flags de risco não podem ser nulas.")
    censoring=np.asarray(censoring,dtype=bool)
    persistent=np.asarray(persistent,dtype=bool)
    return np.select([censoring&persistent,censoring, persistent],
                     [RISK_CELLS[3],RISK_CELLS[2],RISK_CELLS[1]],default=RISK_CELLS[0])


def make_risk_profile(uncertainty,operational,activity):
    validate_profile_scope(operational,TRAIN_END)
    validate_profile_scope(activity,TRAIN_END)
    cols=[*KEYS,"abc_class","xyz_class","stockout_exposure","censoring_risk_flag","stockout_rate",
          "zero_ratio","total_demand","mean_demand"]
    profile=uncertainty.merge(operational[cols],on=KEYS,validate="one_to_one",how="left")
    profile=profile.merge(activity[[*KEYS,"activity_rate"]],on=KEYS,validate="one_to_one",how="left")
    if len(profile)!=len(operational) or profile[[*DIMENSIONS[:-1],"activity_rate"]].isna().any().any():
        raise ValueError("Cobertura ou classes inválidas na junção de risco.")
    profile=profile.rename(columns={"total_demand":"train_normalized_sales_total"})
    profile["demand_observation_risk_cell"]=risk_cells(profile.censoring_risk_flag,profile.persistent_underforecast_flag)
    return profile.sort_values(KEYS).reset_index(drop=True)


def context_totals(metrics,dimensions,profile):
    if dimensions:
        sizes=profile.groupby(dimensions,dropna=False,observed=True).agg(
            train_normalized_sales_total=("train_normalized_sales_total","sum"),
            persistent_series=("persistent_underforecast_flag","sum"),
            mean_activity_rate=("activity_rate","mean")).reset_index()
        result=metrics.merge(sizes,on=dimensions,validate="one_to_one")
    else:
        result=metrics.assign(train_normalized_sales_total=profile.train_normalized_sales_total.sum(),
            persistent_series=profile.persistent_underforecast_flag.sum(),mean_activity_rate=profile.activity_rate.mean())
    result["train_normalized_sales_share"]=result.train_normalized_sales_total/profile.train_normalized_sales_total.sum()
    result["backtest_actual_share"]=result.actual_total/profile.actual_total.sum()
    result["series_share"]=result.n_series/len(profile)
    return result


def grouped_tables(connection,profile,levels):
    frames=[]
    for level,dimensions in levels.items():
        frame=error_aggregation(connection,dimensions,source="risk_observations")
        frame=context_totals(frame,dimensions,profile)
        frame.insert(0,"level",level)
        frames.append(frame)
    result=pd.concat(frames,ignore_index=True)
    for column in DIMENSIONS:
        if column not in result:
            result[column]=None
    return result.sort_values(["level",*DIMENSIONS],na_position="last").reset_index(drop=True)


def select_risk_examples(profile):
    rows=[]
    for cell in RISK_CELLS:
        group=profile.loc[profile.abc_class.eq("A")&profile.demand_observation_risk_cell.eq(cell)].copy()
        if len(group):
            group["selection_distance"]=(group.error_std-group.error_std.median()).abs()
            row=group.sort_values(["selection_distance",*KEYS]).iloc[0].to_dict()
            rows.append({"selection_rule":"A_"+cell,"selection_metric":"nearest_cell_median_error_std",**row})
    for name,mask,metric,ascending in [
        ("A_MAX_ERROR_STD",profile.abc_class.eq("A"),"error_std",False),
        ("A_MAX_UNDERFORECAST_RATE",profile.abc_class.eq("A"),"underforecast_rate",False),
        ("LOW_EXPOSURE_MIN_MAE",profile.stockout_exposure.eq("LOW"),"mae",True)]:
        row=profile.loc[mask].sort_values([metric,*KEYS],ascending=[ascending,True,True]).iloc[0].to_dict()
        rows.append({"selection_rule":name,"selection_metric":metric,**row})
    return pd.DataFrame(rows)


def robustness_tables(connection,profile,series_fold,thresholds):
    rows=[]
    q01,q99=connection.execute("SELECT quantile_cont(error,.01),quantile_cont(error,.99) FROM observations").fetchone()
    scenarios=[("official_all","TRUE"),("central_98pct_error",f"error BETWEEN {q01!r} AND {q99!r}"),
               ("exclude_low_actual_p05",f"series_actual_total>{thresholds['low_actual_p05']!r}")]
    for name,condition in scenarios:
        for dims in [[],["demand_observation_risk_cell"]]:
            frame=error_aggregation(connection,dims,source="risk_observations",where=condition)
            frame["scenario"]=name
            frame["scope"]="risk_cell" if dims else "global"
            rows.append(frame)
    remaining=[]
    official=profile.loc[profile.persistent_underforecast_flag,KEYS]
    for fold in range(1,5):
        frame=error_aggregation(connection,source="risk_observations",where=f"fold_id!={fold}")
        frame["scenario"]=f"omit_fold_{fold}"
        frame["scope"]="global"
        rows.append(frame)
        other=series_fold.loc[series_fold.fold_id.ne(fold)].copy()
        other["negative"]=other.bias.lt(0)
        per_series=other.groupby(KEYS).agg(bias=("bias","mean"),negative_remaining_folds=("negative","sum"))
        prior=official.merge(per_series,on=KEYS,validate="one_to_one")
        remaining.append({"omitted_fold":fold,"official_persistent_series":len(prior),
            "still_negative_consolidated":int(prior.bias.lt(0).sum()),
            "negative_in_all_three_remaining":int(prior.negative_remaining_folds.eq(3).sum()),
            "negative_in_at_least_two_remaining":int(prior.negative_remaining_folds.ge(2).sum())})
    return pd.concat(rows,ignore_index=True),pd.DataFrame(remaining),{"error_p01":q01,"error_p99":q99}


def build_forecast_risk(root=ROOT,write_document=True):
    root=Path(root).resolve()
    started=perf_counter()
    inputs,provenance,source=verified_inputs(root)
    folder=root / "data/outputs/forecast_uncertainty"
    folder.mkdir(parents=True,exist_ok=True)
    temp=root / ".tmp/forecast_uncertainty"
    temp.mkdir(parents=True,exist_ok=True)
    operational=pd.read_parquet(inputs["phase3"])
    activity=pd.read_parquet(inputs["phase2"])
    with duckdb.connect(config={"threads":1,"memory_limit":"768MB","temp_directory":str(temp),"max_temp_directory_size":"2GB"}) as connection:
        connection.execute("SET enable_progress_bar=false")
        connection.execute("CREATE TEMP TABLE observations AS SELECT *,greatest(-error,0) AS underforecast_amount FROM read_parquet(?)",[str(inputs["phase5"])])
        validate_observations(connection)
        series=error_aggregation(connection,KEYS)
        series_fold=error_aggregation(connection,[*KEYS,"fold_id"])
        if len(series)!=50000 or not series.n_forecasts.eq(28).all() or not series_fold.n_forecasts.eq(7).all():
            raise ValueError("Cobertura por série/fold incompleta.")
        uncertainty=attach_bias_persistence(series,series_fold)
        uncertainty["source_split"]="train"
        uncertainty["as_of"]=TRAIN_END
        uncertainty["available_from"]=pd.Timestamp(TRAIN_END).date()+pd.Timedelta(days=1)
        uncertainty["analysis_view"]="post_backtest_as_of_train_end"
        profile=make_risk_profile(uncertainty,operational,activity)
        connection.register("risk_profile",profile)
        connection.execute("""CREATE TEMP TABLE risk_observations AS SELECT o.*,r.abc_class,r.xyz_class,r.stockout_exposure,
            r.censoring_risk_flag,r.demand_observation_risk_cell,r.actual_total AS series_actual_total
            FROM observations o JOIN risk_profile r USING(store_id,product_id)""")
        calibration=grouped_tables(connection,profile,{"global":[],"abc":["abc_class"],"xyz":["xyz_class"],
            "abc_xyz":["abc_class","xyz_class"],"stockout_exposure":["stockout_exposure"],
            "censoring_risk_flag":["censoring_risk_flag"],"abc_xyz_exposure":["abc_class","xyz_class","stockout_exposure"]})
        calibration["adequate_descriptive_support"]=calibration.n_series.ge(MIN_MATRIX_SERIES)
        calibration["as_of"]=TRAIN_END
        calibration["analysis_view"]="post_backtest_as_of_train_end"
        matrix=grouped_tables(connection,profile,{"risk_cell":["demand_observation_risk_cell"],
            "risk_abc":["demand_observation_risk_cell","abc_class"],"risk_xyz":["demand_observation_risk_cell","xyz_class"],
            "risk_exposure":["demand_observation_risk_cell","stockout_exposure"]})
        folds=[]
        for name,dims in [("global",[]),("stockout_exposure",["stockout_exposure"]),
                          ("censoring_risk_flag",["censoring_risk_flag"]),("risk_cell",["demand_observation_risk_cell"])]:
            frame=error_aggregation(connection,["fold_id",*dims],source="risk_observations")
            frame["level"]=name
            folds.append(frame)
        thresholds=descriptive_thresholds(profile)
        robustness,retention,error_bounds=robustness_tables(connection,profile,series_fold,thresholds)
        examples=select_risk_examples(profile)
        connection.register("example_keys",examples[["selection_rule",*KEYS]])
        trajectories=connection.execute("""SELECT k.selection_rule,o.store_id,o.product_id,o.fold_id,o.target_date,
            o.actual,o.forecast,o.error,o.underforecast_amount FROM observations o JOIN example_keys k
            USING(store_id,product_id) ORDER BY k.selection_rule,o.target_date""").df()
        variance_check=connection.execute("SELECT count(*) FROM observations WHERE underforecast_amount!=greatest(actual-forecast,0)").fetchone()[0]
        if variance_check:
            raise ValueError("Sinal de underforecast_amount divergente.")
    distributions=[]
    for metric in ["bias","bias_pct",*UNCERTAINTY_METRICS,"underforecast_rate","actual_total"]:
        values=profile[metric].dropna()
        distributions.append({"metric":metric,"n_valid":len(values),"n_null":int(profile[metric].isna().sum()),
            "min":values.min(),"p05":values.quantile(.05),"p25":values.quantile(.25),"median":values.median(),
            "p75":values.quantile(.75),"p95":values.quantile(.95),"max":values.max()})
    persistence=profile.groupby("negative_bias_fold_count").agg(n_series=("store_id","size"),
        persistent_series=("persistent_underforecast_flag","sum"),train_sales=("train_normalized_sales_total","sum")).reset_index()
    sensitivity=[]
    for minimum in [2,3,4]:
        mask=profile.bias.lt(0)&profile.negative_bias_fold_count.ge(minimum)
        sensitivity.append({"minimum_negative_folds":minimum,"n_series":int(mask.sum()),"series_share":float(mask.mean()),
            "double_risk_series":int((mask&profile.censoring_risk_flag).sum()),
            "train_sales_share":float(profile.loc[mask,"train_normalized_sales_total"].sum()/profile.train_normalized_sales_total.sum())})
    high=[]
    for name,part in [("ALL",profile),*profile.groupby("demand_observation_risk_cell",observed=True,sort=True),
        ("A_DOUBLE",profile.loc[profile.abc_class.eq("A")&profile.demand_observation_risk_cell.eq(RISK_CELLS[3])]),
        ("B_DOUBLE",profile.loc[profile.abc_class.eq("B")&profile.demand_observation_risk_cell.eq(RISK_CELLS[3])])]:
        for metric,value in thresholds["metric_p75"].items():
            high.append({"group":name,"metric":metric,"global_p75_threshold":value,"n_series":len(part),
                "n_at_or_above_p75":int(part[metric].ge(value).sum()),"share_at_or_above_p75":part[metric].ge(value).mean()})
    promotion=[]
    for scope,part in [("ALL",profile),*profile.groupby("abc_class",observed=True,sort=True)]:
        for metric in ["mae","bias","bias_pct","underforecast_rate","error_std","mean_demand","stockout_rate"]:
            promotion.append({"abc_scope":scope,"metric":metric,"spearman_with_activity_rate":part.activity_rate.corr(part[metric],method="spearman"),"n_series":len(part)})
    low=profile.actual_total.le(thresholds["low_actual_p05"])
    low_scale=[]
    for label,mask in [("at_or_below_p05",low),("above_p05",~low)]:
        part=profile.loc[mask]
        low_scale.append({"group":label,"n_series":len(part),"actual_total":part.actual_total.sum(),
            "actual_share":part.actual_total.sum()/profile.actual_total.sum(),"persistent_series":int(part.persistent_underforecast_flag.sum()),
            "median_wape":part.wape.median(),"p95_wape":part.wape.quantile(.95),"median_error_std":part.error_std.median()})
    tables={"uncertainty":uncertainty,"risk_profile":profile,"calibration":calibration,"series_fold":series_fold,
        "risk_matrix":matrix,"fold_diagnostics":pd.concat(folds,ignore_index=True),"robustness":robustness,
        "persistence_retention":retention,"persistence_distribution":persistence,"persistence_sensitivity":pd.DataFrame(sensitivity),
        "series_distributions":pd.DataFrame(distributions),"metric_correlations":metric_correlations(profile),
        "high_uncertainty_diagnostics":pd.DataFrame(high),"activity_associations":pd.DataFrame(promotion),
        "low_scale_diagnostics":pd.DataFrame(low_scale),"example_selection":examples,"example_forecasts":trajectories}
    main_paths={"uncertainty":"mart_forecast_uncertainty.parquet","risk_profile":"mart_demand_risk_profile.parquet","calibration":"mart_error_calibration.parquet"}
    artifacts={}
    for name,frame in tables.items():
        path=root / "data/processed" / main_paths[name] if name in main_paths else folder / f"{name}.parquet"
        export_frame(frame,path)
        artifacts[name]={"path":path.relative_to(root).as_posix(),"rows":len(frame),"sha256":sha256_file(path)}
    summary={"source_split":"train","source":source,"as_of":str(TRAIN_END),"available_from":"2024-06-26",
        "analysis_view":"post_backtest_as_of_train_end","n_series":len(profile),"n_forecasts":int(profile.n_forecasts.sum()),
        "profile_labels":"Phase 3 full-train labels known at 2024-06-25; descriptive grouping of historical backtest errors",
        "prospective_reuse_limit":"usable only after 2024-06-25; never reuse in earlier folds",
        "persistent_rule":"pooled_bias < 0 AND negative_bias_fold_count >= 3 of 4",
        "quantile_method":"linear/type7","std_ddof":1,"risk_cells":RISK_CELLS,"inputs":provenance,
        "n_persistent":int(profile.persistent_underforecast_flag.sum()),"n_negative_bias":int(profile.bias.lt(0).sum()),
        "thresholds":{**thresholds,**error_bounds},"minimum_matrix_series_descriptive":MIN_MATRIX_SERIES,
        "zero_actual_series":int(profile.actual_total.eq(0).sum()),"zero_actual_series_folds":int(series_fold.actual_total.eq(0).sum()),
        "n_fits_performed":0,"point_forecasts_modified":False,"raw_files_opened":False,"artifacts":artifacts}
    write_json(folder / "summary.json",json_ready(summary))
    performance={"seconds":perf_counter()-started,"peak_working_set_bytes":peak_working_set_bytes(),
        "parquet_bytes":sum((root/a["path"]).stat().st_size for a in artifacts.values())}
    write_json(folder / "performance.json",performance)
    if write_document:
        from src.reporting.demand_risk_report import write_report
        write_report(root)
    print(f"Fase 6: {len(profile)} séries; {summary['n_persistent']} persistentes; zero ajustes; {performance['seconds']:.2f}s.",flush=True)
    return summary
