from __future__ import annotations

import numpy as np

from ai.dataset.adapter import load_json_chunks, normalize_record
from backend.config.settings import PROJECT_ROOT
from database.chroma.store import ChromaStore


def test_chroma_upsert_and_query(tmp_path):
    path = PROJECT_ROOT / "dataset" / "2000" / "V_P_Ahuja_vs_State_Of_Punjab_Ors_on_6_March_2000_1.json"
    rows = load_json_chunks(path)
    chunks = [normalize_record(row, year_folder="2000", file_path=path) for row in rows[:2]]
    chunks = [c for c in chunks if c]
    assert chunks
    dim = 8
    rng = np.random.default_rng(0)
    embeddings = rng.normal(size=(len(chunks), dim)).astype("float32")
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
    store = ChromaStore(persist_directory=str(tmp_path / "chroma"), collection_name="unit_test")
    store.upsert_chunks(chunks, embeddings.tolist())
    assert store.count() == len(chunks)
    existing = store.existing_ids([chunks[0].chunk_uid])
    assert chunks[0].chunk_uid in existing
    result = store.query(embedding=embeddings[0].tolist(), n_results=1)
    assert result["ids"][0][0] == chunks[0].chunk_uid
    filtered = store.query(
        embedding=embeddings[0].tolist(),
        n_results=1,
        filters={"year": 2000},
    )
    assert filtered["ids"][0]
