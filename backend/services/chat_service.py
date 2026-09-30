from __future__ import annotations

"""NyayaSathi AI — chat service.

Architecture:
  1. Lightweight rule-based routing (no Gemini call just to classify).
  2. Legal path → semantic_search (top-3 passages) → Gemini with legal RAG prompt.
  3. General path → Gemini with conversational system prompt.
  4. One Gemini call per user message. No repeated retrieval.
"""

import logging
from typing import Optional

from backend.schemas.models import ChatMessage, ChatResponse, PassageHit

logger = logging.getLogger(__name__)

# ── Query routing ─────────────────────────────────────────────────────────────

_LEGAL_KEYWORDS: frozenset[str] = frozenset(
    {
        # Constitutional / fundamental
        "article", "constitution", "fundamental", "right", "rights", "directive",
        "amendment", "preamble", "parliament", "legislative", "legislation",
        # Substantive legal terms
        "law", "legal", "laws", "lawyer", "advocate", "attorney", "judge", "court",
        "tribunal", "judiciary", "jurisdiction", "statute", "statutory",
        "section", "act", "ipc", "crpc", "cpc", "evidence act", "penal", "code",
        # Criminal law
        "bail", "anticipatory", "arrest", "fir", "police", "accused", "custody",
        "parole", "acquittal", "conviction", "sentence", "punishment", "crime",
        "criminal", "offence", "offense", "murder", "theft", "robbery", "rape",
        "assault", "defamation", "cheating", "fraud", "bribery", "corruption",
        "forgery", "abetment", "conspiracy", "kidnapping",
        # Civil law
        "contract", "tort", "negligence", "damages", "liability", "duty",
        "property", "land", "ownership", "inheritance", "succession", "will",
        "partition", "tenancy", "lease", "easement", "mortgage", "lien",
        # Family law
        "divorce", "matrimonial", "marriage", "custody", "maintenance", "alimony",
        "adoption", "guardianship",
        # Courts / procedure
        "supreme court", "high court", "district court", "sessions",
        "magistrate", "writ", "petition", "appeal", "revision", "judgment",
        "judgement", "verdict", "order", "decree", "injunction", "stay",
        "contempt", "precedent", "ratio", "obiter",
        # Specific rights / doctrines
        "privacy", "speech", "expression", "religion", "equality",
        "discrimination", "reservation", "affirmative", "untouchability",
        "habeas corpus", "mandamus", "certiorari", "quo warranto", "prohibition",
        # Commercial / corporate
        "company", "corporate", "shareholder", "merger", "insolvency",
        "bankruptcy", "arbitration", "mediation", "consumer",
        # Tax / service
        "tax", "gst", "income tax", "customs", "excise", "service law",
        # Cyber / IP
        "cyber", "cybercrime", "intellectual property", "patent", "trademark",
        "copyright", "data protection",
        # Environmental
        "environment", "pollution", "forest", "wildlife",
        # Labour
        "labour", "labor", "employment", "workmen", "industrial",
    }
)

_CASUAL_PHRASES: frozenset[str] = frozenset(
    {
        "hi", "hii", "hiee", "hiiii", "hello", "hey", "heyy",
        "good morning", "good evening", "good night", "good afternoon",
        "how are you", "how r u", "how are u", "how do you do",
        "what can you do", "what can you help",
        "thanks", "thank you", "thank u", "ty", "thx",
        "bye", "goodbye", "see you", "ok", "okay", "sure",
        "nice", "cool", "great", "wow", "awesome",
    }
)


def _is_legal_query(text: str) -> bool:
    """Lightweight local classification. Returns True if ANY legal keyword present."""
    lower = text.lower()

    # Exact casual phrase match takes priority
    stripped = lower.strip().rstrip("!?.")
    if stripped in _CASUAL_PHRASES:
        return False

    # Check for legal keywords (word-boundary-safe: check substrings since many
    # keywords are multi-word; short words checked as whole words only)
    for kw in _LEGAL_KEYWORDS:
        if len(kw) <= 4:
            # Short keywords: require word boundary (avoid "act" in "traction")
            import re
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                return True
        else:
            if kw in lower:
                return True

    return False


# ── Prompt builders ───────────────────────────────────────────────────────────

_CHAT_SYSTEM_GENERAL = """You are NyayaSathi AI, a friendly and knowledgeable AI assistant.
You can answer general questions naturally, tell jokes, explain concepts, and have normal conversations.
You also have strong expertise in Indian law and the legal system.
Be helpful, concise, and conversational. Keep responses focused and appropriately brief."""

_CHAT_SYSTEM_LEGAL = """You are NyayaSathi AI, a legal information assistant specialising in Indian law and Supreme Court jurisprudence.

MANDATORY RULES:
1. When Supreme Court evidence is provided below, use it as the PRIMARY authority.
2. NEVER fabricate case names, citations, dates, judges, sections, articles, or legal principles.
3. NEVER attribute a legal principle to the Supreme Court unless it is supported by the retrieved evidence below.
4. If retrieved evidence does not sufficiently support a Supreme Court claim, explicitly state:
   "No sufficiently relevant Supreme Court authority was retrieved for this question."
5. You MAY provide general legal explanations but ALWAYS clearly label them as general information, NOT as retrieved Supreme Court authority.
6. Do NOT provide personalised legal advice. Provide educational legal information only.
7. Keep responses concise — approximately 150-250 words unless the question genuinely requires more detail.
8. Clearly distinguish retrieved Supreme Court evidence from general legal explanation."""

_LEGAL_PROMPT_TEMPLATE = """Recent conversation context:
{history}

Retrieved Supreme Court evidence:
{evidence}

User question: {question}

Answer the question. If the retrieved evidence is directly relevant, cite it clearly as Supreme Court authority. If the evidence is weak or not relevant to the specific question, state: "No sufficiently relevant Supreme Court authority was retrieved for this question." Then provide a general legal explanation clearly labelled as general information."""

_GENERAL_PROMPT_TEMPLATE = """Recent conversation context:
{history}

User: {question}

Respond naturally and helpfully."""


def _build_history_block(history: list[ChatMessage], max_turns: int = 4) -> str:
    """Return compact recent conversation context (last max_turns exchanges)."""
    # Take up to max_turns messages (each turn = user + assistant pair)
    recent = history[-(max_turns * 2):]
    if not recent:
        return "(none)"
    lines = []
    for msg in recent:
        role = "User" if msg.role == "user" else "Assistant"
        # Cap individual history messages to avoid token bloat
        content = msg.content[:300]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_evidence_block(passages: list[PassageHit]) -> str:
    """Build compact evidence block from top 2-3 passages."""
    if not passages:
        return "(No Supreme Court evidence retrieved)"
    parts: list[str] = []
    for i, hit in enumerate(passages[:3], start=1):
        text = (hit.passage or "").strip()
        if len(text) > 800:
            text = text[:800] + "..."
        parts.append(
            f"[Evidence {i}]\n"
            f"Case: {hit.case_name}\n"
            f"Citation: {hit.citation}\n"
            f"Date: {hit.date}\n"
            f"Court: {hit.court}\n"
            f"Passage:\n{text}"
        )
    return "\n\n".join(parts)


# ── Simple in-process response cache (same-session, same-message dedup) ───────

_response_cache: dict[str, str] = {}
_CACHE_MAX = 20


def _cache_key(message: str) -> str:
    return message.strip().lower()[:200]


def _get_cached(message: str) -> Optional[str]:
    return _response_cache.get(_cache_key(message))


def _put_cache(message: str, reply: str) -> None:
    key = _cache_key(message)
    if len(_response_cache) >= _CACHE_MAX:
        # Evict oldest key
        try:
            oldest = next(iter(_response_cache))
            del _response_cache[oldest]
        except StopIteration:
            pass
    _response_cache[key] = reply


# ── Main chat entrypoint ──────────────────────────────────────────────────────

def run_chat(
    message: str,
    history: list[ChatMessage],
) -> ChatResponse:
    """Process one chatbot turn.

    Returns ChatResponse with reply, route label, and source list.
    One Gemini call per invocation. No Gemini call for routing.
    """
    from ai.rag.gemini_client import GeminiError, generate_text_with_system

    message = (message or "").strip()
    if not message:
        return ChatResponse(reply="Please type a message.", route="general")

    # Check response cache for identical repeat requests without conversation context
    if not history:
        cached = _get_cached(message)
        if cached:
            return ChatResponse(
                reply=cached,
                route="legal" if _is_legal_query(message) else "general",
            )

    is_legal = _is_legal_query(message)
    history_block = _build_history_block(history)

    # ── Legal RAG path ──────────────────────────────────────────────────────
    if is_legal:
        passages: list[PassageHit] = []
        sources: list[str] = []

        try:
            from ai.retrieval.search import semantic_search

            _, passages = semantic_search(message, top_k=3)
            # Build source labels from unique cases
            seen: set[str] = set()
            for p in passages:
                if p.case_id not in seen:
                    seen.add(p.case_id)
                    label = p.case_name
                    if p.citation and "not available" not in p.citation.lower():
                        label = f"{p.case_name} ({p.citation})"
                    sources.append(label)
        except Exception as exc:
            logger.warning("Legal retrieval failed: %s", exc)
            # Continue with empty evidence — still answer legally

        evidence_block = _build_evidence_block(passages)
        prompt = _LEGAL_PROMPT_TEMPLATE.format(
            history=history_block,
            evidence=evidence_block,
            question=message,
        )

        try:
            reply = generate_text_with_system(prompt, system_instruction=_CHAT_SYSTEM_LEGAL)
            _put_cache(message, reply)
            return ChatResponse(reply=reply, route="legal", sources=sources)
        except GeminiError as ge:
            logger.warning("Gemini chat error [%s]: %s", ge.error_category, ge.user_message)
            if "429" in ge.error_category or "quota" in ge.error_category:
                msg = "NyayaSathi AI has temporarily reached its AI request limit. Please try again shortly."
            else:
                msg = f"NyayaSathi AI is temporarily unavailable ({ge.error_category}). Please try again in a moment."
            return ChatResponse(reply=msg, route="legal")
        except Exception as exc:
            logger.exception("Unexpected chat error: %s", exc)
            return ChatResponse(
                reply="NyayaSathi AI is temporarily unavailable. Please try again in a moment.",
                route="legal",
            )

    # ── General conversational path ─────────────────────────────────────────
    prompt = _GENERAL_PROMPT_TEMPLATE.format(
        history=history_block,
        question=message,
    )

    try:
        reply = generate_text_with_system(prompt, system_instruction=_CHAT_SYSTEM_GENERAL)
        _put_cache(message, reply)
        return ChatResponse(reply=reply, route="general")
    except GeminiError as ge:
        logger.warning("Gemini chat error [%s]: %s", ge.error_category, ge.user_message)
        if "429" in ge.error_category or "quota" in ge.error_category:
            msg = "NyayaSathi AI has temporarily reached its AI request limit. Please try again shortly."
        else:
            msg = f"NyayaSathi AI is temporarily unavailable ({ge.error_category}). Please try again in a moment."
        return ChatResponse(reply=msg, route="general")
    except Exception as exc:
        logger.exception("Unexpected chat error: %s", exc)
        return ChatResponse(
            reply="NyayaSathi AI is temporarily unavailable. Please try again in a moment.",
            route="general",
        )
