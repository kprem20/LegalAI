from __future__ import annotations

from database.local_store import LocalAppStore, hash_password, verify_password


def test_password_is_not_stored_plain():
    stored = hash_password("secret-pass")
    assert "secret-pass" not in stored
    assert verify_password("secret-pass", stored)
    assert not verify_password("other", stored)


def test_user_history_and_bookmarks(tmp_path):
    store = LocalAppStore(tmp_path / "app.db")
    user = store.register_user("a@b.com", "password12", "A")
    store.add_history(user["id"], "inquiry without hearing", {"year": 2000}, 3)
    hist = store.list_history(user["id"])
    assert hist[0]["query"] == "inquiry without hearing"
    bm = store.add_bookmark(user["id"], "2000::x", "Case X")
    assert store.list_bookmarks(user["id"])
    assert store.delete_bookmark(bm["id"], user["id"])
