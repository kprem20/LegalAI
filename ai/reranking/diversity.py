from __future__ import annotations

from typing import Any

from backend.schemas.models import CaseSummary, PassageHit


def distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    score = 1.0 - float(distance)
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def hits_from_query(result: dict[str, Any]) -> list[PassageHit]:
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    hits: list[PassageHit] = []
    for i, chunk_uid in enumerate(ids):
        meta = metas[i] if i < len(metas) and metas[i] else {}
        dist = dists[i] if i < len(dists) else 1.0
        hits.append(
            PassageHit(
                chunk_uid=str(chunk_uid),
                chunk_id=int(meta.get("chunk_id") or 0),
                case_id=str(meta.get("case_id") or ""),
                case_name=str(meta.get("case_name") or ""),
                citation=str(meta.get("citation") or ""),
                date=str(meta.get("date") or ""),
                court=str(meta.get("court") or ""),
                year=meta.get("year"),
                judges=str(meta.get("judges") or ""),
                case_number=str(meta.get("case_number") or ""),
                score=round(distance_to_score(dist), 4),
                passage=str(docs[i] if i < len(docs) else ""),
                ipc=str(meta.get("ipc") or ""),
                articles=str(meta.get("articles") or ""),
            )
        )
    return hits


def diversify_by_case(hits: list[PassageHit], top_k: int) -> tuple[list[CaseSummary], list[PassageHit]]:
    """Prefer one strong passage per case so the UI shows distinct judgments."""
    by_case: dict[str, list[PassageHit]] = {}
    for hit in hits:
        by_case.setdefault(hit.case_id, []).append(hit)
    for group in by_case.values():
        group.sort(key=lambda h: h.score, reverse=True)

    ranked_cases = sorted(by_case.values(), key=lambda g: g[0].score, reverse=True)
    selected: list[PassageHit] = []
    summaries: list[CaseSummary] = []
    for group in ranked_cases[:top_k]:
        best = group[0]
        selected.append(best)
        summaries.append(
            CaseSummary(
                case_id=best.case_id,
                case_name=best.case_name,
                citation=best.citation,
                date=best.date,
                court=best.court,
                year=best.year,
                judges=best.judges,
                case_number=best.case_number,
                relevance=best.score,
                relevant_passage=best.passage,
                chunk_uid=best.chunk_uid,
            )
        )
    extra: list[PassageHit] = []
    for group in ranked_cases[:top_k]:
        extra.extend(group[1:2])
    evidence = selected + extra
    evidence.sort(key=lambda h: h.score, reverse=True)
    return summaries, evidence
