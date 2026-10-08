"""Staging diário em lotes: preserva valores, converte dt e acrescenta proveniência."""

from pathlib import Path
import tempfile

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.ingestion.source_manifest import ROOT, project_paths, sha256_file

BATCH_SIZE = 65536


def staging_batches(manifest, raw_dir):
    for entry in manifest["files"]:
        parquet = pq.ParquetFile(raw_dir / entry["name"])
        for batch in parquet.iter_batches(batch_size=BATCH_SIZE, use_threads=False):
            date_index = batch.schema.get_field_index("dt")
            date_values = pc.cast(pc.strptime(batch.column(date_index), format="%Y-%m-%d", unit="s"), pa.date32())
            fields = list(batch.schema.remove_metadata())
            fields[date_index] = pa.field("dt", pa.date32(), nullable=fields[date_index].nullable)
            arrays = list(batch.columns)
            arrays[date_index] = date_values
            for name, value in [("source_split",entry["role"]), ("source_file",entry["name"])]:
                fields.append(pa.field(name, pa.string(), nullable=False))
                arrays.append(pa.array([value]*batch.num_rows, type=pa.string()))
            yield pa.RecordBatch.from_arrays(arrays, schema=pa.schema(fields))


def export_staging(manifest, raw_dir, destination):
    """Publica exclusivamente em caminho novo; chamador decide a substituição do staging."""
    destination = Path(destination)
    count = 0
    with destination.open("xb") as stream:
        writer = None
        try:
            for batch in staging_batches(manifest, raw_dir):
                if writer is None:
                    writer = pq.ParquetWriter(stream, batch.schema, compression="zstd", version="2.6")
                writer.write_batch(batch, row_group_size=BATCH_SIZE)
                count += batch.num_rows
        finally:
            if writer is not None:
                writer.close()
    return count


def verify_staging(manifest, raw_dir, path):
    parquet = pq.ParquetFile(path)
    expected_rows = sum(entry["num_rows"] for entry in manifest["files"])
    if parquet.metadata.num_rows != expected_rows:
        raise ValueError("Contagem do staging difere das entradas.")
    # Cada row group corresponde a um lote determinístico da fonte, na ordem train/eval.
    source = iter(staging_batches(manifest, raw_dir))
    for group in range(parquet.num_row_groups):
        for actual in parquet.iter_batches(row_groups=[group], batch_size=BATCH_SIZE, use_threads=False):
            expected = next(source, None)
            if expected is None or not actual.equals(expected, check_metadata=True):
                raise ValueError(f"Staging difere da transformação declarada no row group {group}.")
    if next(source, None) is not None:
        raise ValueError("Staging incompleto.")
    return expected_rows


def build_staging(manifest, root=ROOT):
    _, paths = project_paths(root)
    destination = paths["staging"] / "fresh_retail_daily.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        if not destination.exists():
            # Gerar fora do raw; mover apenas após validar todos os valores.
            with tempfile.NamedTemporaryFile(dir=root/".tmp", suffix=".parquet", delete=False) as handle:
                temporary = Path(handle.name)
            temporary.unlink()
            export_staging(manifest, paths["raw"], temporary)
            verify_staging(manifest, paths["raw"], temporary)
            # Não substituir silenciosamente staging existente/criado por outra execução.
            import os
            os.link(temporary, destination)
        count = verify_staging(manifest, paths["raw"], destination)
        return {
            "path": str(destination.relative_to(root)).replace("\\", "/"),
            "size_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "input_rows": sum(entry["num_rows"] for entry in manifest["files"]),
            "output_rows": count,
            "row_difference": count-sum(entry["num_rows"] for entry in manifest["files"]),
            "columns": pq.ParquetFile(destination).schema_arrow.names,
            "transformations": ["dt: string ISO -> date32", "source_split e source_file: proveniência", "demais 18 colunas preservadas integralmente"],
            "verification": "igualdade de todos os valores em lotes, na ordem dos arquivos do manifesto",
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
