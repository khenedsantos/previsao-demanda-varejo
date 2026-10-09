"""Contratos populacionais e comparação, sem repetir os 200 mil ajustes."""

from datetime import timedelta
import json

import duckdb
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest
from threadpoolctl import threadpool_limits

from src.forecasting.backtesting import make_folds
from src.forecasting.ets_benchmark import load_histories
from src.forecasting.model_comparison import pair_metrics,hybrid_choices,diagnostic_tables,win_rate_tables,materiality_table
from src.forecasting.statistical_backtesting import forecast_batch,attach_actuals
from src.ingestion.source_manifest import ROOT,sha256_file
from src.validation.forecast_metrics import create_metric_tables,metrics_from_arrays


@pytest.fixture
def small_comparison(tmp_path):
    origin=make_folds()[0]["forecast_origin"]
    common={"store_id":[1,1,2,2],"product_id":[99]*4,"fold_id":[1]*4,
        "forecast_origin":[origin]*4,"cutoff_date":[origin-timedelta(days=1)]*4,
        "target_date":[origin,origin+timedelta(days=1)]*2,"horizon_step":[1,2,1,2],"actual":[1.,1.,0.,0.]}
    baseline=pd.DataFrame({**common,"model":"seasonal_naive","forecast":[2.,2.,0.,0.]})
    baseline["error"]=baseline.forecast-baseline.actual
    naive=baseline.assign(model="naive",forecast=100.,error=lambda x:100.-x.actual)
    pd.concat([baseline,naive]).to_parquet(tmp_path/"baseline.parquet",index=False)
    candidate=pd.DataFrame({**common,"model":"ets_ana","forecast":[1.,1.,1.,1.]})
    candidate["error"]=candidate.forecast-candidate.actual
    candidate["forecast_unclipped"]=candidate.forecast
    candidate["negative_clipped"]=False
    candidate["fallback_flag"]=False
    candidate["fallback_reason"]=""
    candidate.to_parquet(tmp_path/"ets.parquet",index=False)
    segments=pd.DataFrame({"store_id":[1,2],"product_id":[99,99],"fold_id":[1,1],"forecast_origin":[origin,origin],
        "abc_class":["A","B"],"xyz_class":["X","Z"],"stockout_exposure":["LOW","HIGH"],"censoring_risk_flag":[False,True]})
    segments.to_parquet(tmp_path/"segments.parquet",index=False)
    return tmp_path,baseline,candidate


def test_multiple_marts_pair_metrics_and_zero_reference(small_comparison):
    path,baseline,candidate=small_comparison
    with duckdb.connect() as connection:
        create_metric_tables(connection,[path/"baseline.parquet",path/"ets.parquet"],path/"segments.parquet",
            models=["seasonal_naive","ets_ana"],extra_levels={"series_abc":["store_id","product_id","abc_class"],"series_xyz":["store_id","product_id","xyz_class"]})
        metrics=connection.execute("SELECT * FROM metrics").df()
    assert set(metrics.model)=={"seasonal_naive","ets_ana"}
    pairs=pair_metrics(metrics)
    global_pair=pairs.loc[pairs.level.eq("global")].iloc[0]
    assert global_pair.winner_mae=="tie"
    assert global_pair.improvement_mae==pytest.approx(0.)
    assert global_pair.actual_sum==2 and global_pair.n_forecasts==4
    assert global_pair.rmse_ets==pytest.approx(np.sqrt(.5))
    first=pairs.loc[pairs.level.eq("series")&pairs.store_id.eq(1)].iloc[0]
    assert first.improvement_mae==pytest.approx(1.) and first.winner_mae=="ets"
    second=pairs.loc[pairs.level.eq("series")&pairs.store_id.eq(2)].iloc[0]
    assert pd.isna(second.improvement_mae) and pd.isna(second.wape_ets)
    assert second.winner_mae=="seasonal_naive" and second.winner_wape=="undefined"
    assert "improvement_bias" not in pairs
    wins=win_rate_tables(pairs)
    row=wins.loc[wins.level.eq("global")&wins.metric.eq("mae")].iloc[0]
    assert row.ets_count==1 and row.seasonal_naive_count==1 and row.tie_count==0
    materiality=materiality_table(pairs)
    assert materiality.loc[materiality.metric.eq("mae"),"undefined_reference"].iloc[0]==1
    wrong=metrics.copy()
    wrong.loc[wrong.model.eq("ets_ana")&wrong.level.eq("global"),"actual_sum"]+=1
    with pytest.raises(ValueError,match="Denominador"):
        pair_metrics(wrong)


def test_fit_diagnostics_count_adjustments_not_forecast_rows(small_comparison):
    path,_,_=small_comparison
    with duckdb.connect() as connection:
        diag,reasons,keys=diagnostic_tables(connection,path/"ets.parquet",path/"segments.parquet")
    row=diag.loc[diag.level.eq("global")].iloc[0]
    assert row.n_fits==2 and row.n_forecasts==4 and row.fallback_fits==0
    assert row.clipped_forecasts==0 and reasons.empty and keys.empty


def test_hybrid_choice_only_uses_two_or_more_completed_folds():
    rows=pd.DataFrame({"fold_id":[1,2,3,4],"abc_class":["A"]*4,"xyz_class":["X"]*4,
        "improvement_wape":[.1,.2,.1,-.9],"improvement_rmse":[.1,.1,.1,-.9],
        "error_sum_ets":[-1.,-1.,-1.,-100.],"error_sum_seasonal_naive":[-2.,-2.,-2.,-2.]})
    choices=hybrid_choices(rows)
    assert choices.model_used.tolist()==["seasonal_naive","seasonal_naive","ets_ana","ets_ana"]
    altered=rows.copy()
    altered.loc[altered.fold_id.eq(4),["improvement_wape","improvement_rmse","error_sum_ets"]]=[999.,999.,999.]
    assert_frame_equal(choices,hybrid_choices(altered))
    rows.loc[rows.fold_id.eq(2),"error_sum_ets"]=-100.
    assert hybrid_choices(rows).loc[lambda f:f.fold_id.eq(3),"model_used"].iloc[0]=="seasonal_naive"


def test_batch_preserves_cutoff_fallback_and_finite_forecasts():
    fold=make_folds()[0]
    histories=pd.DataFrame({"store_id":[1,2],"product_id":[1,1],"last_date":[fold["cutoff_date"]]*2,
        "history":[np.tile([0.,1.,3.,2.,4.,1.,2.],9)[:62],np.zeros(62)]})
    batch,_=forecast_batch(histories,fold)
    assert len(batch)==14 and batch.model.eq("ets_ana").all()
    assert batch.horizon_step.tolist()==list(range(1,8))*2
    assert batch.loc[batch.store_id.eq(2),"fallback_reason"].eq("constant_history").all()
    assert batch.forecast.ge(0).all() and np.isfinite(batch.forecast).all()
    assert "actual" not in batch and "error" not in batch
    histories.loc[0,"last_date"]=fold["forecast_origin"]
    with pytest.raises(ValueError,match="cutoff"):
        forecast_batch(histories,fold)


def test_attach_actuals_excludes_naive_and_preserves_sign(small_comparison):
    path,_,candidate=small_comparison
    predictions=candidate.drop(columns=["actual","error"])
    with duckdb.connect() as connection:
        joined=attach_actuals(connection,predictions,path/"baseline.parquet").to_pandas()
    assert len(joined)==4
    np.testing.assert_array_equal(joined.error,[0.,0.,1.,1.])


@pytest.fixture(scope="module")
def population_summary():
    path=ROOT / "data/outputs/statistical_forecasting/summary.json"
    assert path.is_file(),"Concluir a população e a comparação antes dos testes de integração."
    return json.loads(path.read_text(encoding="utf-8"))


def test_population_coverage_grain_horizon_fallback_clipping_and_no_eval(population_summary):
    path=ROOT / population_summary["artifacts"]["forecasts"]["path"]
    with duckdb.connect(config={"threads":1,"memory_limit":"512MB"}) as connection:
        row=connection.execute("""SELECT count(*),count(DISTINCT (store_id,product_id)),
            count(DISTINCT (store_id,product_id,fold_id)),count(DISTINCT (store_id,product_id,forecast_origin,target_date,model)),
            count(*) FILTER(WHERE model!='ets_ana' OR model_requested!='ets_ana' OR horizon_step NOT BETWEEN 1 AND 7
                OR cutoff_date>=forecast_origin OR target_date<forecast_origin OR target_date>DATE '2024-06-25'
                OR date_diff('day',forecast_origin,target_date)+1!=horizon_step
                OR NOT isfinite(forecast) OR forecast<0 OR abs(error-forecast+actual)>1e-10
                OR negative_clipped!=(forecast_unclipped<0) OR forecast!=greatest(0,forecast_unclipped)
                OR (fallback_flag AND (model_used!='seasonal_naive' OR fallback_reason=''))
                OR (NOT fallback_flag AND (model_used!='ets_ana' OR fallback_reason!='')))
            FROM read_parquet(?)""",[str(path)]).fetchone()
        assert row==(1400000,50000,200000,1400000,0)
        assert connection.execute("""SELECT fold_id,count(*),count(DISTINCT (store_id,product_id)),
            count(DISTINCT target_date) FROM read_parquet(?) GROUP BY fold_id ORDER BY fold_id""",
            [str(path)]).fetchall()==[(i,350000,50000,7) for i in range(1,5)]
        windows=connection.execute("""SELECT DISTINCT fold_id,forecast_origin,cutoff_date
            FROM read_parquet(?) ORDER BY fold_id""",[str(path)]).fetchall()
        assert windows==[(f["fold_id"],f["forecast_origin"],f["cutoff_date"]) for f in make_folds()]
        baseline=ROOT / "data/processed/mart_forecast_baselines.parquet"
        mismatch=connection.execute("""SELECT count(*) FROM read_parquet(?) f JOIN read_parquet(?) b
            USING(store_id,product_id,fold_id,target_date,forecast_origin) WHERE b.model='seasonal_naive'
            AND (f.actual!=b.actual OR (f.fallback_flag AND f.forecast!=b.forecast))""",[str(path),str(baseline)]).fetchone()[0]
        assert mismatch==0
    assert population_summary["source_split"]=="train" and population_summary["analysis_view"]=="prospective"


def test_population_metric_consistency_and_phase4_reference(population_summary):
    pairs=pd.read_parquet(ROOT / population_summary["artifacts"]["comparison"]["path"])
    global_pair=pairs.loc[pairs.level.eq("global")].iloc[0]
    assert global_pair.n_forecasts==1400000 and global_pair.n_folds==4
    assert len(pairs.loc[pairs.level.eq("series")])==50000
    assert len(pairs.loc[pairs.level.eq("series_fold")])==200000
    old=json.loads((ROOT / "data/outputs/forecasting_baselines/summary.json").read_text(encoding="utf-8"))
    reference=next(r for r in old["metrics"] if r["level"]=="global" and r["model"]=="seasonal_naive")
    for metric in ["mae","rmse","wape","bias","bias_pct"]:
        assert global_pair[f"{metric}_seasonal_naive"]==pytest.approx(reference[metric],rel=1e-12,abs=1e-12)
    for level in ["fold","abc","xyz","abc_xyz","stockout_exposure","censoring_risk_flag"]:
        group=pairs.loc[pairs.level.eq(level)]
        assert group.n_forecasts.sum()==1400000
        assert group.actual_sum.sum()==pytest.approx(global_pair.actual_sum)
        for model in ["ets","seasonal_naive"]:
            assert group[f"absolute_error_sum_{model}"].sum()==pytest.approx(global_pair[f"absolute_error_sum_{model}"])
    for metric in ["mae","rmse","wape"]:
        a=pairs[f"{metric}_seasonal_naive"]
        b=pairs[f"{metric}_ets"]
        expected=(a-b)/a
        valid=a.gt(0)&a.notna()&b.notna()
        np.testing.assert_allclose(pairs.loc[valid,f"improvement_{metric}"],expected.loc[valid],rtol=1e-12,atol=1e-12)
        assert pairs.loc[~valid,f"improvement_{metric}"].isna().all()
    assert pairs.loc[pairs.actual_sum.eq(0),["wape_ets","wape_seasonal_naive","bias_pct_ets","bias_pct_seasonal_naive"]].isna().all().all()


def test_population_hashes_and_small_batch_reproduction(population_summary):
    for name,entry in population_summary["artifacts"].items():
        assert sha256_file(ROOT/entry["path"])==entry["sha256"],name
    path=ROOT / population_summary["artifacts"]["forecasts"]["path"]
    saved=pd.read_parquet(path,filters=[("fold_id","=",4)])
    keys=saved[["store_id","product_id"]].drop_duplicates().iloc[[0,10000,20000,30000,40000,49999]]
    fold=make_folds()[-1]
    histories=load_histories(ROOT / "data/raw/train.parquet",fold["cutoff_date"],keys)
    # O runner fixa BLAS/OMP/MKL em uma thread antes dos imports. Reproduzir
    # esse runtime aqui, mesmo se pytest já carregou as bibliotecas numéricas.
    with threadpool_limits(limits=1):
        rebuilt,_=forecast_batch(histories,fold)
    expected=saved.merge(keys,on=["store_id","product_id"]).sort_values(["store_id","product_id","target_date"])
    np.testing.assert_array_equal(rebuilt.forecast.to_numpy(),expected.forecast.to_numpy())
    np.testing.assert_array_equal(rebuilt.forecast_unclipped.to_numpy(),expected.forecast_unclipped.to_numpy())
    assert rebuilt.model_used.tolist()==expected.model_used.tolist()
