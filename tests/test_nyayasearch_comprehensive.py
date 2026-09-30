from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from ai.embeddings.encoder import get_embedding_model, get_encoder
from ai.rag.gemini_client import (
    FALLBACK_MESSAGE,
    QUOTA_MESSAGE,
    GeminiUnavailable,
    try_analysis,
)
from ai.retrieval.search import semantic_search
from backend.main import app
from backend.schemas.models import PassageHit
from database.local_store import LocalAppStore, hash_password, verify_password

client = TestClient(app)


# ─── 1. AUTHENTICATION & USER DB TESTS ──────────────────────

def test_bcrypt_password_hashing():
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_auth_registration_and_login_flow(tmp_path):
    store = LocalAppStore(tmp_path / "test_auth.db")
    email = f"advocate_{uuid.uuid4().hex[:6]}@lawfirm.in"
    name = "Adv. Ramesh Sharma"
    pwd = "StrongPassword2026!"

    # 1. New user registration
    user = store.register_user(email, pwd, name)
    assert user["id"]
    assert user["email"] == email
    assert user["name"] == name

    # 2. Duplicate email registration rejected
    with pytest.raises(ValueError, match="already exists"):
        store.register_user(email, pwd, "Another Name")

    # 3. Invalid login rejected (clean error, does not reveal email)
    with pytest.raises(ValueError, match="Invalid email or password"):
        store.login_user(email, "WrongPassword!")

    with pytest.raises(ValueError, match="Invalid email or password"):
        store.login_user("nonexistent@lawfirm.in", pwd)

    # 4. Valid login succeeds
    logged_in = store.login_user(email, pwd)
    assert logged_in["id"] == user["id"]
    assert logged_in["email"] == email


def test_api_auth_endpoints():
    unique_email = f"lawyer_{uuid.uuid4().hex[:8]}@supremecourt.in"
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "Password12345", "name": "Senior Advocate"},
    )
    assert reg_resp.status_code == 200
    user_data = reg_resp.json()["user"]
    assert user_data["email"] == unique_email

    # Duplicate registration fails
    dup_resp = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "Password12345", "name": "Senior Advocate"},
    )
    assert dup_resp.status_code == 400

    # Login succeeds
    login_resp = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "Password12345"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["id"] == user_data["id"]

    # Invalid login fails
    bad_login = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401


# ─── 2. USER-SPECIFIC BOOKMARKS & HISTORY ────────────────────

def test_user_specific_data_isolation(tmp_path):
    store = LocalAppStore(tmp_path / "test_isolation.db")
    user_a = store.register_user("user_a@law.in", "pass123456", "User A")["id"]
    user_b = store.register_user("user_b@law.in", "pass123456", "User B")["id"]

    # Bookmarks isolation
    store.add_bookmark(user_a, "case_1", "Case One")
    store.add_bookmark(user_b, "case_2", "Case Two")

    bm_a = store.list_bookmarks(user_a)
    bm_b = store.list_bookmarks(user_b)
    assert len(bm_a) == 1
    assert bm_a[0]["case_id"] == "case_1"
    assert len(bm_b) == 1
    assert bm_b[0]["case_id"] == "case_2"

    # User A cannot delete User B's bookmark
    deleted = store.delete_bookmark(bm_b[0]["id"], user_id=user_a)
    assert deleted is False
    assert len(store.list_bookmarks(user_b)) == 1

    # Search history isolation
    store.add_history(user_a, "preventive detention habeas corpus", {}, 5)
    store.add_history(user_b, "specific performance contract", {}, 3)

    hist_a = store.list_history(user_a)
    hist_b = store.list_history(user_b)
    assert len(hist_a) == 1
    assert hist_a[0]["query"] == "preventive detention habeas corpus"
    assert len(hist_b) == 1
    assert hist_b[0]["query"] == "specific performance contract"


# ─── 3. SEARCH & PERFORMANCE TESTS ──────────────────────────

def test_embedding_model_is_singleton():
    model1 = get_embedding_model()
    model2 = get_embedding_model()
    assert model1 is model2  # Exact same Python instance in memory

    enc1 = get_encoder()
    enc2 = get_encoder()
    assert enc1 is enc2
    assert enc1.model is model1


def test_semantic_search_returns_rapidly():
    # Normal query
    summaries, evidence = semantic_search("dismissal of employee without departmental inquiry", top_k=3)
    assert len(summaries) <= 3
    if summaries:
        assert summaries[0].case_name
        assert summaries[0].court

    # Empty query
    empty_summaries, empty_evidence = semantic_search("", top_k=5)
    assert empty_summaries == []
    assert empty_evidence == []


def test_api_search_endpoint_does_not_wait_for_gemini():
    resp = client.post(
        "/api/search",
        json={"query": "fundamental rights article 21", "top_k": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "passages" in data
    assert data["index_ready"] is True
    # Fast search returns without requiring Gemini
    assert "analysis" not in data  # Search response schema has no analysis field


# ─── 4. GEMINI ERROR HANDLING & QUOTA FALLBACK ───────────────

def test_gemini_unavailable_fallback():
    # Passages with no Gemini key
    passages = [
        PassageHit(
            chunk_uid="1",
            chunk_id=1,
            case_id="1950::test",
            case_name="A.K. Gopalan vs State of Madras",
            citation="1950 INSC 14",
            date="19 May 1950",
            court="Supreme Court of India",
            score=0.88,
            passage="Article 21 provides that no person shall be deprived of his life or personal liberty.",
        )
    ]
    # When Gemini raises quota exhausted
    from unittest.mock import patch

    with patch("ai.rag.gemini_client._client", side_effect=GeminiUnavailable(QUOTA_MESSAGE, is_quota=True)):
        text, msg = try_analysis("What is Article 21?", passages)
        assert text is None
        assert "quota has been reached" in msg

    # When Gemini is not configured
    with patch("ai.rag.gemini_client.settings.gemini_api_key", ""):
        text, msg = try_analysis("What is Article 21?", passages)
        assert text is None
        assert FALLBACK_MESSAGE in msg


def test_api_ask_returns_search_results_even_on_gemini_error():
    from unittest.mock import patch

    with patch("ai.rag.gemini_client.generate_text", side_effect=GeminiUnavailable("Quota exceeded", is_quota=True)):
        resp = client.post(
            "/api/ask",
            json={"query": "right to privacy Aadhaar", "top_k": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Search results must STILL be present
        assert "results" in data
        assert data["analysis_available"] is False
        assert "quota" in data["analysis_message"].lower() or "unavailable" in data["analysis_message"].lower()
