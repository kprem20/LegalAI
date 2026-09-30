from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tqdm import tqdm

from ai.dataset.adapter import iter_dataset_files, load_json_chunks, make_case_id, normalize_record
from ai.embeddings.encoder import detect_device, get_encoder
from backend.config.settings import PROJECT_ROOT, settings
from database.chroma.store import ChromaStore
from database.local_store import get_local_store


def parse_years(value: str | None) -> list[str] | None:
    if not value:
        return None
    years = [item.strip() for item in value.split(",") if item.strip()]
    return years or None


def index_dataset(
    years: list[str] | None = None,
    max_files: int | None = None,
    batch_size: int = 32,
    rebuild: bool = False,
) -> dict:
    dataset_dir = settings.dataset_path
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    persist = settings.chroma_path
    persist.mkdir(parents=True, exist_ok=True)
    store = ChromaStore(persist_directory=str(persist), collection_name=settings.chroma_collection)
    encoder = get_encoder()
    local = get_local_store()

    files = list(iter_dataset_files(dataset_dir, years=years, max_files=max_files))
    if not files:
        raise FileNotFoundError("No JSON judgment files were found in the dataset directory.")

    indexed_files = 0
    skipped_files = 0
    upserted_chunks = 0
    invalid_records = 0

    progress = tqdm(files, desc="Indexing judgments", unit="file")
    for path in progress:
        file_key = f"{path.parent.name}/{path.name}"
        if not rebuild and local.is_indexed(file_key):
            skipped_files += 1
            continue
        records = load_json_chunks(path)
        chunks = []
        for record in records:
            chunk = normalize_record(record, year_folder=path.parent.name, file_path=path)
            if chunk:
                chunks.append(chunk)
            else:
                invalid_records += 1
        if not chunks:
            local.mark_indexed(file_key, make_case_id(path.parent.name, path.stem))
            skipped_files += 1
            continue
        ids = [c.chunk_uid for c in chunks]
        existing = store.existing_ids(ids) if not rebuild else set()
        pending = [c for c in chunks if c.chunk_uid not in existing]
        if pending:
            texts = [c.text for c in pending]
            vectors = encoder.encode(texts, batch_size=batch_size, show_progress=False)
            store.upsert_chunks(pending, vectors.tolist())
            upserted_chunks += len(pending)
        local.mark_indexed(file_key, chunks[0].case_id)
        indexed_files += 1
        progress.set_postfix(files=indexed_files, chunks=upserted_chunks, skipped=skipped_files)

    info = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(dataset_dir),
        "files_seen": len(files),
        "files_indexed": indexed_files,
        "files_skipped": skipped_files,
        "chunks_upserted": upserted_chunks,
        "invalid_records": invalid_records,
        "collection_count": store.count(),
        "embedding_model": settings.embedding_model,
        "device": detect_device(),
        "years": years,
        "max_files": max_files,
        "rebuild": rebuild,
    }
    state_path = PROJECT_ROOT / "data" / "index_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or update the NyayaSearch ChromaDB index.")
    parser.add_argument("--years", type=str, default=settings.index_years or None, help="Comma-separated years, e.g. 2000,2024,2025")
    parser.add_argument("--max-files", type=int, default=settings.index_max_files, help="Optional file cap for a quicker first index.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--rebuild", action="store_true", help="Re-embed files even if they were previously marked indexed.")
    args = parser.parse_args()
    info = index_dataset(
        years=parse_years(args.years),
        max_files=args.max_files,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
    )
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
