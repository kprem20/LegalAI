from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS search_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    query TEXT NOT NULL,
    filters_json TEXT DEFAULT '{}',
    result_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookmarks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    case_name TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, case_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    query TEXT DEFAULT '',
    rating TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_files (
    file_key TEXT PRIMARY KEY,
    case_id TEXT,
    indexed_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password with bcrypt. The salt parameter is ignored (bcrypt generates its own)."""
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored: str) -> bool:
    import bcrypt

    # Support bcrypt hashes (start with $2b$ or $2a$)
    if stored.startswith(("$2b$", "$2a$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    # Legacy PBKDF2 fallback for existing users
    try:
        salt, _digest = stored.split("$", 1)
    except ValueError:
        return False
    legacy_hash = salt + "$" + hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()
    return secrets.compare_digest(legacy_hash, stored)


class LocalAppStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or settings.app_db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Safe migration: add last_login if missing
            try:
                conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT DEFAULT ''")
            except Exception:
                pass  # Column already exists

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def register_user(self, email: str, password: str, name: str = "") -> dict[str, Any]:
        email = email.strip().lower()
        user_id = str(uuid.uuid4())
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                raise ValueError("An account with this email already exists.")
            conn.execute(
                "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, name.strip(), hash_password(password), _now()),
            )
        return {"id": user_id, "email": email, "name": name.strip()}

    def login_user(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise ValueError("Invalid email or password.")
        with self._connect() as conn:
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), row["id"]))
        return {"id": row["id"], "email": row["email"], "name": row["name"] or ""}

    def add_history(self, user_id: str, query: str, filters: dict[str, Any], result_count: int) -> dict[str, Any]:
        item_id = str(uuid.uuid4())
        created = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO search_history (id, user_id, query, filters_json, result_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (item_id, user_id, query, json.dumps(filters or {}), int(result_count), created),
            )
        return {
            "id": item_id,
            "query": query,
            "filters": filters or {},
            "result_count": result_count,
            "created_at": created,
        }

    def list_history(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM search_history WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "query": r["query"],
                "filters": json.loads(r["filters_json"] or "{}"),
                "result_count": r["result_count"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def add_bookmark(self, user_id: str, case_id: str, case_name: str) -> dict[str, Any]:
        item_id = str(uuid.uuid4())
        created = _now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM bookmarks WHERE user_id = ? AND case_id = ?",
                (user_id, case_id),
            ).fetchone()
            if existing:
                return {
                    "id": existing["id"],
                    "case_id": existing["case_id"],
                    "case_name": existing["case_name"],
                    "created_at": existing["created_at"],
                }
            conn.execute(
                """INSERT INTO bookmarks (id, user_id, case_id, case_name, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (item_id, user_id, case_id, case_name, created),
            )
        return {"id": item_id, "case_id": case_id, "case_name": case_name, "created_at": created}

    def list_bookmarks(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bookmarks WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [
            {"id": r["id"], "case_id": r["case_id"], "case_name": r["case_name"], "created_at": r["created_at"]}
            for r in rows
        ]

    def delete_bookmark(self, bookmark_id: str, user_id: Optional[str] = None) -> bool:
        with self._connect() as conn:
            if user_id:
                cur = conn.execute(
                    "DELETE FROM bookmarks WHERE id = ? AND user_id = ?",
                    (bookmark_id, user_id),
                )
            else:
                cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            return cur.rowcount > 0

    def add_feedback(self, user_id: Optional[str], query: str, rating: str, comment: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO feedback (id, user_id, query, rating, comment, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, query, rating, comment, _now()),
            )

    def mark_indexed(self, file_key: str, case_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_files (file_key, case_id, indexed_at) VALUES (?, ?, ?)",
                (file_key, case_id, _now()),
            )

    def is_indexed(self, file_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM index_files WHERE file_key = ?", (file_key,)).fetchone()
        return row is not None


_local: LocalAppStore | None = None


def get_local_store() -> LocalAppStore:
    global _local
    if _local is None:
        _local = LocalAppStore()
    return _local
