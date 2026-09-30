from __future__ import annotations

from ai.reranking.diversity import diversify_by_case, distance_to_score, hits_from_query
from backend.schemas.models import PassageHit


def test_distance_to_score_bounds():
    assert distance_to_score(0) == 1.0
    assert distance_to_score(1) == 0.0
    assert 0 <= distance_to_score(0.25) <= 1


def test_diversify_prefers_distinct_cases():
    hits = []
    for i in range(4):
        hits.append(
            PassageHit(
                chunk_uid=f"c1::{i}",
                chunk_id=i,
                case_id="2000::case_one",
                case_name="Case One",
                citation="C1",
                date="2000",
                court="Supreme Court of India",
                score=0.9 - i * 0.01,
                passage=f"passage {i} of case one",
            )
        )
    hits.append(
        PassageHit(
            chunk_uid="c2::1",
            chunk_id=1,
            case_id="2000::case_two",
            case_name="Case Two",
            citation="C2",
            date="2000",
            court="Supreme Court of India",
            score=0.8,
            passage="passage of case two",
        )
    )
    summaries, evidence = diversify_by_case(hits, top_k=2)
    assert len(summaries) == 2
    ids = {s.case_id for s in summaries}
    assert "2000::case_one" in ids
    assert "2000::case_two" in ids
    assert evidence


def test_hits_from_query_parses_chroma_shape():
    raw = {
        "ids": [["uid-1"]],
        "documents": [["held that inquiry is required"]],
        "metadatas": [[{"chunk_id": 2, "case_id": "y::x", "case_name": "X", "citation": "", "date": "2000", "court": "Supreme Court of India"}]],
        "distances": [[0.2]],
    }
    hits = hits_from_query(raw)
    assert len(hits) == 1
    assert hits[0].case_id == "y::x"
    assert hits[0].score > 0.7
