"""Valida o raw; staging só é criado após aprovação dos checks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.source_manifest import ROOT, project_paths
from src.ingestion.build_staging import build_staging
from src.quality.profile_raw import connect_raw, profile, write_json
from src.quality.validate_raw import evaluate_checks, validate_source
from src.reporting.quality_report import write_markdown


def main():
    _, paths = project_paths()
    paths["outputs"].mkdir(parents=True, exist_ok=True)
    output = paths["outputs"] / "data_quality_report.json"
    report = None
    try:
        manifest = validate_source()
        print("Raw: arquivos, hashes, schema e contagens conferidos.", flush=True)
        with connect_raw(manifest) as connection:
            report = profile(connection, manifest)
            checks = evaluate_checks(report)
            write_json(report, output)
            failed = [c["name"] for c in checks if not c["passed"]]
            if failed:
                raise ValueError(f"Checks reprovados: {', '.join(failed)}; staging não criado.")
        print("Raw aprovado. Construindo/conferindo staging em lotes...", flush=True)
        report["staging"] = build_staging(manifest)
        report["storage"] = {
            "raw_bytes": sum(e["size_bytes"] for e in manifest["files"]),
            "staging_bytes": report["staging"]["size_bytes"],
            "coverage_bytes": (paths["outputs"] / "series_coverage.parquet").stat().st_size,
        }
        write_json(report, output)
        write_markdown(report)
        print(f"Qualidade aprovada: {len(checks)} checks. Relatório: {output.relative_to(ROOT)}", flush=True)
    except Exception as error:
        # Não deixar um relatório aprovado de uma execução anterior parecer atual.
        report = report or {}
        report.update({"status":"blocked", "error":str(error)})
        write_json(report, output)
        write_markdown(report)
        print(f"ERRO DE QUALIDADE: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
