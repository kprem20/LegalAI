from __future__ import annotations

from typing import Any, Optional

from ai.embeddings.encoder import get_encoder
from ai.reranking.diversity import diversify_by_case, hits_from_query
from backend.config.settings import settings
from backend.schemas.models import CaseSummary, PassageHit, SearchFilters
from database.chroma.store import get_chroma


def filters_to_dict(filters: Optional[SearchFilters]) -> dict[str, Any]:
    if not filters:
        return {}
    data = filters.model_dump(exclude_none=True)
    # Drop empty strings
    return {k: v for k, v in data.items() if v not in ("", None)}


def semantic_search(
    query: str,
    top_k: int = 5,
    filters: Optional[SearchFilters] = None,
) -> tuple[list[CaseSummary], list[PassageHit]]:
    query = (query or "").strip()
    if not query:
        return [], []
    store = get_chroma()
    if not store.ready():
        return [], []
    encoder = get_encoder()
    embedding = encoder.encode_query(query)
    n_candidates = max(top_k * settings.candidate_multiplier, top_k * 4)
    n_candidates = min(n_candidates, 40)
    raw = store.query(
        embedding=embedding,
        n_results=n_candidates,
        filters=filters_to_dict(filters),
    )
    hits = hits_from_query(raw)
    return diversify_by_case(hits, top_k=top_k)


def similar_cases(case_text: str, exclude_case_id: str, top_k: int = 5) -> list[CaseSummary]:
    text = (case_text or "").strip()
    if not text:
        return []
    store = get_chroma()
    if not store.ready():
        return []
    encoder = get_encoder()
    snippet = text[:4000]
    embedding = encoder.encode_query(snippet)
    raw = store.query(embedding=embedding, n_results=max(top_k * 6, 12))
    hits = hits_from_query(raw)
    hits = [h for h in hits if h.case_id != exclude_case_id]
    summaries, _ = diversify_by_case(hits, top_k=top_k)
    return summaries
