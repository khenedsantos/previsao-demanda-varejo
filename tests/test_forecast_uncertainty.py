"""Fórmulas, persistência, matriz, proveniência e reprodução sem raw ou refit."""

import json
import os
from pathlib import Path
import shutil

import duckdb
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.ingestion.source_manifest import ROOT,sha256_file
from src.segmentation.demand_risk import risk_cells,RISK_CELLS,build_forecast_risk,verified_inputs,select_risk_examples
from src.validation.forecast_uncertainty import error_aggregation,attach_bias_persistence


def test_known_error_distribution_std_quantiles_and_sign():
    frame=pd.DataFrame({"store_id":[1]*5,"product_id":[1]*5,"fold_id":[1]*5,
        "actual":[3.]*5,"forecast":[1.,2.,3.,4.,5.],"error":[-2.,-1.,0.,1.,2.]})
    with duckdb.connect() as c:
        c.register("observations",frame)
        row=error_aggregation(c).iloc[0]
    assert row.mae==pytest.approx(1.2) and row.rmse==pytest.approx(np.sqrt(2))
    assert row.wape==pytest.approx(.4) and row.bias==0 and row.bias_pct==0
    assert row.error_std==pytest.approx(np.sqrt(2.5))
    assert row.absolute_error_std==pytest.approx(np.sqrt(.7))
    assert [row.error_q10,row.error_q25,row.error_q50,row.error_q75,row.error_q90]==pytest.approx([-1.6,-1,0,1,1.6])
    assert [row.p50_absolute_error,row.p90_absolute_error,row.p95_absolute_error]==[1.,2.,2.]
    assert row.underforecast_days==row.overforecast_days==2 and row.exact_forecast_days==1
    assert row.underforecast_rate==row.overforecast_rate==pytest.approx(.4)
    assert row.total_underforecast_amount==3 and row.mean_underforecast_amount_when_positive==1.5


def test_zero_denominator_and_no_underforecast_remain_null():
    frame=pd.DataFrame({"store_id":[1,1],"product_id":[1,1],"fold_id":[1,1],"actual":[0.,0.],"forecast":[1.,2.],"error":[1.,2.]})
    with duckdb.connect() as c:
        c.register("observations",frame)
        row=error_aggregation(c).iloc[0]
    assert pd.isna(row.wape) and pd.isna(row.bias_pct) and pd.isna(row.mean_underforecast_amount_when_positive)
    assert row.mae==1.5 and row.underforecast_rate==0 and row.total_underforecast_amount==0


def test_bias_persistence_requires_sign_and_three_of_four():
    folds=pd.DataFrame({"store_id":np.repeat([1,2,3,4],4),"product_id":1,"fold_id":list(range(1,5))*4,
        "bias":[-1,-1,-1,1,-1,-1,-1,10,-1,-1,0,0,-1,-1,-1,-1]})
    series=folds.groupby(["store_id","product_id"],as_index=False).bias.mean()
    result=attach_bias_persistence(series,folds)
    assert result.negative_bias_fold_count.tolist()==[3,3,2,4]
    assert result.persistent_underforecast_flag.tolist()==[True,False,False,True]
    assert_frame_equal(result,attach_bias_persistence(series.sample(frac=1,random_state=1),folds.iloc[::-1]))
    with pytest.raises(ValueError,match="quatro folds"):
        attach_bias_persistence(series,folds.loc[folds.fold_id.ne(4)])


def test_risk_matrix_is_exact_truth_table_and_rejects_null():
    assert risk_cells(pd.Series([False,False,True,True]),pd.Series([False,True,False,True])).tolist()==RISK_CELLS
    with pytest.raises(ValueError,match="nulas"):
        risk_cells(pd.Series([None]),pd.Series([True]))


@pytest.fixture(scope="module")
def risk_summary():
    return json.loads((ROOT/"data/outputs/forecast_uncertainty/summary.json").read_text(encoding="utf-8"))


def test_population_profile_coverage_classes_and_upstream_consistency(risk_summary):
    s=risk_summary
    u=pd.read_parquet(ROOT/s["artifacts"]["uncertainty"]["path"])
    r=pd.read_parquet(ROOT/s["artifacts"]["risk_profile"]["path"])
    f=pd.read_parquet(ROOT/s["artifacts"]["series_fold"]["path"])
    assert len(u)==len(r)==50000 and len(f)==200000
    assert not u.duplicated(["store_id","product_id"]).any() and not r.duplicated(["store_id","product_id"]).any()
    assert u.n_forecasts.eq(28).all() and f.n_forecasts.eq(7).all()
    assert not r[["abc_class","xyz_class","stockout_exposure","censoring_risk_flag","demand_observation_risk_cell"]].isna().any().any()
    np.testing.assert_array_equal(u.persistent_underforecast_flag,u.bias.lt(0)&u.negative_bias_fold_count.ge(3))
    np.testing.assert_array_equal(r.demand_observation_risk_cell,risk_cells(r.censoring_risk_flag,r.persistent_underforecast_flag))
    assert (u.underforecast_days+u.overforecast_days+u.exact_forecast_days).eq(28).all()
    assert u.negative_bias_fold_count.between(0,4).all()
    assert u.source_split.eq("train").all() and pd.to_datetime(u.as_of).eq(pd.Timestamp("2024-06-25")).all()
    assert pd.to_datetime(u.available_from).eq(pd.Timestamp("2024-06-26")).all()
    original=pd.read_parquet(ROOT/"data/processed/mart_operational_profile.parquet").sort_values(["store_id","product_id"])
    for col in ["abc_class","xyz_class","stockout_exposure","censoring_risk_flag"]:
        np.testing.assert_array_equal(r[col],original[col])
    # Identidade variância amostral = N/(N-1) * (RMSE² - bias²).
    np.testing.assert_allclose(u.error_std**2,28/27*(u.rmse**2-u.bias**2),rtol=1e-10,atol=1e-12)
    old=pd.read_parquet(ROOT/"data/processed/mart_model_comparison.parquet",filters=[("level","=","series")]).sort_values(["store_id","product_id"])
    for metric in ["mae","rmse","wape","bias","bias_pct"]:
        np.testing.assert_allclose(u[metric],old[f"{metric}_ets"],rtol=1e-11,atol=1e-12)
    assert s["n_fits_performed"]==0 and not s["raw_files_opened"] and not s["point_forecasts_modified"]


def test_population_calibration_partitions_and_example_rules(risk_summary):
    s=risk_summary
    c=pd.read_parquet(ROOT/s["artifacts"]["calibration"]["path"])
    r=pd.read_parquet(ROOT/s["artifacts"]["risk_profile"]["path"])
    g=c.loc[c.level.eq("global")].iloc[0]
    for _,part in c.groupby("level"):
        assert part.n_forecasts.sum()==1400000 and part.n_series.sum()==50000
        assert part.actual_total.sum()==pytest.approx(g.actual_total)
        assert part.train_normalized_sales_share.sum()==pytest.approx(1.)
        assert np.dot(part.n_forecasts,part.mae)/1400000==pytest.approx(g.mae)
    matrix=pd.read_parquet(ROOT/s["artifacts"]["risk_matrix"]["path"])
    for _,part in matrix.groupby("level"):
        assert part.n_series.sum()==50000 and part.n_forecasts.sum()==1400000
        assert part.train_normalized_sales_share.sum()==pytest.approx(1.)
    chosen=pd.read_parquet(ROOT/s["artifacts"]["example_selection"]["path"])
    assert_frame_equal(chosen,select_risk_examples(r.sample(frac=1,random_state=30)))
    assert len(chosen)==7


def test_population_outputs_reproduce_without_raw_eval_or_forecast_fitting(tmp_path,risk_summary,monkeypatch):
    import src.forecasting.ets as ets
    def forbidden(*args,**kwargs):
        raise AssertionError("Fase 6 não pode ajustar ETS.")
    monkeypatch.setattr(ets,"forecast_history",forbidden)
    required=["config/source_manifest.yaml"]
    for entry in risk_summary["inputs"].values():
        required.extend([entry["summary_path"],entry["path"]])
    for name in required:
        target=tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        try:
            os.link(ROOT/name,target)
        except OSError:
            shutil.copyfile(ROOT/name,target)
    assert not (tmp_path/"data/raw").exists()
    rebuilt=build_forecast_risk(tmp_path,write_document=False)
    for name,item in risk_summary["artifacts"].items():
        assert rebuilt["artifacts"][name]["sha256"]==item["sha256"],name
        assert sha256_file(ROOT/item["path"])==item["sha256"]
    assert sha256_file(tmp_path/"data/outputs/forecast_uncertainty/summary.json")==sha256_file(ROOT/"data/outputs/forecast_uncertainty/summary.json")


def test_input_scope_guard_rejects_eval_metadata_before_opening_artifact(tmp_path):
    (tmp_path/"config").mkdir()
    shutil.copyfile(ROOT/"config/source_manifest.yaml",tmp_path/"config/source_manifest.yaml")
    folder=tmp_path/"data/outputs/statistical_forecasting"
    folder.mkdir(parents=True)
    s=json.loads((ROOT/"data/outputs/statistical_forecasting/summary.json").read_text(encoding="utf-8"))
    s["source_split"]="eval"
    (folder/"summary.json").write_text(json.dumps(s),encoding="utf-8")
    with pytest.raises(ValueError,match="train"):
        verified_inputs(tmp_path)
