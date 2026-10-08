"""Profiling descritivo de qualidade via DuckDB, sem materializar o raw em pandas."""

import json
from importlib.metadata import version
from pathlib import Path
import re
import sys

import duckdb

from src.ingestion.source_manifest import ROOT, project_paths


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def records(connection, sql):
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def connect_raw(manifest, root=ROOT):
    config, paths = project_paths(root)
    temporary = root / ".tmp/duckdb"
    temporary.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(config={
        "memory_limit": config["quality"]["duckdb_memory_limit"],
        "threads": config["quality"]["duckdb_threads"],
        "temp_directory": str(temporary),
        "max_temp_directory_size": "2GB",
    })
    selects = []
    for entry in manifest["files"]:
        selects.append(
            f"SELECT *, {literal(entry['role'])} AS source_split, "
            f"{literal(entry['name'])} AS source_file FROM read_parquet("
            f"{literal(paths['raw'] / entry['name'])})"
        )
    connection.execute("CREATE TEMP VIEW raw AS " + " UNION ALL ".join(selects))
    return connection


def load_sql(root=ROOT):
    source = (root / "sql/validation/raw_quality.sql").read_text(encoding="utf-8")
    pieces = re.split(r"^-- name: (\w+)\s*$", source, flags=re.MULTILINE)
    return {pieces[i]: pieces[i+1].strip().rstrip(";") for i in range(1, len(pieces), 2)}


def profile(connection, manifest, root=ROOT):
    _, paths = project_paths(root)
    sql = load_sql(root)
    report = {"source": manifest, "summary": records(connection, sql["summary"])}
    print("Qualidade: chave, nulos e cobertura temporal...", flush=True)
    connection.execute("CREATE TEMP TABLE duplicates AS " + sql["duplicate_keys"])
    report["duplicates"] = records(connection, """
        SELECT scope, count(*) duplicate_groups, sum(occurrences-1)::BIGINT duplicate_excess_rows,
               sum(occurrences)::BIGINT rows_in_duplicate_groups FROM duplicates GROUP BY scope ORDER BY scope
    """)
    report["duplicate_examples"] = records(connection, "SELECT * FROM duplicates ORDER BY scope,dt,store_id,product_id LIMIT 10")
    for item in report["summary"]:
        duplicate = next((d for d in report["duplicates"] if d["scope"] == item["scope"]), {})
        item["duplicate_excess_rows"] = duplicate.get("duplicate_excess_rows", 0)
        item["distinct_daily_keys"] = item["n_rows"] - item["duplicate_excess_rows"]
    columns = [c["name"] for c in manifest["files"][0]["observed_schema"]]
    null_select = ", ".join(f'count(*) FILTER (WHERE "{c}" IS NULL) AS "{c}"' for c in columns)
    report["nulls"] = records(connection, f"SELECT coalesce(source_split,'all') AS scope,{null_select} FROM raw GROUP BY GROUPING SETS ((source_split),()) ORDER BY scope")
    connection.execute("CREATE TEMP TABLE coverage AS " + sql["coverage"])
    report["coverage_summary"] = records(connection, sql["coverage_summary"])
    report["coverage_distribution"] = records(connection, sql["coverage_distribution"])
    coverage_path = paths["outputs"] / "series_coverage.parquet"
    paths["outputs"].mkdir(parents=True, exist_ok=True)
    connection.execute(f"COPY (SELECT * FROM coverage ORDER BY scope,store_id,product_id) TO {literal(coverage_path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    report["coverage_file"] = str(coverage_path.relative_to(root)).replace("\\", "/")

    print("Qualidade: domínios, extremos e relação train/eval...", flush=True)
    numeric_columns = [c for c in columns if c not in {"dt", "hours_sale", "hours_stock_status"}]
    report["numeric"] = {}
    for column in numeric_columns:
        report["numeric"][column] = records(connection, f"""
            SELECT coalesce(source_split,'all') AS scope, count(DISTINCT {column}) n_distinct,
                count(*) FILTER (WHERE {column} IS NULL) AS "nulls",
                count(*) FILTER (WHERE NOT isfinite({column})) nonfinite,
                count(*) FILTER (WHERE {column}<0) negatives,
                count(*) FILTER (WHERE {column}=0) zeros,
                min({column}) minimum, max({column}) maximum,
                quantile_cont({column}, [0.01,0.05,0.25,0.50,0.75,0.95,0.99]) quantiles
            FROM raw GROUP BY GROUPING SETS ((source_split),()) ORDER BY scope
        """)
    report["quantile_probabilities"] = [0.01,0.05,0.25,0.50,0.75,0.95,0.99]
    report["domains"] = {}
    for column in ["discount", "activity_flag", "holiday_flag", "stock_hour6_22_cnt"]:
        report["domains"][column] = records(connection, f"""
            SELECT coalesce(source_split,'all') AS scope, {column} AS "value", count(*) n_rows
            FROM raw GROUP BY GROUPING SETS ((source_split,{column}),({column})) ORDER BY scope,value
        """)
    report["discount_review"] = [
        {"scope": scope,
         "zero_rows": sum(r["n_rows"] for r in report["domains"]["discount"] if r["scope"] == scope and r["value"] == 0),
         "greater_than_one_rows": sum(r["n_rows"] for r in report["domains"]["discount"] if r["scope"] == scope and r["value"] is not None and r["value"] > 1),
         "action": "preservar; significado dos extremos não confirmado pela fonte"}
        for scope in ["all", "train", "eval"]
    ]
    report["overlap"] = {}
    for label, keys in {"dates":"dt", "cities":"city_id", "stores":"store_id", "products":"product_id", "series":"store_id,product_id", "daily_keys":"dt,store_id,product_id"}.items():
        select_train = f"SELECT DISTINCT {keys} FROM raw WHERE source_split='train'"
        select_eval = f"SELECT DISTINCT {keys} FROM raw WHERE source_split='eval'"
        report["overlap"][label] = records(connection, f"""
            SELECT (SELECT count(*) FROM ({select_train} INTERSECT {select_eval})) AS shared,
                   (SELECT count(*) FROM ({select_train} EXCEPT {select_eval})) train_only,
                   (SELECT count(*) FROM ({select_eval} EXCEPT {select_train})) eval_only
        """)[0]
    report["hierarchy"] = {}
    for label, key, parent in [("store_city", "store_id", "city_id"), ("product_category", "product_id", "third_category_id")]:
        report["hierarchy"][label] = records(connection, f"SELECT count(*) inconsistent_entities FROM (SELECT {key} FROM raw GROUP BY {key} HAVING count(DISTINCT {parent})>1)")[0]

    print("Qualidade: ruptura × venda e consistência dos vetores horários...", flush=True)
    for section in ["stockout_sales", "stockout_summary", "hourly"]:
        report[section] = records(connection, sql[section])
    report["hourly_stock_domain"] = records(connection, """
        SELECT value, count(*) n_hour_slots FROM
        (SELECT unnest(hours_stock_status) AS "value" FROM raw) GROUP BY value ORDER BY value
    """)
    report["schema_comparison"] = []
    documented = manifest["documented_schema"]
    schemas = {e["role"]: {c["name"]: c for c in e["observed_schema"]} for e in manifest["files"]}
    for name in dict.fromkeys([*documented, *schemas["train"], *schemas["eval"]]):
        report["schema_comparison"].append({"column": name, "documented_type": documented.get(name), "train": schemas["train"].get(name), "eval": schemas["eval"].get(name)})
    report["runtime"] = {"python": sys.version.split()[0], **{name: version(name) for name in ["duckdb", "pyarrow", "PyYAML"]}}
    return report


def write_json(report, path):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
