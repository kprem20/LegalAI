from __future__ import annotations

from ai.rag.gemini_client import try_analysis
from ai.retrieval.search import semantic_search
from backend.config.settings import settings
from backend.schemas.models import AskResponse, SearchFilters, SearchResponse
from database.chroma.store import get_chroma
from database.supabase.client import get_app_store


def run_search(
    query: str,
    top_k: int | None = None,
    filters: SearchFilters | None = None,
    user_id: str | None = None,
) -> SearchResponse:
    query = (query or "").strip()
    if not query:
        return SearchResponse(
            query=query,
            results=[],
            passages=[],
            result_count=0,
            index_ready=get_chroma().ready(),
            message="Enter a legal question to search the judgment database.",
        )
    store = get_chroma()
    if not store.ready():
        return SearchResponse(
            query=query,
            results=[],
            passages=[],
            result_count=0,
            index_ready=False,
            message="The vector index has not been built yet. Run python scripts/index_dataset.py first.",
        )
    k = top_k or settings.default_top_k
    results, passages = semantic_search(query, top_k=k, filters=filters)
    if user_id:
        try:
            get_app_store().add_history(
                user_id=user_id,
                query=query,
                filters=(filters.model_dump(exclude_none=True) if filters else {}),
                result_count=len(results),
            )
        except Exception:
            pass
    message = None
    if not results:
        message = "No matching judgments were found for this query with the current filters."
    return SearchResponse(
        query=query,
        results=results,
        passages=passages,
        result_count=len(results),
        index_ready=True,
        message=message,
    )


def run_ask(
    query: str,
    top_k: int | None = None,
    filters: SearchFilters | None = None,
    user_id: str | None = None,
) -> AskResponse:
    search = run_search(query, top_k=top_k, filters=filters, user_id=user_id)
    analysis, analysis_message = try_analysis(query, search.passages[:8])
    sources = []
    seen = set()
    for item in search.results:
        key = item.case_id
        if key in seen:
            continue
        seen.add(key)
        label = item.case_name
        if item.citation and "not available" not in item.citation.lower():
            label = f"{item.case_name} ({item.citation})"
        sources.append(label)
    return AskResponse(
        query=search.query,
        results=search.results,
        passages=search.passages,
        result_count=search.result_count,
        index_ready=search.index_ready,
        message=search.message,
        analysis=analysis,
        analysis_available=bool(analysis),
        analysis_message=analysis_message,
        sources=sources,
    )
