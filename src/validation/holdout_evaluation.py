"""Avaliação do holdout a partir de previsões persistidas e labels pré-holdout."""

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd

from src.forecasting.backtesting import export_frame, peak_working_set_bytes
from src.forecasting.holdout import (ROOT, FOLDER, PREDICTIONS, RISK, KEYS, LABELS, HISTORICAL_METRICS,
    MODELS, read_json, verify_protocol, read_validated_eval, attach_eval)
from src.forecasting.statistical_backtesting import write_json
from src.ingestion.source_manifest import sha256_file
from src.segmentation.operational_profile import json_ready
from src.validation.forecast_uncertainty import error_aggregation


LEVELS={"global":[],"abc":["abc_class"],"xyz":["xyz_class"],"abc_xyz":["abc_class","xyz_class"],
    "stockout_exposure":["stockout_exposure"],"censoring_risk_flag":["censoring_risk_flag"],
    "persistent_underforecast_flag":["persistent_underforecast_flag"],"risk_cell":["demand_observation_risk_cell"]}
METRICS=["mae","rmse","wape","bias","bias_pct"]


def historical_quartiles(values,cuts):
    if len(cuts)!=3 or list(cuts)!=sorted(cuts) or not np.isfinite(values).all():
        raise ValueError("Quartis históricos inválidos.")
    return np.searchsorted(cuts,np.asarray(values),side="left")+1


def paired_metrics(frame,keys):
    metrics=["mae","rmse","wape","bias","bias_pct","underforecast_rate","actual_total","n_forecasts","n_series"]
    left=frame.loc[frame.model.eq("seasonal_naive"),[*keys,*metrics]]
    right=frame.loc[frame.model.eq("ets_ana"),[*keys,*metrics]]
    paired=left.merge(right,on=keys,suffixes=("_sn","_ets"),how="outer",validate="one_to_one",indicator=True)
    if not paired._merge.eq("both").all():
        raise ValueError("Modelos não pareados.")
    paired=paired.drop(columns="_merge")
    for metric in ["actual_total","n_forecasts","n_series"]:
        if not np.allclose(paired[metric+"_sn"],paired[metric+"_ets"],rtol=1e-12,atol=1e-12):
            raise ValueError("Cobertura/denominadores divergentes.")
    for metric in ["mae","rmse","wape"]:
        baseline=paired[metric+"_sn"]
        paired["improvement_"+metric]=(baseline-paired[metric+"_ets"])/baseline.where(baseline.ne(0))
    return paired.sort_values(keys,na_position="last").reset_index(drop=True)


def build_evaluation_tables(forecasts,profile,protocol,backtest_folds,backtest_pairs,examples):
    """Função tabular pura: nenhum raw/fit/recalibração; cortes vêm do protocolo."""
    label_cols=[*KEYS,*LABELS,"actual_total",*HISTORICAL_METRICS]
    frozen=profile[label_cols].rename(columns={m:"historical_"+m for m in ["actual_total",*HISTORICAL_METRICS]})
    observations=forecasts.merge(frozen,on=KEYS,how="left",validate="many_to_one")
    if observations[LABELS].isna().any().any():
        raise ValueError("Labels congelados ausentes.")
    observations["historical_low_scale"]=observations.historical_actual_total.le(protocol["low_scale_history_actual_p05"])
    observations["eval_stockout"]=observations.eval_stockout_hours.gt(0)
    with duckdb.connect(config={"threads":1,"memory_limit":"768MB"}) as c:
        c.register("observations",observations)
        series=error_aggregation(c,[*KEYS,"model"]).merge(frozen,on=KEYS,validate="many_to_one")
        groups=[]
        for level,dims in LEVELS.items():
            group=error_aggregation(c,["model",*dims])
            group["level"]=level
            groups.append(group)
        group=error_aggregation(c,["model"],where="abc_class='A' AND demand_observation_risk_cell='CENSORING_AND_UNDERFORECAST'")
        group["level"]="a_double_signal"
        groups.append(group)
        comparison=pd.concat(groups,ignore_index=True)
        comparison=comparison.sort_values(["level",*LABELS,"model"],na_position="last").reset_index(drop=True)
        low=error_aggregation(c,["model","historical_low_scale"])
        contemporary=error_aggregation(c,["model","eval_stockout"])
        quartiles=[]
        for metric,cuts in protocol["historical_quartile_cuts"].items():
            q=profile[KEYS].copy()
            q["historical_quartile"]=historical_quartiles(profile[metric],cuts)
            c.register("quartile_keys",q)
            c.execute("CREATE OR REPLACE TEMP VIEW quartile_observations AS SELECT o.*,q.historical_quartile FROM observations o JOIN quartile_keys q USING(store_id,product_id)")
            part=error_aggregation(c,["model","historical_quartile"],source="quartile_observations")
            part["historical_metric"]=metric
            part["cut_q25"],part["cut_q50"],part["cut_q75"]=cuts
            quartiles.append(part)
    ets=series.loc[series.model.eq("ets_ana")]
    association=[]
    for metric in HISTORICAL_METRICS:
        for target in ["mae","rmse"]:
            association.append({"historical_metric":metric,"holdout_metric":target,"n_series":len(ets),
                "spearman":ets["historical_"+metric].corr(ets[target],method="spearman")})
    retention=[]
    for flag,part in ets.groupby("persistent_underforecast_flag",sort=True):
        retention.append({"persistent_underforecast_flag":bool(flag),"n_series":len(part),
            "negative_holdout_bias_series":int(part.bias.lt(0).sum()),"negative_holdout_bias_rate":part.bias.lt(0).mean(),
            "zero_actual_series":int(part.actual_total.eq(0).sum())})
    temporal=[]
    for model in MODELS:
        for metric in METRICS:
            values=(backtest_folds.loc[backtest_folds.level.eq("global")].sort_values("fold_id")[metric] if model=="ets_ana"
                    else backtest_pairs.loc[backtest_pairs.level.eq("fold")].sort_values("fold_id")[metric+"_seasonal_naive"])
            holdout=float(comparison.loc[comparison.level.eq("global")&comparison.model.eq(model),metric].iloc[0])
            pooled=float(backtest_pairs.loc[backtest_pairs.level.eq("global"),metric+("_ets" if model=="ets_ana" else "_seasonal_naive")].iloc[0])
            temporal.append({"model":model,"metric":metric,"backtest_pooled":pooled,"fold_mean":values.mean(),
                "fold_min":values.min(),"fold_max":values.max(),"fold_std_ddof1":values.std(ddof=1),
                "fold4":values.iloc[-1],"holdout":holdout,"change_vs_fold4":holdout-values.iloc[-1],
                "change_vs_pooled":holdout-pooled,"outside_fold_range":bool(holdout<values.min() or holdout>values.max())})
    series_pairs=paired_metrics(series,KEYS)
    wins=[]
    for metric in ["mae","rmse","wape"]:
        a,b=series_pairs[metric+"_sn"],series_pairs[metric+"_ets"]
        valid=a.notna()&b.notna()
        tie=pd.Series(np.isclose(a,b,rtol=1e-10,atol=1e-12),index=a.index)&valid
        values=series_pairs["improvement_"+metric].dropna()
        wins.append({"metric":metric,"valid_series":int(valid.sum()),"ets_wins":int((valid&~tie&b.lt(a)).sum()),
            "sn_wins":int((valid&~tie&b.gt(a)).sum()),"ties":int(tie.sum()),"undefined":int((~valid).sum()),
            "valid_improvements":len(values),"improvement_p25":values.quantile(.25),
            "improvement_median":values.median(),"improvement_p75":values.quantile(.75)})
    selected=forecasts.merge(examples[["selection_rule",*KEYS]],on=KEYS,validate="many_to_many")
    return {"series_evaluation":series.sort_values([*KEYS,"model"]).reset_index(drop=True),
        "model_comparison":comparison,"paired_comparison":paired_metrics(comparison,["level",*LABELS]),
        "series_comparison":series_pairs,"uncertainty_association":pd.DataFrame(association),
        "uncertainty_quartiles":pd.concat(quartiles,ignore_index=True),"persistence_retention":pd.DataFrame(retention),
        "backtest_comparison":pd.DataFrame(temporal),"low_scale":low,"contemporary_stockout":contemporary,
        "win_rates":pd.DataFrame(wins),"example_forecasts":selected.sort_values(["selection_rule","model","dt"]).reset_index(drop=True)}


def evaluate_holdout(root=ROOT):
    root=Path(root)
    started=perf_counter()
    folder=root/FOLDER
    protocol=read_json(folder/"protocol.json")
    population=read_json(folder/"population_performance.json")
    verify_protocol(root,protocol)
    if sha256_file(root/PREDICTIONS)!=population["prediction_sha256"]:
        raise ValueError("Previsões congeladas divergentes.")
    predictions=pd.read_parquet(root/PREDICTIONS)
    if "actual" in predictions or len(predictions)!=700000 or predictions.duplicated([*KEYS,"dt","model"]).any():
        raise ValueError("Artefato de previsões inválido.")
    if not predictions.groupby("model").size().reindex(MODELS).eq(350000).all():
        raise ValueError("Cobertura dos modelos inválida.")
    opening=folder/"eval_opening.json"
    if not opening.exists():
        write_json(opening,{"first_analytical_opening_started_utc":datetime.now(timezone.utc).isoformat(),
            "authorization":"explicit Phase 7 user request after approval and commit of Phases 0-6",
            "protocol_sha256":sha256_file(folder/"protocol.json"),"predictions_sha256_before_eval":sha256_file(root/PREDICTIONS),
            "no_actuals_in_predictions":True,"scope":"one frozen methodology; rereads only for reproducibility, never tuning"})
    actuals,integrity=read_validated_eval(root,protocol)
    forecasts=attach_eval(predictions,actuals)
    profile=pd.read_parquet(root/RISK)
    backtest_folds=pd.read_parquet(root/"data/outputs/forecast_uncertainty/fold_diagnostics.parquet")
    backtest_pairs=pd.read_parquet(root/"data/processed/mart_model_comparison.parquet",filters=[("level","in",["fold","global"])])
    examples=pd.read_parquet(root/"data/outputs/forecast_uncertainty/example_selection.parquet")
    tables={"forecasts":forecasts,**build_evaluation_tables(forecasts,profile,protocol,backtest_folds,backtest_pairs,examples)}
    paths={"forecasts":"data/processed/mart_holdout_forecast.parquet",
        "series_evaluation":"data/processed/mart_holdout_series_evaluation.parquet",
        "model_comparison":"data/processed/mart_holdout_model_comparison.parquet"}
    artifacts={}
    for name,frame in tables.items():
        path=root/paths.get(name,f"{FOLDER}/{name}.parquet")
        export_frame(frame,path)
        artifacts[name]={"path":path.relative_to(root).as_posix(),"rows":len(frame),"sha256":sha256_file(path)}
    fit_rows=predictions.loc[predictions.model.eq("ets_ana")&predictions.horizon_step.eq(1)]
    summary={"source_split":"eval","training_split":"train","starting_head":protocol["starting_head"],
        "cutoff":protocol["cutoff"],"origin":protocol["origin"],"end":protocol["end"],"n_series":50000,
        "n_forecasts_per_model":350000,"protocol_sha256":sha256_file(folder/"protocol.json"),
        "prediction_sha256":population["prediction_sha256"],"integrity":integrity,"source_hashes":protocol["source_hashes"],
        "n_fits":population["fits_completed"],"n_fallbacks":int(fit_rows.fallback_flag.sum()),
        "fallback_reasons":fit_rows.loc[fit_rows.fallback_flag,"fallback_reason"].value_counts().to_dict(),
        "warning_categories":fit_rows.warning_categories.value_counts().to_dict(),
        "negative_clipped_forecasts":int(predictions.loc[predictions.model.eq("ets_ana"),"negative_clipped"].sum()),
        "negative_clipped_series":int(predictions.loc[predictions.model.eq("ets_ana")&predictions.negative_clipped,KEYS].drop_duplicates().shape[0]),
        "zero_actual_series":int(tables["series_evaluation"].loc[lambda x:x.model.eq("ets_ana"),"actual_total"].eq(0).sum()),
        "historical_quartile_cuts":protocol["historical_quartile_cuts"],"artifacts":artifacts}
    write_json(folder/"summary.json",json_ready(summary))
    performance={"evaluation_seconds":perf_counter()-started,"peak_working_set_bytes":peak_working_set_bytes(),
        "parquet_bytes":sum((root/a["path"]).stat().st_size for a in artifacts.values()),
        "n_fits_in_evaluation":0}
    write_json(folder/"evaluation_performance.json",performance)
    print("Holdout avaliado com protocolo congelado; nenhum ajuste nesta etapa.",flush=True)
    return summary
