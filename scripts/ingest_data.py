"""Aquisição rastreável: execute com o Python da .venv, de qualquer diretório."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.download_dataset import ingest


if __name__ == "__main__":
    try:
        ingest()
    except Exception as error:
        print(f"ERRO DE INGESTÃO: {error}", file=sys.stderr)
        sys.exit(1)
