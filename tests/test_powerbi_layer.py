"""Contract, exact CSV transport, frozen metric parity and no upstream execution."""

import builtins
import io
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.ingestion.source_manifest import ROOT, sha256_file
from src.reporting.powerbi_contract import (
    KEYS, ATTRIBUTES, SCHEMAS, TABLES, RELATIONSHIPS, SCENARIOS,
)
from src.reporting.powerbi_layer import (
    DATA_DIR, DICTIONARY_PATH, MANIFEST_PATH, SOURCES, SUMMARY_PATHS,
    make_dim_series, make_dim_date, attach_series, normalize_table,
    validate_tables, validate_metrics, data_dictionary, load_sources,
    verify_sources, create_tables, read_exported_tables, build_powerbi_layer,
)


@pytest.fixture(autouse=True)
def forbid_fitting(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Forecast execution is forbidden in Phase 9.")
    from src.forecasting import ets, statistical_backtesting
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    monkeypatch.setattr(ets, "forecast_history", forbidden)
    monkeypatch.setattr(statistical_backtesting, "forecast_history", forbidden)
    monkeypatch.setattr(ExponentialSmoothing, "fit", forbidden)


@pytest.fixture(scope="module")
def tables():
    return read_exported_tables(ROOT)


@pytest.fixture(scope="module")
def sources():
    return load_sources(ROOT)[0]


def test_exact_population_counts_grains_and_zero_orphans(tables):
    orphans = validate_tables(tables)
    assert len(orphans) == 5 and set(orphans.values()) == {0}
    assert {name: len(frame) for name, frame in tables.items()} == {
        "DimSeries": 50000, "DimDate": 7, "DimScenario": 3,
        "FactForecast": 700000, "FactReplenishment": 150000, "FactScenarioValidation": 3}
    for name, (_, _, keys) in TABLES.items():
        assert not tables[name].duplicated(keys).any()


def test_stable_series_key_after_full_population_shuffle(sources, tables):
    original = make_dim_series(sources["replenishment"])
    shuffled = make_dim_series(sources["replenishment"].sample(frac=1, random_state=91))
    assert_frame_equal(original, shuffled, check_exact=True)
    assert_frame_equal(normalize_table("DimSeries", original), tables["DimSeries"], check_exact=True)
    assert original.series_key.tolist() == list(range(1, 50001))
    assert original[KEYS].equals(original.sort_values(KEYS)[KEYS])


def test_conflicting_attributes_or_missing_series_block():
    fixture = pd.DataFrame({"store_id": [2, 1, 1], "product_id": [4, 3, 3],
        "abc_class": ["A", "B", "B"], "xyz_class": "X", "stockout_exposure": "LOW",
        "censoring_risk_flag": False, "persistent_underforecast_flag": False,
        "demand_observation_risk_cell": "NEITHER"})
    dimension = make_dim_series(fixture)
    assert dimension[KEYS + ["series_key"]].values.tolist() == [[1, 3, 1], [2, 4, 2]]
    fixture.loc[2, "abc_class"] = "C"
    with pytest.raises(ValueError, match="invariant"):
        make_dim_series(fixture)
    with pytest.raises(ValueError, match="Orphan"):
        attach_series(pd.DataFrame({"store_id": [99], "product_id": [99]}), dimension)


def test_date_types_weekday_sorting_and_no_invented_holidays(tables):
    d = tables["DimDate"]
    assert d.date.astype(str).tolist() == pd.date_range("2024-06-26", "2024-07-02").strftime("%Y-%m-%d").tolist()
    assert d.day_of_week_number.tolist() == [3, 4, 5, 6, 7, 1, 2]
    assert d.day_of_week_name.tolist() == ["quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo", "segunda-feira", "terça-feira"]
    assert d.is_weekend.tolist() == [False, False, False, True, True, False, False]
    assert d.month_name.tolist() == ["junho"] * 5 + ["julho"] * 2
    assert d.date_sort.tolist() == [20240626, 20240627, 20240628, 20240629, 20240630, 20240701, 20240702]
    assert "holiday" not in " ".join(d.columns)


def test_scenarios_and_global_validation_from_structured_source(tables, sources):
    d = tables["DimScenario"]
    assert d.scenario.tolist() == SCENARIOS and d.scenario_order.tolist() == [1, 2, 3]
    assert d.lead_time_days.tolist() == [1, 2, 3]
    np.testing.assert_array_equal(d.target_coverage_level, [.9, .95, .98])
    assert d.scenario_description.str.contains("hipotético").all()
    v = tables["FactScenarioValidation"].set_index("scenario").loc[SCENARIOS]
    np.testing.assert_allclose(v.observed_coverage_rate, [.79648, .84084, .88322], atol=1e-12, rtol=0)
    np.testing.assert_allclose(v.coverage_gap, [-.10352, -.10916, -.09678], atol=1e-12, rtol=0)
    np.testing.assert_allclose(v.normal_reference_coverage, [.83640, .86136, .87204], atol=1e-12, rtol=0)
    original = sources["scenario_summary"].loc[lambda x: x.stage.eq("validation_fold4") & x.level.eq("global")].set_index("scenario").loc[SCENARIOS]
    np.testing.assert_array_equal(v.observed_coverage_rate, original.observed_coverage_rate)
    assert v.validation_stage.eq("validation_fold4").all()


def test_relationship_contract_has_only_five_single_direction_dimension_fact_edges():
    assert len(RELATIONSHIPS) == 5
    for relation in RELATIONSHIPS:
        assert relation["dimension"].startswith("Dim") and relation["fact"].startswith("Fact")
        assert relation["cardinality"] == "1:N"
        assert relation["filter_direction"] == "single_dimension_to_fact"
    validation_edges = [r for r in RELATIONSHIPS if r["fact"] == "FactScenarioValidation"]
    assert len(validation_edges) == 1 and validation_edges[0]["dimension"] == "DimScenario"


def test_metrics_match_frozen_references_and_approved_numbers(tables, sources):
    checks = validate_metrics(tables, sources)
    ets, naive = checks["forecast"]["ETS"], checks["forecast"]["Seasonal Naive"]
    assert ets["mae"] == pytest.approx(.424983, abs=5e-7)
    assert ets["rmse"] == pytest.approx(.711311, abs=5e-7)
    assert ets["wape"] == pytest.approx(.35621479, abs=5e-9)
    assert ets["bias_pct"] == pytest.approx(-.02251621, abs=5e-9)
    assert naive["mae"] == pytest.approx(.499071, abs=5e-7)
    assert naive["rmse"] == pytest.approx(.835819, abs=5e-7)
    assert naive["wape"] == pytest.approx(.41831405, abs=5e-9)
    for scenario, ss, rop in zip(SCENARIOS, [.572306, 1.147687, 2.024079], [1.646254, 3.263576, 5.239064]):
        assert checks["replenishment"][scenario]["mean_safety_stock"] == pytest.approx(ss, abs=5e-7)
        assert checks["replenishment"][scenario]["mean_reorder_point"] == pytest.approx(rop, abs=5e-7)


def test_export_copies_every_exposed_value_without_recomputing_sources(tables, sources):
    rebuilt = create_tables(sources)
    for name in TABLES:
        assert_frame_equal(rebuilt[name], tables[name], check_exact=True)
    f = tables["FactForecast"]
    assert f.groupby("model").size().to_dict() == {"ETS": 350000, "Seasonal Naive": 350000}
    assert tables["FactReplenishment"].groupby("scenario").size().to_dict() == {s: 50000 for s in SCENARIOS}


def test_dimension_attributes_reconstruct_all_replenishment_slices(tables, sources):
    fact, dim = tables["FactReplenishment"], tables["DimSeries"]
    assert not set(ATTRIBUTES).intersection(fact.columns)
    assert not {"safety_stock", "reorder_point", "historical_error_std", "forecast"}.intersection(dim.columns)
    joined = fact.merge(dim, on="series_key", validate="many_to_one")
    columns = KEYS + ["scenario"] + ATTRIBUTES
    reconstructed = joined[columns].sort_values(KEYS + ["scenario"]).reset_index(drop=True)
    original = sources["replenishment"][columns].sort_values(KEYS + ["scenario"]).reset_index(drop=True)
    assert_frame_equal(reconstructed, original, check_exact=True, check_dtype=False)


@pytest.mark.parametrize("table", ["DimSeries", "FactForecast", "FactReplenishment", "FactScenarioValidation"])
def test_duplicate_primary_keys_are_rejected(tables, table):
    changed = dict(tables)
    changed[table] = tables[table].copy()
    changed[table].iloc[1] = changed[table].iloc[0]
    with pytest.raises(ValueError, match="primary key"):
        validate_tables(changed)


def test_orphan_key_is_rejected(tables):
    changed = dict(tables)
    changed["FactForecast"] = tables["FactForecast"].copy()
    changed["FactForecast"].loc[0, "series_key"] = 50001
    with pytest.raises(ValueError, match="Orphan foreign key"):
        validate_tables(changed)


def test_metric_divergence_blocks_instead_of_silently_exporting(tables, sources):
    changed = dict(tables)
    changed["FactForecast"] = tables["FactForecast"].copy()
    changed["FactForecast"].loc[0, "absolute_error"] += 100.
    with pytest.raises(ValueError, match="Forecast metric divergence"):
        validate_metrics(changed, sources)
    changed = dict(tables)
    changed["FactReplenishment"] = tables["FactReplenishment"].copy()
    changed["FactReplenishment"].loc[0, "safety_stock"] += 100.
    with pytest.raises(ValueError, match="Replenishment metric divergence"):
        validate_metrics(changed, sources)


def test_dictionary_covers_all_exposed_columns_types_and_aggregation():
    actual = pd.read_csv(ROOT / DICTIONARY_PATH, encoding="utf-8-sig", keep_default_na=False)
    assert_frame_equal(actual, data_dictionary(), check_exact=True)
    assert not actual.duplicated(["table", "column"]).any()
    assert len(actual) == sum(len(s) for s in SCHEMAS.values())
    assert set(actual.data_type) == {"integer", "decimal", "date", "boolean", "text"}
    assert actual.business_definition.str.len().gt(0).all() and actual.notes.str.len().gt(0).all()
    assert actual.loc[actual.column.isin(["target_coverage_level", "observed_coverage_rate", "calibration_n"]), "aggregation_behavior"].eq("DO_NOT_SUM").all()


def test_csv_encoding_dates_booleans_and_manifest_hashes():
    manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    assert manifest["csv_round_trip_exact"] is True
    assert manifest["starting_head"].startswith("c5f1178")
    for name, artifact in manifest["tables"].items():
        path = ROOT / artifact["path"]
        with path.open("rb") as stream:
            assert stream.read(3) == b"\xef\xbb\xbf"
        assert sha256_file(path) == artifact["sha256"]
        assert artifact["rows"] == TABLES[name][1]
    dates = (ROOT / DATA_DIR / "dim_date.csv").read_text(encoding="utf-8-sig")
    assert "2024-06-26" in dates and "true" in dates and "false" in dates
    assert "quarta-feira" in dates and "sábado" in dates


def test_reproduction_from_only_allowed_marts_without_raw_or_forecasting(tmp_path, monkeypatch):
    for relative in [*(spec[2] for spec in SOURCES.values()), *SUMMARY_PATHS.values()]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    # Poisoned files are synthetic sentinels, not real source data.
    for folder in ["data/raw", "data/staging"]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "eval.parquet").write_bytes(b"FORBIDDEN RAW/STAGING")
    allowed = {spec[2] for spec in SOURCES.values()}
    reader = pd.read_parquet
    def guarded_parquet(path, *args, **kwargs):
        assert Path(path).relative_to(tmp_path).as_posix() in allowed
        return reader(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", guarded_parquet)
    original_open, original_io_open = builtins.open, io.open
    def guard(open_function):
        def wrapped(path, *args, **kwargs):
            if isinstance(path, (str, bytes, Path)):
                candidate = Path(path).resolve()
                for folder in [tmp_path / "data/raw", tmp_path / "data/staging", ROOT / "data/raw", ROOT / "data/staging"]:
                    assert not candidate.is_relative_to(folder), "Raw/staging access prohibited"
            return open_function(path, *args, **kwargs)
        return wrapped
    monkeypatch.setattr(builtins, "open", guard(original_open))
    monkeypatch.setattr(io, "open", guard(original_io_open))
    expected = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    first = build_powerbi_layer(tmp_path)
    assert first == expected
    # Another build also checks deterministic replacement and output ordering.
    second = build_powerbi_layer(tmp_path)
    assert second == expected
    assert sha256_file(tmp_path / MANIFEST_PATH) == sha256_file(ROOT / MANIFEST_PATH)
    assert sha256_file(tmp_path / DICTIONARY_PATH) == sha256_file(ROOT / DICTIONARY_PATH)
    assert set(first["orphan_keys"].values()) == {0}
    assert first["raw_reads"] == first["ets_fits"] == 0


def test_upstream_frozen_sources_unchanged_after_export():
    assert len(verify_sources(ROOT)) == 4
