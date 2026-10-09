"""Contrato one-shot, fronteira train/eval e reprodução sem repetir a população."""

from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import shutil

import duckdb
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.forecasting import statistical_backtesting as fitting
from src.forecasting.holdout import (ROOT, FOLDER, PREDICTIONS, RISK, KEYS, LABELS,
    CUTOFF, ORIGIN, END, assert_frozen_model, predict_histories, attach_eval, validate_eval_frame, read_json)
from src.ingestion.source_manifest import sha256_file
from src.validation.holdout_evaluation import historical_quartiles, paired_metrics, evaluate_holdout
from src.validation.forecast_metrics import metrics_from_arrays


def histories():
    return pd.DataFrame({"store_id":[1],"product_id":[2],"history":[np.tile(np.arange(1.,8.),13)[:90]],
        "first_date":[date(2024,3,28)],"last_date":[CUTOFF],"n_days":[90],"distinct_days":[90]})


def test_holdout_frozen_configuration_and_code():
    assert_frozen_model()
    assert sha256_file(ROOT/"src/forecasting/ets.py")=="a8119c6d53300a74d00c9166ec813324cdd7a4c77071549a4450815e8188b49f"


def test_holdout_only_train_history_and_no_eval_update(monkeypatch):
    seen=[]
    def frozen(history,specification):
        seen.append((np.array(history),specification))
        raw=np.arange(-1.,6.)
        return {"forecast":np.maximum(raw,0),"forecast_unclipped":raw,"negative_clipped":raw<0,
            "model_requested":"ets_ana","model_used":"ets_ana","fallback_flag":False,
            "fallback_reason":"","warning_categories":"","converged":True}
    monkeypatch.setattr(fitting,"forecast_history",frozen)
    source=histories()
    predictions,_=predict_histories(source)
    assert len(seen)==1 and len(seen[0][0])==90 and seen[0][1]=="ets_ana"
    actual=predictions.loc[predictions.model.eq("ets_ana"),[*KEYS,"dt"]].copy()
    actual["dt"]=pd.to_datetime(actual.dt)  # DuckDB timestamps versus Parquet date objects.
    actual["actual"]=1.
    actual["eval_stockout_hours"]=0
    first=attach_eval(predictions,actual)
    actual["actual"]=100000.
    actual["eval_stockout_hours"]=16
    second=attach_eval(predictions,actual)
    assert len(seen)==1  # attach não atualiza/ajusta modelo.
    assert_frame_equal(first[predictions.columns],second[predictions.columns])
    assert not first.error.equals(second.error)
    assert predictions.loc[predictions.model.eq("ets_ana"),"negative_clipped"].sum()==1
    sn=predictions.loc[predictions.model.eq("seasonal_naive")]
    np.testing.assert_array_equal(sn.forecast,source.history.iloc[0][-7:])
    assert (pd.to_datetime(sn.dt)-pd.to_datetime(sn.source_observation_date)).dt.days.eq(7).all()
    assert pd.to_datetime(sn.source_observation_date).max()<=pd.Timestamp(CUTOFF)


def test_holdout_rejects_wrong_history_cutoff_or_length():
    wrong=histories()
    wrong["last_date"]=date(2024,6,26)
    with pytest.raises(ValueError,match="cutoff"):
        predict_histories(wrong)
    wrong=histories()
    wrong["n_days"]=91
    with pytest.raises(ValueError,match="90 dias"):
        predict_histories(wrong)


def test_holdout_preserves_existing_constant_history_fallback():
    h=histories()
    h.at[0,"history"]=np.zeros(90)
    forecasts,_=predict_histories(h)
    ets=forecasts.loc[forecasts.model.eq("ets_ana")]
    assert ets.fallback_flag.all() and ets.fallback_reason.eq("constant_history").all()
    assert ets.model_used.eq("seasonal_naive").all() and ets.forecast.eq(0).all()
    assert not ets.negative_clipped.any()


def test_holdout_quartiles_use_frozen_cuts_and_ties():
    np.testing.assert_array_equal(historical_quartiles(np.array([0,1,2,3,4]),[1,2,3]),[1,1,2,3,4])
    np.testing.assert_array_equal(historical_quartiles(np.array([1,1,1,2]),[1,1,1]),[1,1,1,4])
    with pytest.raises(ValueError):
        historical_quartiles(np.array([1.]),[2,1,3])


def test_holdout_eval_contract_rejects_incomplete_frame():
    actual=pd.DataFrame({"store_id":[1],"product_id":[2],"dt":[ORIGIN],"actual":[1.],"eval_stockout_hours":[0]})
    with pytest.raises(ValueError,match="grão"):
        validate_eval_frame(actual,actual[KEYS])


@pytest.fixture(scope="module")
def population():
    return read_json(ROOT/FOLDER/"summary.json")


def test_population_holdout_grain_sn_train_and_frozen_forecasts(population):
    s=population
    f=pd.read_parquet(ROOT/s["artifacts"]["forecasts"]["path"])
    p=pd.read_parquet(ROOT/PREDICTIONS)
    assert len(f)==700000 and not f.duplicated([*KEYS,"dt","model"]).any()
    assert f.groupby("model").size().eq(350000).all()
    assert f.groupby([*KEYS,"model"]).size().eq(7).all()
    assert set(pd.to_datetime(f.dt))==set(pd.date_range(ORIGIN,END))
    assert_frame_equal(f[p.columns],p)
    np.testing.assert_array_equal(f.error,f.forecast-f.actual)
    np.testing.assert_array_equal(f.negative_clipped,f.forecast_unclipped<0)
    np.testing.assert_array_equal(f.forecast,np.maximum(f.forecast_unclipped,0))
    with duckdb.connect() as c:
        train=c.execute("SELECT store_id,product_id,cast(dt AS DATE)+7 AS dt,sale_amount AS expected FROM read_parquet(?) WHERE cast(dt AS DATE) BETWEEN DATE '2024-06-19' AND DATE '2024-06-25' ORDER BY store_id,product_id,dt",[str(ROOT/"data/raw/train.parquet")]).df()
    train["dt"]=pd.to_datetime(train.dt).dt.date
    sn=f.loc[f.model.eq("seasonal_naive")].merge(train,on=[*KEYS,"dt"],validate="one_to_one")
    assert len(sn)==350000
    np.testing.assert_array_equal(sn.forecast,sn.expected)
    protocol=read_json(ROOT/FOLDER/"protocol.json")
    opening=read_json(ROOT/FOLDER/"eval_opening.json")
    assert opening["predictions_sha256_before_eval"]==sha256_file(ROOT/PREDICTIONS)
    assert opening["protocol_sha256"]==sha256_file(ROOT/FOLDER/"protocol.json")
    performance=read_json(ROOT/FOLDER/"population_performance.json")
    assert performance["finished_utc"]<opening["first_analytical_opening_started_utc"]
    assert protocol["cutoff"]=="2024-06-25" and protocol["numeric_threads"]==1


def test_population_holdout_metrics_and_preexisting_labels(population):
    f=pd.read_parquet(ROOT/population["artifacts"]["forecasts"]["path"])
    series=pd.read_parquet(ROOT/population["artifacts"]["series_evaluation"]["path"])
    frozen=pd.read_parquet(ROOT/RISK).sort_values(KEYS)
    assert len(series)==100000 and not series.duplicated([*KEYS,"model"]).any()
    for _,part in series.groupby("model"):
        part=part.sort_values(KEYS)
        for label in LABELS:
            np.testing.assert_array_equal(part[label],frozen[label])
        assert part.persistent_underforecast_flag.sum()==16529
        assert (part.abc_class.eq("A")&part.demand_observation_risk_cell.eq("CENSORING_AND_UNDERFORECAST")).sum()==706
        assert part.loc[part.actual_total.eq(0),["wape","bias_pct"]].isna().all().all()
    groups=pd.read_parquet(ROOT/population["artifacts"]["model_comparison"]["path"])
    for model,part in f.groupby("model"):
        got=groups.loc[groups.level.eq("global")&groups.model.eq(model)].iloc[0]
        expected=metrics_from_arrays(part.actual.to_numpy(),part.forecast.to_numpy())
        for metric in ["mae","rmse","wape","bias","bias_pct"]:
            assert got[metric]==pytest.approx(expected[metric])
    for (level,model),part in groups.groupby(["level","model"]):
        assert part.n_series.sum()==(706 if level=="a_double_signal" else 50000)


def test_population_holdout_quartiles_examples_and_protected_artifacts(population):
    protocol=read_json(ROOT/FOLDER/"protocol.json")
    for path,want in protocol["protected_artifacts"].items():
        assert sha256_file(ROOT/path)==want,path
    q=pd.read_parquet(ROOT/population["artifacts"]["uncertainty_quartiles"]["path"])
    for _,part in q.groupby(["historical_metric","model"]):
        assert part.n_series.sum()==50000 and part.n_forecasts.sum()==350000
    examples=pd.read_parquet(ROOT/population["artifacts"]["example_forecasts"]["path"])
    old=pd.read_parquet(ROOT/"data/outputs/forecast_uncertainty/example_selection.parquet")
    keys=["selection_rule",*KEYS]
    assert_frame_equal(examples[keys].drop_duplicates().sort_values(keys).reset_index(drop=True),old[keys].sort_values(keys).reset_index(drop=True))
    assert len(examples)==98


def test_population_holdout_reproduces_without_train_or_fits(tmp_path,population,monkeypatch):
    import src.forecasting.ets as ets
    def forbidden(*args,**kwargs):
        raise AssertionError("Avaliação não pode ajustar modelos.")
    monkeypatch.setattr(ets,"forecast_history",forbidden)
    monkeypatch.setattr(fitting,"forecast_history",forbidden)
    protocol=read_json(ROOT/FOLDER/"protocol.json")
    required=set(protocol["protected_artifacts"])|set(protocol["code_hashes"])
    required.update(["config/source_manifest.yaml","data/raw/eval.parquet",PREDICTIONS,
        FOLDER+"/protocol.json",FOLDER+"/population_performance.json",FOLDER+"/eval_opening.json"])
    for name in required:
        target=tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        try:
            os.link(ROOT/name,target)
        except OSError:
            shutil.copyfile(ROOT/name,target)
    assert not (tmp_path/"data/raw/train.parquet").exists()
    rebuilt=evaluate_holdout(tmp_path)
    for name,item in population["artifacts"].items():
        assert rebuilt["artifacts"][name]["sha256"]==item["sha256"],name
        assert sha256_file(ROOT/item["path"])==item["sha256"]
    assert sha256_file(tmp_path/FOLDER/"summary.json")==sha256_file(ROOT/FOLDER/"summary.json")
