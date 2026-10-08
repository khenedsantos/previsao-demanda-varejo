"""Download oficial em streaming; publicação sem sobrescrever arquivos existentes."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen

from src.ingestion.source_manifest import (
    ROOT, load_manifest, project_paths, save_manifest, utc_now, verify_file,
)


def download_file(url, destination, entry, temporary_dir):
    destination = Path(destination)
    if destination.exists():
        verify_file(destination, entry)
        return False
    if not url.startswith("https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K/resolve/"):
        raise ValueError("Download permitido apenas do repositório oficial.")
    temporary_dir.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part", dir=temporary_dir)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            request = Request(url, headers={"User-Agent": "previsao-demanda-varejo/0.1"})
            with urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, output, length=1024 * 1024)
        verify_file(temporary, entry)
        # Hard link no mesmo volume: criação exclusiva, sem cópia e sem overwrite.
        os.link(temporary, destination)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def ingest(root=ROOT):
    _, paths = project_paths(root)
    manifest = load_manifest(root)
    paths["raw"].mkdir(parents=True, exist_ok=True)
    expected_names = {e["name"] for e in manifest["files"]} | {".gitkeep"}
    unexpected = [p.name for p in paths["raw"].iterdir() if p.name not in expected_names]
    if unexpected:
        raise ValueError(f"Arquivos raw inesperados: {unexpected}")
    missing_bytes = sum(e["size_bytes"] for e in manifest["files"] if not (paths["raw"] / e["name"]).exists())
    free = shutil.disk_usage(root).free
    if free < missing_bytes + 512 * 1024**2:
        raise ValueError("Espaço insuficiente: preservar 512 MiB livres além do download.")
    print(f"Fonte oficial, revisão {manifest['source_revision']}; download pendente: {missing_bytes:,} bytes.", flush=True)
    for entry in manifest["files"]:
        destination = paths["raw"] / entry["name"]
        url = f"{manifest['source_url']}/resolve/{manifest['source_revision']}/{entry['source_path']}"
        downloaded = download_file(url, destination, entry, root / ".tmp/downloads")
        entry.update(verify_file(destination, entry))
        entry["download_url"] = url
        if downloaded:
            entry["retrieved_at_utc"] = utc_now()
            if manifest["retrieval_date"] == "not_confirmed":
                manifest["retrieval_date"] = datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
        save_manifest(manifest, root)
        action = "baixado e verificado" if downloaded else "reutilizado; hash e schema conferidos"
        print(f"{entry['name']}: {action}; {entry['num_rows']:,} linhas.", flush=True)
    return manifest
