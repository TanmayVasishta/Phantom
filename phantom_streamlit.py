"""
PHANTOM Chat — Streamlit front end.

Talks to the LangGraph pipeline in phantom_graph.py. Handles the HITL
approval gate: when the graph pauses on a high-risk action, this renders an
approve/reject panel showing exactly which files would be touched, then
resumes the paused graph with the user's decision.

Visual layer only below the CSS/HEADER/SIDEBAR markers — no pipeline, HITL,
or session-state *decision* logic was changed from the prior version. See
the note above each addition for exactly what's new and why.
"""
import streamlit as st
import uuid
import sys
import os
import time

# Ensure PHANTOM root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from phantom_graph import run_query, resume_query, prewarm_pipeline

st.set_page_config(page_title="PHANTOM Chat", page_icon="🔒", layout="centered")


# ═══════════════════════════════════════════════════════════════════════════
# GLASSMORPHISM THEME — single CSS injection, verified against the real
# Streamlit DOM (not guessed selectors). Two spec selectors don't exist and
# were swapped for the real equivalents:
#   .stChatMessage[data-testid="user"]   -> no such attribute exists;
#       Streamlit nests data-testid="stChatMessageAvatarUser/Assistant"
#       *inside* the message instead, so role targeting uses :has().
#   .stTextInput > div > div > input     -> this app uses st.chat_input, not
#       st.text_input; the real element is textarea[data-testid=
#       "stChatInputTextArea"].
# The floating input bar uses Streamlit's own position:sticky container
# (data-testid="stBottom") rather than forcing position:fixed — overriding
# Streamlit's own layout containers to fixed is a common way to break its
# scroll math; sticky achieves the same pinned-to-bottom look safely.
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)
# Split from the <link> markdown call above: combining the font <link> tags
# and this <style> block in one st.markdown() silently truncates the style
# tag's content partway through in this Streamlit version, leaking the rest
# of the CSS as literal page text. Two calls render both correctly.
st.markdown("""<style>
:root {
    --pt-bg: #0a0a0f;
    --pt-glass: rgba(255, 255, 255, 0.05);
    --pt-glass-border: rgba(255, 255, 255, 0.08);
    --pt-accent: #7c3aed;
    --pt-accent-glow: rgba(124, 58, 237, 0.3);
    --pt-text: #f1f5f9;
    --pt-text-muted: #64748b;
    --pt-user-bg: rgba(124, 58, 237, 0.15);
    --pt-ai-bg: rgba(255, 255, 255, 0.04);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Base app background ─────────────────────────────────────────────── */
.stApp {
    background: var(--pt-bg);
    color: var(--pt-text);
}

/* ── Custom header row (replaces the old st.title/st.caption pair) ───── */
.pt-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0 14px 0;
    border-bottom: 1px solid var(--pt-glass-border);
    margin-bottom: 18px;
}
.pt-header-title {
    font-weight: 500;
    font-size: 22px;
    letter-spacing: -0.02em;
    color: var(--pt-text);
    display: flex;
    align-items: center;
    gap: 10px;
}
.pt-header-sub {
    font-size: 13px;
    color: var(--pt-text-muted);
    margin-top: 2px;
}
.pt-status-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 8px #22c55e;
    flex-shrink: 0;
}
.pt-status-dot.pt-live {
    animation: pt-pulse 1.1s ease-in-out infinite;
}
@keyframes pt-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(1.3); }
}

/* ── Sidebar: darker glass, blur(30px) ────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(10, 10, 15, 0.85);
    backdrop-filter: blur(30px);
    -webkit-backdrop-filter: blur(30px);
    border-right: 1px solid var(--pt-glass-border);
}
.pt-logo {
    color: var(--pt-accent);
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 0.1em;
    padding: 4px 0 12px 0;
}
.pt-divider {
    height: 1px;
    background: linear-gradient(90deg, var(--pt-accent), transparent);
    margin-bottom: 16px;
    opacity: 0.6;
}
.pt-section-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--pt-text-muted);
    margin: 14px 0 8px 0;
    font-weight: 500;
}

/* Provider pill badges */
.pt-pill-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
}
.pt-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid transparent;
}
.pt-pill-dot { width: 6px; height: 6px; border-radius: 50%; }
.pt-pill.healthy   { background: rgba(34,197,94,0.12);  color: #4ade80; border-color: rgba(34,197,94,0.25); }
.pt-pill.healthy   .pt-pill-dot { background: #4ade80; }
.pt-pill.quarantined { background: rgba(239,68,68,0.12); color: #f87171; border-color: rgba(239,68,68,0.25); }
.pt-pill.quarantined .pt-pill-dot { background: #f87171; }
.pt-pill.saturated { background: rgba(148,163,184,0.10); color: #94a3b8; border-color: rgba(148,163,184,0.2); }
.pt-pill.saturated .pt-pill-dot { background: #94a3b8; }
.pt-provider-name { font-size: 12px; color: var(--pt-text); font-family: monospace; }

/* Token usage bars */
.pt-bar-track {
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 10px;
}
.pt-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--pt-accent), #a78bfa);
    border-radius: 2px;
}

.pt-session-line {
    font-size: 12px;
    color: var(--pt-text-muted);
    margin-bottom: 3px;
}
.pt-session-line b { color: var(--pt-text); font-weight: 500; }

/* ── Chat messages: glass panels ──────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: var(--pt-ai-bg);
    border: 1px solid var(--pt-glass-border);
    border-radius: 16px;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    padding: 4px 6px;
    margin-bottom: 12px;
    animation: pt-fadeInUp 0.3s ease;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: var(--pt-user-bg);
    border-left: 3px solid var(--pt-accent);
    border-top: 1px solid var(--pt-glass-border);
    border-right: 1px solid var(--pt-glass-border);
    border-bottom: 1px solid var(--pt-glass-border);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: var(--pt-ai-bg);
}
@keyframes pt-fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
[data-testid="stChatMessageContent"] p {
    font-size: 14px;
    line-height: 1.6;
    color: var(--pt-text);
}

/* Per-message timestamp + copy affordance */
.pt-msg-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
}
.pt-timestamp {
    font-size: 11px;
    color: var(--pt-text-muted);
    text-align: right;
}
/* Copy button is a real st.button (see CHAT AREA section for why raw HTML
   onclick handlers don't work in Streamlit) — hidden until the message
   row is hovered, revealed via :has() reaching back up to the block. */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.pt-copy-anchor) button {
    opacity: 0;
    transition: opacity 0.15s ease;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 4px !important;
    min-height: unset !important;
    color: var(--pt-text-muted) !important;
    font-size: 11px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.pt-copy-anchor):hover button {
    opacity: 1;
}

/* ── Typing indicator: restyle Streamlit's own spinner as 3 pulsing dots ─
   The st.spinner(...) call in the app code is untouched; this only hides
   its default icon/text and draws three dots via ::before/::after instead. */
[data-testid="stSpinner"] {
    display: flex;
    align-items: center;
    gap: 5px;
    min-height: 20px;
}
[data-testid="stSpinner"] > div:first-child { display: none; }
[data-testid="stSpinner"] p { display: none; }
[data-testid="stSpinner"]::before,
[data-testid="stSpinner"]::after,
[data-testid="stSpinner"] > div:last-child::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--pt-accent);
    display: inline-block;
    animation: pt-dot-pulse 1.2s ease-in-out infinite;
}
[data-testid="stSpinner"]::after { animation-delay: 0.2s; }
[data-testid="stSpinner"] > div:last-child::before { animation-delay: 0.4s; }
@keyframes pt-dot-pulse {
    0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
    40%           { opacity: 1;    transform: scale(1.15); }
}

/* ── Floating input bar (Streamlit's own sticky bottom container) ────── */
[data-testid="stBottom"] {
    background: rgba(10, 10, 15, 0.75);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-top: 1px solid var(--pt-glass-border);
}
[data-testid="stChatInput"] {
    background: var(--pt-glass);
    border: 1px solid var(--pt-glass-border);
    border-radius: 14px;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--pt-accent);
    box-shadow: 0 0 0 3px var(--pt-accent-glow);
}
textarea[data-testid="stChatInputTextArea"] {
    color: var(--pt-text) !important;
    font-size: 14px !important;
}

/* ── Buttons: glass + violet hover glow ───────────────────────────────── */
.stButton > button {
    background: var(--pt-glass) !important;
    border: 1px solid var(--pt-glass-border) !important;
    color: var(--pt-text) !important;
    border-radius: 10px !important;
    transition: box-shadow 0.2s ease, border-color 0.2s ease !important;
}
.stButton > button:hover {
    border-color: var(--pt-accent) !important;
    box-shadow: 0 0 14px var(--pt-accent-glow) !important;
}
.stButton > button[kind="primary"] {
    background: var(--pt-accent) !important;
    border-color: var(--pt-accent) !important;
}

/* Headers/expanders/etc. pick up the same weight + tracking as the spec */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-weight: 500;
    letter-spacing: -0.02em;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "thread_id": None,
    "messages": [],
    "hitl_pending": False,
    "hitl_data": None,
    "pending_query": None,
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default
if st.session_state.thread_id is None:
    st.session_state.thread_id = str(uuid.uuid4())


# ── One-time model warm-up ────────────────────────────────────────────────────
# spaCy, Presidio, the embedder and the cross-encoder take ~30-90s to load on
# first use. Doing that lazily inside the first query blew the request timeout
# and surfaced as "Groq API key may be missing" — a misleading error for what
# is really just a cold start. Load them once, up front, with honest feedback.
@st.cache_resource(show_spinner=False)
def _warm_up():
    prewarm_pipeline()
    return True


with st.spinner("Loading PHANTOM models (first run only, ~1 min)…"):
    _warm_up()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _meta_from(result: dict) -> dict:
    return {
        "pii": result.get("n_pii_redacted", 0),
        "provider": result.get("provider_used", ""),
        "latency": result.get("latency_ms", 0),
        "risk": result.get("risk_score", 0),
    }


def _append_assistant(result: dict):
    """Append a reply, guaranteeing the bubble is never empty."""
    content = (result.get("final_response") or result.get("response") or "").strip()
    if not content:
        content = "_(PHANTOM returned no text for that request.)_"
    st.session_state.messages.append(
        {"role": "assistant", "content": content, "meta": _meta_from(result),
         "ts": time.strftime("%H:%M")}
    )


def _render_meta(meta: dict):
    parts = []
    if meta.get("pii", 0) > 0:
        parts.append(f"🛡 {meta['pii']} PII stripped")
    if meta.get("provider"):
        parts.append(str(meta["provider"]))
    if meta.get("latency"):
        parts.append(f"{meta['latency']}ms")
    if meta.get("risk"):
        parts.append(f"risk {float(meta['risk']):.2f}")
    if parts:
        st.caption("  ·  ".join(parts))


# ═══════════════════════════════════════════════════════════════════════════
# HEADER — slim top bar: "PHANTOM" left, connection status dot right.
# The dot's pulse state reads st.session_state.pending_query, which already
# exists for pipeline control — this only *reads* it to drive a CSS class,
# it doesn't add any new state or change when queries run.
# ═══════════════════════════════════════════════════════════════════════════
_in_flight = bool(st.session_state.get("pending_query"))
st.markdown(f"""
<div class="pt-header">
  <div>
    <div class="pt-header-title">🔒 PHANTOM</div>
    <div class="pt-header-sub">Privacy-First AI Agent · Local Tools · HITL</div>
  </div>
  <div class="pt-status-dot {'pt-live' if _in_flight else ''}" title="{'call in flight' if _in_flight else 'live'}"></div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — logo, divider, router status pills + usage bars, session info.
# The router status block is READ-ONLY: it calls llm_router.get_router()'s
# existing status_all()/daily_summary() (built for exactly this purpose in
# an earlier pass) purely to display state. It never influences routing,
# and is wrapped so a display glitch here can never break the chat itself.
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="pt-logo">⬡ PHANTOM</div><div class="pt-divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="pt-section-label">Providers</div>', unsafe_allow_html=True)
    try:
        from llm_router import get_router
        _router = get_router()
        _statuses = _router.status_all()
        _pill_html = []
        for name, s in _statuses.items():
            pct = (s["tokens_remaining"] / s["limit"] * 100) if s["limit"] else 100
            if not s.get("has_key"):
                cls, label = "saturated", "no key"
            elif not s.get("healthy"):
                cls, label = "quarantined", f"back off {s.get('backoff_remaining_seconds', 0):.0f}s"
            elif pct < 15:
                cls, label = "saturated", "saturated"
            else:
                cls, label = "healthy", "healthy"
            used_pct = 100 - pct
            _pill_html.append(f"""
            <div class="pt-pill-row">
              <span class="pt-provider-name">{name}</span>
              <span class="pt-pill {cls}"><span class="pt-pill-dot"></span>{label}</span>
            </div>
            <div class="pt-bar-track"><div class="pt-bar-fill" style="width:{used_pct:.1f}%"></div></div>
            """)
        st.markdown("".join(_pill_html), unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"Router status unavailable: {e}")

    st.markdown('<div class="pt-section-label">Session</div>', unsafe_allow_html=True)
    _last_provider = "—"
    for _m in reversed(st.session_state.messages):
        if _m.get("role") == "assistant" and _m.get("meta", {}).get("provider"):
            _last_provider = _m["meta"]["provider"]
            break
    st.markdown(f"""
    <div class="pt-session-line">Thread <b>{st.session_state.thread_id[:8]}</b></div>
    <div class="pt-session-line">{len(st.session_state.messages)} message(s)</div>
    <div class="pt-session-line">Last model: <b>{_last_provider}</b></div>
    """, unsafe_allow_html=True)

    if st.button("🧹 New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.hitl_pending = False
        st.session_state.hitl_data = None
        st.session_state.pending_query = None
        st.rerun()
    st.divider()
    st.caption(
        "**Try:** list my downloads · find duplicates in downloads · "
        "make an html summary page · draft an email to someone@example.com"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TRANSCRIPT — same message loop, now with a timestamp and (assistant-only)
# copy affordance. A genuinely working copy-to-clipboard needed an actual
# st.button: I verified first that a raw <button onclick="..."> injected via
# st.markdown(unsafe_allow_html=True) is stripped by Streamlit's sanitizer
# (tested in isolation — the onclick never fires), so a real widget backed
# by pyperclip is the only way to make "click to copy" actually work rather
# than just look clickable. It reads clipboard state only; it never touches
# routing, HITL, or the message content itself.
# ═══════════════════════════════════════════════════════════════════════════
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "meta" in msg:
            _render_meta(msg["meta"])
        ts = msg.get("ts", "")
        if msg["role"] == "assistant":
            st.markdown('<span class="pt-copy-anchor"></span>', unsafe_allow_html=True)
            fcol1, fcol2 = st.columns([10, 1])
            with fcol1:
                if ts:
                    st.markdown(f'<div class="pt-timestamp">{ts}</div>', unsafe_allow_html=True)
            with fcol2:
                if st.button("📋", key=f"copy_{i}", help="Copy to clipboard"):
                    try:
                        import pyperclip
                        pyperclip.copy(msg["content"])
                        st.toast("Copied", icon="📋")
                    except Exception:
                        st.toast("Clipboard unavailable", icon="⚠️")
        elif ts:
            st.markdown(f'<div class="pt-timestamp">{ts}</div>', unsafe_allow_html=True)


# ── Process a queued query ────────────────────────────────────────────────────
# The user's message is appended and rendered on the previous rerun, so it
# appears instantly instead of only showing up once the reply is finished.
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None

    with st.chat_message("assistant"):
        with st.spinner("PHANTOM is working…"):
            try:
                result = run_query(
                    query,
                    thread_id=st.session_state.thread_id,
                    verbose=False,
                    timeout=180,
                )
            except Exception as e:
                result = {"final_response": f"Error: {e}"}

    if result.get("hitl_required"):
        _append_assistant(result)
        st.session_state.hitl_pending = True
        st.session_state.hitl_data = result
    else:
        _append_assistant(result)
    st.rerun()


# ── HITL approval gate ────────────────────────────────────────────────────────
def _handle_decision(decision: str):
    """Resume the paused graph and record the outcome."""
    with st.spinner("Executing…" if decision == "approve" else "Cancelling…"):
        try:
            result = resume_query(decision, st.session_state.thread_id)
        except Exception as e:
            result = {"final_response": f"Error resuming: {e}"}

    st.session_state.hitl_pending = bool(result.get("hitl_required"))
    st.session_state.hitl_data = result if result.get("hitl_required") else None
    _append_assistant(result)
    st.rerun()


if st.session_state.hitl_pending:
    data = st.session_state.hitl_data or {}
    payload = data.get("hitl_payload") or {}
    action = payload.get("action") or "a high-risk action"
    affected = payload.get("affected") or []
    risk = data.get("risk_score") or payload.get("risk_score") or 0

    st.warning(f"⚠️ **Approval required** — risk score `{float(risk):.2f}`\n\n{action}")

    if affected:
        with st.expander(f"Show the {len(affected)} file(s) this will affect", expanded=True):
            for item in affected:
                st.code(item, language=None)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            _handle_decision("approve")
    with col2:
        if st.button("❌ Reject", use_container_width=True):
            _handle_decision("reject")


# ── Input ─────────────────────────────────────────────────────────────────────
if not st.session_state.hitl_pending:
    if prompt := st.chat_input("Ask PHANTOM anything..."):
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "ts": time.strftime("%H:%M")}
        )
        st.session_state.pending_query = prompt
        st.rerun()
