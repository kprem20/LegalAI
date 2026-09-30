from __future__ import annotations

from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ai.dataset.adapter import NormalizedChunk
from backend.config.settings import settings


def _to_metadata(chunk: NormalizedChunk) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "chunk_uid": chunk.chunk_uid,
        "case_id": chunk.case_id,
        "chunk_id": int(chunk.chunk_id),
        "case_name": chunk.case_name[:500],
        "citation": chunk.citation[:300],
        "date": chunk.date[:80],
        "court": chunk.court[:200],
        "judges": chunk.judges[:400],
        "case_number": chunk.case_number[:200],
        "ipc": chunk.ipc[:300],
        "articles": chunk.articles[:200],
        "file_name": chunk.file_name[:300],
        "source_file": chunk.source_file[:400],
    }
    if chunk.year is not None:
        meta["year"] = int(chunk.year)
    return meta


def _chroma_where(filters: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not filters:
        return None
    clauses: list[dict[str, Any]] = []
    year = filters.get("year")
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    court = filters.get("court")
    citation = filters.get("citation")
    case_name = filters.get("case_name")

    if year not in (None, "", 0):
        clauses.append({"year": int(year)})
    else:
        if year_from not in (None, "", 0):
            clauses.append({"year": {"$gte": int(year_from)}})
        if year_to not in (None, "", 0):
            clauses.append({"year": {"$lte": int(year_to)}})
    if court:
        clauses.append({"court": {"$eq": str(court)}})
    if citation:
        clauses.append({"citation": {"$eq": str(citation)}})
    if case_name:
        clauses.append({"case_name": {"$eq": str(case_name)}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class ChromaStore:
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        persist = persist_directory or str(settings.chroma_path)
        name = collection_name or settings.chroma_collection
        self.client = chromadb.PersistentClient(
            path=persist,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        try:
            return int(self.collection.count())
        except Exception:
            return 0

    def ready(self) -> bool:
        return self.count() > 0

    def existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        found: set[str] = set()
        for i in range(0, len(ids), 200):
            batch = ids[i : i + 200]
            try:
                result = self.collection.get(ids=batch, include=[])
                found.update(result.get("ids") or [])
            except Exception:
                continue
        return found

    def upsert_chunks(
        self,
        chunks: list[NormalizedChunk],
        embeddings: list[list[float]],
    ) -> int:
        if not chunks:
            return 0
        ids = [c.chunk_uid for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [_to_metadata(c) for c in chunks]
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(ids)

    def query(
        self,
        embedding: list[float],
        n_results: int = 20,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        where = _chroma_where(filters)
        kwargs: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": max(1, n_results),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

    def stats(self) -> dict[str, Any]:
        return {
            "collection": self.collection.name,
            "count": self.count(),
            "persist_directory": str(settings.chroma_path),
        }


_store: ChromaStore | None = None


def get_chroma() -> ChromaStore:
    global _store
    if _store is None:
        _store = ChromaStore()
    return _store
