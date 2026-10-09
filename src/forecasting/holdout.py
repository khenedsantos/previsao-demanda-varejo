"""Holdout único: previsões persistidas antes da primeira leitura analítica de eval."""

from datetime import date, datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
from time import perf_counter

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.forecasting.backtesting import peak_working_set_bytes
from src.forecasting.ets import PRIMARY_MODEL, SPECIFICATIONS, FIT_OPTIONS
from src.forecasting.ets_benchmark import load_histories
from src.forecasting.statistical_backtesting import forecast_batch, write_json
from src.ingestion.source_manifest import ROOT, load_manifest, verify_file, sha256_file


START_HEAD="d6681aa5a92c7283ff3ab1892197b003a3de68c4"
CUTOFF=date(2024,6,25)
ORIGIN=date(2024,6,26)
END=date(2024,7,2)
KEYS=["store_id","product_id"]
MODELS=["ets_ana","seasonal_naive"]
HISTORICAL_METRICS=["error_std","rmse","p90_absolute_error","p95_absolute_error"]
LABELS=["abc_class","xyz_class","stockout_exposure","censoring_risk_flag",
        "persistent_underforecast_flag","demand_observation_risk_cell"]
FOLDER="data/outputs/final_holdout"
PREDICTIONS=FOLDER+"/frozen_predictions.parquet"
RISK="data/processed/mart_demand_risk_profile.parquet"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_frozen_model():
    if PRIMARY_MODEL!="ets_ana" or SPECIFICATIONS[PRIMARY_MODEL]!={"trend":None,"seasonal":"add","seasonal_periods":7}:
        raise ValueError("Configuração ETS diferente da aprovada.")
    if FIT_OPTIONS!={"optimized":True,"use_brute":False,"method":"SLSQP",
        "minimize_kwargs":{"options":{"maxiter":200,"ftol":1e-6}},"remove_bias":False}:
        raise ValueError("Opções de ajuste divergentes.")


def freeze_protocol(root=ROOT):
    """Lê somente train e artefatos anteriores; identidade eval vem do manifesto."""
    root=Path(root)
    assert_frozen_model()
    if subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()!=START_HEAD:
        raise ValueError("HEAD de partida diferente do autorizado.")
    manifest=load_manifest(root)
    sources={entry["role"]:entry for entry in manifest["files"]}
    verify_file(root/"data/raw/train.parquet",sources["train"])
    protected={}
    for folder in ["segmentation","forecasting_baselines","statistical_forecasting","forecast_uncertainty"]:
        relative=f"data/outputs/{folder}/summary.json"
        summary=read_json(root/relative)
        if summary["source_split"]!="train" or summary["source"]["sha256"]!=sources["train"]["sha256"]:
            raise ValueError("Artefatos prévios devem derivar exclusivamente do train congelado.")
        protected[relative]=sha256_file(root/relative)
        for item in summary["artifacts"].values():
            path=(root/item["path"]).resolve()
            if not path.is_relative_to((root/"data").resolve()) or sha256_file(path)!=item["sha256"]:
                raise ValueError(f"Artefato prévio divergente: {item['path']}")
            protected[item["path"]]=item["sha256"]
    profile=pd.read_parquet(root/RISK).sort_values(KEYS)
    if len(profile)!=50000 or profile.duplicated(KEYS).any() or not profile.source_split.eq("train").all():
        raise ValueError("Perfil congelado inválido.")
    if not pd.to_datetime(profile.as_of).eq(pd.Timestamp(CUTOFF)).all() or profile[LABELS].isna().any().any():
        raise ValueError("Labels precisam ser conhecidos em 25/06.")
    if profile.persistent_underforecast_flag.sum()!=16529 or profile.demand_observation_risk_cell.eq("CENSORING_AND_UNDERFORECAST").sum()!=1028:
        raise ValueError("Populações da Fase 6 divergentes.")
    code_paths=["src/forecasting/ets.py","src/forecasting/statistical_backtesting.py",
        "src/forecasting/ets_benchmark.py","src/validation/forecast_uncertainty.py",
        "src/validation/forecast_metrics.py","src/segmentation/demand_risk.py",
        "src/forecasting/holdout.py","src/validation/holdout_evaluation.py"]
    return {"starting_head":START_HEAD,"first_authorized_analytical_opening_of_eval":True,
        "cutoff":str(CUTOFF),"origin":str(ORIGIN),"end":str(END),"n_series":50000,"horizon":7,
        "n_eval_rows":350000,"models":MODELS,"configuration":SPECIFICATIONS[PRIMARY_MODEL],
        "fit_options":FIT_OPTIONS,"initialization_method":"estimated","use_boxcox":False,
        "numeric_threads":1,"error_sign":"forecast - actual","no_tuning_after_eval":True,
        "source_revision":manifest["source_revision"],"source_hashes":{r:sources[r]["sha256"] for r in sources},
        "protected_artifacts":protected,"code_hashes":{p:sha256_file(root/p) for p in code_paths},
        "historical_quartile_cuts":{m:profile[m].quantile([.25,.5,.75]).tolist() for m in HISTORICAL_METRICS},
        "quartile_rule":"Q1 <= q25; Q2 <= q50; Q3 <= q75; Q4 > q75; ties stay together",
        "low_scale_history_actual_p05":read_json(root/"data/outputs/forecast_uncertainty/summary.json")["thresholds"]["low_actual_p05"],
        "examples":"reuse all seven Phase 6 selections without holdout-based selection",
        "contemporary_stockout":"separate descriptive grouping of eval rows by stock_hour6_22_cnt > 0",
        "classification":"qualitative A/B/C/D using error, bias, segments and backtest consistency; no retrospective numerical gate",
        "runtime":{"python":platform.python_version(),**{n:version(n) for n in ["numpy","scipy","statsmodels","pandas","duckdb","pyarrow"]}}}


def verify_protocol(root,protocol,check_code=True):
    for path,want in protocol["protected_artifacts"].items():
        if sha256_file(root/path)!=want:
            raise ValueError(f"Artefato congelado alterado: {path}")
    if check_code:
        for path,want in protocol["code_hashes"].items():
            if sha256_file(root/path)!=want:
                raise ValueError(f"Código do protocolo alterado: {path}")
    assert_frozen_model()


def predict_histories(histories):
    """Interface sem eval, sem labels ou features de holdout; somente 90 valores train."""
    if not histories.n_days.eq(90).all() or not histories.distinct_days.eq(90).all():
        raise ValueError("Holdout exige histórico train completo de 90 dias.")
    with threadpool_limits(limits=1):
        ets,seconds=forecast_batch(histories,{"fold_id":5,"forecast_origin":ORIGIN,"cutoff_date":CUTOFF})
    ets=ets.rename(columns={"target_date":"dt"})
    ets["source_observation_date"]=pd.NaT
    sn=ets.copy()
    last_week=np.concatenate([np.asarray(row.history)[-7:] for row in histories.itertuples(index=False)])
    sn["model"]="seasonal_naive"
    sn["forecast"]=last_week
    sn["forecast_unclipped"]=last_week
    sn["negative_clipped"]=False
    sn["model_requested"]="seasonal_naive"
    sn["model_used"]="seasonal_naive"
    sn["fallback_flag"]=False
    sn["fallback_reason"]=""
    sn["warning_categories"]=""
    sn["converged"]=True
    sn["source_observation_date"]=pd.to_datetime(sn.dt)-pd.Timedelta(days=7)
    return pd.concat([ets,sn],ignore_index=True).sort_values([*KEYS,"model","dt"]).reset_index(drop=True),seconds


def run_holdout_predictions(root=ROOT):
    root=Path(root)
    folder=root/FOLDER
    folder.mkdir(parents=True,exist_ok=True)
    path=root/PREDICTIONS
    temporary=path.with_suffix(".parquet.tmp")
    if any(p.exists() for p in [path,temporary,folder/"eval_opening.json",folder/"execution.json"]):
        raise FileExistsError("Execução final/parcial existente: não repetir ajustes; auditar estado.")
    started=perf_counter()
    protocol=freeze_protocol(root)
    write_json(folder/"protocol.json",protocol)
    write_json(folder/"execution.json",{"started_utc":datetime.now(timezone.utc).isoformat(),
        "protocol_sha256":sha256_file(folder/"protocol.json"),"eval_not_opened":True})
    keys=pd.read_parquet(root/RISK,columns=KEYS).sort_values(KEYS).reset_index(drop=True)
    writer=None
    fit_seconds=0.
    fits=fallbacks=clipped=0
    try:
        for first in range(0,len(keys),2500):
            batch=keys.iloc[first:first+2500]
            histories=load_histories(root/"data/raw/train.parquet",CUTOFF,batch)
            if not np.array_equal(histories[KEYS].to_numpy(),batch.to_numpy()):
                raise ValueError("Chaves do histórico divergentes.")
            predictions,seconds=predict_histories(histories)
            table=pa.Table.from_pandas(predictions,preserve_index=False)
            if writer is None:
                writer=pq.ParquetWriter(temporary,table.schema,compression="zstd",version="2.6")
            writer.write_table(table,row_group_size=65536)
            ets=predictions.loc[predictions.model.eq(PRIMARY_MODEL)]
            fits+=len(batch)
            fit_seconds+=seconds
            fallbacks+=int(ets.loc[ets.horizon_step.eq(1),"fallback_flag"].sum())
            clipped+=int(ets.negative_clipped.sum())
            progress={"fits_completed":fits,"fits_expected":50000,"fit_seconds":fit_seconds,
                "elapsed_seconds":perf_counter()-started,"fallbacks":fallbacks,"clipped":clipped,
                "peak_working_set_bytes":peak_working_set_bytes(),"eval_not_opened":True}
            write_json(folder/"progress.json",progress)
            print(f"Holdout train-only: {fits}/50000; {progress['elapsed_seconds']:.1f}s; fallback {fallbacks}; clipping {clipped}",flush=True)
    finally:
        if writer is not None:
            writer.close()
    if fits!=50000 or pq.ParquetFile(temporary).metadata.num_rows!=700000:
        raise ValueError("Previsões incompletas.")
    temporary.replace(path)
    performance={**progress,"population_seconds":perf_counter()-started,"prediction_sha256":sha256_file(path),
        "prediction_bytes":path.stat().st_size,"finished_utc":datetime.now(timezone.utc).isoformat()}
    write_json(folder/"population_performance.json",performance)
    print("Previsões congeladas antes de abrir eval.",flush=True)
    return performance


def validate_eval_frame(actuals,keys):
    expected_dates=set(pd.date_range(ORIGIN,END))
    if len(actuals)!=350000 or actuals.duplicated([*KEYS,"dt"]).any() or actuals[[*KEYS,"dt","actual","eval_stockout_hours"]].isna().any().any():
        raise ValueError("Eval: grão/linhas/nulos inválidos.")
    if set(pd.to_datetime(actuals.dt))!=expected_dates:
        raise ValueError("Eval: período inesperado.")
    counts=actuals.groupby(KEYS).size()
    found=actuals[KEYS].drop_duplicates().sort_values(KEYS).reset_index(drop=True)
    if len(counts)!=50000 or not counts.eq(7).all() or not found.equals(keys.sort_values(KEYS).reset_index(drop=True)):
        raise ValueError("Eval: cobertura diferente das 50000 séries congeladas.")
    if not np.isfinite(actuals.actual).all() or actuals.actual.lt(0).any() or not actuals.eval_stockout_hours.between(0,16).all():
        raise ValueError("Eval: valores inválidos.")


def read_validated_eval(root,protocol):
    """Só chamada após verificar o arquivo completo de previsões sem actuals."""
    entry=next(x for x in load_manifest(root)["files"] if x["role"]=="eval")
    verify_file(root/"data/raw/eval.parquet",entry)
    if entry["sha256"]!=protocol["source_hashes"]["eval"]:
        raise ValueError("Identidade eval divergente do protocolo.")
    with duckdb.connect(config={"threads":1}) as c:
        actuals=c.execute("""SELECT cast(dt AS DATE) AS dt,store_id,product_id,sale_amount AS actual,
            stock_hour6_22_cnt AS eval_stockout_hours FROM read_parquet(?) ORDER BY store_id,product_id,dt""",
            [str(root/"data/raw/eval.parquet")]).df()
    validate_eval_frame(actuals,pd.read_parquet(root/RISK,columns=KEYS))
    return actuals,{"sha256":entry["sha256"],"rows":len(actuals),"n_series":50000,"n_dates":7,
        "start":str(ORIGIN),"end":str(END),"unique_grain":True,"schema_and_hash_verified":True}


def attach_eval(predictions,actuals):
    """Junção posterior: eval não participa da construção dos forecasts."""
    predictions=predictions.copy()
    actuals=actuals.copy()
    predictions["dt"]=pd.to_datetime(predictions.dt).dt.date
    actuals["dt"]=pd.to_datetime(actuals.dt).dt.date
    result=predictions.merge(actuals,on=[*KEYS,"dt"],validate="many_to_one",how="left")
    if len(result)!=len(predictions) or result.actual.isna().any():
        raise ValueError("Actuals ausentes após junção.")
    result["error"]=result.forecast-result.actual
    result["absolute_error"]=result.error.abs()
    result["squared_error"]=result.error**2
    return result.sort_values([*KEYS,"model","dt"]).reset_index(drop=True)
