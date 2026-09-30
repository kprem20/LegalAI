from __future__ import annotations

from ai.dataset.adapter import load_case_chunks
from ai.rag.gemini_client import try_comparison
from ai.retrieval.search import similar_cases
from backend.config.settings import UNAVAILABLE
from backend.schemas.models import CaseDetailResponse, CaseSummary, CompareRequest, CompareResponse


def _detail_from_chunks(case_id: str, include_similar: bool = False) -> CaseDetailResponse | None:
    chunks = load_case_chunks(case_id)
    if not chunks:
        return None
    first = chunks[0]
    similar: list[CaseSummary] = []
    if include_similar:
        joined = "\n".join(c.text for c in chunks[:4])
        similar = similar_cases(joined, exclude_case_id=case_id, top_k=5)
    return CaseDetailResponse(
        case_id=case_id,
        case_name=first.case_name,
        citation=first.citation or UNAVAILABLE,
        date=first.date or UNAVAILABLE,
        court=first.court or UNAVAILABLE,
        judges=first.judges or UNAVAILABLE,
        case_number=first.case_number or UNAVAILABLE,
        year=first.year,
        ipc=first.ipc or UNAVAILABLE,
        articles=first.articles or UNAVAILABLE,
        source_file=first.source_file,
        chunks=[
            {"chunk_id": c.chunk_id, "chunk_uid": c.chunk_uid, "text": c.text}
            for c in chunks
        ],
        similar=similar,
    )


def get_case(case_id: str, include_similar: bool = False) -> CaseDetailResponse | None:
    return _detail_from_chunks(case_id, include_similar=include_similar)


def get_similar(case_id: str, top_k: int = 5) -> list[CaseSummary]:
    chunks = load_case_chunks(case_id)
    if not chunks:
        return []
    joined = "\n".join(c.text for c in chunks[:4])
    return similar_cases(joined, exclude_case_id=case_id, top_k=top_k)


def compare_cases(payload: CompareRequest) -> CompareResponse | None:
    case_a = _detail_from_chunks(payload.case_id_a, include_similar=False)
    case_b = _detail_from_chunks(payload.case_id_b, include_similar=False)
    if not case_a or not case_b:
        return None
    comparison = None
    message = None
    available = False
    if payload.include_ai:
        chunks_a = load_case_chunks(payload.case_id_a)
        chunks_b = load_case_chunks(payload.case_id_b)
        comparison, message = try_comparison(chunks_a, chunks_b)
        available = bool(comparison)
    return CompareResponse(
        case_a=case_a,
        case_b=case_b,
        comparison=comparison,
        comparison_available=available,
        comparison_message=message,
    )
