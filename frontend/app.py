from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import html
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FRONTEND = Path(__file__).resolve().parent
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))

import api_client
from styles import CSS

PAGES = [
    ("home", "Home"),
    ("search", "Search"),
    ("compare", "Compare Cases"),
    ("bookmarks", "Bookmarks"),
    ("history", "History"),
    ("about", "About"),
]

DISCLAIMER = (
    "This system provides AI-assisted legal information retrieval for "
    "educational and research purposes. It is not a substitute for advice "
    "from a qualified legal professional."
)


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def init_state() -> None:
    defaults = {
        "page": "home",
        "user": None,
        "search_query": "",
        "search_result": None,
        "ask_result": None,
        "selected_case_id": None,
        "case_detail": None,
        "compare_a": "",
        "compare_b": "",
        "compare_result": None,
        "guest_history": [],
        "guest_bookmarks": [],
        "error": "",
        "health": None,
        "pending_ai_analysis": False,
        # AI analysis async state
        "analysis_status": "idle",   # idle | running | done | error
        "analysis_future": None,     # concurrent.futures.Future
        # NyayaSathi AI chatbot state
        "chat_open": False,          # collapsed by default
        "chat_messages": [],         # list of {"role": "user"|"assistant", "content": str, "route": str, "sources": list}
        "chat_processing": False,    # True while waiting for Gemini response
        "chat_input_key": 0,         # increment to clear text_input widget
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_page(page: str) -> None:
    st.session_state.page = page
    st.session_state.error = ""


def current_user_id() -> str | None:
    user = st.session_state.user
    if user:
        return user.get("id")
    return None


def relevance_pct(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{round(float(score) * 100)}%"


def escape(text: str | None) -> str:
    return html.escape(text or "")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="ns-wordmark">NyayaSearch AI<span>Indian Supreme Court research</span></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        for key, label in PAGES:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                set_page(key)
                st.rerun()
        st.write("")
        user = st.session_state.user
        if user:
            st.caption(f"Signed in as {user.get('email')}")
            if st.button("Sign out", use_container_width=True):
                st.session_state.user = None
                set_page("home")
                st.rerun()
        else:
            st.caption("Sign in to access the application.")
        health = st.session_state.health
        if health:
            indexed = "Index ready" if health.get("index_ready") else "Index not built"
            st.caption(indexed)
            st.caption(f"{health.get('collection_count', 0):,} indexed chunks")


def login_form() -> None:
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Sign in", key="login_btn"):
        try:
            data = api_client.login(email.strip(), password)
            st.session_state.user = data["user"]
            st.rerun()
        except api_client.ApiError as exc:
            st.error(str(exc))


def register_form() -> None:
    name = st.text_input("Name", key="reg_name")
    email = st.text_input("Email", key="reg_email")
    password = st.text_input("Password", type="password", key="reg_password")
    if st.button("Register", key="reg_btn"):
        try:
            data = api_client.register(email.strip(), password, name.strip())
            st.session_state.user = data["user"]
            st.rerun()
        except api_client.ApiError as split_exc:
            st.error(str(split_exc))


def disclaimer() -> None:
    st.markdown(f'<div class="ns-disclaimer">{escape(DISCLAIMER)}</div>', unsafe_allow_html=True)


def open_case(case_id: str) -> None:
    try:
        st.session_state.case_detail = api_client.get_case(case_id, similar=True)
        st.session_state.selected_case_id = case_id
        st.session_state.page = "case"
        st.session_state.error = ""
    except api_client.ApiError as exc:
        st.session_state.error = str(exc)


def save_history(query: str, result_count: int, filters: dict) -> None:
    item = {"query": query, "result_count": result_count, "filters": filters}
    user_id = current_user_id()
    if user_id:
        return
    history = st.session_state.guest_history
    history.insert(0, item)
    st.session_state.guest_history = history[:40]


def bookmark_case(case_id: str, case_name: str) -> None:
    user_id = current_user_id()
    if user_id:
        api_client.add_bookmark(user_id, case_id, case_name)
        return
    existing = [b for b in st.session_state.guest_bookmarks if b["case_id"] == case_id]
    if not existing:
        st.session_state.guest_bookmarks.insert(
            0, {"id": case_id, "case_id": case_id, "case_name": case_name}
        )


def page_home() -> None:
    st.markdown(
        """
        <div class="ns-hero">
            <div class="ns-brand">NyayaSearch AI</div>
            <div class="ns-kicker">Legal research workspace</div>
            <h1>AI-Assisted Legal Case Research</h1>
            <p>Search and explore relevant Indian Supreme Court judgments using
            semantic search and evidence-grounded AI analysis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    query = st.text_area("Describe your legal question...", key="home_query", height=90, label_visibility="collapsed", placeholder="Describe your legal question...")
    if st.button("Search Cases", type="primary"):
        st.session_state.search_query = query
        st.session_state.page = "search"
        st.session_state.run_search = True
        st.rerun()
    cols = st.columns(4)
    features = [
        ("Semantic Search", "Retrieve judgment passages by meaning, not only keywords."),
        ("AI-Assisted Analysis", "Optional grounded explanation from retrieved evidence."),
        ("Case Comparison", "Place two judgments side by side for structured review."),
        ("Source-Based Results", "Every answer is tied to retrieved Supreme Court text."),
    ]
    for col, (title, body) in zip(cols, features):
        col.markdown(
            f'<div class="ns-feature"><strong>{title}</strong><span>{body}</span></div>',
            unsafe_allow_html=True,
        )
    user = st.session_state.user
    if user:
        st.markdown("### Workspace")
        left, right = st.columns(2)
        with left:
            st.markdown('<div class="ns-panel"><h2>Recent searches</h2>', unsafe_allow_html=True)
            try:
                items = api_client.history(user["id"]).get("items", [])[:5]
                if not items:
                    st.caption("No saved searches yet.")
                for item in items:
                    if st.button(item["query"][:90], key=f"dash_q_{item['id']}"):
                        st.session_state.search_query = item["query"]
                        st.session_state.page = "search"
                        st.session_state.run_search = True
                        st.rerun()
            except api_client.ApiError as exc:
                st.caption(str(exc))
            st.markdown("</div>", unsafe_allow_html=True)
        with right:
            st.markdown('<div class="ns-panel"><h2>Bookmarked cases</h2>', unsafe_allow_html=True)
            try:
                items = api_client.bookmarks(user["id"]).get("items", [])[:5]
                if not items:
                    st.caption("No bookmarks yet.")
                for item in items:
                    if st.button(item["case_name"][:90], key=f"dash_b_{item['id']}"):
                        open_case(item["case_id"])
                        st.rerun()
            except api_client.ApiError as exc:
                st.caption(str(exc))
            st.markdown("</div>", unsafe_allow_html=True)
    disclaimer()


def _filters_from_ui() -> dict:
    filters: dict = {}
    year = st.session_state.get("flt_year")
    year_from = st.session_state.get("flt_from")
    year_to = st.session_state.get("flt_to")
    citation = st.session_state.get("flt_citation")
    if year and year != "Any":
        filters["year"] = int(year)
    if year_from and year_from != "Any":
        filters["year_from"] = int(year_from)
    if year_to and year_to != "Any":
        filters["year_to"] = int(year_to)
    if citation:
        filters["citation"] = citation.strip()
    filters["court"] = "Supreme Court of India"
    return {k: v for k, v in filters.items() if v not in (None, "", "Any")}


def execute_search_only() -> None:
    """Executes fast semantic search immediately without waiting for Gemini."""
    query = (st.session_state.search_query or "").strip()
    if len(query) < 3:
        st.session_state.error = "Enter a legal question of at least a few words."
        return
    filters = _filters_from_ui()
    try:
        result = api_client.search(
            query,
            top_k=st.session_state.get("top_k", 5),
            filters=filters,
            user_id=current_user_id(),
        )
        st.session_state.search_result = result
        st.session_state.ask_result = None
        st.session_state.error = ""
        save_history(query, result.get("result_count", 0), filters)
    except api_client.ApiError as exc:
        st.session_state.error = str(exc)


# Module-level executor shared across reruns (one thread at a time is fine for analysis)
_ANALYSIS_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _build_sources_from_result(result: dict) -> list[str]:
    """Build source labels from a search result dict (no Pydantic needed)."""
    sources = []
    seen: set[str] = set()
    for item in (result.get("results") or []):
        key = item.get("case_id", "")
        if key in seen:
            continue
        seen.add(key)
        label = item.get("case_name", key)
        citation = item.get("citation", "")
        if citation and "not available" not in citation.lower():
            label = f"{label} ({citation})"
        sources.append(label)
    return sources


def _run_analysis_in_background(query: str, passages: list, sources: list) -> dict:
    """Called in a background thread — only does the API call, no Streamlit ops."""
    try:
        return api_client.analyse(query, passages, sources)
    except api_client.ApiError as exc:
        # Return the real error message from the API (quota/auth/config/unavailable)
        # so the UI displays an accurate cause rather than a generic message.
        return {
            "analysis_available": False,
            "analysis_message": str(exc),
        }
    except Exception:
        return {
            "analysis_available": False,
            "analysis_message": "Gemini analysis could not be generated. The retrieved legal cases are still available above.",
        }


@st.fragment(run_every=1)
def _render_ai_analysis_fragment() -> None:
    """Polls analysis_future every second; renders result when ready; stops polling when done."""
    status = st.session_state.get("analysis_status", "idle")

    if status == "idle":
        # Show any previously stored ask_result (from before async refactor)
        ask = st.session_state.get("ask_result")
        if ask:
            st.markdown("---")
            st.markdown("### AI Analysis")
            if not ask.get("analysis_available"):
                st.info(ask.get("analysis_message") or "AI analysis is temporarily unavailable. The retrieved legal cases are shown above.")
            else:
                st.markdown(
                    f'<div class="ns-panel"><div class="ns-analysis">{escape(ask.get("analysis"))}</div></div>',
                    unsafe_allow_html=True,
                )
                if ask.get("sources"):
                    st.markdown("**Source cases**")
                    for src in ask["sources"]:
                        st.write(f"- {src}")
        return

    if status == "running":
        future = st.session_state.get("analysis_future")
        if future is not None and future.done():
            # Future finished — collect result and stop polling
            result = future.result()
            st.session_state.ask_result = result
            st.session_state.analysis_status = "done"
            st.session_state.analysis_future = None
            # Fall through to render immediately
            status = "done"
        else:
            st.markdown("---")
            st.markdown("### AI Analysis")
            st.info("⚙️ Analysing retrieved judgment evidence with Gemini...")
            return  # keep polling

    # status == "done" or "error"
    ask = st.session_state.get("ask_result")
    if ask:
        st.markdown("---")
        st.markdown("### AI Analysis")
        if not ask.get("analysis_available"):
            st.info(ask.get("analysis_message") or "AI analysis is temporarily unavailable. The retrieved legal cases are shown above.")
        else:
            st.markdown(
                f'<div class="ns-panel"><div class="ns-analysis">{escape(ask.get("analysis"))}</div></div>',
                unsafe_allow_html=True,
            )
            if ask.get("sources"):
                st.markdown("**Source cases**")
                for src in ask["sources"]:
                    st.write(f"- {src}")


def page_search() -> None:
    st.markdown("## Legal Case Search")
    st.caption("Semantic retrieval over Indian Supreme Court judgment chunks.")
    query = st.text_area(
        "Legal question",
        value=st.session_state.search_query,
        height=100,
        placeholder="Describe your legal question...",
    )
    st.session_state.search_query = query
    years = ["Any"] + [str(y) for y in range(2025, 1949, -1)]
    c1, c2, c3, c4 = st.columns(4)
    c1.selectbox("Year", years, key="flt_year")
    c2.selectbox("From", years, key="flt_from")
    c3.selectbox("To", years, key="flt_to")
    c4.text_input("Citation", key="flt_citation", placeholder="e.g. 2025 INSC 338")
    st.caption("Court: Supreme Court of India (dataset scope)")
    st.slider("Results", 3, 12, 5, key="top_k")

    b1, b2 = st.columns([1, 1])
    run = b1.button("Search Cases", type="primary") or st.session_state.pop("run_search", False)
    with_ai = b2.button("Search and Analyse")

    if run:
        # Plain search — reset analysis state
        st.session_state.analysis_status = "idle"
        st.session_state.analysis_future = None
        st.session_state.ask_result = None
        execute_search_only()

    if with_ai:
        # 1. Cancel any in-progress analysis future
        old_future = st.session_state.get("analysis_future")
        if old_future is not None and not old_future.done():
            old_future.cancel()
        st.session_state.ask_result = None

        # 2. Run fast semantic search immediately
        execute_search_only()

        # 3. Kick off background analysis using passages already retrieved
        result = st.session_state.search_result
        if result and result.get("passages"):
            passages = result["passages"]   # list of PassageHit dicts from JSON
            sources = _build_sources_from_result(result)
            query_text = st.session_state.search_query
            future = _ANALYSIS_EXECUTOR.submit(
                _run_analysis_in_background, query_text, passages, sources
            )
            st.session_state.analysis_future = future
            st.session_state.analysis_status = "running"
        else:
            # No passages (index not ready or no results) — mark done with nothing
            st.session_state.analysis_status = "idle"

    if st.session_state.error:
        st.warning(st.session_state.error)

    result = st.session_state.search_result
    if not result:
        return

    if result.get("message"):
        st.info(result["message"])

    # ── Immediate Search Results ──
    st.markdown("### Search Results")
    st.caption(f"{result.get('result_count', 0)} relevant cases from Supreme Court judgment chunks")

    for i, case in enumerate(result.get("results") or []):
        st.markdown(
            f"""
            <div class="ns-card">
                <h3>{escape(case.get("case_name"))}</h3>
                <div class="ns-meta">{escape(case.get("citation"))} · {escape(case.get("date"))} · {escape(case.get("court"))}</div>
                <div class="ns-score">Relevance: {relevance_pct(case.get("relevance"))}</div>
                <div class="ns-passage">{escape((case.get("relevant_passage") or "")[:520])}{"…" if len(case.get("relevant_passage") or "") > 520 else ""}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 1, 1, 3])
        if cols[0].button("View Case", key=f"view_{i}"):
            open_case(case["case_id"])
            st.rerun()
        if cols[1].button("Bookmark", key=f"bm_{i}"):
            try:
                bookmark_case(case["case_id"], case["case_name"])
                st.success("Saved.")
            except api_client.ApiError as exc:
                st.warning(str(exc))
        if cols[2].button("Compare", key=f"cmp_{i}"):
            if not st.session_state.compare_a:
                st.session_state.compare_a = case["case_id"]
            else:
                st.session_state.compare_b = case["case_id"]
            st.session_state.page = "compare"
            st.rerun()

    # ── AI Analysis section — polled independently via st.fragment ──
    _render_ai_analysis_fragment()
    disclaimer()



def page_case() -> None:
    detail = st.session_state.case_detail
    if not detail:
        st.info("Select a case from search results to open the judgment record.")
        return
    st.markdown(f"## {detail.get('case_name')}")
    st.caption(
        f"{detail.get('citation')}  ·  {detail.get('date')}  ·  {detail.get('court')}"
    )
    meta_cols = st.columns(4)
    meta_cols[0].markdown(f"**Case ID**  \n{detail.get('case_id')}")
    meta_cols[1].markdown(f"**Judges**  \n{detail.get('judges')}")
    meta_cols[2].markdown(f"**Case number**  \n{detail.get('case_number')}")
    meta_cols[3].markdown(f"**Year**  \n{detail.get('year') or 'Information not available in the dataset.'}")
    a, b, c = st.columns(3)
    if a.button("Bookmark"):
        try:
            bookmark_case(detail["case_id"], detail["case_name"])
            st.success("Case bookmarked.")
        except api_client.ApiError as exc:
            st.warning(str(exc))
    if b.button("Add to compare"):
        if not st.session_state.compare_a:
            st.session_state.compare_a = detail["case_id"]
        else:
            st.session_state.compare_b = detail["case_id"]
        st.session_state.page = "compare"
        st.rerun()
    if c.button("Find similar cases"):
        try:
            similar = api_client.similar_cases(detail["case_id"]).get("results", [])
            st.session_state.case_detail["similar"] = similar
        except api_client.ApiError as exc:
            st.warning(str(exc))

    chunks = detail.get("chunks") or []
    st.markdown("### Overview")
    st.write(
        "This record is assembled from the provided chunked Supreme Court dataset. "
        "Missing fields are shown as unavailable rather than inferred."
    )
    if detail.get("ipc") and "not available" not in str(detail.get("ipc")).lower():
        st.caption(f"IPC references in metadata: {detail.get('ipc')}")
    if detail.get("articles") and "not available" not in str(detail.get("articles")).lower():
        st.caption(f"Constitutional articles in metadata: {detail.get('articles')}")

    st.markdown("### Relevant Passage")
    if chunks:
        st.write(chunks[min(1, len(chunks) - 1)]["text"][:1800])
    else:
        st.caption("Information not available in the dataset.")

    st.markdown("### Judgment Content")
    for chunk in chunks:
        with st.expander(f"Chunk {chunk.get('chunk_id')}"):
            st.write(chunk.get("text") or "Information not available in the dataset.")

    st.markdown("### Similar Cases")
    similar = detail.get("similar") or []
    if not similar:
        st.caption("Use Find similar cases after the index has been built.")
    for item in similar:
        st.markdown(
            f"""
            <div class="ns-card">
                <h3>{escape(item.get("case_name"))}</h3>
                <div class="ns-meta">{escape(item.get("citation"))} · {escape(item.get("date"))} · Similarity {relevance_pct(item.get("relevance"))}</div>
                <div class="ns-passage">{escape((item.get("relevant_passage") or "")[:400])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Open", key=f"sim_{item.get('case_id')}"):
            open_case(item["case_id"])
            st.rerun()
    disclaimer()


def _excerpt(chunks: list, pattern: str, fallback_n: int = 2) -> str:
    joined = "\n".join(c.get("text", "") for c in chunks[:8])
    match = re.search(pattern, joined, flags=re.IGNORECASE)
    if match:
        start = max(0, match.start() - 120)
        return joined[start : start + 700]
    if chunks:
        return chunks[min(fallback_n, len(chunks) - 1)].get("text", "")[:700]
    return "Information not available in the dataset."


def page_compare() -> None:
    st.markdown("## Compare Cases")
    st.caption("Side-by-side review of two judgments from the dataset.")
    left, right = st.columns(2)
    st.session_state.compare_a = left.text_input("Case A ID", value=st.session_state.compare_a)
    st.session_state.compare_b = right.text_input("Case B ID", value=st.session_state.compare_b)
    if st.button("Compare", type="primary"):
        if not st.session_state.compare_a or not st.session_state.compare_b:
            st.warning("Select two case IDs from search results or case pages.")
        else:
            try:
                st.session_state.compare_result = api_client.compare(
                    st.session_state.compare_a, st.session_state.compare_b, include_ai=True
                )
            except api_client.ApiError as exc:
                st.session_state.error = str(exc)
    if st.session_state.error:
        st.warning(st.session_state.error)
    result = st.session_state.compare_result
    if not result:
        return
    case_a, case_b = result["case_a"], result["case_b"]
    col_a, col_b = st.columns(2)
    for col, case, label in ((col_a, case_a, "CASE A"), (col_b, case_b, "CASE B")):
        chunks = case.get("chunks") or []
        with col:
            st.markdown(f"### {label}")
            st.markdown(f"**{case.get('case_name')}**")
            st.caption(f"{case.get('date')} · {case.get('citation')}")
            st.markdown("**Facts**")
            st.write(_excerpt(chunks, r"facts|prosecution case|briefly stated", 1))
            st.markdown("**Legal issue**")
            st.write(_excerpt(chunks, r"question for consideration|issue|whether", 2))
            st.markdown("**Court reasoning**")
            st.write(_excerpt(chunks, r"we hold|in our view|reasoning|held that", 4))
            st.markdown("**Decision**")
            st.write(_excerpt(chunks, r"appeal is|petition is|dismissed|allowed|disposed", max(0, len(chunks) - 1)))
    st.markdown("### AI Comparison")
    if not result.get("comparison_available"):
        st.info(result.get("comparison_message") or "AI analysis is temporarily unavailable. The relevant cases retrieved from the legal database are shown below.")
    else:
        st.markdown(
            f'<div class="ns-panel"><div class="ns-analysis">{escape(result.get("comparison"))}</div></div>',
            unsafe_allow_html=True,
        )
    disclaimer()


def page_bookmarks() -> None:
    st.markdown("## Bookmarks")
    user_id = current_user_id()
    items = []
    if user_id:
        try:
            items = api_client.bookmarks(user_id).get("items", [])
        except api_client.ApiError as exc:
            st.warning(str(exc))
    else:
        items = st.session_state.guest_bookmarks
        st.caption("Guest bookmarks are stored in this browser session. Sign in to keep them.")
    if not items:
        st.info("No bookmarked cases yet.")
        return
    for item in items:
        st.markdown(
            f'<div class="ns-card"><h3>{escape(item.get("case_name"))}</h3><div class="ns-meta">{escape(item.get("case_id"))}</div></div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        if c1.button("Open", key=f"bopen_{item.get('id')}"):
            open_case(item["case_id"])
            st.rerun()
        if c2.button("Remove", key=f"bdel_{item.get('id')}"):
            if user_id:
                try:
                    api_client.delete_bookmark(item["id"], user_id)
                except api_client.ApiError as exc:
                    st.warning(str(exc))
            else:
                st.session_state.guest_bookmarks = [
                    b for b in st.session_state.guest_bookmarks if b["id"] != item["id"]
                ]
            st.rerun()


def page_history() -> None:
    st.markdown("## Search History")
    user_id = current_user_id()
    items = []
    if user_id:
        try:
            items = api_client.history(user_id).get("items", [])
        except api_client.ApiError as exc:
            st.warning(str(exc))
    else:
        items = st.session_state.guest_history
        st.caption("Guest history is stored in this session. Sign in to persist searches.")
    if not items:
        st.info("No previous searches.")
        return
    for i, item in enumerate(items):
        st.markdown(
            f'<div class="ns-card"><h3>{escape(item.get("query"))}</h3><div class="ns-meta">{item.get("result_count", 0)} results · {escape(str(item.get("created_at") or "this session"))}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Reopen", key=f"hist_{i}_{item.get('id', i)}"):
            st.session_state.search_query = item["query"]
            st.session_state.page = "search"
            st.session_state.run_search = True
            st.rerun()


def page_about() -> None:
    st.markdown("## About NyayaSearch AI")
    st.write(
        "NyayaSearch AI is an academic legal research system for retrieving Indian Supreme Court "
        "judgments from a locally stored, pre-chunked dataset. It is designed for law students, "
        "researchers, and demonstration before a faculty panel."
    )
    st.markdown("### Purpose")
    st.write(
        "Researchers often need to find precedents by legal issue rather than by a known citation. "
        "This application embeds judgment chunks locally and retrieves the most semantically similar passages."
    )
    st.markdown("### Dataset")
    st.write(
        "The knowledge base is the project `dataset/` directory: JSON files organised by year from 1950 to 2025. "
        "Each file contains ordered text chunks with case name, court, citation, case number, judges, IPC sections, "
        "and constitutional articles where those fields were present in the source extraction. "
        "The original files are not modified."
    )
    st.markdown("### Architecture")
    st.write(
        "A user query is embedded with a local Sentence Transformer model, searched in persistent ChromaDB, "
        "grouped by judgment for diversity, and optionally passed to Gemini for a grounded explanation. "
        "If Gemini is unavailable, retrieved cases and passages are still shown."
    )
    st.markdown("### Technology")
    st.write(
        "Python, FastAPI, Streamlit, Sentence Transformers, ChromaDB, Google Gemini (optional), "
        "and SQLite or Supabase for accounts, history, and bookmarks."
    )
    st.markdown("### Limitations")
    st.write(
        "- Retrieval quality depends on the chunk text and embedding model.\n"
        "- Some records have incomplete citation, date, or judge metadata.\n"
        "- The system does not cover High Courts or statutes outside the supplied dataset.\n"
        "- AI analysis may be unavailable when the Gemini quota or key is missing."
    )
    disclaimer()


def render_nyayasathi_chatbot() -> None:
    """Render the NyayaSathi AI floating chatbot launcher and panel.

    - Closed state: floating round button at bottom-right corner.
    - Open state: floating panel at bottom-right corner.
    - Uses st.form(clear_on_submit=True) to reliably clear input immediately upon submit.
    - Native Enter-to-send support.
    - Connects directly to existing backend /api/chat.
    """
    is_open = st.session_state.get("chat_open", False)
    processing = st.session_state.get("chat_processing", False)
    messages = st.session_state.get("chat_messages", [])

    if not is_open:
        # ── Floating Circular Launcher Button ──
        if st.button("⚖", key="chat_float_launcher", help="Open NyayaSathi AI Chatbot"):
            st.session_state.chat_open = True
            st.rerun()
        return

    # ── Floating Chat Panel ──
    with st.container(key="chat_panel_container"):
        # Header with branding and controls
        h_col1, h_col2, h_col3 = st.columns([5, 2, 1])
        with h_col1:
            st.markdown(
                '<div style="line-height:1.2;padding-top:4px;">'
                '<strong style="color:#10243a;font-size:1.05rem;">NyayaSathi AI</strong><br>'
                '<small style="color:#5b6b7c;font-size:0.76rem;">Legal • Conversational</small>'
                '</div>',
                unsafe_allow_html=True,
            )
        with h_col2:
            if st.button("Clear", key="chat_clear_btn", help="Clear chat history", use_container_width=True):
                st.session_state.chat_messages = []
                st.session_state.chat_processing = False
                st.rerun()
        with h_col3:
            if st.button("✕", key="chat_close_btn", help="Close chatbot", use_container_width=True):
                st.session_state.chat_open = False
                st.rerun()

        # Chat history container (scrollable)
        chat_box = st.container(height=390)
        with chat_box:
            if not messages and not processing:
                st.markdown(
                    '<div class="ns-chat-empty">'
                    '👋 Hi! I\'m <strong>NyayaSathi AI</strong>.<br><br>'
                    'Ask me anything, or ask a legal question to search the available Supreme Court evidence.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                for msg in messages:
                    role = msg.get("role", "user")
                    content = escape(msg.get("content", ""))
                    route = msg.get("route", "general")
                    sources = msg.get("sources") or []

                    if role == "user":
                        st.markdown(f'<div class="ns-msg-user">{content}</div>', unsafe_allow_html=True)
                    else:
                        route_badge = ""
                        if route == "legal":
                            route_badge = '<span class="ns-msg-route">⚖️ Legal · Supreme Court RAG</span>'
                        sources_html = ""
                        if sources:
                            items = "".join(f"<li>{escape(s)}</li>" for s in sources[:3])
                            sources_html = f'<div class="ns-chat-sources"><strong>Sources:</strong><ul style="margin:0.2rem 0 0 1rem;padding:0">{items}</ul></div>'
                        st.markdown(
                            f'<div class="ns-msg-assistant">{content}{route_badge}{sources_html}</div>',
                            unsafe_allow_html=True,
                        )

                if processing:
                    st.markdown(
                        '<div class="ns-msg-thinking">NyayaSathi AI is thinking…</div>',
                        unsafe_allow_html=True,
                    )

        # Input form (clear_on_submit=True clears the input automatically on submit!)
        with st.form("chat_input_form", clear_on_submit=True):
            f_col1, f_col2 = st.columns([5, 1])
            with f_col1:
                user_msg = st.text_input(
                    "Message",
                    placeholder="Type your message...",
                    disabled=processing,
                    label_visibility="collapsed",
                )
            with f_col2:
                submitted = st.form_submit_button("Send", disabled=processing, type="primary", use_container_width=True)

        # Unobtrusive disclaimer at bottom of panel
        st.markdown(
            '<div style="font-size:0.72rem;color:#718096;line-height:1.3;padding-top:2px;text-align:center;">'
            'NyayaSathi AI provides educational legal information and is not a substitute for professional legal advice.'
            '</div>',
            unsafe_allow_html=True,
        )

        # Process message submission
        if submitted and (user_msg or "").strip():
            msg_clean = user_msg.strip()
            st.session_state.chat_messages.append({"role": "user", "content": msg_clean})
            st.session_state.chat_processing = True
            st.rerun()

        # Handle backend request during processing turn
        if processing:
            msgs = st.session_state.chat_messages
            pending = msgs[-1]["content"] if msgs and msgs[-1]["role"] == "user" else None
            if pending:
                history_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in msgs[:-1]
                ]
                try:
                    result = api_client.chat(pending, history=history_for_api)
                    reply = result.get("reply", "NyayaSathi AI is temporarily unavailable. Please try again.")
                    route = result.get("route", "general")
                    sources = result.get("sources") or []
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": reply,
                        "route": route,
                        "sources": sources,
                    })
                except api_client.ApiError as exc:
                    err = str(exc)
                    if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                        reply_text = "NyayaSathi AI has temporarily reached its AI request limit. Please try again shortly."
                    elif "not running" in err.lower() or "connect" in err.lower():
                        reply_text = "Cannot connect to the backend. Please ensure the server is running."
                    elif "timed out" in err.lower():
                        reply_text = "The request timed out. Please try again."
                    else:
                        reply_text = "NyayaSathi AI is temporarily unavailable. Please try again in a moment."
                    st.session_state.chat_messages.append({
                        "role": "assistant", "content": reply_text, "route": "general", "sources": [],
                    })
                except Exception:
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": "NyayaSathi AI is temporarily unavailable. Please try again in a moment.",
                        "route": "general",
                        "sources": [],
                    })
                finally:
                    st.session_state.chat_processing = False
                st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="NyayaSearch AI",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    inject_css()
    if st.session_state.health is None:
        try:
            st.session_state.health = api_client.health()
        except api_client.ApiError as exc:
            st.session_state.health = {"index_ready": False, "collection_count": 0, "message": str(exc)}
    render_sidebar()
    if st.session_state.health and not st.session_state.health.get("index_ready") and st.session_state.page != "about":
        st.info(st.session_state.health.get("message") or "Build the local index before searching.")

    # ── Authentication gate ──────────────────────────────────────────────────
    if st.session_state.user is None:
        st.markdown(
            '<div class="ns-hero"><div class="ns-brand">NyayaSearch AI</div>'
            '<div class="ns-kicker">Indian Supreme Court research</div>'
            "<h1>Sign in to continue</h1></div>",
            unsafe_allow_html=True,
        )
        tab_login, tab_register = st.tabs(["Sign in", "Create account"])
        with tab_login:
            login_form()
        with tab_register:
            register_form()
        return
    # ────────────────────────────────────────────────────────────────────────

    page = st.session_state.page
    if page == "home":
        page_home()
    elif page == "search":
        page_search()
    elif page == "case":
        page_case()
    elif page == "compare":
        page_compare()
    elif page == "bookmarks":
        page_bookmarks()
    elif page == "history":
        page_history()
    else:
        page_about()

    # ── NyayaSathi AI Chatbot — always visible on authenticated pages ──────────
    render_nyayasathi_chatbot()


if __name__ == "__main__":
    main()
