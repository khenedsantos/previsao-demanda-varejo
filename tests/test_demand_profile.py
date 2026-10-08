"""Contratos da Fase 2, casos matemáticos e isolamento temporal de train."""

from datetime import timedelta
import json
import os
from pathlib import Path
import shutil

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features.demand_profile import (
    MEAN_EPSILON, TRAIN_START, TRAIN_END, build_demand_profile, prepare_tables, summarize,
)
from src.ingestion.source_manifest import ROOT, sha256_file


@pytest.fixture
def synthetic_train(tmp_path):
    rows = []
    for product in range(1, 6):
        for t in range(90):
            value = {1:1.0, 2:0.0, 3:1e-12*(1+t%2), 4:float(1+t%7), 5:float(t%2)}[product]
            rows.append({"store_id":1,"product_id":product,"dt":str(TRAIN_START+timedelta(days=t)),
                         "sale_amount":value,"stock_hour6_22_cnt":4 if t in [0,1,2,5,6,7,8,9,89] else 0,
                         "activity_flag":t%2,"discount":0.8 if t%2 else 1.0})
    path = tmp_path / "train.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def profile_rows(path, as_of=TRAIN_END):
    with duckdb.connect(config={"threads":1}) as connection:
        prepare_tables(connection, path, as_of)
        table = connection.execute("SELECT * FROM profile ORDER BY store_id,product_id").to_arrow_table()
        return table, summarize(connection, as_of)


def test_metric_formulas_and_undefined_values(synthetic_train):
    table, summary = profile_rows(synthetic_train)
    rows = {row["product_id"]:row for row in table.to_pylist()}
    constant, zero, tiny, periodic, intermittent = [rows[p] for p in range(1,6)]
    assert constant["std_demand"] == constant["coefficient_of_variation"] == 0
    assert constant["autocorrelation_lag7"] is None
    assert constant["weekly_pattern_half_correlation"] is None
    assert constant["weekly_pattern_half_mae"] == 0
    assert zero["coefficient_of_variation"] is zero["adi"] is zero["autocorrelation_lag7"] is None
    assert zero["maximum_consecutive_zero_days"] == 90
    assert zero["positive_demand_cv_squared"] is None
    assert zero["weekly_pattern_half_mae"] is None
    assert zero["early_valid_weeks"] == zero["late_valid_weeks"] == 0
    assert tiny["mean_demand"] <= MEAN_EPSILON
    assert tiny["near_zero_mean"] and tiny["coefficient_of_variation"] is None
    assert tiny["autocorrelation_lag7"] is None
    assert periodic["autocorrelation_lag7"] == pytest.approx(1)
    assert periodic["weekly_pattern_half_correlation"] == pytest.approx(1)
    assert periodic["lag7_pairs"] == 83
    assert periodic["complete_weeks"] == 12
    assert periodic["mean_weekly_demand"] == 28
    assert periodic["weekly_coefficient_of_variation"] == 0
    assert periodic["std_demand"] == pytest.approx(np.std([1+t%7 for t in range(90)], ddof=1))
    assert intermittent["zero_days"] == intermittent["positive_days"] == 45
    assert intermittent["adi"] == 2
    assert intermittent["positive_demand_cv_squared"] == 0
    assert intermittent["maximum_consecutive_zero_days"] == 1
    for row in rows.values():
        assert row["maximum_consecutive_stockout_days"] == 5
        assert row["stockout_days"] == 9
        assert row["total_stockout_hours"] == 36
        assert row["mean_stockout_hours_when_affected"] == 4
        assert row["activity_days"] == row["discount_days"] == 45
        assert row["zero_days"]+row["positive_days"] == 90
        assert 0 <= row["zero_ratio"] <= 1 and 0 <= row["stockout_rate"] <= 1
    assert summary["overview"]["n_series"] == 5


def test_future_values_cannot_change_cutoff_metrics_or_selection(synthetic_train):
    cutoff = TRAIN_START+timedelta(days=41)
    original_table, original_summary = profile_rows(synthetic_train, cutoff)
    altered = pq.read_table(synthetic_train).to_pylist()
    for row in altered:
        if row["dt"] > str(cutoff):
            row.update(sale_amount=1e8, discount=99.0, stock_hour6_22_cnt=16, activity_flag=1)
    # Inclui até observação de data do holdout no arquivo de teste: filtro temporal a exclui.
    altered.append({**altered[-1],"dt":"2024-06-26"})
    pq.write_table(pa.Table.from_pylist(altered), synthetic_train)
    updated_table, updated_summary = profile_rows(synthetic_train, cutoff)
    assert original_table.equals(updated_table)
    assert original_summary == updated_summary
    assert all(row["last_date"] == cutoff for row in updated_table.to_pylist())


def test_holdout_path_and_future_cutoff_are_rejected(synthetic_train):
    with duckdb.connect() as connection:
        with pytest.raises(ValueError, match="somente train"):
            prepare_tables(connection, synthetic_train.with_name("eval.parquet"))
        with pytest.raises(ValueError, match="Corte"):
            prepare_tables(connection, synthetic_train, TRAIN_END+timedelta(days=1))


@pytest.mark.parametrize("mutation",["duplicate","gap","negative","nonfinite"])
def test_invalid_calendar_or_sales_block_metrics(synthetic_train, mutation):
    rows = pq.read_table(synthetic_train).to_pylist()
    if mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "gap":
        rows.pop(0)
    elif mutation == "negative":
        rows[0]["sale_amount"] = -1.0
    else:
        rows[0]["sale_amount"] = float("nan")
    pq.write_table(pa.Table.from_pylist(rows), synthetic_train)
    with duckdb.connect() as connection:
        with pytest.raises(ValueError, match="inválido|incompleto"):
            prepare_tables(connection, synthetic_train)


def test_discount_extremes_preserved_and_counted_separately(synthetic_train):
    rows = pq.read_table(synthetic_train).to_pylist()
    rows[0]["discount"],rows[1]["discount"] = 0.0,1.088
    pq.write_table(pa.Table.from_pylist(rows), synthetic_train)
    table, summary = profile_rows(synthetic_train)
    row = table.to_pylist()[0]
    assert row["discount_zero_days"] == row["discount_above_one_days"] == 1
    assert row["discount_days"] == 44
    assert summary["discount_anomalies"][0]["discount"] == 1.088
    assert row["mean_discount"] == pytest.approx(np.mean([r["discount"] for r in rows if r["product_id"]==1]))


@pytest.fixture(scope="module")
def real_summary():
    path = ROOT / "data/outputs/demand_understanding/summary.json"
    assert path.is_file(), "Execute scripts/build_demand_profile.py antes dos testes de integração."
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_profile_contract_and_provenance(real_summary):
    path = ROOT / real_summary["artifacts"]["profile"]["path"]
    assert sha256_file(path) == real_summary["artifacts"]["profile"]["sha256"]
    with duckdb.connect() as connection:
        row = connection.execute("""
            SELECT count(*),count(DISTINCT (store_id,product_id)),
                   count(*) FILTER(WHERE source_split!='train' OR n_days!=90
                       OR positive_days+zero_days!=90 OR zero_ratio NOT BETWEEN 0 AND 1
                       OR stockout_rate NOT BETWEEN 0 AND 1 OR first_date!=DATE '2024-03-28'
                       OR last_date!=DATE '2024-06-25'),min(lag7_pairs),max(lag7_pairs)
            FROM read_parquet(?)
        """,[str(path)]).fetchone()
    assert row == (50000,50000,0,83,83)
    assert real_summary["source"]["path"] == "data/raw/train.parquet"
    assert real_summary["overview"]["n_rows"] == 4500000
    assert not {"abc","xyz"}.intersection(pq.ParquetFile(path).schema_arrow.names)


def test_full_outputs_reproduce_with_eval_absent(tmp_path, real_summary):
    # Nova raiz sem eval nem staging: o pipeline deve funcionar apenas com train.
    (tmp_path / "config").mkdir()
    for name in ["project.yaml","source_manifest.yaml"]:
        shutil.copyfile(ROOT / "config" / name, tmp_path / "config" / name)
    (tmp_path / "data/raw").mkdir(parents=True)
    train_copy = tmp_path / "data/raw/train.parquet"
    try:
        os.link(ROOT / "data/raw/train.parquet", train_copy)
    except OSError:
        shutil.copyfile(ROOT / "data/raw/train.parquet", train_copy)
    assert not (tmp_path / "data/raw/eval.parquet").exists()
    rebuilt = build_demand_profile(root=tmp_path)
    for name, artifact in real_summary["artifacts"].items():
        assert rebuilt["artifacts"][name]["sha256"] == artifact["sha256"], name
    relative = Path("data/outputs/demand_understanding/summary.json")
    assert sha256_file(tmp_path / relative) == sha256_file(ROOT / relative)
