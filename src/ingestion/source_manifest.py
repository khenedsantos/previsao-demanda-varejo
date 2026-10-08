"""Identidade da fonte e verificação de arquivos; nunca altera o raw."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]


def project_paths(root=ROOT):
    config = yaml.safe_load((root / "config/project.yaml").read_text(encoding="utf-8"))
    paths = {}
    for name, relative in config["directories"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Diretório fora do projeto: {relative}")
        paths[name] = path
    if config["raw"]["immutable"] is not True:
        raise ValueError("O projeto exige raw imutável.")
    return config, paths


def load_manifest(root=ROOT):
    manifest = yaml.safe_load((root / "config/source_manifest.yaml").read_text(encoding="utf-8"))
    if manifest["dataset_identifier"] != "Dingdong-Inc/FreshRetailNet-50K":
        raise ValueError("Fonte diferente do dataset oficial aprovado.")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["source_revision"]):
        raise ValueError("A revisão deve ser um commit fixo, não uma branch.")
    entries = manifest["files"]
    if {e["name"] for e in entries} != {"train.parquet", "eval.parquet"} or len(entries) != 2:
        raise ValueError("Manifesto deve conter exatamente os dois Parquet oficiais.")
    for entry in entries:
        if entry["source_path"] != f"data/{entry['name']}" or entry["role"] != Path(entry["name"]).stem:
            raise ValueError("Caminho ou papel do arquivo incompatível com a fonte.")
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) or entry["size_bytes"] <= 0:
            raise ValueError("Hash ou tamanho inválido no manifesto.")
    return manifest


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def schema_details(path):
    parquet = pq.ParquetFile(path)
    result = []
    for index, field in enumerate(parquet.schema_arrow):
        result.append({
            "name": field.name,
            "arrow_type": str(field.type),
            "physical_type": parquet.schema.column(index).physical_type,
            "nullable": field.nullable,
            "element_nullable": field.type.value_field.nullable if pa.types.is_list(field.type) else None,
        })
    return result


def verify_file(path, entry):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Raw ausente: {path.name}; execute scripts/ingest_data.py.")
    if path.stat().st_size != entry["size_bytes"]:
        raise ValueError(f"Tamanho divergente: {path.name}; raw não será sobrescrito.")
    if sha256_file(path) != entry["sha256"]:
        raise ValueError(f"SHA-256 divergente: {path.name}; raw não será sobrescrito.")
    rows = pq.ParquetFile(path).metadata.num_rows
    expected = entry.get("num_rows") or entry["documented_num_rows"]
    if rows != expected or rows == 0:
        raise ValueError(f"Contagem de linhas divergente: {path.name}: {rows} != {expected}.")
    schema = schema_details(path)
    if entry.get("observed_schema") is not None and entry["observed_schema"] != schema:
        raise ValueError(f"Schema físico/nullable divergente: {path.name}.")
    return {"num_rows": rows, "observed_schema": schema}


def save_manifest(manifest, root=ROOT):
    path = root / "config/source_manifest.yaml"
    text = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    if path.read_text(encoding="utf-8") != text:
        temporary = root / ".tmp/source_manifest.yaml.tmp"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()
