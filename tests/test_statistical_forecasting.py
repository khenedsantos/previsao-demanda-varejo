"""Contratos do ETS e do benchmark preservado, sem reexecutar a população."""

from datetime import timedelta
import json

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.features.demand_profile import TRAIN_START
from src.forecasting.backtesting import make_folds
from src.forecasting.ets import forecast_history,PRIMARY_MODEL,SPECIFICATIONS
from src.forecasting.ets_benchmark import select_sample,load_histories
from src.ingestion.source_manifest import ROOT,sha256_file


def test_weekly_additive_forecast_has_seven_finite_values():
    pattern=np.array([0.,1.,3.,2.,4.,1.,2.])
    result=forecast_history(np.tile(pattern,10))
    assert not result["fallback_flag"]
    assert result["converged"]
    assert result["model_requested"]==result["model_used"]==PRIMARY_MODEL
    assert len(result["forecast"])==7 and np.isfinite(result["forecast"]).all()
    assert (result["forecast"]>=0).all()
    np.testing.assert_allclose(result["forecast"],pattern,atol=1e-4)
    assert SPECIFICATIONS[PRIMARY_MODEL]["seasonal_periods"]==7
    assert SPECIFICATIONS[PRIMARY_MODEL]["trend"] is None
    assert SPECIFICATIONS[PRIMARY_MODEL]["seasonal"]=="add"


@pytest.mark.parametrize("history,reason",[(np.zeros(28),"constant_history"),
    (np.ones(28)*3,"constant_history"),(np.arange(10.),"insufficient_seasonal_history")])
def test_documented_fallbacks_preserve_seasonal_naive(history,reason):
    result=forecast_history(history)
    assert result["fallback_flag"] and result["fallback_reason"]==reason
    assert result["model_requested"]==PRIMARY_MODEL and result["model_used"]=="seasonal_naive"
    np.testing.assert_array_equal(result["forecast"],history[-7:])


@pytest.mark.parametrize("mode,reason",[("exception","fit_exception:ValueError"),
    ("not_converged","optimizer_not_converged"),("nonfinite","nonfinite_fit_or_forecast")])
def test_fit_failures_are_auditable(monkeypatch,mode,reason):
    class Fitted:
        mle_retvals={"success":mode!="not_converged"}
        sse=1.
        def forecast(self,horizon):
            return np.full(horizon,np.nan if mode=="nonfinite" else 2.)
    class Model:
        def __init__(self,*args,**kwargs):
            pass
        def fit(self,**kwargs):
            if mode=="exception":
                raise ValueError("controlled failure")
            return Fitted()
    monkeypatch.setattr("src.forecasting.ets.ExponentialSmoothing",Model)
    history=np.arange(28.)
    result=forecast_history(history)
    assert result["fallback_reason"]==reason and result["fallback_flag"]
    np.testing.assert_array_equal(result["forecast"],history[-7:])


def test_negative_projection_keeps_unclipped_audit(monkeypatch):
    raw=np.array([-2.,1.,0.,3.,-1.,2.,4.])
    class Fitted:
        mle_retvals={"success":True}
        sse=1.
        def forecast(self,horizon):
            return raw
    class Model:
        def __init__(self,*args,**kwargs):
            pass
        def fit(self,**kwargs):
            return Fitted()
    monkeypatch.setattr("src.forecasting.ets.ExponentialSmoothing",Model)
    history=np.arange(28.)
    original=history.copy()
    result=forecast_history(history)
    assert not result["fallback_flag"]
    np.testing.assert_array_equal(result["forecast_unclipped"],raw)
    np.testing.assert_array_equal(result["forecast"],[0.,1.,0.,3.,0.,2.,4.])
    np.testing.assert_array_equal(result["negative_clipped"],raw<0)
    np.testing.assert_array_equal(history,original)


@pytest.mark.parametrize("history",[[],[1]*6,[1]*13+[np.nan],[1]*13+[-1],np.ones((3,7))])
def test_invalid_history_does_not_disappear_into_fallback(history):
    with pytest.raises(ValueError):
        forecast_history(history)


def test_future_mutation_does_not_change_history_or_forecast(tmp_path):
    fold=make_folds()[0]
    frame=pd.DataFrame({"store_id":[1]*90,"product_id":[2]*90,
        "dt":[str(TRAIN_START+timedelta(days=i)) for i in range(90)],
        "sale_amount":[1.+i%7+i*.01 for i in range(90)]})
    path=tmp_path / "train.parquet"
    frame.to_parquet(path,index=False)
    before=load_histories(path,fold["cutoff_date"])
    first=forecast_history(before.iloc[0].history)
    frame.loc[frame.dt>=str(fold["forecast_origin"]),"sale_amount"]=999999.
    frame.to_parquet(path,index=False)
    after=load_histories(path,fold["cutoff_date"])
    second=forecast_history(after.iloc[0].history)
    assert before.iloc[0].n_days==62
    assert before.iloc[0].last_date<pd.Timestamp(fold["forecast_origin"])
    assert_frame_equal(before,after)
    np.testing.assert_array_equal(first["forecast"],second["forecast"])
    assert not (tmp_path / "eval.parquet").exists()


def test_benchmark_sample_is_reproducible_and_uses_only_first_snapshot():
    segments=pd.read_parquet(ROOT / "data/outputs/forecasting_baselines/fold_segments.parquet")
    sample,population=select_sample(segments)
    assert len(sample)==135 and len(population)==27 and population.population_series.sum()==50000
    assert sample.fold_id.eq(1).all()
    assert sample.groupby(["abc_class","xyz_class","scale_band"]).size().eq(5).all()
    changed=segments.copy()
    changed.loc[changed.fold_id.gt(1),["abc_class","xyz_class","mean_demand"]]=["C","Z",999999.]
    other,other_counts=select_sample(changed.sample(frac=1,random_state=123))
    assert_frame_equal(sample,other)
    assert_frame_equal(population,other_counts)
    saved=pd.read_parquet(ROOT / "data/outputs/statistical_forecasting/benchmark_sample.parquet")
    assert_frame_equal(sample,saved)


def test_benchmark_uses_train_and_weighted_cost_projection():
    folder=ROOT / "data/outputs/statistical_forecasting"
    summary=json.loads((folder / "benchmark.json").read_text(encoding="utf-8"))
    fits=pd.read_parquet(folder / "benchmark_fits.parquet")
    assert summary["source_split"]=="train"
    assert len(fits)==1080 and fits.groupby("specification").size().eq(540).all()
    assert sha256_file(folder / "benchmark_sample.parquet")==summary["sample_sha256"]
    group_keys=["specification","fold_id","abc_class","xyz_class","scale_band"]
    strata=fits.groupby(group_keys).agg(seconds=("fit_seconds","mean"),n=("population_series","first"))
    projected=(strata.seconds*strata.n).groupby("specification").sum()
    for row in summary["results"]:
        assert row["projected_fit_seconds_200000"]==pytest.approx(projected[row["specification"]])
        assert row["within_cost_gate"]==(row["projected_total_with_margin_seconds"]<=summary["max_projected_seconds"])
