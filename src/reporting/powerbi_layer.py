"""Small BI export from frozen marts. No model fitting or analytical decisions."""

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pyarrow.parquet as pq

from src.ingestion.source_manifest import ROOT, sha256_file
from src.reporting.powerbi_contract import (
    STARTING_HEAD, KEYS, ATTRIBUTES, MODEL_NAMES, SCENARIOS, NULLABLE,
    SCHEMAS, TABLES, RELATIONSHIPS,
)

SUMMARY_PATHS = {
    "holdout": "data/outputs/final_holdout/summary.json",
    "replenishment": "data/outputs/replenishment_simulation/summary.json",
}
SOURCES = {
    "forecast": ("holdout", "forecasts", "data/processed/mart_holdout_forecast.parquet", 700000),
    "forecast_reference": ("holdout", "model_comparison", "data/processed/mart_holdout_model_comparison.parquet", 56),
    "replenishment": ("replenishment", "simulation", "data/processed/mart_replenishment_simulation.parquet", 150000),
    "scenario_summary": ("replenishment", "summary", "data/processed/mart_replenishment_summary.parquet", 129),
}
DATA_DIR = Path("powerbi/data")
MANIFEST_PATH = Path("powerbi/data_manifest.json")
DICTIONARY_PATH = Path("powerbi/data_dictionary.csv")
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]
WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_sources(root):
    """Fixed paths only: raw, staging and calibration auxiliaries are never inputs."""
    summaries = {label: read_json(root / path) for label, path in SUMMARY_PATHS.items()}
    if summaries["replenishment"].get("starting_head") != "3c52827a140e484d4b4257682bb944f2bb4eb6ae":
        raise ValueError("Unexpected frozen Phase 8 lineage.")
    records = {}
    for label, (owner, artifact, relative, rows) in SOURCES.items():
        item = summaries[owner]["artifacts"][artifact]
        path = root / relative
        if item["path"] != relative or item["rows"] != rows or pq.read_metadata(path).num_rows != rows:
            raise ValueError(f"Source contract mismatch: {label}")
        digest = sha256_file(path)
        if digest != item["sha256"]:
            raise ValueError(f"Frozen source modified: {label}")
        records[label] = {"path": relative, "rows": rows, "sha256": digest,
                          "bytes": path.stat().st_size,
                          "role": "validation_only" if label == "forecast_reference" else "export_source"}
    return records


def load_sources(root):
    records = verify_sources(root)
    frames = {label: pd.read_parquet(root / record["path"]) for label, record in records.items()}
    return frames, records


def make_dim_series(replenishment):
    result = replenishment[KEYS + ATTRIBUTES].drop_duplicates()
    if result.duplicated(KEYS).any() or result.isna().any().any():
        raise ValueError("Series attributes must be non-null and invariant across scenarios.")
    result = result.sort_values(KEYS, kind="stable").reset_index(drop=True)
    result.insert(0, "series_key", np.arange(1, len(result) + 1, dtype="int64"))
    return result


def make_dim_date(dates):
    dates = pd.to_datetime(dates)
    calendar = pd.Series(pd.date_range(dates.min(), dates.max(), freq="D"))
    return pd.DataFrame({
        "date": calendar.dt.date, "year": calendar.dt.year,
        "month_number": calendar.dt.month, "month_name": calendar.dt.month.map(dict(enumerate(MONTHS, 1))),
        "year_month": calendar.dt.strftime("%Y-%m"), "day": calendar.dt.day,
        "day_of_week_number": calendar.dt.dayofweek + 1,
        "day_of_week_name": calendar.dt.dayofweek.map(dict(enumerate(WEEKDAYS))),
        "is_weekend": calendar.dt.dayofweek.ge(5), "date_sort": calendar.dt.strftime("%Y%m%d").astype("int64"),
    })


def make_dim_scenario(replenishment):
    result = replenishment[["scenario", "lead_time_days", "target_coverage_level"]].drop_duplicates()
    if result.scenario.duplicated().any() or set(result.scenario) != set(SCENARIOS):
        raise ValueError("Exactly three consistent frozen scenarios required.")
    result["scenario_order"] = result.scenario.map({s: i for i, s in enumerate(SCENARIOS, 1)})
    result = result.sort_values("scenario_order").reset_index(drop=True)
    if result.lead_time_days.tolist() != [1, 2, 3] or result.target_coverage_level.tolist() != [.9, .95, .98]:
        raise ValueError("Frozen scenario assumptions changed.")
    result["scenario_description"] = [
        f"{int(days)} {'dia' if days == 1 else 'dias'} / target hipotético {q:.0%}; simulação, não serviço real"
        for days, q in zip(result.lead_time_days, result.target_coverage_level)
    ]
    return result


def attach_series(frame, dimension):
    result = frame.merge(dimension[KEYS + ["series_key"]], on=KEYS, how="left", validate="many_to_one")
    if result.series_key.isna().any():
        raise ValueError("Orphan natural series key.")
    return result


def normalize_table(name, frame):
    columns = [column for column, *_ in SCHEMAS[name]]
    result = frame[columns].copy()
    for column, dtype, *_ in SCHEMAS[name]:
        values = result[column]
        nullable = (name, column) in NULLABLE
        if values.isna().any() and not nullable:
            raise ValueError(f"Null prohibited: {name}.{column}")
        if dtype == "integer":
            numeric = pd.to_numeric(values, errors="raise")
            if not np.isfinite(numeric).all() or not numeric.eq(np.floor(numeric)).all():
                raise ValueError(f"Non-integer values: {name}.{column}")
            result[column] = numeric.astype("int64")
        elif dtype == "decimal":
            result[column] = pd.to_numeric(values, errors="raise").astype("float64")
            if not np.isfinite(result[column].dropna()).all():
                raise ValueError(f"Non-finite decimal: {name}.{column}")
        elif dtype == "boolean":
            if not pd.api.types.is_bool_dtype(values):
                raise ValueError(f"Explicit boolean type required: {name}.{column}")
            result[column] = values.astype(bool)
        elif dtype == "date":
            if not values.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                raise ValueError(f"ISO date without time required: {name}.{column}")
            result[column] = pd.to_datetime(values, errors="raise").dt.date
        else:
            result[column] = values.astype("str")
            if result[column].eq("").any():
                raise ValueError(f"Empty text prohibited: {name}.{column}")
    return result


def create_tables(sources):
    replenishment, forecast = sources["replenishment"], sources["forecast"]
    series = make_dim_series(replenishment)
    scenario = make_dim_scenario(replenishment)
    f = attach_series(forecast, series).rename(columns={"dt": "date", "model": "model_code"})
    f["model"] = f.model_code.map(MODEL_NAMES)
    if f.model.isna().any():
        raise ValueError("Unknown frozen model code.")
    r = attach_series(replenishment, series)
    validation = sources["scenario_summary"].loc[lambda x: x.stage.eq("validation_fold4") & x.level.eq("global")].rename(
        columns={"normal_coverage_rate": "normal_reference_coverage", "stage": "validation_stage"})
    tables = {"DimSeries": series, "DimDate": make_dim_date(f.date), "DimScenario": scenario,
              "FactForecast": f, "FactReplenishment": r, "FactScenarioValidation": validation}
    for name, frame in tables.items():
        sort = ["scenario_order"] if name == "DimScenario" else TABLES[name][2]
        tables[name] = normalize_table(name, frame).sort_values(sort, kind="stable").reset_index(drop=True)
    return tables


def validate_tables(tables):
    if set(tables) != set(TABLES):
        raise ValueError("Exactly six BI tables required.")
    for name, frame in tables.items():
        _, rows, pk = TABLES[name]
        if list(frame.columns) != [c[0] for c in SCHEMAS[name]]:
            raise ValueError(f"Unexpected schema: {name}")
        if len(frame) != rows or frame.duplicated(pk).any():
            raise ValueError(f"Row count or primary key violation: {name}")
        assert_frame_equal(frame, normalize_table(name, frame), check_exact=True)
    orphan_keys = {}
    for relation in RELATIONSHIPS:
        dim, fact, col = relation["dimension"], relation["fact"], relation["column"]
        n = int((~tables[fact][col].isin(tables[dim][col])).sum())
        orphan_keys[f"{fact}.{col}->{dim}.{col}"] = n
        if n:
            raise ValueError(f"Orphan foreign key: {fact}.{col}")
    series, dates, scenarios = [tables[name] for name in ["DimSeries", "DimDate", "DimScenario"]]
    if series.duplicated(KEYS).any() or not np.array_equal(series.series_key, np.arange(1, 50001)):
        raise ValueError("Invalid stable series key mapping.")
    if not series[KEYS].equals(series.sort_values(KEYS)[KEYS]):
        raise ValueError("Series keys must follow ordered natural keys.")
    if dates.date.tolist() != pd.date_range("2024-06-26", "2024-07-02").date.tolist():
        raise ValueError("Wrong final forecast date window.")
    assert_frame_equal(dates, normalize_table("DimDate", make_dim_date(dates.date)), check_exact=True)
    f, r, v = [tables[name] for name in ["FactForecast", "FactReplenishment", "FactScenarioValidation"]]
    if f.groupby("model").size().to_dict() != {"ETS": 350000, "Seasonal Naive": 350000}:
        raise ValueError("Wrong model counts.")
    if not f.model.eq(f.model_code.map(MODEL_NAMES)).all():
        raise ValueError("Model name/code mismatch.")
    if r.groupby("scenario").size().to_dict() != {s: 50000 for s in SCENARIOS}:
        raise ValueError("Wrong scenario counts.")
    scenario_check = make_dim_scenario(r)
    assert_frame_equal(scenarios, normalize_table("DimScenario", scenario_check), check_exact=True)
    for fact in [r, v]:
        checked = fact.merge(scenarios, on="scenario", validate="many_to_one", suffixes=("", "_dim"))
        for column in ["target_coverage_level"] + (["lead_time_days"] if "lead_time_days" in fact else []):
            if not checked[column].eq(checked[column + "_dim"]).all():
                raise ValueError("Scenario attributes differ between fact and dimension.")
    if not v.validation_stage.eq("validation_fold4").all() or set(v.scenario) != set(SCENARIOS):
        raise ValueError("Wrong historical validation stage.")
    if not np.allclose(v.coverage_gap, v.observed_coverage_rate - v.target_coverage_level, rtol=0, atol=1e-12):
        raise ValueError("Coverage identity changed.")
    if not v[["observed_coverage_rate", "normal_reference_coverage"]].apply(lambda x: x.between(0, 1)).all().all():
        raise ValueError("Coverage outside [0,1].")
    if not np.allclose(f.error, f.forecast - f.actual, rtol=0, atol=1e-12):
        raise ValueError("Forecast error identity changed.")
    if not np.allclose(f.absolute_error, f.error.abs(), rtol=0, atol=1e-12) or not np.allclose(f.squared_error, f.error**2, rtol=1e-12, atol=1e-12):
        raise ValueError("Frozen error components changed.")
    if f[["actual", "forecast"]].lt(0).any().any() or r[["lead_time_forecast", "safety_stock"]].lt(0).any().any():
        raise ValueError("Negative official forecast/actual/buffer.")
    if not np.allclose(r.reorder_point, r.lead_time_forecast + r.safety_stock, rtol=0, atol=1e-12):
        raise ValueError("Frozen replenishment identity changed.")
    if not r.as_of.eq(pd.Timestamp("2024-06-25").date()).all() or not r.available_from.eq(pd.Timestamp("2024-06-26").date()).all():
        raise ValueError("Wrong replenishment snapshot.")
    # Both models share the same observed outcomes; never sum these copies as distinct sales.
    actuals = f.pivot(index=["date", "series_key"], columns="model", values="actual")
    if not np.array_equal(actuals["ETS"], actuals["Seasonal Naive"]):
        raise ValueError("Actuals differ across models.")
    return orphan_keys


def validate_metrics(tables, sources):
    """Reconcile exported sufficient statistics; never fit/select/recalibrate anything."""
    checks = {"forecast": {}, "replenishment": {}, "scenario_validation": {}}
    reference = sources["forecast_reference"].loc[lambda x: x.level.eq("global")].set_index("model")
    if set(reference.index) != set(MODEL_NAMES) or reference.index.duplicated().any():
        raise ValueError("Incomplete global forecast reference.")
    for code, group in tables["FactForecast"].groupby("model_code", sort=True):
        actual_sum = group.actual.sum()
        metrics = {"mae": group.absolute_error.mean(), "rmse": np.sqrt(group.squared_error.mean()),
                   "wape": group.absolute_error.sum() / actual_sum, "bias": group.error.mean(),
                   "bias_pct": group.error.sum() / actual_sum}
        for metric, value in metrics.items():
            if not np.isclose(value, reference.loc[code, metric], rtol=1e-10, atol=1e-12):
                raise ValueError(f"Forecast metric divergence: {code}.{metric}")
        checks["forecast"][MODEL_NAMES[code]] = {k: float(v) for k, v in metrics.items()}
    final = sources["scenario_summary"].loc[lambda x: x.stage.eq("final_snapshot") & x.level.eq("global")].set_index("scenario")
    for scenario, group in tables["FactReplenishment"].groupby("scenario", sort=True):
        metrics = {"mean_safety_stock": group.safety_stock.mean(), "mean_reorder_point": group.reorder_point.mean()}
        for metric, value in metrics.items():
            if not np.isclose(value, final.loc[scenario, metric], rtol=1e-10, atol=1e-12):
                raise ValueError(f"Replenishment metric divergence: {scenario}.{metric}")
        checks["replenishment"][scenario] = {k: float(v) for k, v in metrics.items()}
    original = sources["scenario_summary"].loc[lambda x: x.stage.eq("validation_fold4") & x.level.eq("global")].set_index("scenario")
    for row in tables["FactScenarioValidation"].itertuples():
        values = {"target_coverage_level": row.target_coverage_level, "observed_coverage_rate": row.observed_coverage_rate,
                  "coverage_gap": row.coverage_gap, "normal_reference_coverage": row.normal_reference_coverage}
        for metric, value in values.items():
            source_metric = "normal_coverage_rate" if metric == "normal_reference_coverage" else metric
            if not np.isclose(value, original.loc[row.scenario, source_metric], rtol=0, atol=1e-12):
                raise ValueError(f"Historical coverage divergence: {row.scenario}.{metric}")
        checks["scenario_validation"][row.scenario] = values
    return checks


def data_dictionary():
    rows = [{"table": name, "column": column, "data_type": dtype, "business_definition": definition,
             "aggregation_behavior": aggregation, "notes": notes}
            for name, schema in SCHEMAS.items() for column, dtype, definition, aggregation, notes in schema]
    return pd.DataFrame(rows)


def write_csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    serial = frame.copy()
    for column in serial:
        if pd.api.types.is_bool_dtype(serial[column]):
            serial[column] = serial[column].map({True: "true", False: "false"})
    serial.to_csv(path, index=False, encoding="utf-8-sig", sep=",", lineterminator="\n",
                  float_format="%.17g", na_rep="")


def read_csv_table(name, path):
    dtypes = {col: {"integer": "int64", "decimal": "float64", "boolean": "boolean"}.get(kind, "str")
              for col, kind, *_ in SCHEMAS[name]}
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=dtypes, float_precision="round_trip",
                        true_values=["true"], false_values=["false"], keep_default_na=False, na_values=[""])
    return normalize_table(name, frame)


def read_exported_tables(root):
    return {name: read_csv_table(name, root / DATA_DIR / spec[0]) for name, spec in TABLES.items()}


def build_powerbi_layer(root=ROOT):
    # The BI path must fail before an accidental optimizer invocation.
    with patch("statsmodels.tsa.holtwinters.ExponentialSmoothing.fit",
               side_effect=RuntimeError("STOP: model fitting is forbidden in Phase 9")):
        return _build_powerbi_layer(Path(root))


def _build_powerbi_layer(root):
    started = perf_counter()
    sources, records = load_sources(root)
    expected = create_tables(sources)
    validate_tables(expected)
    validate_metrics(expected, sources)
    temporary = {}
    for name, (filename, _, _) in TABLES.items():
        path = root / DATA_DIR / (filename + ".tmp")
        write_csv(expected[name], path)
        temporary[name] = path
    reread = {name: read_csv_table(name, path) for name, path in temporary.items()}
    for name in TABLES:
        assert_frame_equal(expected[name], reread[name], check_exact=True)
    orphans = validate_tables(reread)
    checks = validate_metrics(reread, sources)
    if verify_sources(root) != records:
        raise ValueError("Frozen inputs changed during export; do not publish.")
    # Publish only after metric reconciliation and exact CSV round-trip validation.
    artifacts = {}
    for name, (filename, _, pk) in TABLES.items():
        path = root / DATA_DIR / filename
        temporary[name].replace(path)
        artifacts[name] = {"path": (DATA_DIR / filename).as_posix(), "rows": len(reread[name]),
            "primary_key": pk, "sha256": sha256_file(path), "bytes": path.stat().st_size,
            "schema": [{"column": col, "data_type": kind, "nullable": (name, col) in NULLABLE,
                        "null_count": int(reread[name][col].isna().sum())} for col, kind, *_ in SCHEMAS[name]]}
    write_csv(data_dictionary(), root / DICTIONARY_PATH)
    manifest = {"contract_version": 1, "starting_head": STARTING_HEAD,
        "sources": records, "source_manifest_hashes": {p: sha256_file(root / p) for p in SUMMARY_PATHS.values()},
        "csv_format": {"encoding": "UTF-8 with BOM", "delimiter": ",", "decimal_separator": ".", "date_format": "YYYY-MM-DD",
                       "boolean_values": ["true", "false"], "null": "empty field", "line_ending": "LF", "float_format": "17 significant digits"},
        "tables": artifacts, "relationships": RELATIONSHIPS, "orphan_keys": orphans,
        "metric_reconciliation": checks, "csv_round_trip_exact": True,
        "series_key_rule": "1..50000 after ascending store_id, product_id; stable for the frozen source population",
        "optional_series_attributes": {"included": [], "omitted": ["city_id", "management_group_id", "first_category_id", "second_category_id", "third_category_id"],
                                       "reason": "Not available in existing processed mart schemas; no raw/staging access"},
        "data_dictionary": {"path": DICTIONARY_PATH.as_posix(), "rows": len(data_dictionary()), "sha256": sha256_file(root / DICTIONARY_PATH)},
        "raw_reads": 0, "ets_fits": 0, "new_analytical_decisions": False,
        "caveats": ["Observed sales normalized scale, not money or physical units", "Actual repeats for each model; select one model",
                    "Replenishment scenarios are alternatives; do not sum across scenarios", "Validation coverage is global historical fold4 and ignores series/date filters",
                    "All three historical targets were missed; no actuals used for a new decision"]}
    write_json(root / MANIFEST_PATH, manifest)
    performance = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": perf_counter() - started,
                   "csv_bytes": sum(a["bytes"] for a in artifacts.values()), "ets_fits": 0, "raw_reads": 0}
    write_json(root / "powerbi/build_performance.json", performance)
    print(json.dumps({"tables": {n: a["rows"] for n, a in artifacts.items()}, **performance}), flush=True)
    return manifest
