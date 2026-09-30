from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.models import AskResponse, CaseSummary, SearchResponse

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "index_ready" in data
    assert "embedding_model" in data


def test_search_rejects_short_query():
    response = client.post("/api/search", json={"query": "ab"})
    assert response.status_code == 422


def test_search_empty_index_message(monkeypatch):
    class Dummy:
        def ready(self):
            return False

        def count(self):
            return 0

    monkeypatch.setattr("backend.services.search_service.get_chroma", lambda: Dummy())
    response = client.post("/api/search", json={"query": "departmental inquiry termination"})
    assert response.status_code == 200
    data = response.json()
    assert data["index_ready"] is False
    assert data["result_count"] == 0
    assert "index" in data["message"].lower()


def test_ask_fallback_when_gemini_off(monkeypatch):
    results = [
        CaseSummary(
            case_id="2000::V_P_Ahuja_vs_State_Of_Punjab_Ors_on_6_March_2000_1",
            case_name="V.P. Ahuja vs State Of Punjab & Ors on 6 March, 2000",
            citation="Information not available in the dataset.",
            date="06 March 2000",
            court="Supreme Court of India",
            relevance=0.91,
            relevant_passage="The order, ex facie, is stigmatic as also punitive.",
            chunk_uid="x",
        )
    ]

    def fake_search(*args, **kwargs):
        return SearchResponse(query=kwargs.get("query") or args[0], results=results, passages=[], result_count=1)

    monkeypatch.setattr("backend.services.search_service.run_search", fake_search)
    monkeypatch.setattr("backend.services.search_service.try_analysis", lambda q, p: (None, "AI analysis is temporarily unavailable. The relevant cases retrieved from the legal database are shown below."))
    response = client.post("/api/ask", json={"query": "Can a probationer be dismissed with a stigmatic order?"})
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_available"] is False
    assert "temporarily unavailable" in (data["analysis_message"] or "").lower()
    assert data["results"]


def test_missing_case_returns_404():
    response = client.get("/api/cases/1999::does_not_exist")
    assert response.status_code == 404


def test_register_and_bookmark_roundtrip():
    import uuid

    email = f"researcher-{uuid.uuid4().hex[:8]}@example.com"
    password = "research-pass"
    client.post("/api/auth/register", json={"email": email, "password": password, "name": "Researcher"})
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    user_id = login.json()["user"]["id"]
    saved = client.post(
        "/api/bookmarks",
        json={"user_id": user_id, "case_id": "2000::demo", "case_name": "Demo Case"},
    )
    assert saved.status_code == 200
    listed = client.get("/api/bookmarks", params={"user_id": user_id})
    assert listed.status_code == 200
    assert listed.json()["items"]
    history = client.get("/api/history", params={"user_id": user_id})
    assert history.status_code == 200
