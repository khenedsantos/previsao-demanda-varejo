"""Previsões auditáveis, leakage prospectivo, fórmulas e reprodução dos quatro folds."""

from datetime import timedelta
import json
import os
from pathlib import Path
import shutil

import duckdb
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features.demand_profile import TRAIN_START,TRAIN_END
from src.forecasting.baselines import create_predictions
from src.forecasting.backtesting import make_folds,compute_fold,run_backtest
from src.ingestion.source_manifest import ROOT,sha256_file
from src.segmentation.stockout_exposure import classify_exposure,fit_exposure_thresholds
from src.validation.forecast_metrics import metrics_from_arrays,create_metric_tables,relative_improvement


def test_folds_are_expanding_disjoint_and_inside_train():
    folds=make_folds()
    assert len(folds)==4
    assert [fold["history_days"] for fold in folds]==[62,69,76,83]
    targets=[]
    for fold in folds:
        assert fold["history_start"]==TRAIN_START
        assert fold["history_end"]==fold["cutoff_date"]<fold["test_start"]
        assert fold["forecast_origin"]==fold["test_start"]
        assert (fold["test_end"]-fold["test_start"]).days==6
        targets.extend(fold["test_start"]+timedelta(days=i) for i in range(7))
    assert len(set(targets))==28 and max(targets)==TRAIN_END


def test_naive_repeats_last_value_and_seasonal_repeats_only_prior_week():
    origin=TRAIN_START+timedelta(days=14)
    history=pd.DataFrame({"store_id":[1]*21,"product_id":[2]*21,
                          "dt":[TRAIN_START+timedelta(days=i) for i in range(21)],
                          "sale_amount":[float(i+1) if i<14 else 99999. for i in range(21)]})
    with duckdb.connect() as connection:
        connection.register("train",history)
        create_predictions(connection,origin)
        predictions=connection.execute("SELECT * FROM predictions ORDER BY model,target_date").df()
    naive=predictions.loc[predictions.model=="naive"]
    seasonal=predictions.loc[predictions.model=="seasonal_naive"]
    assert naive.forecast.tolist()==[14.]*7
    assert seasonal.forecast.tolist()==list(np.arange(8.,15.))
    assert (predictions.source_observation_date<pd.Timestamp(origin)).all()
    assert (seasonal.target_date-seasonal.source_observation_date).dt.days.eq(7).all()
    assert naive.horizon_step.tolist()==list(range(1,8))


def test_metrics_known_errors_and_signs():
    result=metrics_from_arrays([0,1,3],[1,2,2])
    assert result==pytest.approx({"mae":1.,"rmse":1.,"wape":.75,"bias":1/3,
                                  "bias_pct":.25,"actual_sum":4.,"n_forecasts":3})
    assert metrics_from_arrays([2,4],[1,2])["bias"]==-1.5


@pytest.mark.parametrize("forecast",[[1.,2.],[0.,0.]])
def test_zero_denominator_stays_undefined(forecast):
    result=metrics_from_arrays([0,0],forecast)
    assert result["wape"] is None and result["bias_pct"] is None
    assert result["mae"]==pytest.approx(np.mean(forecast))
    assert result["rmse"]==pytest.approx(np.sqrt(np.mean(np.square(forecast))))


@pytest.mark.parametrize("actual,forecast",[([],[]),([1],[1,2]),([np.nan],[1]),([-1],[1]),([1],[np.inf])])
def test_invalid_metric_inputs_are_rejected(actual,forecast):
    with pytest.raises(ValueError):
        metrics_from_arrays(actual,forecast)


def test_relative_improvement_does_not_divide_by_zero_or_apply_to_signed_bias():
    assert relative_improvement(.5,.4)==pytest.approx(.2)
    assert relative_improvement(.4,.5)==pytest.approx(-.25)
    assert relative_improvement(0,.1) is None
    assert relative_improvement(None,.1) is None


def test_pooled_metrics_use_sums_not_average_series_percentages(tmp_path):
    origin=make_folds()[0]["forecast_origin"]
    f=pd.DataFrame({"store_id":[1,1,2,2],"product_id":[1]*4,"fold_id":[1]*4,
                    "forecast_origin":[origin]*4,"model":["naive"]*4,"actual":[1.,1.,100.,100.],
                    "forecast":[2.,2.,100.,100.],"error":[1.,1.,0.,0.]})
    s=pd.DataFrame({"store_id":[1,2],"product_id":[1,1],"fold_id":[1,1],"forecast_origin":[origin]*2,
                    "abc_class":["A","A"],"xyz_class":["X","Z"],"stockout_exposure":["LOW","HIGH"],
                    "censoring_risk_flag":[False,True]})
    f.to_parquet(tmp_path/"forecast.parquet",index=False)
    s.to_parquet(tmp_path/"segments.parquet",index=False)
    with duckdb.connect() as connection:
        create_metric_tables(connection,tmp_path/"forecast.parquet",tmp_path/"segments.parquet")
        pooled=connection.execute("SELECT mae,rmse,wape,bias,bias_pct,actual_sum,n_forecasts,n_series,n_folds FROM metrics WHERE level='global'").fetchone()
    assert pooled==pytest.approx((.5,np.sqrt(.5),2/202,.5,2/202,202,4,2,1))


@pytest.fixture
def synthetic_train(tmp_path):
    rows=[]
    for product in [1,2]:
        for index in range(90):
            rows.append({"store_id":1,"product_id":product,"dt":str(TRAIN_START+timedelta(days=index)),
                         "sale_amount":float(1+index%7) if product==1 else 1+index*.05,
                         "stock_hour6_22_cnt":4 if index%5==0 else 0,
                         "activity_flag":index%2,"discount":.8 if index%2 else 1.})
    path=tmp_path / "train.parquet"
    pq.write_table(pa.Table.from_pylist(rows),path)
    return path


def test_future_mutation_cannot_change_predictions_or_prospective_segments(synthetic_train,tmp_path):
    fold=make_folds()[0]
    first,segments,abc,details=compute_fold(synthetic_train,fold,tmp_path/"first")
    rows=pq.read_table(synthetic_train).to_pylist()
    for row in rows:
        if row["dt"]>=str(fold["forecast_origin"]):
            row.update(sale_amount=999999.,stock_hour6_22_cnt=16,activity_flag=1,discount=999.)
    pq.write_table(pa.Table.from_pylist(rows),synthetic_train)
    second,new_segments,new_abc,new_details=compute_fold(synthetic_train,fold,tmp_path/"second")
    assert first.drop(["actual","error"]).equals(second.drop(["actual","error"]))
    assert not first["actual"].equals(second["actual"])
    assert_frame_equal(segments,new_segments)
    assert_frame_equal(abc,new_abc)
    assert details==new_details
    assert segments.cutoff_date.eq(fold["cutoff_date"]).all()


def test_no_stockout_history_keeps_undefined_duration_without_changing_rules():
    p=pd.DataFrame({"store_id":[1,2,3],"product_id":[1]*3,"stockout_rate":[0.,.5,1.],
                    "zero_ratio":[0.,.1,.2],"total_stockout_hours":[0,10,20],
                    "maximum_consecutive_stockout_days":[0,2,4],
                    "mean_stockout_hours_when_affected":[np.nan,5.,5.]})
    result=classify_exposure(p,fit_exposure_thresholds(p))
    assert result.iloc[0].stockout_exposure=="LOW"
    assert pd.isna(result.iloc[0].mean_stockout_hours_when_affected)
    p.loc[0,"total_stockout_hours"]=1
    with pytest.raises(ValueError):
        classify_exposure(p,fit_exposure_thresholds(p))


@pytest.fixture(scope="module")
def summary():
    path=ROOT / "data/outputs/forecasting_baselines/summary.json"
    assert path.is_file(),"Execute scripts/run_baseline_backtest.py antes dos testes de integração."
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_forecast_grain_sources_and_all_actuals(summary):
    forecasts=ROOT / summary["artifacts"]["forecasts"]["path"]
    with duckdb.connect(config={"threads":1}) as connection:
        row=connection.execute("""
            SELECT count(*),count(DISTINCT (store_id,product_id,forecast_origin,target_date,model)),
                count(*) FILTER(WHERE source_observation_date>=forecast_origin OR target_date<forecast_origin
                    OR target_date>DATE '2024-06-25' OR horizon_step NOT BETWEEN 1 AND 7
                    OR abs(error-(forecast-actual))>1e-12),min(target_date),max(target_date)
            FROM read_parquet(?)
        """,[str(forecasts)]).fetchone()
        assert row[:3]==(2800000,2800000,0)
        assert row[3]==make_folds()[0]["test_start"] and row[4]==TRAIN_END
        errors=connection.execute("""
            SELECT count(*) FROM read_parquet(?) f LEFT JOIN read_parquet(?) r
              ON f.store_id=r.store_id AND f.product_id=r.product_id AND f.source_observation_date=cast(r.dt AS DATE)
            WHERE r.sale_amount IS NULL OR f.forecast!=r.sale_amount
                OR (f.model='naive' AND f.source_observation_date!=f.cutoff_date)
                OR (f.model='seasonal_naive' AND date_diff('day',f.source_observation_date,f.target_date)!=7)
        """,[str(forecasts),str(ROOT/"data/raw/train.parquet")]).fetchone()[0]
        assert errors==0


def test_real_metric_grains_partitions_and_zero_denominators(summary):
    metrics=pd.read_parquet(ROOT / summary["artifacts"]["metrics"]["path"])
    global_rows=metrics.loc[metrics.level.eq("global")].set_index("model")
    assert global_rows.n_forecasts.eq(1400000).all()
    assert global_rows.n_folds.eq(4).all()
    assert len(metrics.loc[metrics.level.eq("series_fold")])==400000
    assert len(metrics.loc[metrics.level.eq("series")])==100000
    for level in ["fold","abc","xyz","stockout_exposure","censoring_risk_flag","abc_xyz"]:
        for model,group in metrics.loc[metrics.level.eq(level)].groupby("model"):
            assert group.n_forecasts.sum()==global_rows.loc[model,"n_forecasts"]
            assert group.actual_sum.sum()==pytest.approx(global_rows.loc[model,"actual_sum"])
            assert group.absolute_error_sum.sum()==pytest.approx(global_rows.loc[model,"absolute_error_sum"])
    undefined=metrics.actual_sum.eq(0)
    assert metrics.loc[undefined,["wape","bias_pct"]].isna().all().all()
    assert metrics.loc[~undefined,["wape","bias_pct"]].notna().all().all()


def test_prospective_snapshots_have_fold_specific_dates_and_thresholds(summary):
    segments=pd.read_parquet(ROOT / summary["artifacts"]["fold_segments"]["path"])
    assert len(segments)==200000 and not segments.duplicated(["store_id","product_id","fold_id"]).any()
    assert segments.source_split.eq("train").all()
    assert (pd.to_datetime(segments.cutoff_date)<pd.to_datetime(segments.forecast_origin)).all()
    assert segments["n_days"].isin([62,69,76,83]).all()
    assert segments[SEGMENT_COLUMNS].notna().all().all()
    for fold in summary["folds"]:
        part=segments.loc[segments.fold_id==fold["fold_id"]]
        assert fold["xyz_thresholds"]["variability_high"]==pytest.approx(part.weekly_coefficient_of_variation.quantile(.75))
        assert fold["exposure_thresholds"]["stockout_high"]==pytest.approx(part.stockout_rate.quantile(.75))
    assert [f["no_stockout_history_count"] for f in summary["folds"]]==[2,1,0,0]


SEGMENT_COLUMNS=["abc_class","xyz_class","stockout_exposure","censoring_risk_flag"]


def test_full_pipeline_reproduces_without_eval_or_any_previous_mart(tmp_path,summary):
    for relative in ["config/project.yaml","config/source_manifest.yaml","data/raw/train.parquet"]:
        destination=tmp_path/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            os.link(ROOT/relative,destination)
        except OSError:
            shutil.copyfile(ROOT/relative,destination)
    assert not (tmp_path/"data/raw/eval.parquet").exists()
    assert not (tmp_path/"data/processed").exists()
    recreated,_=run_backtest(tmp_path)
    for name,entry in summary["artifacts"].items():
        assert recreated["artifacts"][name]["sha256"]==entry["sha256"],name
        assert sha256_file(ROOT/entry["path"])==entry["sha256"]
    relative="data/outputs/forecasting_baselines/summary.json"
    assert sha256_file(ROOT/relative)==sha256_file(tmp_path/relative)
