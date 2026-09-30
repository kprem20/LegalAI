from database.supabase.client import get_app_store


def register(email: str, password: str, name: str = ""):
    return get_app_store().register_user(email, password, name)


def login(email: str, password: str):
    return get_app_store().login_user(email, password)


def history(user_id: str):
    return get_app_store().list_history(user_id)


def bookmarks(user_id: str):
    return get_app_store().list_bookmarks(user_id)


def add_bookmark(user_id: str, case_id: str, case_name: str):
    return get_app_store().add_bookmark(user_id, case_id, case_name)


def remove_bookmark(bookmark_id: str, user_id: str | None = None):
    return get_app_store().delete_bookmark(bookmark_id, user_id=user_id)


def add_feedback(user_id: str | None, query: str, rating: str, comment: str = ""):
    return get_app_store().add_feedback(user_id, query, rating, comment)
