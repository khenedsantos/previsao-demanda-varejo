"""Checks explícitos da versão congelada; falhas impedem a publicação do staging."""

from src.ingestion.source_manifest import ROOT, load_manifest, project_paths, verify_file


def validate_source(root=ROOT):
    _, paths = project_paths(root)
    manifest = load_manifest(root)
    expected = {entry["name"] for entry in manifest["files"]} | {".gitkeep"}
    extra = [p.name for p in paths["raw"].iterdir() if p.name not in expected]
    if extra:
        raise ValueError(f"Raw contém arquivos não manifestados: {extra}")
    for entry in manifest["files"]:
        if not entry.get("observed_schema") or entry.get("num_rows") is None:
            raise ValueError("Manifesto incompleto; execute a ingestão antes da validação.")
        verify_file(paths["raw"] / entry["name"], entry)
        actual_names = [field["name"] for field in entry["observed_schema"]]
        if actual_names != list(manifest["documented_schema"]):
            raise ValueError(f"Colunas ausentes, extras ou ordem alterada: {entry['name']}")
    if manifest["files"][0]["observed_schema"] != manifest["files"][1]["observed_schema"]:
        raise ValueError("Schemas de train/eval incompatíveis.")
    return manifest


def evaluate_checks(report):
    checks = []

    def check(name, condition, evidence):
        checks.append({"name": name, "passed": bool(condition), "evidence": evidence})

    for row in report["summary"]:
        scope = row["scope"]
        for field in ["invalid_dates", "null_keys", "duplicate_excess_rows"]:
            check(f"{scope}.{field}", row[field] == 0, row[field])
        check(f"{scope}.nonempty", row["n_rows"] > 0, row["n_rows"])
    for row in report["nulls"]:
        total = sum(value for key,value in row.items() if key != "scope")
        check(f"{row['scope']}.null_cells", total == 0, total)
    for row in report["hourly"]:
        scope = row["scope"]
        for field in ["sale_null_lists", "stock_null_lists", "sale_null_elements", "stock_null_elements", "sale_nonfinite_elements", "sale_negative_elements", "stock_invalid_elements", "daily_hourly_sales_mismatches", "stock_count_mismatches_06_22_exclusive"]:
            check(f"{scope}.{field}", row[field] == 0, row[field])
        lengths = [row[f"{kind}_{edge}_length"] for kind in ["sale","stock"] for edge in ["min","max"]]
        check(f"{scope}.hourly_lengths", lengths == [24]*4, lengths)
    for column, rows in report["numeric"].items():
        for row in rows:
            check(f"{row['scope']}.{column}.finite", row["nonfinite"] == 0, row["nonfinite"])
    for column in ["holiday_flag", "activity_flag"]:
        domain = {r["value"] for r in report["domains"][column]}
        check(f"{column}.binary_domain", domain <= {0,1}, sorted(domain, key=str))
    stock_domain = {r["value"] for r in report["domains"]["stock_hour6_22_cnt"]}
    check("stock_count.domain", stock_domain <= set(range(17)), sorted(stock_domain, key=str))
    for row in report["coverage_summary"]:
        check(f"{row['scope']}.complete_calendar", row["series_with_gaps"] == 0, row["series_with_gaps"])
    for name in ["dates", "daily_keys"]:
        check(f"split.no_overlap.{name}", report["overlap"][name]["shared"] == 0, report["overlap"][name])
    check("split.same_series", report["overlap"]["series"]["train_only"] == report["overlap"]["series"]["eval_only"] == 0, report["overlap"]["series"])
    summaries = {r["scope"]: r for r in report["summary"]}
    check("split.temporal_order", summaries["train"]["last_date"] < summaries["eval"]["first_date"], {s: str(summaries[s]["first_date"]) for s in ["train","eval"]})
    for entry in report["source"]["files"]:
        actual = summaries[entry["role"]]["n_rows"]
        check(f"{entry['role']}.manifest_rows", actual == entry["num_rows"], actual)
    all_stock = next(r for r in report["stockout_summary"] if r["scope"] == "all")
    check("stockout.present_and_comparable", 0 < all_stock["stockout_rows"] < all_stock["n_rows"], all_stock["stockout_rows"])
    report["checks"] = checks
    report["status"] = "passed" if all(c["passed"] for c in checks) else "blocked"
    return checks
