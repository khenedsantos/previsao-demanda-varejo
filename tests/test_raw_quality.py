"""Contratos da fonte real e falhas controladas em cópias pequenas de suas linhas.

Pré-requisito dos testes de integração: executar ingest_data.py e validate_raw.py.
Nenhum teste altera data/raw; casos negativos usam somente tmp_path.
"""

from copy import deepcopy
import io
import json

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.ingestion.build_staging import export_staging, verify_staging
from src.ingestion.download_dataset import download_file
from src.ingestion.source_manifest import ROOT, load_manifest, schema_details, sha256_file, verify_file
from src.quality.profile_raw import load_sql, records
from src.quality.validate_raw import evaluate_checks, validate_source


@pytest.fixture(scope="session")
def manifest():
    return load_manifest()


@pytest.fixture(scope="session")
def quality_report():
    path = ROOT / "data/outputs/data_quality_report.json"
    assert path.is_file(), "Execute python scripts/validate_raw.py antes do pytest."
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def source_sample():
    # Quatro registros efetivamente publicados; casos negativos não são dados do projeto.
    return pa.Table.from_batches([next(pq.ParquetFile(ROOT / "data/raw/train.parquet").iter_batches(batch_size=4))])


def test_raw_files_manifest_hashes_and_schema(manifest):
    actual = validate_source()
    assert actual == manifest
    for entry in manifest["files"]:
        path = ROOT / "data/raw" / entry["name"]
        assert verify_file(path, entry)["num_rows"] == entry["documented_num_rows"]
        assert entry["retrieved_at_utc"] != "not_confirmed"
        assert entry["download_url"].endswith(f"/{manifest['source_revision']}/{entry['source_path']}")


def test_raw_grain_dates_coverage_and_split_are_proven(manifest, quality_report):
    assert quality_report["source"] == manifest
    assert quality_report["status"] == "passed"
    for summary in quality_report["summary"]:
        assert summary["distinct_daily_keys"] == summary["n_rows"]
        assert summary["invalid_dates"] == summary["null_keys"] == 0
    assert quality_report["overlap"]["daily_keys"]["shared"] == 0
    assert quality_report["overlap"]["series"]["train_only"] == 0
    assert quality_report["overlap"]["series"]["eval_only"] == 0
    assert all(row["series_with_gaps"] == 0 for row in quality_report["coverage_summary"])
    assert all(check["passed"] for check in evaluate_checks(deepcopy(quality_report)))


@pytest.mark.parametrize("mutation", ["missing_column", "extra_column", "changed_type", "changed_nullable"])
def test_schema_changes_fail_even_with_updated_content_hash(tmp_path, source_sample, mutation):
    original = tmp_path / "original.parquet"
    pq.write_table(source_sample, original)
    expected_schema = schema_details(original)
    if mutation == "missing_column":
        changed = source_sample.drop(["discount"])
    elif mutation == "extra_column":
        changed = source_sample.append_column("unexpected", source_sample["sale_amount"])
    elif mutation == "changed_type":
        index = source_sample.schema.get_field_index("discount")
        changed = source_sample.set_column(index, "discount", source_sample["discount"].cast(pa.float32()))
    else:
        fields = list(source_sample.schema)
        fields[0] = pa.field(fields[0].name, fields[0].type, nullable=False)
        changed = pa.Table.from_arrays(source_sample.columns, schema=pa.schema(fields))
    path = tmp_path / "changed.parquet"
    pq.write_table(changed, path)
    entry = {"size_bytes":path.stat().st_size, "sha256":sha256_file(path), "num_rows":4, "observed_schema":expected_schema}
    with pytest.raises(ValueError, match="Schema"):
        verify_file(path, entry)


def test_missing_empty_and_incorrect_row_count_fail(tmp_path, source_sample):
    path = tmp_path / "sample.parquet"
    with pytest.raises(ValueError, match="ausente"):
        verify_file(path, {})
    pq.write_table(source_sample.slice(0,0), path)
    entry = {"size_bytes":path.stat().st_size, "sha256":sha256_file(path), "num_rows":4}
    with pytest.raises(ValueError, match="Contagem"):
        verify_file(path, entry)
    pq.write_table(source_sample, path)
    entry.update(size_bytes=path.stat().st_size, sha256=sha256_file(path), num_rows=5)
    with pytest.raises(ValueError, match="Contagem"):
        verify_file(path, entry)


def test_hash_change_is_not_repaired_by_downloader(tmp_path, manifest):
    entry = manifest["files"][0]
    path = tmp_path / entry["name"]
    original = b"arquivo truncado para teste de imutabilidade"
    path.write_bytes(original)
    with pytest.raises(ValueError, match="Tamanho"):
        download_file(entry["download_url"], path, entry, tmp_path / "downloads")
    assert path.read_bytes() == original
    smaller_entry = {"size_bytes":len(original), "sha256":"0"*64}
    with pytest.raises(ValueError, match="SHA-256"):
        verify_file(path, smaller_entry)


def test_failed_download_does_not_publish_partial_raw(tmp_path, manifest, monkeypatch):
    entry = manifest["files"][0]
    monkeypatch.setattr("src.ingestion.download_dataset.urlopen", lambda *args,**kwargs: io.BytesIO(b"truncated response"))
    destination = tmp_path / "raw" / entry["name"]
    temporary = tmp_path / "downloads"
    with pytest.raises(ValueError, match="Tamanho"):
        download_file(entry["download_url"], destination, entry, temporary)
    assert not destination.exists()
    assert list(temporary.iterdir()) == []


def test_sql_detects_duplicate_and_gap_without_hiding_one_with_the_other(source_sample):
    # Remover o segundo dia e duplicar o terceiro mantém quatro linhas, mas há uma lacuna.
    table = source_sample.take(pa.array([0,2,2,3]))
    table = table.append_column("source_split", pa.array(["train"]*4))
    sql = load_sql()
    with duckdb.connect() as connection:
        connection.register("raw", table)
        duplicates = records(connection, sql["duplicate_keys"])
        assert any(r["scope"] == "train" and r["occurrences"] == 2 for r in duplicates)
        coverage = records(connection, sql["coverage"])
        assert all(r["n_observations"] == 4 and r["missing_days"] == 1 and r["coverage_ratio"] == .75 for r in coverage)


def test_sql_detects_unparseable_date(source_sample):
    dates = source_sample["dt"].to_pylist()
    dates[0] = "2024-02-30"
    table = source_sample.set_column(source_sample.schema.get_field_index("dt"), "dt", pa.array(dates))
    table = table.append_column("source_split", pa.array(["train"]*4))
    with duckdb.connect() as connection:
        connection.register("raw", table)
        assert all(r["invalid_dates"] == 1 for r in records(connection, load_sql()["summary"]))


@pytest.mark.parametrize("section,field,value", [
    ("summary","duplicate_excess_rows",1),
    ("summary","invalid_dates",1),
    ("nulls","discount",1),
    ("hourly","stock_count_mismatches_06_22_exclusive",1),
    ("hourly","sale_min_length",23),
])
def test_gate_blocks_regressions(quality_report, section, field, value):
    changed = deepcopy(quality_report)
    changed[section][0][field] = value
    assert not all(c["passed"] for c in evaluate_checks(changed))
    assert changed["status"] == "blocked"


def test_staging_reproducible_from_full_raw(tmp_path, manifest, quality_report):
    staging = ROOT / "data/staging/fresh_retail_daily.parquet"
    assert staging.is_file()
    assert verify_staging(manifest, ROOT / "data/raw", staging) == sum(e["num_rows"] for e in manifest["files"])
    rebuilt = tmp_path / "rebuilt.parquet"
    try:
        count = export_staging(manifest, ROOT / "data/raw", rebuilt)
        assert count == quality_report["staging"]["input_rows"] == quality_report["staging"]["output_rows"]
        assert sha256_file(rebuilt) == sha256_file(staging) == quality_report["staging"]["sha256"]
    finally:
        rebuilt.unlink(missing_ok=True)
