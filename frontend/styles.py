CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: "Source Sans 3", "Segoe UI", sans-serif;
    color: #1c2430;
}

.stApp {
    background: #f4f6f8;
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
    max-width: 1180px;
}

section[data-testid="stSidebar"] {
    background: #10243a;
    border-right: 1px solid #0b1b2c;
}
section[data-testid="stSidebar"] * {
    color: #e8eef4 !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: transparent;
    color: #e8eef4 !important;
    border: 1px solid #35506b;
    text-align: left;
    justify-content: flex-start;
    font-weight: 500;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: #1a3654;
    border-color: #8aa4bc;
}

.ns-wordmark {
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #ffffff;
}
.ns-wordmark span {
    color: #c5d4e4;
    font-weight: 500;
    display: block;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 0.2rem;
}

/* Authentication Screen */
.ns-auth-wrapper {
    text-align: center;
    padding: 2.5rem 1rem 1rem 1rem;
    max-width: 480px;
    margin: 0 auto;
}
.ns-auth-brand {
    font-size: 2rem;
    font-weight: 700;
    color: #10243a;
    letter-spacing: 0.03em;
}
.ns-auth-subtitle {
    color: #4a5c70;
    font-size: 0.95rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 0.35rem;
    font-weight: 500;
}
.ns-auth-card {
    background: #ffffff;
    border: 1px solid #d8dee6;
    border-top: 3px solid #16324f;
    padding: 2rem 2.2rem;
    max-width: 480px;
    margin: 1.2rem auto 2rem auto;
}
.ns-auth-card h3 {
    margin: 0 0 0.3rem 0;
    color: #10243a;
    font-size: 1.3rem;
    font-weight: 600;
}

/* Hero Section */
.ns-hero {
    background: #ffffff;
    border: 1px solid #d8dee6;
    border-top: 3px solid #16324f;
    padding: 2.1rem 2rem 1.7rem 2rem;
    margin-bottom: 1.2rem;
}
.ns-brand {
    font-size: 1.55rem;
    font-weight: 700;
    color: #10243a;
    letter-spacing: 0.02em;
    margin-bottom: 0.55rem;
}
.ns-kicker {
    color: #3d5a78;
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 0.45rem;
}
.ns-hero h1 {
    font-size: 1.55rem;
    margin: 0 0 0.5rem 0;
    color: #243447;
    font-weight: 600;
}
.ns-hero p {
    margin: 0;
    color: #445062;
    font-size: 1.02rem;
    line-height: 1.55;
}

/* Cards and Panels */
.ns-card {
    background: #ffffff;
    border: 1px solid #d8dee6;
    padding: 1.05rem 1.15rem;
    margin-bottom: 0.85rem;
}
.ns-card h3 {
    margin: 0 0 0.35rem 0;
    font-size: 1.05rem;
    color: #10243a;
}
.ns-meta {
    color: #5b6b7c;
    font-size: 0.9rem;
    margin-bottom: 0.45rem;
}
.ns-score {
    display: inline-block;
    background: #eef3f8;
    color: #1e3d5c;
    padding: 0.12rem 0.5rem;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 0.45rem;
}
.ns-passage {
    color: #2c3846;
    font-size: 0.95rem;
    line-height: 1.55;
}

.ns-panel {
    background: #ffffff;
    border: 1px solid #d8dee6;
    padding: 1.2rem 1.3rem;
    margin: 0.8rem 0 1rem 0;
}
.ns-panel h2 {
    font-size: 1.05rem;
    margin: 0 0 0.7rem 0;
    color: #10243a;
    border-bottom: 1px solid #e4e9ef;
    padding-bottom: 0.45rem;
}

.ns-disclaimer {
    background: #f8f5ee;
    border: 1px solid #e4d9c5;
    color: #5a4e3a;
    padding: 0.75rem 0.95rem;
    font-size: 0.88rem;
    line-height: 1.5;
    margin-top: 1.4rem;
}

.ns-feature {
    background: #ffffff;
    border: 1px solid #d8dee6;
    padding: 1rem 1.05rem;
    height: 100%;
}
.ns-feature strong {
    display: block;
    color: #10243a;
    margin-bottom: 0.25rem;
}
.ns-feature span {
    color: #556273;
    font-size: 0.92rem;
}

.ns-analysis {
    white-space: pre-wrap;
    line-height: 1.65;
    color: #243040;
    font-size: 0.98rem;
}
.ns-analysis-heading {
    display: block;
    color: #10243a;
    font-size: 1.02rem;
    font-weight: 700;
    margin-top: 0.9rem;
    margin-bottom: 0.2rem;
    border-bottom: 1px solid #e4e9ef;
    padding-bottom: 0.15rem;
}

/* Buttons */
div.stButton > button[kind="primary"] {
    background: #16324f;
    border: 1px solid #16324f;
    color: #ffffff;
    font-weight: 600;
    border-radius: 2px;
}
div.stButton > button[kind="primary"]:hover {
    background: #10243a;
    border-color: #10243a;
}
div.stButton > button {
    border-radius: 2px;
    border: 1px solid #c5ced8;
    background: #ffffff;
    color: #16324f;
}

/* ── NyayaSathi AI Floating Chatbot ───────────────────────────────────── */

.st-key-chat_float_launcher {
    position: fixed !important;
    bottom: 28px !important;
    right: 28px !important;
    z-index: 99999 !important;
}
.st-key-chat_float_launcher button {
    width: 60px !important;
    height: 60px !important;
    border-radius: 50% !important;
    background: #16324f !important;
    color: #ffffff !important;
    font-size: 1.6rem !important;
    box-shadow: 0 4px 20px rgba(16, 36, 58, 0.45) !important;
    border: 2px solid #ffffff !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    cursor: pointer !important;
    transition: transform 0.15s ease, background 0.15s ease !important;
}
.st-key-chat_float_launcher button:hover {
    background: #0f2338 !important;
    transform: scale(1.08) !important;
    border-color: #cbd5e1 !important;
}

.st-key-chat_panel_container {
    position: fixed !important;
    bottom: 24px !important;
    right: 24px !important;
    width: 420px !important;
    max-width: calc(100vw - 32px) !important;
    height: 620px !important;
    max-height: calc(100vh - 48px) !important;
    background: #ffffff !important;
    border: 1px solid #c8d4e0 !important;
    border-top: 3px solid #16324f !important;
    box-shadow: 0 10px 40px rgba(16, 36, 58, 0.28) !important;
    border-radius: 8px !important;
    z-index: 99998 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    padding: 0.8rem 1rem !important;
}

.ns-chat-empty {
    text-align: center;
    color: #64748b;
    font-size: 0.88rem;
    padding: 2rem 1rem;
    line-height: 1.6;
}

.ns-msg-user {
    background: #16324f;
    color: #ffffff;
    padding: 0.55rem 0.85rem;
    border-radius: 12px 12px 3px 12px;
    align-self: flex-end;
    max-width: 82%;
    font-size: 0.9rem;
    line-height: 1.45;
    word-break: break-word;
    margin-bottom: 0.5rem;
    margin-left: auto;
}

.ns-msg-assistant {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    padding: 0.55rem 0.85rem;
    border-radius: 3px 12px 12px 12px;
    align-self: flex-start;
    max-width: 90%;
    font-size: 0.9rem;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    margin-bottom: 0.5rem;
}

.ns-msg-route {
    font-size: 0.72rem;
    color: #64748b;
    margin-top: 0.25rem;
    display: block;
}

.ns-msg-thinking {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #475569;
    padding: 0.5rem 0.8rem;
    border-radius: 3px 12px 12px 12px;
    align-self: flex-start;
    font-size: 0.85rem;
    font-style: italic;
    animation: ns-pulse 1.4s ease-in-out infinite;
    margin-bottom: 0.5rem;
}

@keyframes ns-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
}

.ns-chat-sources {
    font-size: 0.74rem;
    color: #475569;
    margin-top: 0.3rem;
    line-height: 1.4;
    border-top: 1px solid #e2e8f0;
    padding-top: 0.25rem;
}
"""

