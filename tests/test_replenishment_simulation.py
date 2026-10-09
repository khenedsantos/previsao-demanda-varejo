"""No model fitting or real eval access, including the population reproduction."""

import builtins
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.ingestion.source_manifest import ROOT, sha256_file
from src.replenishment.simulation import (
    CONFIG, PROTOCOL, INPUTS, METADATA, FOLDER, scenarios_from_config,
    build_simulation, assert_simulation, verify_inputs,
)
from src.validation.replenishment import (
    KEYS, DIMS, minimum_n, historical_scale, lead_time_values, calibrate,
    choose_calibration, apply_policy, dependence_diagnostics,
)


@pytest.fixture(autouse=True)
def prohibit_fitting(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Any ETS fitting is forbidden in Phase 8.")
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from src.forecasting import ets, statistical_backtesting
    monkeypatch.setattr(ExponentialSmoothing, "fit", forbidden)
    monkeypatch.setattr(ets, "forecast_history", forbidden)
    monkeypatch.setattr(statistical_backtesting, "forecast_history", forbidden)


def synthetic():
    errors = np.tile(np.arange(-3., 4.), 4)
    daily = pd.DataFrame({"store_id": 1, "product_id": 2,
        "fold_id": np.repeat([1, 2, 3, 4], 7), "horizon_step": np.tile(np.arange(1, 8), 4),
        "forecast": 5., "actual": 5. - errors, "error": errors})
    segments = pd.DataFrame({"store_id": 1, "product_id": 2, "fold_id": [1, 2, 3, 4],
        "abc_class": "A", "xyz_class": "X", "stockout_exposure": "LOW"})
    return daily, segments


def test_frozen_scenarios_and_decimal_tail_sizes(tmp_path):
    scenarios = scenarios_from_config(ROOT)
    assert [(x["scenario"], x["lead_time_days"], x["target_coverage_level"]) for x in scenarios] == [
        ("LEAN", 1, .9), ("BASE", 2, .95), ("PROTECTED", 3, .98)]
    assert [minimum_n(q) for q in [.9, .95, .98]] == [200, 400, 1000]
    (tmp_path / "config").mkdir()
    (tmp_path / CONFIG).write_text((ROOT / CONFIG).read_text().replace("0.90", "0.91"))
    with pytest.raises(ValueError, match="cannot change"):
        scenarios_from_config(tmp_path)


def test_known_lead_time_sums_errors_and_shortfall():
    d, _ = synthetic()
    for days, expected in [(1, (5, 8, -3, 3)), (2, (10, 15, -5, 5)), (3, (15, 21, -6, 6))]:
        row = lead_time_values(d, days).iloc[0]
        assert tuple(row[["lead_time_forecast", "lead_time_actual", "lead_time_error", "lead_time_shortfall"]]) == expected
    d["actual"] = 1.
    assert lead_time_values(d, 3).lead_time_shortfall.eq(0).all()


def test_historical_scale_uses_exactly_21_errors_and_no_fold4_leakage():
    d, _ = synthetic()
    first = historical_scale(d)
    assert first.n_errors.iloc[0] == 21
    assert first.historical_error_std.iloc[0] == pytest.approx(np.std(np.tile(np.arange(-3., 4.), 3), ddof=1))
    d.loc[d.fold_id.eq(4), "error"] = 1000000.
    assert_frame_equal(first, historical_scale(d))
    assert historical_scale(d, (1, 2, 3, 4)).historical_error_std.iloc[0] > 100


def test_invalid_scale_and_incomplete_windows_block():
    d, _ = synthetic()
    d["error"] = 0.
    with pytest.raises(ValueError, match="Invalid historical"):
        historical_scale(d)
    with pytest.raises(ValueError, match="Incomplete"):
        lead_time_values(d.iloc[1:], 2)
    with pytest.raises(ValueError, match="Duplicate"):
        lead_time_values(pd.concat([d, d.iloc[:1]]), 1)


def test_known_standardization_quantile_and_no_calibration_fold4_leakage():
    d, s = synthetic()
    scenarios = scenarios_from_config(ROOT)
    scale = historical_scale(d)
    table, obs = calibrate(d, s, scale, scenarios, (1, 2, 3))
    std = scale.historical_error_std.iloc[0]
    assert obs.loc[obs.scenario.eq("BASE"), "standardized_shortfall"].tolist() == pytest.approx([5 / (std * np.sqrt(2))] * 3)
    assert table.loc[table.scenario.eq("LEAN"), "empirical_multiplier"].tolist() == pytest.approx([3 / std] * 4)
    d.loc[d.fold_id.eq(4), ["error", "actual", "forecast"]] = 999.
    other, _ = calibrate(d, s, historical_scale(d), scenarios, (1, 2, 3))
    assert_frame_equal(table, other)
    # Nonconstant order statistics confirm linear interpolation, not nearest rank.
    d.loc[(d.fold_id.eq(2)) & d.horizon_step.eq(1), "actual"] = 9.
    d.loc[(d.fold_id.eq(3)) & d.horizon_step.eq(1), "actual"] = 10.
    table, _ = calibrate(d, s, scale, scenarios[:1], (1, 2, 3))
    assert table.empirical_multiplier.iloc[0] == pytest.approx(4.8 / std)


def test_hierarchy_prefers_specific_eligible_support_and_blocks_no_global():
    labels = pd.DataFrame({"store_id": [1, 2, 3, 4], "product_id": 1,
        "abc_class": ["A", "A", "B", "C"], "xyz_class": ["X", "Y", "Z", "X"], "stockout_exposure": "LOW"})
    table = pd.DataFrame({"calibration_level_used": ["ABC_XYZ_EXPOSURE", "ABC_XYZ", "XYZ", "GLOBAL"],
        "calibration_key": ["A|X|LOW", "A|Y", "Z", "ALL"], "eligible": True,
        "calibration_n": [200, 400, 1000, 2000], "calibration_n_series": [100, 200, 500, 1000],
        "empirical_multiplier": [1., 2., 3., 4.], "theoretical_normal_z": 1.28})
    result = choose_calibration(labels, table)
    assert result.calibration_level_used.tolist() == table.calibration_level_used.tolist()
    assert result.calibration_fallback_flag.tolist() == [False, True, True, True]
    table.loc[0, "eligible"] = False
    assert choose_calibration(labels, table).calibration_level_used.iloc[0] == "GLOBAL"
    with pytest.raises(ValueError, match="Insufficient GLOBAL"):
        choose_calibration(labels, table.iloc[:3])


def test_policy_identity_flags_do_not_change_formula_and_zero_ratios_null():
    d, segments = synthetic()
    scale = historical_scale(d)
    scenarios = scenarios_from_config(ROOT)
    table, _ = calibrate(d, segments, scale, scenarios, (1, 2, 3))
    table["eligible"] = True  # Tiny synthetic fixture only; production support is fixed.
    labels = segments.loc[segments.fold_id.eq(4), KEYS + DIMS].copy()
    labels["censoring_risk_flag"] = False
    labels["persistent_underforecast_flag"] = False
    labels["demand_observation_risk_cell"] = "NEITHER"
    daily = d.loc[d.fold_id.eq(4)]
    result = apply_policy(daily, labels, scale, table, scenarios)
    assert result.safety_stock.tolist() == pytest.approx([5., 3., 6.])  # BASE, LEAN, PROTECTED
    np.testing.assert_allclose(result.reorder_point, result.lead_time_forecast + result.safety_stock)
    labels["censoring_risk_flag"] = True
    labels["persistent_underforecast_flag"] = True
    labels["demand_observation_risk_cell"] = "CENSORING_AND_UNDERFORECAST"
    changed = apply_policy(daily, labels, scale, table, scenarios)
    for col in ["empirical_multiplier", "safety_stock", "reorder_point"]:
        np.testing.assert_array_equal(result[col], changed[col])
    daily = daily.assign(forecast=0.)
    assert apply_policy(daily, labels, scale, table, scenarios).buffer_to_forecast_ratio.isna().all()


def test_dependence_excludes_fold4_and_does_not_cross_fold_boundaries():
    d, _ = synthetic()
    scale = historical_scale(d)
    result = dependence_diagnostics(d, scale)
    assert result.loc[result.diagnostic.eq("within_fold_lag_correlation"), "n"].tolist() == [18, 15, 12, 9, 6, 3]
    d.loc[d.fold_id.eq(4), "error"] = 99999.
    assert_frame_equal(result, dependence_diagnostics(d, scale))


def test_population_grain_identities_prospective_labels_and_final_scale():
    frame = pd.read_parquet(ROOT / "data/processed/mart_replenishment_simulation.parquet")
    assert_simulation(frame)
    assert frame.simulation.all() and frame.source_split_calibration.eq("train").all()
    assert not {"actual", "order_quantity", "inventory_position", "purchase_quantity"}.intersection(frame.columns)
    uncertainty = pd.read_parquet(ROOT / INPUTS["uncertainty"], columns=KEYS + ["error_std"])
    merged = frame.merge(uncertainty, on=KEYS, validate="many_to_one")
    np.testing.assert_array_equal(merged.historical_error_std, merged.error_std)
    np.testing.assert_allclose(frame.safety_stock, frame.empirical_multiplier * frame.historical_error_std * np.sqrt(frame.lead_time_days))
    assert frame.calibration_n.ge(frame.target_coverage_level.map(minimum_n)).all()
    assert frame.groupby("scenario").size().to_dict() == {"BASE": 50000, "LEAN": 50000, "PROTECTED": 50000}
    cal = pd.read_parquet(ROOT / "data/processed/mart_replenishment_calibration.parquet")
    assert cal.loc[cal.stage.eq("calibration_folds1234"), "fold4_observed_coverage"].isna().all()
    validation = pd.read_parquet(ROOT / FOLDER / "fold4_validation.parquet")
    labels = pd.read_parquet(ROOT / INPUTS["segments"], filters=[("fold_id", "=", 4)])
    merged = validation.merge(labels[KEYS + DIMS], on=KEYS, suffixes=("", "_check"), validate="many_to_one")
    for col in DIMS:
        np.testing.assert_array_equal(merged[col], merged[col + "_check"])


def test_population_reproducible_without_eval_and_invariant_to_changed_eval(tmp_path, monkeypatch):
    """Two full 150k-row runs with absent then poisoned eval; no fitting possible."""
    for relative in [*INPUTS.values(), *METADATA, CONFIG, PROTOCOL]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    # Fail if any reader even tries accessing raw or an evaluated holdout mart.
    original = pd.read_parquet
    def guarded(path, *args, **kwargs):
        relative = Path(path).relative_to(tmp_path).as_posix()
        assert relative in INPUTS.values(), f"Unauthorized input: {relative}"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", guarded)
    expected = json.loads((ROOT / FOLDER / "summary.json").read_text(encoding="utf-8"))
    first = build_simulation(tmp_path)
    assert first == expected
    raw = tmp_path / "data/raw"
    raw.mkdir()
    (raw / "eval.parquet").write_bytes(b"POISONED EVAL ACTUALS MUST NEVER BE OPENED")
    for name in ["mart_holdout_forecast", "mart_holdout_series_evaluation", "mart_holdout_model_comparison"]:
        (tmp_path / "data/processed" / f"{name}.parquet").write_bytes(b"POISONED EVALUATED HOLDOUT")
    second = build_simulation(tmp_path)
    assert second == first
    for artifact in expected["artifacts"].values():
        assert sha256_file(tmp_path / artifact["path"]) == artifact["sha256"]


def test_frozen_inputs_still_match_pre_holdout_manifest():
    records = verify_inputs(ROOT)
    assert len(records) == 6
