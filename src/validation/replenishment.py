"""Fixed empirical policy calibration using historical train errors only.

This module never reads files or fits forecasting models. Flags are not inputs
to calibration or buffer formulas. Invalid scales fail closed.
"""

from decimal import Decimal, ROUND_CEILING
from statistics import NormalDist

import numpy as np
import pandas as pd

KEYS = ["store_id", "product_id"]
DIMS = ["abc_class", "xyz_class", "stockout_exposure"]
HIERARCHY = [("ABC_XYZ_EXPOSURE", DIMS), ("ABC_XYZ", DIMS[:2]),
             ("XYZ", ["xyz_class"]), ("GLOBAL", [])]


def minimum_n(q):
    return int((Decimal(20) / (1 - Decimal(str(q)))).to_integral_value(rounding=ROUND_CEILING))


def historical_scale(errors, folds=(1, 2, 3)):
    selected = errors.loc[errors.fold_id.isin(folds)]
    result = selected.groupby(KEYS, sort=True).error.agg(
        historical_error_std="std", historical_bias="mean", n_errors="size").reset_index()
    if not result.n_errors.eq(7 * len(folds)).all():
        raise ValueError("Historical scale requires seven errors per series/fold.")
    validate_scale(result.historical_error_std)
    return result


def validate_scale(scale):
    if not np.isfinite(scale).all() or (np.asarray(scale) <= 0).any():
        raise ValueError("Invalid historical error scale; no silent substitution or exclusion.")


def lead_time_values(daily, lead_time_days):
    if lead_time_days not in (1, 2, 3):
        raise ValueError("Only the three frozen lead times are authorized.")
    keys = KEYS + (["fold_id"] if "fold_id" in daily else [])
    selected = daily.loc[daily.horizon_step.le(lead_time_days)]
    if selected.duplicated(keys + ["horizon_step"]).any():
        raise ValueError("Duplicate daily forecast.")
    grouped = selected.groupby(keys, sort=True)
    if not grouped.size().eq(lead_time_days).all():
        raise ValueError("Incomplete lead-time window.")
    result = grouped.forecast.sum().rename("lead_time_forecast").to_frame()
    if "actual" in daily:
        result["lead_time_actual"] = grouped.actual.sum()
        result["lead_time_error"] = result.lead_time_forecast - result.lead_time_actual
        result["lead_time_shortfall"] = (-result.lead_time_error).clip(lower=0)
    return result.reset_index()


def cell_key(frame, dimensions):
    if not dimensions:
        return pd.Series("ALL", index=frame.index)
    if frame[dimensions].isna().any().any():
        raise ValueError("Missing prospective segmentation.")
    result = frame[dimensions[0]].astype(str)
    for column in dimensions[1:]:
        result = result.str.cat(frame[column].astype(str), sep="|")
    return result


def calibrate(daily, segments, scale, scenarios, folds):
    """The caller explicitly declares available folds; no performance selection."""
    validate_scale(scale.historical_error_std)
    observations, tables = [], []
    selected = daily.loc[daily.fold_id.isin(folds)]
    labels = segments.loc[segments.fold_id.isin(folds), KEYS + ["fold_id"] + DIMS]
    for scenario in scenarios:
        lt = lead_time_values(selected, scenario["lead_time_days"])
        lt = lt.merge(scale, on=KEYS, how="left", validate="many_to_one")
        lt = lt.merge(labels, on=KEYS + ["fold_id"], how="left", validate="one_to_one")
        validate_scale(lt.historical_error_std)
        lt["standardized_shortfall"] = lt.lead_time_shortfall / (
            lt.historical_error_std * np.sqrt(scenario["lead_time_days"]))
        lt["scenario"] = scenario["scenario"]
        observations.append(lt)
        q = scenario["target_coverage_level"]
        for level, dimensions in HIERARCHY:
            lt["calibration_key"] = cell_key(lt, dimensions)
            for key, group in lt.groupby("calibration_key", sort=True):
                n = len(group)
                tables.append({**scenario, "calibration_level_used": level,
                    "calibration_key": key, "calibration_n": n,
                    "calibration_n_series": len(group[KEYS].drop_duplicates()),
                    "minimum_n": minimum_n(q), "eligible": n >= minimum_n(q),
                    "empirical_multiplier": group.standardized_shortfall.quantile(q, interpolation="linear"),
                    "theoretical_normal_z": NormalDist().inv_cdf(q)})
    return pd.DataFrame(tables), pd.concat(observations, ignore_index=True)


def choose_calibration(labels, table):
    """Most specific eligible cell; never inspect validation outcomes."""
    result = labels.copy().reset_index(drop=True)
    result["calibration_level_used"] = pd.Series([None] * len(result), dtype=object)
    result["calibration_key"] = pd.Series([None] * len(result), dtype=object)
    for col in ["calibration_n", "calibration_n_series", "empirical_multiplier", "theoretical_normal_z"]:
        result[col] = np.nan
    for level, dimensions in HIERARCHY:
        available = table.loc[table.calibration_level_used.eq(level) & table.eligible].set_index("calibration_key")
        keys = cell_key(result, dimensions)
        use = result.calibration_level_used.isna() & keys.isin(available.index)
        result.loc[use, "calibration_level_used"] = level
        result.loc[use, "calibration_key"] = keys[use]
        for col in ["calibration_n", "calibration_n_series", "empirical_multiplier", "theoretical_normal_z"]:
            result.loc[use, col] = keys[use].map(available[col])
    if result.calibration_level_used.isna().any():
        raise ValueError("Insufficient GLOBAL calibration support.")
    for col in ["calibration_n", "calibration_n_series"]:
        result[col] = result[col].astype("int64")
    result["calibration_fallback_flag"] = result.calibration_level_used.ne("ABC_XYZ_EXPOSURE")
    return result


def apply_policy(daily, labels, scale, table, scenarios):
    pieces = []
    for scenario in scenarios:
        name, days = scenario["scenario"], scenario["lead_time_days"]
        assigned = choose_calibration(labels, table.loc[table.scenario.eq(name)])
        result = lead_time_values(daily, days).merge(assigned, on=KEYS, how="left", validate="one_to_one")
        result = result.merge(scale, on=KEYS, how="left", validate="one_to_one")
        validate_scale(result.historical_error_std)
        if result.empirical_multiplier.isna().any():
            raise ValueError("Missing policy assignment.")
        for key, value in scenario.items():
            result[key] = value
        reference = result.historical_error_std * np.sqrt(days)
        result["safety_stock"] = result.empirical_multiplier * reference
        result["normal_safety_stock"] = result.theoretical_normal_z * reference
        result["reorder_point"] = result.lead_time_forecast + result.safety_stock
        result["normal_reorder_point"] = result.lead_time_forecast + result.normal_safety_stock
        result["buffer_to_forecast_ratio"] = result.safety_stock / result.lead_time_forecast.where(result.lead_time_forecast.gt(0))
        if "lead_time_actual" in result:
            result["covered"] = result.reorder_point.ge(result.lead_time_actual)
            result["normal_covered"] = result.normal_reorder_point.ge(result.lead_time_actual)
        pieces.append(result)
    return pd.concat(pieces, ignore_index=True).sort_values(KEYS + ["scenario"]).reset_index(drop=True)


def dependence_diagnostics(daily, scale):
    """Only calibration folds 1–3; pairs never bridge folds or series."""
    sample = daily.loc[daily.fold_id.isin([1, 2, 3])].merge(scale, on=KEYS, validate="many_to_one")
    sample["standardized_error"] = (sample.error - sample.historical_bias) / sample.historical_error_std
    matrix = sample.pivot(index=KEYS + ["fold_id"], columns="horizon_step", values="standardized_error").to_numpy()
    rows = []
    for lag in range(1, 7):
        a, b = matrix[:, :-lag].ravel(), matrix[:, lag:].ravel()
        correlation = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else np.nan
        rows.append({"diagnostic": "within_fold_lag_correlation", "step": lag, "n": len(a),
                     "value": correlation})
    for days in (1, 2, 3):
        part = matrix[:, :days]
        denominator = np.var(part, axis=0, ddof=1).sum()
        ratio = np.var(part.sum(axis=1), ddof=1) / denominator if denominator > 0 else np.nan
        rows.append({"diagnostic": "variance_aggregation_ratio", "step": days, "n": len(part), "value": ratio})
    return pd.DataFrame(rows)


def aggregate_policy(frame, stage):
    """Compact levels: filter level before summing; overlays are overlapping subsets."""
    rows = []
    definitions = [("global", []), ("ABC", ["abc_class"]), ("XYZ", ["xyz_class"]),
                   ("exposure", ["stockout_exposure"]), ("ABC_XYZ", DIMS[:2])]
    if "demand_observation_risk_cell" in frame:
        definitions += [("risk_cell", ["demand_observation_risk_cell"])]
    for scenario, population in frame.groupby("scenario", sort=True):
        groups = []
        for level, dims in definitions:
            groups.extend((level, cell, group) for cell, group in population.groupby(cell_key(population, dims), sort=True))
        if "demand_observation_risk_cell" in frame:
            groups.append(("A_double_signal", "A|CENSORING_AND_UNDERFORECAST", population.loc[
                population.abc_class.eq("A") & population.demand_observation_risk_cell.eq("CENSORING_AND_UNDERFORECAST")]))
        for level, cell, group in groups:
            if group.empty:
                continue
            forecast, buffer = group.lead_time_forecast.sum(), group.safety_stock.sum()
            row = {"stage": stage, "scenario": scenario, "level": level, "cell": cell, "n_series": len(group),
                "lead_time_days": int(group.lead_time_days.iloc[0]), "target_coverage_level": group.target_coverage_level.iloc[0],
                "forecast_demand": forecast, "total_safety_stock": buffer, "total_reorder_point": group.reorder_point.sum(),
                "mean_lead_time_forecast": group.lead_time_forecast.mean(),
                "mean_safety_stock": group.safety_stock.mean(), "median_safety_stock": group.safety_stock.median(),
                "p90_safety_stock": group.safety_stock.quantile(.9), "mean_reorder_point": group.reorder_point.mean(),
                "median_reorder_point": group.reorder_point.median(),
                "buffer_to_forecast_ratio": buffer / forecast if forecast > 0 else np.nan,
                "median_buffer_ratio": group.buffer_to_forecast_ratio.median(),
                "undefined_ratio_series": int(group.buffer_to_forecast_ratio.isna().sum()),
                "buffer_above_forecast_rate": group.safety_stock.gt(group.lead_time_forecast).mean(),
                "fallback_rate": group.calibration_fallback_flag.mean(),
                "mean_empirical_multiplier": group.empirical_multiplier.mean(),
                "mean_normal_safety_stock": group.normal_safety_stock.mean(),
                "mean_normal_reorder_point": group.normal_reorder_point.mean(),
                "observed_coverage_rate": group.covered.mean() if "covered" in group else np.nan,
                "normal_coverage_rate": group.normal_covered.mean() if "covered" in group else np.nan,
                "mean_lead_time_error": group.lead_time_error.mean() if "lead_time_error" in group else np.nan,
                "buffer_share": buffer / population.safety_stock.sum()}
            row["coverage_gap"] = row["observed_coverage_rate"] - row["target_coverage_level"]
            row["normal_coverage_gap"] = row["normal_coverage_rate"] - row["target_coverage_level"]
            for flag in ["censoring_risk_flag", "persistent_underforecast_flag"]:
                row[f"{flag}_share"] = group[flag].mean() if flag in group else np.nan
            row["double_signal_share"] = group.demand_observation_risk_cell.eq("CENSORING_AND_UNDERFORECAST").mean() if "demand_observation_risk_cell" in group else np.nan
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["stage", "scenario", "level", "cell"]).reset_index(drop=True)
