"""Execução populacional autorizada de A/N/A, sem repetir benchmark ou abrir eval."""

from datetime import datetime,timezone
import gc
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.forecasting.backtesting import make_folds,peak_working_set_bytes
from src.forecasting.baselines import HORIZON
from src.forecasting.ets import PRIMARY_MODEL,SPECIFICATIONS,FIT_OPTIONS,forecast_history
from src.forecasting.ets_benchmark import phase4_inputs,load_histories
from src.ingestion.source_manifest import ROOT,sha256_file


BATCH_SERIES=2500


def forecast_batch(histories,fold):
    """Ajusta somente históricos cortados. Actuals não são argumento nem resultado."""
    if not pd.to_datetime(histories.last_date).eq(pd.Timestamp(fold["cutoff_date"])).all():
        raise ValueError("Histórico não termina no cutoff autorizado.")
    outputs=[]
    fitting_seconds=0.
    for row in histories.itertuples(index=False):
        tick=perf_counter()
        result=forecast_history(row.history,PRIMARY_MODEL)
        fitting_seconds+=perf_counter()-tick
        outputs.append(result)
    count=len(histories)
    dates=[(pd.Timestamp(fold["forecast_origin"])+pd.Timedelta(days=i)).date() for i in range(HORIZON)]
    frame=pd.DataFrame({"store_id":np.repeat(histories.store_id.to_numpy(),HORIZON),
        "product_id":np.repeat(histories.product_id.to_numpy(),HORIZON),"fold_id":fold["fold_id"],
        "forecast_origin":fold["forecast_origin"],"cutoff_date":fold["cutoff_date"],
        "target_date":np.tile(dates,count),"horizon_step":np.tile(np.arange(1,HORIZON+1,dtype=np.int16),count),
        "model":PRIMARY_MODEL,"forecast":np.concatenate([o["forecast"] for o in outputs]),
        "forecast_unclipped":np.concatenate([o["forecast_unclipped"] for o in outputs]),
        "negative_clipped":np.concatenate([o["negative_clipped"] for o in outputs])})
    for column in ["model_requested","model_used","fallback_flag","fallback_reason","warning_categories","converged"]:
        frame[column]=np.repeat([o[column] for o in outputs],HORIZON)
    if len(frame)!=count*HORIZON or not np.isfinite(frame.forecast).all() or frame.forecast.lt(0).any():
        raise ValueError("Forecasts inválidos ou cobertura incompleta no lote.")
    return frame,fitting_seconds


def attach_actuals(connection,predictions,baseline_path):
    """Une actuals de train da Fase 4 somente após produzir o lote de forecasts."""
    connection.register("batch_predictions",pa.Table.from_pandas(predictions,preserve_index=False))
    evaluated=connection.execute("""
        SELECT p.*,b.actual,p.forecast-b.actual AS error
        FROM batch_predictions p JOIN read_parquet(?) b
          USING(store_id,product_id,fold_id,forecast_origin,target_date)
        WHERE b.model='seasonal_naive'
        ORDER BY p.store_id,p.product_id,p.target_date
    """,[str(baseline_path)]).to_arrow_table()
    connection.unregister("batch_predictions")
    if len(evaluated)!=len(predictions) or evaluated["actual"].null_count:
        raise ValueError("Actuals ausentes ou duplicados no lote.")
    return evaluated


def write_json(path,payload):
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(path)


def run_population(root=ROOT):
    root=Path(root)
    started=perf_counter()
    started_utc=datetime.now(timezone.utc).isoformat()
    phase4=phase4_inputs(root)
    folder=root / "data/outputs/statistical_forecasting"
    benchmark=json.loads((folder / "benchmark.json").read_text(encoding="utf-8"))
    if benchmark["configurations"][PRIMARY_MODEL]!=SPECIFICATIONS[PRIMARY_MODEL] or benchmark["fit_options"]!=FIT_OPTIONS:
        raise ValueError("Configuração diferente da benchmarkada e autorizada.")
    path=root / "data/processed/mart_forecast_statistical.parquet"
    if path.exists():
        raise FileExistsError("Execução populacional já existe. Use --compare-only para comparar sem repetir ajustes.")
    if shutil.disk_usage(root).free<5*2**30:
        raise OSError("Menos de 5 GiB livres antes da execução; verificar disco.")
    temporary=path.with_suffix(".parquet.tmp")
    if temporary.exists():
        raise FileExistsError("Artefato parcial existente: revisar antes de reiniciar a execução.")
    phase4_summary=root / "data/outputs/forecasting_baselines/summary.json"
    execution={"started_utc":started_utc,"source_split":"train","target":"sale_amount",
        "target_interpretation":"venda observada normalizada","model_requested":PRIMARY_MODEL,
        "specification":SPECIFICATIONS[PRIMARY_MODEL],"fit_options":FIT_OPTIONS,
        "execution_mode":"one sequential process; ANA only; user authorized complete population",
        "history_loading":"2500 series per batch, using prospective snapshot keys; same history filter and model",
        "old_30_minute_gate_applies":False,"n_series_expected":50000,"n_fits_expected":200000,
        "horizon_days":HORIZON,"phase4_summary_sha256":sha256_file(phase4_summary),
        "ets_code_sha256":sha256_file(root / "src/forecasting/ets.py"),
        "benchmark_sha256":sha256_file(folder / "benchmark.json"),"disk_free_bytes_start":shutil.disk_usage(root).free,
        "runtime":{"python":platform.python_version(),**{name:version(name) for name in ["statsmodels","scipy","numpy","pandas","duckdb","pyarrow"]}}}
    write_json(folder / "execution.json",execution)
    print(f"Início UTC: {started_utc}; A/N/A somente, 200000 ajustes; sem limite antigo de 30 minutos.",flush=True)
    writer=None
    requested=fallbacks=clipped=0
    fit_total=0.
    fold_performance=[]
    try:
        for fold in make_folds():
            fold_start=perf_counter()
            keys=pd.read_parquet(root / phase4["artifacts"]["fold_segments"]["path"],
                columns=["store_id","product_id"],filters=[("fold_id","=",fold["fold_id"])])
            keys=keys.sort_values(["store_id","product_id"]).reset_index(drop=True)
            if len(keys)!=50000 or keys.duplicated(["store_id","product_id"]).any():
                raise ValueError("São esperadas exatamente 50000 séries únicas em cada fold.")
            fit_fold=0.
            with duckdb.connect(config={"threads":1,"memory_limit":"512MB"}) as connection:
                connection.execute("SET enable_progress_bar=false")
                for start in range(0,len(keys),BATCH_SERIES):
                    batch_keys=keys.iloc[start:start+BATCH_SERIES]
                    batch=load_histories(root / "data/raw/train.parquet",fold["cutoff_date"],batch_keys)
                    if not np.array_equal(batch[["store_id","product_id"]].to_numpy(),batch_keys.to_numpy()):
                        raise ValueError("Cobertura das séries divergente no lote de históricos.")
                    predictions,fit_seconds=forecast_batch(batch,fold)
                    evaluated=attach_actuals(connection,predictions,root / phase4["artifacts"]["forecasts"]["path"])
                    if writer is None:
                        writer=pq.ParquetWriter(temporary,evaluated.schema,compression="zstd",version="2.6")
                    writer.write_table(evaluated,row_group_size=65536)
                    requested+=len(batch)
                    fallbacks+=int(predictions.loc[predictions.horizon_step.eq(1),"fallback_flag"].sum())
                    clipped+=int(predictions.negative_clipped.sum())
                    fit_total+=fit_seconds
                    fit_fold+=fit_seconds
                    progress={"status":"running","fold_id":fold["fold_id"],"fits_completed":requested,
                        "fits_expected":200000,"fallbacks":fallbacks,"negative_clipped_forecasts":clipped,
                        "elapsed_seconds":perf_counter()-started,"fit_seconds":fit_total,
                        "peak_working_set_bytes":peak_working_set_bytes(),"disk_free_bytes":shutil.disk_usage(root).free}
                    write_json(folder / "progress.json",progress)
                    print(f"Fold {fold['fold_id']} | {requested}/200000 | {progress['elapsed_seconds']:.1f}s | fallback {fallbacks} | clipping {clipped}",flush=True)
                    if progress["disk_free_bytes"]<2**30:
                        raise OSError("Espaço disponível caiu abaixo de 1 GiB; execução interrompida.")
                    del predictions,evaluated,batch
            fold_performance.append({"fold_id":fold["fold_id"],"fits":len(keys),
                "total_seconds":perf_counter()-fold_start,"fit_seconds":fit_fold})
            del keys
            gc.collect()
    finally:
        if writer is not None:
            writer.close()
    if requested!=200000 or pq.ParquetFile(temporary).metadata.num_rows!=1400000:
        raise ValueError("Execução populacional incompleta.")
    temporary.replace(path)
    elapsed=perf_counter()-started
    performance={"started_utc":started_utc,"finished_utc":datetime.now(timezone.utc).isoformat(),
        "population_seconds":elapsed,"fit_seconds":fit_total,"population_overhead_seconds":elapsed-fit_total,
        "n_fits":requested,"n_ets_fits":requested-fallbacks,"n_fallbacks":fallbacks,
        "negative_clipped_forecasts":clipped,"folds":fold_performance,
        "peak_working_set_bytes":peak_working_set_bytes(),"forecast_bytes":path.stat().st_size,
        "forecast_sha256":sha256_file(path),"disk_free_bytes_end":shutil.disk_usage(root).free,
        "scope":"population fitting, source verification and forecast output; comparison/report/notebook measured separately"}
    write_json(folder / "population_performance.json",performance)
    write_json(folder / "progress.json",{"status":"completed",**performance})
    print(f"População concluída: {requested} ajustes, {fallbacks} fallbacks, {elapsed/60:.2f} minutos.",flush=True)
    return performance
