from __future__ import annotations

from ai.rag.gemini_client import FALLBACK_MESSAGE, try_analysis
from ai.rag.prompts import SYSTEM_PROMPT, build_evidence_block
from backend.schemas.models import PassageHit


def test_system_prompt_forbids_invention():
    assert "Do not invent" in SYSTEM_PROMPT
    assert "Do not provide personalized legal advice" in SYSTEM_PROMPT


def test_try_analysis_without_passages():
    text, message = try_analysis("What is the law?", [])
    assert text is None
    assert message


def test_try_analysis_falls_back_when_gemini_missing(monkeypatch):
    monkeypatch.setattr("ai.rag.gemini_client.settings.gemini_api_key", "")
    passages = [
        PassageHit(
            chunk_uid="1",
            chunk_id=1,
            case_id="2000::x",
            case_name="Example",
            citation="",
            date="2000",
            court="Supreme Court of India",
            score=0.9,
            passage="The services were terminated during probation.",
        )
    ]
    text, message = try_analysis("Can services be terminated?", passages)
    assert text is None
    assert FALLBACK_MESSAGE in (message or "")


def test_evidence_block_includes_case_name():
    passages = [
        PassageHit(
            chunk_uid="1",
            chunk_id=1,
            case_id="2000::x",
            case_name="V.P. Ahuja vs State Of Punjab",
            citation="",
            date="6 March 2000",
            court="Supreme Court of India",
            score=0.9,
            passage="The order, ex facie, is stigmatic.",
        )
    ]
    block = build_evidence_block(passages)
    assert "V.P. Ahuja" in block
    assert "stigmatic" in block
