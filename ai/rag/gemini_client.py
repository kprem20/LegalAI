from __future__ import annotations

import logging
import time
from typing import Optional

from ai.rag.prompts import (
    ANALYSIS_INSTRUCTIONS,
    COMPARISON_INSTRUCTIONS,
    SYSTEM_PROMPT,
    build_case_text_block,
    build_evidence_block,
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# ── Accurate, user-visible error messages (shown only when Gemini actually fails) ──

_MSG_QUOTA = (
    "NyayaSathi AI has temporarily reached its AI request limit (quota has been reached). "
    "Please try again shortly."
)
QUOTA_MESSAGE = _MSG_QUOTA
_MSG_UNAVAILABLE = (
    "NyayaSathi AI is temporarily unavailable. "
    "Please try again in a moment."
)
_MSG_AUTH = (
    "Gemini API authentication/permission error. "
    "Check that GEMINI_API_KEY is valid and has the required permissions."
)
_MSG_CONFIG = (
    "Gemini API request/model configuration error. "
    "Check GEMINI_MODEL in .env — the current model may be incorrect."
)
_MSG_GENERIC = (
    "NyayaSathi AI is temporarily unavailable. "
    "Please try again in a moment."
)
_MSG_NO_KEY = (
    "Gemini API key is not configured. "
    "Set GEMINI_API_KEY in .env to enable AI analysis."
)

FALLBACK_MESSAGE = _MSG_NO_KEY


class GeminiError(Exception):
    """Raised when Gemini cannot produce an analysis.

    ``user_message`` is a human-readable string suitable for display in the UI.
    ``error_category`` records the HTTP/error class for internal logging.
    """

    def __init__(self, user_message: str, error_category: str = "unknown") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.error_category = error_category


class GeminiUnavailable(GeminiError):
    """Compatibility alias for Gemini error scenarios."""

    def __init__(self, user_message: str = "", is_quota: bool = False, error_category: str = "") -> None:
        msg = user_message or (QUOTA_MESSAGE if is_quota else _MSG_UNAVAILABLE)
        cat = error_category or ("429_quota" if is_quota else "unavailable")
        super().__init__(msg, cat)
        self.is_quota = is_quota


def _classify_error(exc: Exception) -> tuple[str, str]:
    """Return (user_message, error_category) for a Gemini API exception."""
    name = type(exc).__name__
    msg = str(exc)
    msg_lower = msg.lower()

    logger.error(
        "Gemini API error [%s]: %s",
        name,
        # Truncate to avoid leaking full response bodies; never log the key
        msg[:500],
    )

    # 429 / RESOURCE_EXHAUSTED
    if (
        "429" in msg
        or "resource_exhausted" in msg_lower
        or "quota" in msg_lower
        or name == "ResourceExhausted"
    ):
        return _MSG_QUOTA, "429_quota"

    # 401 / 403 — authentication / permission
    if (
        "401" in msg
        or "403" in msg
        or "permission" in msg_lower
        or "authentication" in msg_lower
        or "api_key" in msg_lower
        or "forbidden" in msg_lower
        or name in ("PermissionDenied", "Unauthenticated")
    ):
        return _MSG_AUTH, "401_403_auth"

    # 400 / 404 — bad request / model not found
    if (
        "400" in msg
        or "404" in msg
        or "not found" in msg_lower
        or "invalid" in msg_lower
        or name in ("InvalidArgument", "NotFound")
    ):
        return _MSG_CONFIG, "400_404_config"

    # 503 / 504 / UNAVAILABLE / ServerError
    if (
        "503" in msg
        or "504" in msg
        or "unavailable" in msg_lower
        or "deadline" in msg_lower
        or name in ("ServerError", "ServiceUnavailable", "DeadlineExceeded")
    ):
        return _MSG_UNAVAILABLE, "503_unavailable"

    return _MSG_GENERIC, "other"


def _is_retryable(exc: Exception) -> bool:
    """Return True only for transient 503/504/server errors."""
    name = type(exc).__name__
    msg = str(exc)
    return (
        "503" in msg
        or "504" in msg
        or "unavailable" in msg.lower()
        or "deadline" in msg.lower()
        or name in ("ServerError", "ServiceUnavailable", "DeadlineExceeded")
    )


def _make_client():
    """Create and return a google-genai Client.

    Raises GeminiError if the key is absent or the SDK is unavailable.
    """
    if not settings.gemini_enabled:
        raise GeminiError(_MSG_NO_KEY, "no_key")

    try:
        from google import genai  # google-genai >= 1.0.0

        # No custom HttpRetryOptions — we handle 503 retries ourselves with
        # explicit backoff so the UI doesn't stall on hidden SDK retries.
        client = genai.Client(api_key=settings.gemini_api_key)
        return client, genai

    except ImportError as exc:
        logger.error("google-genai SDK not importable: %s", exc)
        raise GeminiError(_MSG_GENERIC, "import_error") from exc
    except Exception as exc:
        logger.error("Gemini client init failed: %s", exc)
        raise GeminiError(_MSG_GENERIC, "init_error") from exc


_client = _make_client


def generate_text(prompt: str) -> str:
    """Send a single generation request to Gemini and return the text.

    Retries up to 2 times (3 total attempts) on 503 / transient errors only.
    Does NOT retry on quota (429) or auth (401/403) errors.

    Raises GeminiError with an accurate, user-visible message on failure.
    """
    return generate_text_with_system(prompt, system_instruction=SYSTEM_PROMPT)


def generate_text_with_system(prompt: str, system_instruction: str = "") -> str:
    """Send a generation request to Gemini with a custom system instruction.

    Unlike generate_text(), this allows callers to override the system prompt
    instead of always using the strict legal analysis SYSTEM_PROMPT.

    Tries configured model first; if 429 quota or 503 occurs, falls back once to
    gemini-flash-lite-latest to avoid service disruption.
    Raises GeminiError with a user-visible message on failure.
    """
    client, genai = _client()

    try:
        from google.genai import types as genai_types
    except ImportError:
        genai_types = None

    candidate_models = [settings.gemini_model]
    if settings.gemini_model != "gemini-flash-lite-latest":
        candidate_models.append("gemini-flash-lite-latest")

    last_exc: Exception | None = None

    for model in candidate_models:
        try:
            config = None
            if genai_types is not None:
                config = genai_types.GenerateContentConfig(
                    system_instruction=system_instruction or SYSTEM_PROMPT,
                    temperature=0.15,
                    max_output_tokens=1024,
                )

            kwargs: dict = {
                "model": model,
                "contents": prompt,
            }
            if config is not None:
                kwargs["config"] = config

            response = client.models.generate_content(**kwargs)
            text = (getattr(response, "text", None) or "").strip()
            if text:
                return text

        except GeminiError:
            raise
        except Exception as exc:
            last_exc = exc
            msg_str = str(exc).lower()
            # If 429 or 503 on primary model, try fallback model once
            if (
                "429" in msg_str
                or "quota" in msg_str
                or "resource_exhausted" in msg_str
                or "503" in msg_str
                or "unavailable" in msg_str
            ) and model != candidate_models[-1]:
                logger.warning(
                    "Gemini model %s hit quota/unavailable (%s) — falling back to %s",
                    model,
                    type(exc).__name__,
                    candidate_models[-1],
                )
                continue
            break

    if last_exc is not None:
        user_msg, category = _classify_error(last_exc)
        raise GeminiError(user_msg, category) from last_exc

    raise GeminiError(_MSG_GENERIC, "exhausted")



def grounded_analysis(question: str, passages: list) -> str:
    """Build an evidence-grounded Gemini analysis from retrieved judgment passages.

    Selects up to 4 diverse passages (one per case where possible) to keep
    the prompt focused and avoid triggering 503 from oversized payloads.
    Does NOT repeat ChromaDB retrieval.
    """
    # Prefer one passage per unique case (diversity), up to 4 cases
    seen_cases: set[str] = set()
    diverse: list = []
    for hit in passages:
        if hit.case_id not in seen_cases:
            seen_cases.add(hit.case_id)
            diverse.append(hit)
        if len(diverse) >= 4:
            break

    # Top up to 3 if fewer than 3 unique cases
    if len(diverse) < 3:
        for hit in passages:
            if hit not in diverse:
                diverse.append(hit)
            if len(diverse) >= 3:
                break

    evidence = build_evidence_block(diverse, max_passages=4, max_chars_per_passage=900)

    prompt = (
        f"{ANALYSIS_INSTRUCTIONS}\n\n"
        f"Question:\n{question}\n\n"
        f"Retrieved judgment evidence:\n{evidence}\n"
    )

    return generate_text(prompt)


def grounded_comparison(chunks_a: list, chunks_b: list) -> str:
    """Build a structured Gemini comparison of two cases from their chunks."""
    block_a = build_case_text_block("CASE A", chunks_a)
    block_b = build_case_text_block("CASE B", chunks_b)

    prompt = (
        f"{COMPARISON_INSTRUCTIONS}\n\n"
        f"{block_a}\n\n"
        f"----\n\n"
        f"{block_b}\n"
    )

    return generate_text(prompt)


def try_analysis(
    question: str,
    passages: list,
) -> tuple[Optional[str], Optional[str]]:
    """Run grounded analysis; return (analysis_text, None) or (None, error_message).

    Never fabricates an analysis — returns (None, message) instead of hiding errors.
    """
    if not passages:
        return None, "No retrieved evidence is available for analysis."

    try:
        return grounded_analysis(question, passages), None

    except GeminiError as ge:
        logger.warning(
            "Gemini analysis unavailable [%s]: %s",
            ge.error_category,
            ge.user_message,
        )
        return None, ge.user_message

    except Exception as exc:
        logger.exception("Unexpected error during AI analysis: %s", exc)
        return None, _MSG_GENERIC


def try_comparison(
    chunks_a: list,
    chunks_b: list,
) -> tuple[Optional[str], Optional[str]]:
    """Run comparison; return (text, None) or (None, error_message)."""
    try:
        return grounded_comparison(chunks_a, chunks_b), None

    except GeminiError as ge:
        logger.warning(
            "Gemini comparison unavailable [%s]: %s",
            ge.error_category,
            ge.user_message,
        )
        return None, ge.user_message

    except Exception as exc:
        logger.exception("Unexpected error during AI comparison: %s", exc)
        return None, _MSG_GENERIC