from __future__ import annotations

from typing import Any, Optional

from backend.config.settings import settings


class SupabaseAppStore:
    def __init__(self) -> None:
        if not settings.supabase_enabled:
            raise RuntimeError("Supabase is not configured.")
        from supabase import create_client

        self.client = create_client(settings.supabase_url, settings.supabase_key)

    def register_user(self, email: str, password: str, name: str = "") -> dict[str, Any]:
        result = self.client.auth.sign_up(
            {"email": email, "password": password, "options": {"data": {"name": name}}}
        )
        user = result.user
        if not user:
            raise ValueError("Registration did not complete. Check email confirmation settings.")
        return {"id": user.id, "email": email, "name": name}

    def login_user(self, email: str, password: str) -> dict[str, Any]:
        result = self.client.auth.sign_in_with_password({"email": email, "password": password})
        user = result.user
        if not user:
            raise ValueError("Invalid email or password.")
        name = ""
        if user.user_metadata:
            name = str(user.user_metadata.get("name") or "")
        return {"id": user.id, "email": email, "name": name}

    def add_history(self, user_id: str, query: str, filters: dict[str, Any], result_count: int) -> dict[str, Any]:
        payload = {
            "user_id": user_id,
            "query": query,
            "filters": filters or {},
            "result_count": result_count,
        }
        data = self.client.table("search_history").insert(payload).execute().data
        row = data[0] if data else payload
        return {
            "id": str(row.get("id", "")),
            "query": query,
            "filters": filters or {},
            "result_count": result_count,
            "created_at": str(row.get("created_at", "")),
        }

    def list_history(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        data = (
            self.client.table("search_history")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return [
            {
                "id": str(r.get("id")),
                "query": r.get("query", ""),
                "filters": r.get("filters") or {},
                "result_count": r.get("result_count") or 0,
                "created_at": str(r.get("created_at", "")),
            }
            for r in data
        ]

    def add_bookmark(self, user_id: str, case_id: str, case_name: str) -> dict[str, Any]:
        payload = {"user_id": user_id, "case_id": case_id, "case_name": case_name}
        data = self.client.table("bookmarks").upsert(payload, on_conflict="user_id,case_id").execute().data
        row = data[0] if data else payload
        return {
            "id": str(row.get("id", "")),
            "case_id": case_id,
            "case_name": case_name,
            "created_at": str(row.get("created_at", "")),
        }

    def list_bookmarks(self, user_id: str) -> list[dict[str, Any]]:
        data = (
            self.client.table("bookmarks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return [
            {
                "id": str(r.get("id")),
                "case_id": r.get("case_id", ""),
                "case_name": r.get("case_name", ""),
                "created_at": str(r.get("created_at", "")),
            }
            for r in data
        ]

    def delete_bookmark(self, bookmark_id: str, user_id: Optional[str] = None) -> bool:
        query = self.client.table("bookmarks").delete().eq("id", bookmark_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()
        return True

    def add_feedback(self, user_id: Optional[str], query: str, rating: str, comment: str = "") -> None:
        self.client.table("feedback").insert(
            {"user_id": user_id, "query": query, "rating": rating, "comment": comment}
        ).execute()


def get_app_store():
    if settings.supabase_enabled:
        try:
            return SupabaseAppStore()
        except Exception:
            from database.local_store import get_local_store

            return get_local_store()
    from database.local_store import get_local_store

    return get_local_store()
