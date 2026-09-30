from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    court: Optional[str] = None
    citation: Optional[str] = None
    case_name: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=25)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    user_id: Optional[str] = None


class PassageHit(BaseModel):
    chunk_uid: str
    chunk_id: int
    case_id: str
    case_name: str
    citation: str
    date: str
    court: str
    year: Optional[int] = None
    judges: str = ""
    case_number: str = ""
    score: float
    passage: str
    ipc: str = ""
    articles: str = ""


class CaseSummary(BaseModel):
    case_id: str
    case_name: str
    citation: str
    date: str
    court: str
    year: Optional[int] = None
    judges: str = ""
    case_number: str = ""
    relevance: Optional[float] = None
    relevant_passage: str = ""
    chunk_uid: str = ""


class SearchResponse(BaseModel):
    query: str
    results: list[CaseSummary]
    passages: list[PassageHit]
    result_count: int
    index_ready: bool = True
    message: Optional[str] = None


class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=25)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    user_id: Optional[str] = None


class AnalyseRequest(BaseModel):
    """Accepts already-retrieved passages to run Gemini analysis without a second search."""

    query: str = Field(..., min_length=3, max_length=4000)
    passages: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class AnalyseResponse(BaseModel):
    query: str
    analysis: Optional[str] = None
    analysis_available: bool = False
    analysis_message: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class AskResponse(BaseModel):
    query: str
    results: list[CaseSummary]
    passages: list[PassageHit]
    result_count: int = 0
    index_ready: bool = True
    message: Optional[str] = None
    analysis: Optional[str] = None
    analysis_available: bool = False
    analysis_message: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class CaseDetailResponse(BaseModel):
    case_id: str
    case_name: str
    citation: str
    date: str
    court: str
    judges: str = ""
    case_number: str = ""
    year: Optional[int] = None
    ipc: str = ""
    articles: str = ""
    source_file: str = ""
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    similar: list[CaseSummary] = Field(default_factory=list)


class CompareRequest(BaseModel):
    case_id_a: str
    case_id_b: str
    include_ai: bool = True


class CompareResponse(BaseModel):
    case_a: CaseDetailResponse
    case_b: CaseDetailResponse
    comparison: Optional[str] = None
    comparison_available: bool = False
    comparison_message: Optional[str] = None


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str = ""


class AuthResponse(BaseModel):
    user: UserOut
    message: str = "ok"


class HistoryItem(BaseModel):
    id: str
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    result_count: int = 0
    created_at: str


class BookmarkItem(BaseModel):
    id: str
    case_id: str
    case_name: str
    created_at: str


class BookmarkCreate(BaseModel):
    user_id: str
    case_id: str
    case_name: str = ""


class FeedbackCreate(BaseModel):
    user_id: Optional[str] = None
    query: str = ""
    rating: Literal["up", "down"]
    comment: str = ""


class HealthResponse(BaseModel):
    status: str
    dataset_present: bool
    index_ready: bool
    collection_count: int = 0
    embedding_model: str
    gemini_configured: bool
    supabase_configured: bool
    message: str = ""


# ── NyayaSathi AI Chatbot schemas ────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    route: Literal["general", "legal"] = "general"
    sources: list[str] = Field(default_factory=list)
