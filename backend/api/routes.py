from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ai.dataset.adapter import available_years, dataset_file_count
from backend.config.settings import settings
from backend.schemas.models import (
    AskRequest,
    AskResponse,
    AnalyseRequest,
    AnalyseResponse,
    AuthResponse,
    BookmarkCreate,
    BookmarkItem,
    ChatRequest,
    ChatResponse,
    CompareRequest,
    CompareResponse,
    FeedbackCreate,
    HealthResponse,
    LoginRequest,
    PassageHit,
    RegisterRequest,
    SearchRequest,
    SearchResponse,
    UserOut,
)
from backend.services import app_data_service, case_service, search_service
from database.chroma.store import get_chroma

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    store = get_chroma()
    dataset_present = settings.dataset_path.exists()
    ready = store.ready()
    message = "NyayaSearch AI is running."
    if not dataset_present:
        message = "Dataset folder was not found."
    elif not ready:
        message = "Dataset is present. Build the index with python scripts/index_dataset.py before searching."
    return HealthResponse(
        status="ok",
        dataset_present=dataset_present,
        index_ready=ready,
        collection_count=store.count(),
        embedding_model=settings.embedding_model,
        gemini_configured=settings.gemini_enabled,
        supabase_configured=settings.supabase_enabled,
        message=message,
    )


@router.get("/api/meta")
def meta():
    return {
        "years": available_years(),
        "dataset_files": dataset_file_count(),
        "courts": ["Supreme Court of India"],
        "index": get_chroma().stats(),
        "unavailable_label": "Information not available in the dataset.",
    }


@router.post("/api/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    try:
        return search_service.run_search(
            payload.query,
            top_k=payload.top_k,
            filters=payload.filters,
            user_id=payload.user_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Search could not be completed. Please try again.")


@router.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    try:
        return search_service.run_ask(
            payload.query,
            top_k=payload.top_k,
            filters=payload.filters,
            user_id=payload.user_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="The research request could not be completed.")


@router.post("/api/analyse", response_model=AnalyseResponse)
def analyse(payload: AnalyseRequest) -> AnalyseResponse:
    """Run Gemini analysis on already-retrieved passages. Does NOT repeat semantic search."""
    try:
        passages = [PassageHit(**p) for p in payload.passages]
        from ai.rag.gemini_client import try_analysis

        analysis, analysis_message = try_analysis(payload.query, passages[:8])
        return AnalyseResponse(
            query=payload.query,
            analysis=analysis,
            analysis_available=bool(analysis),
            analysis_message=analysis_message,
            sources=payload.sources,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="AI analysis could not be completed.")


@router.get("/api/cases/{case_id}/similar")
def similar(case_id: str, top_k: int = Query(default=5, ge=1, le=15)):
    results = case_service.get_similar(case_id, top_k=top_k)
    return {"case_id": case_id, "results": results}


@router.get("/api/cases/{case_id}")
def get_case(case_id: str, similar: bool = Query(default=False)):
    detail = case_service.get_case(case_id, include_similar=similar)
    if not detail:
        raise HTTPException(status_code=404, detail="Case not found in the dataset.")
    return detail


@router.post("/api/cases/compare", response_model=CompareResponse)
def compare(payload: CompareRequest) -> CompareResponse:
    result = case_service.compare_cases(payload)
    if not result:
        raise HTTPException(status_code=404, detail="One or both cases were not found in the dataset.")
    return result


@router.post("/api/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    try:
        user = app_data_service.register(payload.email, payload.password, payload.name)
        return AuthResponse(user=UserOut(**user), message="Account created.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable. Please try again.")


@router.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    try:
        user = app_data_service.login(payload.email, payload.password)
        return AuthResponse(user=UserOut(**user), message="Signed in.")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable. Please try again.")


@router.get("/api/history")
def history(user_id: str = Query(...)):
    try:
        items = app_data_service.history(user_id)
        return {"items": items}
    except Exception:
        raise HTTPException(status_code=503, detail="Search history is temporarily unavailable.")


@router.get("/api/bookmarks")
def bookmarks(user_id: str = Query(...)):
    try:
        items = app_data_service.bookmarks(user_id)
        return {"items": items}
    except Exception:
        raise HTTPException(status_code=503, detail="Bookmarks are temporarily unavailable.")


@router.post("/api/bookmarks", response_model=BookmarkItem)
def create_bookmark(payload: BookmarkCreate) -> BookmarkItem:
    try:
        item = app_data_service.add_bookmark(payload.user_id, payload.case_id, payload.case_name)
        return BookmarkItem(**item)
    except Exception:
        raise HTTPException(status_code=503, detail="The bookmark could not be saved.")


@router.delete("/api/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str, user_id: str | None = Query(default=None)):
    try:
        ok = app_data_service.remove_bookmark(bookmark_id, user_id=user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Bookmark not found.")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The bookmark could not be removed.")


@router.post("/api/feedback")
def feedback(payload: FeedbackCreate):
    try:
        app_data_service.add_feedback(payload.user_id, payload.query, payload.rating, payload.comment)
        return {"saved": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Feedback could not be stored.")


@router.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """NyayaSathi AI — hybrid conversational + legal RAG chatbot endpoint."""
    try:
        from backend.services.chat_service import run_chat
        return run_chat(message=payload.message, history=payload.history)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="NyayaSathi AI is temporarily unavailable. Please try again in a moment.",
        )
