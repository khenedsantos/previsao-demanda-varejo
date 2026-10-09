"""Benchmark estratificado antes de autorizar 200 mil ajustes estatísticos."""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd

from src.forecasting.backtesting import make_folds,export_frame,peak_working_set_bytes
from src.forecasting.ets import forecast_history,PRIMARY_MODEL,SPECIFICATIONS,FIT_OPTIONS
from src.ingestion.source_manifest import ROOT,load_manifest,verify_file,sha256_file
from src.segmentation.operational_profile import json_ready


MAX_PROJECTED_SECONDS=30*60
SAMPLE_PER_STRATUM=5
SAMPLE_SEED="phase5-20261008"
STRATA=["abc_class","xyz_class","scale_band"]


def phase4_inputs(root=ROOT):
    root=Path(root)
    summary_path=root / "data/outputs/forecasting_baselines/summary.json"
    summary=json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["source_split"]!="train" or summary["analysis_view"]!="prospective":
        raise ValueError("Exige outputs prospectivos da Fase 4 exclusivamente em train.")
    if [(f["forecast_origin"],f["cutoff_date"]) for f in summary["folds"]]!=[
        (str(f["forecast_origin"]),str(f["cutoff_date"])) for f in make_folds()]:
        raise ValueError("Protocolo temporal divergente da Fase 4.")
    manifest=load_manifest(root)
    entry=next(e for e in manifest["files"] if e["role"]=="train")
    verify_file(root / "data/raw/train.parquet",entry)
    if summary["source"]["sha256"]!=entry["sha256"]:
        raise ValueError("Fonte dos baselines divergente do train verificado.")
    for name,entry in summary["artifacts"].items():
        if sha256_file(root / entry["path"])!=entry["sha256"]:
            raise ValueError(f"Output da Fase 4 alterado: {name}")
    return summary


def select_sample(segments):
    """ABC/XYZ/escala do primeiro corte; hash de IDs, sem olhar desempenho futuro."""
    first=segments.loc[segments.fold_id.eq(1)].sort_values(["store_id","product_id"]).copy()
    if first.duplicated(["store_id","product_id"]).any():
        raise ValueError("Snapshot inicial contém chaves duplicadas.")
    group=first.groupby(["abc_class","xyz_class"],observed=True)
    rank=group.mean_demand.rank(method="first",ascending=True)-1
    count=group.mean_demand.transform("size")
    first["scale_band"]=(3*rank/count).astype(int).map({0:"LOW",1:"MID",2:"HIGH"})
    # Hash estável entre versões, sem estado de gerador aleatório.
    first["sample_hash"]=[hashlib.sha256(f"{SAMPLE_SEED}:{s}:{p}".encode()).hexdigest()
                          for s,p in zip(first.store_id,first.product_id)]
    counts=first.groupby(STRATA,observed=True).size().rename("population_series").reset_index()
    sample=(first.sort_values([*STRATA,"sample_hash","store_id","product_id"])
            .groupby(STRATA,observed=True,sort=True).head(SAMPLE_PER_STRATUM)
            .merge(counts,on=STRATA,validate="many_to_one")
            .sort_values([*STRATA,"store_id","product_id"]).reset_index(drop=True))
    return sample,counts


def load_histories(train_path,cutoff,keys=None):
    """Aplica o corte na SQL antes da agregação e do ajuste de qualquer série."""
    with duckdb.connect(config={"threads":1,"memory_limit":"512MB"}) as connection:
        connection.execute("SET enable_progress_bar=false")
        join=""
        if keys is not None:
            connection.register("selected_keys",keys[["store_id","product_id"]])
            join="JOIN selected_keys USING(store_id,product_id)"
        frame=connection.execute(f"""
            SELECT store_id,product_id,list(sale_amount ORDER BY cast(dt AS DATE)) AS history,
                   min(cast(dt AS DATE)) AS first_date,max(cast(dt AS DATE)) AS last_date,
                   count(*) AS n_days,count(DISTINCT cast(dt AS DATE)) AS distinct_days
            FROM read_parquet(?) {join} WHERE cast(dt AS DATE)<=?::DATE
            GROUP BY store_id,product_id ORDER BY store_id,product_id
        """,[str(train_path),cutoff]).df()
    from src.features.demand_profile import TRAIN_START
    expected_days=(pd.Timestamp(cutoff)-pd.Timestamp(TRAIN_START)).days+1
    if frame.empty or not frame.n_days.eq(expected_days).all() or not frame.distinct_days.eq(expected_days).all():
        raise ValueError("Históricos incompletos ou duplicados.")
    if not pd.to_datetime(frame.first_date).eq(pd.Timestamp(TRAIN_START)).all() or not pd.to_datetime(frame.last_date).eq(pd.Timestamp(cutoff)).all():
        raise ValueError("Janela de histórico inesperada.")
    return frame


def run_benchmark(root=ROOT):
    started=perf_counter()
    root=Path(root)
    phase4=phase4_inputs(root)
    segments=pd.read_parquet(root / phase4["artifacts"]["fold_segments"]["path"])
    sample,population=select_sample(segments)
    del segments
    output=root / "data/outputs/statistical_forecasting"
    output.mkdir(parents=True,exist_ok=True)
    export_frame(sample,output / "benchmark_sample.parquet")
    measurements=[]
    # Aquecimento de imports/otimizador fora dos tempos por ajuste, mas dentro do tempo total.
    for specification in SPECIFICATIONS:
        forecast_history(2.+np.tile([0.,.3,.8,.2,.7,1.2,.4],12),specification)
    for fold in make_folds():
        histories=load_histories(root / "data/raw/train.parquet",fold["cutoff_date"],sample)
        frame=histories.merge(sample[["store_id","product_id",*STRATA,"population_series"]],
                              on=["store_id","product_id"],validate="one_to_one")
        for specification in SPECIFICATIONS:
            tick=perf_counter()
            for row in frame.itertuples(index=False):
                fit_start=perf_counter()
                result=forecast_history(row.history,specification)
                measurements.append({"store_id":row.store_id,"product_id":row.product_id,
                    "fold_id":fold["fold_id"],"history_days":fold["history_days"],"specification":specification,
                    **{key:getattr(row,key) for key in STRATA},"population_series":row.population_series,
                    "fit_seconds":perf_counter()-fit_start,"fallback_flag":result["fallback_flag"],
                    "fallback_reason":result["fallback_reason"],"warning_categories":result["warning_categories"],
                    "n_negative_clipped":int(result["negative_clipped"].sum()),
                    "converged":result["converged"]})
            print(f"Benchmark fold {fold['fold_id']} / {specification}: {len(frame)} ajustes, {perf_counter()-tick:.2f}s",flush=True)
    measurements=pd.DataFrame(measurements)
    export_frame(measurements,output / "benchmark_fits.parquet")
    # Corrige o peso da amostragem estratificada: não extrapola a média bruta da amostra.
    means=measurements.groupby(["specification","fold_id",*STRATA],observed=True).fit_seconds.mean().reset_index()
    means=means.merge(population,on=STRATA,validate="many_to_one")
    means["projected_seconds"]=means.fit_seconds*means.population_series
    projections=means.groupby("specification").projected_seconds.sum()
    results=[]
    for specification,part in measurements.groupby("specification",sort=True):
        projected=float(projections[specification])
        # Margem de 25% para serialização e flutuação, mais custo tabular medido na Fase 4.
        baseline_perf=json.loads((root / "data/outputs/forecasting_baselines/performance.json").read_text())
        budget_estimate=1.25*projected+baseline_perf["pipeline_seconds"]
        results.append({"specification":specification,"n_series":len(sample),"n_fits":len(part),
            "measured_fit_seconds":float(part.fit_seconds.sum()),"mean_seconds_per_fit":float(part.fit_seconds.mean()),
            "median_seconds_per_fit":float(part.fit_seconds.median()),"p95_seconds_per_fit":float(part.fit_seconds.quantile(.95)),
            "projected_fit_seconds_200000":projected,"projected_total_with_margin_seconds":budget_estimate,
            "fallback_count":int(part.fallback_flag.sum()),"fallback_rate":float(part.fallback_flag.mean()),
            "failure_count":int((part.fallback_flag & ~part.fallback_reason.isin(["constant_history","insufficient_seasonal_history"])).sum()),
            "negative_clipped_forecasts":int(part.n_negative_clipped.sum()),"within_cost_gate":budget_estimate<=MAX_PROJECTED_SECONDS})
    summary={"source_split":"train","phase4_summary_sha256":sha256_file(root / "data/outputs/forecasting_baselines/summary.json"),
        "sample_seed":SAMPLE_SEED,"sample_series":len(sample),"strata_count":len(population),
        "selection_origin":phase4["folds"][0]["forecast_origin"],"sample_per_stratum":SAMPLE_PER_STRATUM,
        "scale_definition":"terciles of rank(mean_demand), within first-origin ABC x XYZ; IDs break ties",
        "configurations":SPECIFICATIONS,"fit_options":FIT_OPTIONS,"primary_predeclared":PRIMARY_MODEL,
        "selection_basis":"simple global weekly additive model, no trend; not selected by future error",
        "max_projected_seconds":MAX_PROJECTED_SECONDS,"results":results,
        "benchmark_total_seconds":perf_counter()-started,"process_peak_working_set_bytes":peak_working_set_bytes(),
        "runtime":{"python":platform.python_version(),**{name:version(name) for name in ["statsmodels","scipy","numpy","pandas","duckdb"]}},
        "sample_sha256":sha256_file(output / "benchmark_sample.parquet"),
        "measurement_note":"one sequential process; weighted projection by stratum; 25% margin plus Phase 4 tabular runtime; timing not deterministic"}
    summary=json_ready(summary)
    (output / "benchmark.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return summary
