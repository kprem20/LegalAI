from __future__ import annotations

import os
from typing import Any, Optional

import httpx

API_URL = os.environ.get("NYAYA_API_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


def _client() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=120.0)


def _detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
    except Exception:
        pass
    return "The request could not be completed. Please try again."


def request(method: str, path: str, **kwargs) -> Any:
    try:
        with _client() as client:
            response = client.request(method, path, **kwargs)
    except httpx.ConnectError:
        raise ApiError(
            "The NyayaSearch API is not running. Start the backend with: python -m backend.main"
        )
    except httpx.TimeoutException:
        raise ApiError("The request timed out. Try a shorter query or wait and retry.")
    if response.status_code >= 400:
        raise ApiError(_detail(response), status_code=response.status_code)
    if response.status_code == 204:
        return None
    return response.json()


def health() -> dict[str, Any]:
    return request("GET", "/health")


def meta() -> dict[str, Any]:
    return request("GET", "/api/meta")


def search(query: str, top_k: int = 5, filters: Optional[dict] = None, user_id: Optional[str] = None) -> dict:
    return request(
        "POST",
        "/api/search",
        json={"query": query, "top_k": top_k, "filters": filters or {}, "user_id": user_id},
    )


def ask(query: str, top_k: int = 5, filters: Optional[dict] = None, user_id: Optional[str] = None) -> dict:
    return request(
        "POST",
        "/api/ask",
        json={"query": query, "top_k": top_k, "filters": filters or {}, "user_id": user_id},
    )


def analyse(query: str, passages: list, sources: Optional[list] = None) -> dict:
    """Run Gemini analysis on already-retrieved passages without repeating semantic search."""
    return request(
        "POST",
        "/api/analyse",
        json={"query": query, "passages": passages, "sources": sources or []},
    )


def get_case(case_id: str, similar: bool = False) -> dict:
    return request("GET", f"/api/cases/{case_id}", params={"similar": similar})


def similar_cases(case_id: str) -> dict:
    return request("GET", f"/api/cases/{case_id}/similar")


def compare(case_id_a: str, case_id_b: str, include_ai: bool = True) -> dict:
    return request(
        "POST",
        "/api/cases/compare",
        json={"case_id_a": case_id_a, "case_id_b": case_id_b, "include_ai": include_ai},
    )


def register(email: str, password: str, name: str = "") -> dict:
    return request("POST", "/api/auth/register", json={"email": email, "password": password, "name": name})


def login(email: str, password: str) -> dict:
    return request("POST", "/api/auth/login", json={"email": email, "password": password})


def history(user_id: str) -> dict:
    return request("GET", "/api/history", params={"user_id": user_id})


def bookmarks(user_id: str) -> dict:
    return request("GET", "/api/bookmarks", params={"user_id": user_id})


def add_bookmark(user_id: str, case_id: str, case_name: str) -> dict:
    return request(
        "POST",
        "/api/bookmarks",
        json={"user_id": user_id, "case_id": case_id, "case_name": case_name},
    )


def delete_bookmark(bookmark_id: str, user_id: Optional[str] = None) -> dict:
    params = {"user_id": user_id} if user_id else {}
    return request("DELETE", f"/api/bookmarks/{bookmark_id}", params=params)


def chat(message: str, history: Optional[list] = None) -> dict:
    """Send a message to NyayaSathi AI chatbot and return the reply."""
    return request(
        "POST",
        "/api/chat",
        json={"message": message, "history": history or []},
    )
