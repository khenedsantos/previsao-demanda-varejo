"""Reproduce Phase 8 from an explicit allowlist of frozen, non-eval inputs."""

import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from src.forecasting.backtesting import export_frame, peak_working_set_bytes
from src.ingestion.source_manifest import ROOT, sha256_file
from src.validation.replenishment import (
    KEYS, DIMS, HIERARCHY, historical_scale, calibrate, apply_policy,
    dependence_diagnostics, aggregate_policy, validate_scale,
)

HEAD = "3c52827a140e484d4b4257682bb944f2bb4eb6ae"
FOLDER = Path("data/outputs/replenishment_simulation")
CONFIG = "config/replenishment_scenarios.yaml"
PROTOCOL = "docs/replenishment_simulation_protocol.md"
INPUTS = {
    "backtest": "data/processed/mart_forecast_statistical.parquet",
    "segments": "data/outputs/forecasting_baselines/fold_segments.parquet",
    "uncertainty": "data/processed/mart_forecast_uncertainty.parquet",
    "risk_profile": "data/processed/mart_demand_risk_profile.parquet",
    "examples": "data/outputs/forecast_uncertainty/example_selection.parquet",
    "predictions": "data/outputs/final_holdout/frozen_predictions.parquet",
}
METADATA = ["data/outputs/final_holdout/protocol.json",
            "data/outputs/final_holdout/population_performance.json"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def scenarios_from_config(root):
    config = yaml.safe_load((root / CONFIG).read_text(encoding="utf-8"))
    expected = {"lean": (1, .90), "base": (2, .95), "protected": (3, .98)}
    if config.get("simulation") is not True or set(config["scenarios"]) != set(expected):
        raise ValueError("Frozen hypothetical scenarios required.")
    result = []
    for name, (days, q) in expected.items():
        actual = config["scenarios"][name]
        if actual["lead_time_days"] != days or actual["service_level"] != q:
            raise ValueError("Scenario values cannot change.")
        result.append({"scenario": name.upper(), "lead_time_days": days, "target_coverage_level": q})
    return result


def verify_inputs(root):
    """Never discovers arbitrary files or opens raw/holdout-actual tables."""
    protocol = read_json(root / METADATA[0])
    performance = read_json(root / METADATA[1])
    if performance.get("eval_not_opened") is not True:
        raise ValueError("Planning forecasts must have been frozen before eval.")
    expected = {**protocol["protected_artifacts"], INPUTS["predictions"]: performance["prediction_sha256"]}
    records = {}
    for name, relative in INPUTS.items():
        path = root / relative
        digest = sha256_file(path)
        if digest != expected[relative]:
            raise ValueError(f"Frozen input modified: {name}")
        records[name] = {"path": relative, "sha256": digest, "bytes": path.stat().st_size,
                         "rows": pq.read_metadata(path).num_rows}
    schema = pq.read_schema(root / INPUTS["predictions"])
    if "actual" in schema.names or "error" in schema.names:
        raise ValueError("Planning snapshot cannot contain actuals/errors.")
    return records


def load_inputs(root):
    records = verify_inputs(root)
    frames = {
        "backtest": pd.read_parquet(root / INPUTS["backtest"], columns=KEYS + ["fold_id", "horizon_step", "forecast", "actual", "error", "target_date", "model"]),
        "segments": pd.read_parquet(root / INPUTS["segments"], columns=KEYS + ["fold_id", "cutoff_date", "source_split"] + DIMS),
        "uncertainty": pd.read_parquet(root / INPUTS["uncertainty"], columns=KEYS + ["error_std", "as_of", "source_split"]),
        "risk_profile": pd.read_parquet(root / INPUTS["risk_profile"], columns=KEYS + DIMS + ["as_of", "available_from", "censoring_risk_flag", "persistent_underforecast_flag", "demand_observation_risk_cell"]),
        "predictions": pd.read_parquet(root / INPUTS["predictions"], filters=[("model", "=", "ets_ana")], columns=KEYS + ["horizon_step", "forecast", "dt", "cutoff_date", "model"]),
        "examples": pd.read_parquet(root / INPUTS["examples"]),
    }
    b, s, u, p, r = [frames[k] for k in ["backtest", "segments", "uncertainty", "predictions", "risk_profile"]]
    if (len(b), len(s), len(u), len(p), len(r)) != (1400000, 200000, 50000, 350000, 50000):
        raise ValueError("Incomplete frozen population.")
    for frame, keys in [(b, KEYS + ["fold_id", "horizon_step"]), (s, KEYS + ["fold_id"]),
                        (p, KEYS + ["horizon_step"]), (u, KEYS), (r, KEYS)]:
        if frame.duplicated(keys).any() or len(frame[KEYS].drop_duplicates()) != 50000:
            raise ValueError("Invalid frozen grain.")
    if not b.model.eq("ets_ana").all() or not np.allclose(b.error, b.forecast - b.actual, atol=1e-12, rtol=0):
        raise ValueError("Wrong model/error convention.")
    if not np.isfinite(b[["actual", "forecast", "error"]]).all().all() or (b[["actual", "forecast"]] < 0).any().any():
        raise ValueError("Invalid backtest values.")
    expected_date = pd.Timestamp("2024-05-29") + pd.to_timedelta((b.fold_id - 1) * 7 + b.horizon_step - 1, unit="D")
    if not pd.to_datetime(b.target_date).eq(expected_date).all() or not b.fold_id.isin([1, 2, 3, 4]).all() or not b.horizon_step.between(1, 7).all():
        raise ValueError("Only the four train folds are allowed.")
    expected_cutoff = pd.Timestamp("2024-05-28") + pd.to_timedelta((s.fold_id - 1) * 7, unit="D")
    if not s.source_split.eq("train").all() or not pd.to_datetime(s.cutoff_date).eq(expected_cutoff).all():
        raise ValueError("Segmentation must be prospective per fold.")
    if not u.source_split.eq("train").all() or not pd.to_datetime(u.as_of).eq(pd.Timestamp("2024-06-25")).all():
        raise ValueError("Historical uncertainty must be frozen at 25/06.")
    if not pd.to_datetime(p.dt).eq(pd.Timestamp("2024-06-26") + pd.to_timedelta(p.horizon_step - 1, unit="D")).all() or not pd.to_datetime(p.cutoff_date).eq(pd.Timestamp("2024-06-25")).all():
        raise ValueError("Wrong planning horizon.")
    if not np.isfinite(p.forecast).all() or p.forecast.lt(0).any() or not p.horizon_step.between(1, 7).all():
        raise ValueError("Invalid frozen planning forecasts.")
    if not pd.to_datetime(r.as_of).eq(pd.Timestamp("2024-06-25")).all() or not pd.to_datetime(r.available_from).eq(pd.Timestamp("2024-06-26")).all():
        raise ValueError("Final labels must precede planning horizon.")
    return frames, records


def calibration_audit(table, applications, stage):
    keys = ["scenario", "calibration_level_used", "calibration_key"]
    aggregates = applications.groupby(keys, as_index=False).agg(applied_n_series=("store_id", "size"))
    result = table.merge(aggregates, on=keys, how="left", validate="one_to_one")
    result["applied_n_series"] = result.applied_n_series.fillna(0).astype("int64")
    result["stage"] = stage
    result["fallback_status"] = np.where(result.applied_n_series.eq(0), "NOT_USED",
        np.where(result.calibration_level_used.eq("ABC_XYZ_EXPOSURE"), "PRIMARY", "FALLBACK"))
    if "covered" in applications:
        metrics = applications.groupby(keys, as_index=False).agg(fold4_observed_coverage=("covered", "mean"),
            fold4_normal_coverage=("normal_covered", "mean"))
        result = result.merge(metrics, on=keys, how="left", validate="one_to_one")
    else:
        result["fold4_observed_coverage"] = np.nan
        result["fold4_normal_coverage"] = np.nan
    result["coverage_gap"] = result.fold4_observed_coverage - result.target_coverage_level
    return result


def assert_simulation(frame):
    if len(frame) != 150000 or frame.duplicated(KEYS + ["scenario"]).any() or not frame.groupby("scenario").size().eq(50000).all():
        raise ValueError("Simulation must have 50,000 unique series per scenario.")
    values = frame[["lead_time_forecast", "safety_stock", "reorder_point"]]
    if not np.isfinite(values).all().all() or values.lt(0).any().any():
        raise ValueError("Invalid simulation amounts.")
    np.testing.assert_allclose(frame.reorder_point, frame.lead_time_forecast + frame.safety_stock, rtol=0, atol=1e-12)
    if frame.reorder_point.lt(frame.lead_time_forecast).any() or "order_quantity" in frame:
        raise ValueError("Invalid simulated threshold contract.")


def build_simulation(root=ROOT):
    # An accidental future fitting call must stop before any optimizer runs.
    with patch("statsmodels.tsa.holtwinters.ExponentialSmoothing.fit",
               side_effect=RuntimeError("STOP: ETS fitting is forbidden in Phase 8")):
        return _build_simulation(root)


def _build_simulation(root):
    started = perf_counter()
    scenarios = scenarios_from_config(root)
    inputs, records = load_inputs(root)
    b, s = inputs["backtest"], inputs["segments"]
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    artifacts = {}

    def save(name, frame, main=False):
        relative = Path("data/processed") / f"mart_replenishment_{name}.parquet" if main else FOLDER / f"{name}.parquet"
        export_frame(frame, root / relative)
        artifacts[name] = {"path": relative.as_posix(), "rows": len(frame), "sha256": sha256_file(root / relative),
                           "bytes": (root / relative).stat().st_size}

    scale3 = historical_scale(b)
    diagnostics = dependence_diagnostics(b, scale3)
    save("dependence", diagnostics)
    print("Dependence assessed using folds 1-3 only; freezing calibration before fold 4.", flush=True)
    table3, shortfalls3 = calibrate(b, s, scale3, scenarios, (1, 2, 3))
    save("validation_scale", scale3)
    save("calibration_folds123", table3)
    # Persist the method and calibration before policy performance is computed.
    locked = {"starting_head": HEAD, "protocol_sha256": sha256_file(root / PROTOCOL),
        "config_sha256": sha256_file(root / CONFIG), "calibration_sha256": artifacts["calibration_folds123"]["sha256"],
        "scale_sha256": artifacts["validation_scale"]["sha256"], "calibration_folds": [1, 2, 3], "validation_fold": 4,
        "hierarchy": [level for level, _ in HIERARCHY], "quantile_interpolation": "linear",
        "minimum_tail_observations": 20, "invalid_scale_policy": "BLOCK", "no_performance_selection": True}
    write_json(folder / "calibration_locked.json", locked)
    validation = apply_policy(b.loc[b.fold_id.eq(4)], s.loc[s.fold_id.eq(4), KEYS + DIMS], scale3, table3, scenarios)
    save("fold4_validation", validation)
    validation_summary = aggregate_policy(validation, "validation_fold4")
    print(validation_summary.loc[validation_summary.level.eq("global"), ["scenario", "observed_coverage_rate", "coverage_gap", "normal_coverage_rate"]].to_string(index=False), flush=True)

    # Same predeclared method, all train folds now known on 25/06.
    scale4 = inputs["uncertainty"][KEYS + ["error_std"]].rename(columns={"error_std": "historical_error_std"})
    recomputed = historical_scale(b, (1, 2, 3, 4))
    check = scale4.merge(recomputed, on=KEYS, validate="one_to_one", suffixes=("", "_check"))
    np.testing.assert_allclose(check.historical_error_std, check.historical_error_std_check, rtol=1e-11, atol=1e-12)
    table4, shortfalls4 = calibrate(b, s, scale4, scenarios, (1, 2, 3, 4))
    simulation = apply_policy(inputs["predictions"], inputs["risk_profile"], scale4, table4, scenarios)
    average = inputs["predictions"].groupby(KEYS, as_index=False).forecast.mean().rename(columns={"forecast": "forecast_daily_average"})
    simulation = simulation.merge(average, on=KEYS, validate="many_to_one")
    simulation["equivalent_coverage_days"] = simulation.reorder_point / simulation.forecast_daily_average.where(simulation.forecast_daily_average.gt(0))
    simulation["source_split_calibration"] = "train"
    simulation["simulation"] = True
    assert_simulation(simulation)
    save("simulation", simulation, main=True)
    calibration = pd.concat([calibration_audit(table3, validation, "calibration_folds123"),
                             calibration_audit(table4, simulation, "calibration_folds1234")], ignore_index=True)
    save("calibration", calibration, main=True)
    final_summary = aggregate_policy(simulation, "final_snapshot")
    summary_frame = pd.concat([validation_summary, final_summary], ignore_index=True)
    # Separate validation metrics joined by level/cell for convenience, never final in-sample coverage.
    coverage = validation_summary[["scenario", "level", "cell", "observed_coverage_rate"]].rename(
        columns={"observed_coverage_rate": "historical_fold4_coverage"})
    summary_frame = summary_frame.merge(coverage, on=["scenario", "level", "cell"], how="left", validate="many_to_one")
    save("summary", summary_frame, main=True)
    save("examples", inputs["examples"][[*KEYS, "selection_rule"]].merge(simulation, on=KEYS, validate="one_to_many"))
    bias = pd.concat([shortfalls3.assign(stage="calibration_folds123"), shortfalls4.assign(stage="calibration_folds1234")])
    save("lead_time_diagnostics", bias.groupby(["stage", "scenario", "fold_id"], as_index=False).agg(
        n_observations=("store_id", "size"), mean_lead_time_error=("lead_time_error", "mean"),
        mean_shortfall=("lead_time_shortfall", "mean"), mean_standardized_shortfall=("standardized_shortfall", "mean")))
    fallback = pd.concat([validation.assign(stage="validation_fold4"), simulation.assign(stage="final_snapshot")])
    save("fallback_distribution", fallback.groupby(["stage", "scenario", "calibration_level_used"], as_index=False).agg(n_series=("store_id", "size")))
    top = simulation.loc[simulation.abc_class.eq("A")].sort_values(
        ["scenario", "safety_stock", *KEYS], ascending=[True, False, True, True]).groupby("scenario", sort=True).head(10)
    save("top_a_buffers", top.assign(selection_rule="TOP10_A_SAFETY_STOCK_THEN_IDS"))
    if verify_inputs(root) != records:
        raise ValueError("Upstream inputs changed during simulation.")
    summary = {"starting_head": HEAD, "simulation": True, "n_ets_fits": 0, "eval_actuals_read": False,
        "n_series": 50000, "n_rows": len(simulation), "as_of": "2024-06-25", "available_from": "2024-06-26",
        "scenarios": scenarios, "formula": "SS=empirical_quantile(shortfall/(std*sqrt(L)))*std*sqrt(L); ROP=sum(forecast[:L])+SS",
        "flags_affect_formula": False, "target_interpretation": "historical observed normalized sales error distribution coverage",
        "inputs": records, "config": {"path": CONFIG, "sha256": sha256_file(root / CONFIG)}, "protocol": locked,
        "metadata_hashes": {path: sha256_file(root / path) for path in METADATA},
        "artifacts": artifacts, "invalid_scale_series": 0,
        "method_selection": "EMPIRICAL_PREDECLARED", "normal_reference_only": True}
    write_json(folder / "summary.json", summary)
    performance = {"elapsed_seconds": perf_counter() - started, "peak_working_set_bytes": peak_working_set_bytes(),
                   "parquet_bytes": sum(a["bytes"] for a in artifacts.values()), "n_ets_fits": 0}
    write_json(folder / "performance.json", performance)
    print(json.dumps(performance), flush=True)
    return summary
