"""Fronteiras, independência das dimensões, proveniência e reprodução da Fase 3."""

from datetime import timedelta
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.features.demand_profile import TRAIN_END
from src.ingestion.source_manifest import ROOT,sha256_file
from src.segmentation.abc import classify_products
from src.segmentation.xyz import WEEKLY_CV,PATTERN,fit_thresholds,classify_series
from src.segmentation.stockout_exposure import fit_exposure_thresholds,classify_exposure
from src.segmentation.operational_profile import build_segmentation,validate_profile_scope,select_examples


@pytest.mark.parametrize("sales,expected",[
    ([50,31,15,4],["A","A","B","C"]),
    ([80,15,5],["A","B","C"]),
    ([96,4],["A","C"]),
])
def test_abc_crossing_item_and_exact_boundaries(sales,expected):
    frame=pd.DataFrame({"product_id":range(1,len(sales)+1),"normalized_sales_total":sales})
    actual=classify_products(frame)
    assert actual.abc_class.tolist()==expected
    assert actual.normalized_sales_share.sum()==pytest.approx(1)
    assert actual.normalized_sales_cumulative_share.is_monotonic_increasing
    assert actual.abc_rank.tolist()==list(range(1,len(sales)+1))


def test_abc_ties_use_product_id_and_are_order_invariant():
    frame=pd.DataFrame({"product_id":[20,10,40,30],"normalized_sales_total":[40.,40.,5.,15.]})
    actual=classify_products(frame)
    assert actual.product_id.tolist()==[10,20,30,40]
    assert actual.abc_class.tolist()==["A","A","B","C"]
    assert_frame_equal(actual,classify_products(frame.iloc[::-1]))


@pytest.mark.parametrize("sales",[[-1,2],[0,0],[np.nan,1],[np.inf,1]])
def test_abc_rejects_invalid_contributions(sales):
    with pytest.raises(ValueError,match="contribuições"):
        classify_products(pd.DataFrame({"product_id":[1,2],"normalized_sales_total":sales}))


def test_xyz_boundaries_and_missing_values_are_explained():
    frame=pd.DataFrame({"store_id":range(9),"product_id":[1]*9,
                        WEEKLY_CV:[.2,.3,.4,.2,.4,.5,.1,np.nan,np.nan],
                        PATTERN:[.6,.5,.5,-.1,-.1,np.nan,np.nan,-.2,np.nan]})
    thresholds={"name":"test_rule","variability_metric":WEEKLY_CV,"variability_low":.2,
                "variability_high":.4,"stability_low":-.1,"stability_good":.6}
    actual=classify_series(frame,thresholds)
    assert actual.xyz_class.tolist()==["X","Y","Z","Z","Z","Z","Y","Z","Y"]
    assert actual.xyz_reason.tolist()==["X_LOW_CV_STABLE","Y_INTERMEDIATE","Z_HIGH_CV",
        "Z_LOW_STABILITY","Z_BOTH","Z_HIGH_CV_NO_PATTERN","Y_INCOMPLETE_METRICS",
        "Z_LOW_PATTERN_NO_CV","Y_INCOMPLETE_METRICS"]
    assert actual[PATTERN].isna().sum()==3


def test_xyz_thresholds_recompute_and_ignore_unrelated_dimensions():
    frame=pd.DataFrame({"store_id":range(100),"product_id":[1]*100,
                        WEEKLY_CV:np.arange(100)/100,PATTERN:np.linspace(-1,1,100)})
    thresholds=fit_thresholds(frame)
    assert thresholds["variability_low"]==pytest.approx(.495)
    assert thresholds["variability_high"]==pytest.approx(.7425)
    assert thresholds["stability_low"]==pytest.approx(-.5)
    assert thresholds["stability_good"]==pytest.approx(0)
    expected=classify_series(frame,thresholds)
    unrelated=frame.assign(stockout_rate=1,stockout_exposure="HIGH",abc_class="A",activity_rate=1,
                           total_stockout_hours=1440,censoring_risk_flag=True,zero_ratio=1,adi=999,
                           coefficient_of_variation=999,autocorrelation_lag7=-1)
    assert fit_thresholds(unrelated)==thresholds
    assert_frame_equal(expected,classify_series(unrelated,fit_thresholds(unrelated)))
    scaled=frame.copy()
    scaled[WEEKLY_CV]*=10
    new_thresholds=fit_thresholds(scaled)
    assert new_thresholds["variability_high"]==pytest.approx(10*thresholds["variability_high"])
    assert classify_series(scaled,new_thresholds).xyz_class.tolist()==expected.xyz_class.tolist()


def test_exposure_boundaries_and_flag_are_separate_from_xyz():
    frame=pd.DataFrame({"store_id":range(5),"product_id":[1]*5,"stockout_rate":[.1,.2,.5,.8,.9],
                        "zero_ratio":[.1,.2,.5,.8,.9],"total_stockout_hours":[10,20,50,80,90],
                        "maximum_consecutive_stockout_days":[1,2,3,4,5],
                        "mean_stockout_hours_when_affected":[2]*5})
    thresholds=fit_exposure_thresholds(frame)
    assert thresholds["stockout_low"]==.2 and thresholds["stockout_high"]==.8
    actual=classify_exposure(frame,thresholds)
    assert actual.stockout_exposure.tolist()==["LOW","LOW","MEDIUM","HIGH","HIGH"]
    assert actual.censoring_risk_flag.tolist()==[False,False,False,True,True]
    assert_frame_equal(actual,classify_exposure(frame.assign(xyz_class="X",abc_class="A"),thresholds))


def test_degenerate_exposure_quantiles_keep_ties_together():
    frame=pd.DataFrame({"store_id":[1,2],"product_id":[1,1],"stockout_rate":[.4,.4],"zero_ratio":[0.,0.],
                        "total_stockout_hours":[100,100],"maximum_consecutive_stockout_days":[5,5],
                        "mean_stockout_hours_when_affected":[4.,4.]})
    result=classify_exposure(frame,fit_exposure_thresholds(frame))
    assert result.stockout_exposure.tolist()==["HIGH","HIGH"]


@pytest.fixture(scope="module")
def artifacts():
    summary_path=ROOT / "data/outputs/segmentation/summary.json"
    assert summary_path.is_file(),"Execute scripts/build_segmentation.py antes dos testes de integração."
    summary=json.loads(summary_path.read_text(encoding="utf-8"))
    tables={name:pd.read_parquet(ROOT / entry["path"]) for name,entry in summary["artifacts"].items()}
    return summary,tables


def test_real_abc_contract_and_propagation(artifacts):
    summary,tables=artifacts
    abc=tables["product_abc"]
    assert len(abc)==abc.product_id.nunique()==865
    assert abc.abc_class.notna().all() and set(abc.abc_class)=={"A","B","C"}
    assert abc.normalized_sales_share.sum()==pytest.approx(1)
    assert abc.normalized_sales_cumulative_share.is_monotonic_increasing
    assert abc.abc_class.map({"A":0,"B":1,"C":2}).is_monotonic_increasing
    assert abc.groupby("abc_class").size().to_dict()=={"A":122,"B":167,"C":576}
    op=tables["operational_profile"]
    propagated=op.merge(abc[["product_id","abc_class"]],on="product_id",validate="many_to_one",suffixes=("","_product"))
    assert propagated.abc_class.eq(propagated.abc_class_product).all()
    assert op.groupby("product_id").abc_class.nunique().eq(1).all()
    assert abc.associated_series.sum()==50000
    assert abc.normalized_sales_total.sum()==pytest.approx(op.total_demand.sum())


def test_real_xyz_exposure_and_operational_contracts(artifacts):
    summary,tables=artifacts
    profile=pd.read_parquet(ROOT / "data/processed/mart_demand_profile.parquet")
    validate_profile_scope(profile,TRAIN_END)
    assert summary["source_split"]=="train" and summary["as_of"]==str(TRAIN_END)
    assert summary["xyz"]["thresholds"]==fit_thresholds(profile)
    assert summary["exposure"]["thresholds"]==fit_exposure_thresholds(profile)
    for name in ["series_xyz","stockout_exposure","operational_profile"]:
        frame=tables[name]
        assert len(frame)==50000 and not frame.duplicated(["store_id","product_id"]).any()
    op=tables["operational_profile"]
    assert op[["abc_class","xyz_class","xyz_reason","stockout_exposure","censoring_risk_flag"]].notna().all().all()
    assert set(op.xyz_class)=={"X","Y","Z"}
    assert set(op.stockout_exposure)=={"LOW","MEDIUM","HIGH"}
    expected_flag=(op.stockout_rate>=profile.stockout_rate.quantile(.75))&(op.zero_ratio>=profile.zero_ratio.quantile(.75))
    assert op.censoring_risk_flag.equals(expected_flag)
    assert int(expected_flag.sum())==2651
    undefined=tables["series_xyz"].loc[tables["series_xyz"][PATTERN].isna()]
    assert len(undefined)==4
    assert undefined.xyz_class.eq("Z").all()
    assert undefined.xyz_reason.eq("Z_HIGH_CV_NO_PATTERN").all()
    assert op.loc[op.zero_ratio>.5,"xyz_class"].eq("Z").all()
    assert summary["xyz"]["zero_majority_classes"]=={"X":0,"Y":0,"Z":74}


@pytest.mark.parametrize("mutation",["eval","future","duplicate","wrong_origin"])
def test_scope_guard_prevents_eval_and_future_reuse(mutation):
    profile=pd.read_parquet(ROOT / "data/processed/mart_demand_profile.parquet").iloc[:5].copy()
    cutoff=TRAIN_END
    if mutation=="eval":
        profile.loc[profile.index[0],"source_split"]="eval"
    elif mutation=="future":
        profile.loc[profile.index[0],"last_date"]=TRAIN_END+timedelta(days=1)
    elif mutation=="duplicate":
        profile=pd.concat([profile,profile.iloc[:1]],ignore_index=True)
    else:
        cutoff=TRAIN_END-timedelta(days=7)
    with pytest.raises(ValueError):
        validate_profile_scope(profile,cutoff)


def test_matrix_conserves_series_sales_and_flags(artifacts):
    _,tables=artifacts
    matrix,op=tables["abc_xyz_matrix"],tables["operational_profile"]
    assert len(matrix)==9 and not matrix.duplicated(["abc_class","xyz_class"]).any()
    assert matrix.n_series.sum()==50000
    assert matrix.normalized_sales_total.sum()==pytest.approx(op.total_demand.sum())
    assert matrix.normalized_sales_share.sum()==pytest.approx(1)
    assert matrix.censoring_risk_count.sum()==2651
    assert matrix.high_exposure_count.sum()==(op.stockout_exposure=="HIGH").sum()


def test_example_selection_is_order_invariant(artifacts):
    _,tables=artifacts
    op=tables["operational_profile"]
    first=select_examples(op)
    second=select_examples(op.iloc[::-1])
    assert_frame_equal(first,second)
    assert len(first)==6


def test_all_outputs_reproduce_without_eval_or_staging(tmp_path,artifacts):
    summary,_=artifacts
    # Clone mínimo de entradas aprovadas; nenhum eval/staging/relatório global de qualidade.
    relatives=["config/project.yaml","config/source_manifest.yaml","data/raw/train.parquet",
               "data/processed/mart_demand_profile.parquet","data/outputs/demand_understanding/summary.json"]
    for relative in relatives:
        destination=tmp_path / relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            os.link(ROOT / relative,destination)
        except OSError:
            shutil.copyfile(ROOT / relative,destination)
    assert not (tmp_path / "data/raw/eval.parquet").exists()
    assert not (tmp_path / "data/staging").exists()
    recreated=build_segmentation(tmp_path)
    for name,entry in summary["artifacts"].items():
        assert recreated["artifacts"][name]["sha256"]==entry["sha256"],name
        assert sha256_file(ROOT / entry["path"])==entry["sha256"]
    relative=Path("data/outputs/segmentation/summary.json")
    assert sha256_file(ROOT / relative)==sha256_file(tmp_path / relative)
