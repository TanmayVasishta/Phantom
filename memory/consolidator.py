"""
Async memory consolidation — runs AFTER the response is already on its way
back to the user, never in the request path.

Per turn:
  1. write the turn to L1 (always)
  2. scan for durable facts, write any to L3 (always)
  3. every 5th turn, summarise the session into L2 via the router

Durable-fact extraction is regex-based on purpose: it runs on every single
turn, so it has to be free. The L2 summary is the only step that spends an
API call, and it is amortised across five turns.
"""
from __future__ import annotations

import logging
import re
import threading

logger = logging.getLogger(__name__)

L2_SUMMARY_EVERY_N_TURNS = 5
L2_SUMMARY_TOKENS = 150

SUMMARY_PROMPT = (
    "Summarize this conversation exchange in 2-3 sentences, focusing on key "
    "facts, decisions, and user intent. Be specific. Turns:\n{turns}"
)

# ── Durable fact patterns ────────────────────────────────────────────────────
# Each captures the fact-bearing clause, not just the trigger word, so what
# lands in L3 reads as a statement rather than a bare verb.
DURABLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("preference", re.compile(
        r"\b(i\s+(?:prefer|like|hate|love|always|never)\s+[^.!?;\n]{2,120})", re.IGNORECASE)),
    ("identity", re.compile(
        r"\b((?:i\s+am|i'm)\s+(?:a|an)\s+[^.!?;\n]{2,120}"
        r"|my\s+name\s+is\s+[^.!?;\n]{2,80}"
        r"|i\s+(?:work|study)\s+at\s+[^.!?;\n]{2,80})", re.IGNORECASE)),
    ("goal", re.compile(
        r"\b((?:i\s+want\s+to|i'm\s+trying\s+to|i\s+am\s+trying\s+to|my\s+goal\s+is)"
        r"\s+[^.!?;\n]{2,120})", re.IGNORECASE)),
    ("correction", re.compile(
        r"\b((?:that's\s+wrong|actually\s+i|no,?\s+i)\s*[^.!?;\n]{0,120})", re.IGNORECASE)),
]


def extract_durable_facts(text: str) -> list[tuple[str, str]]:
    """Returns [(kind, fact_text)] for every durable pattern that fires."""
    if not text or not text.strip():
        return []
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, pattern in DURABLE_PATTERNS:
        for match in pattern.finditer(text):
            fact = " ".join(match.group(1).split()).strip(" ,;:")
            key = fact.lower()
            if fact and key not in seen:
                seen.add(key)
                found.append((kind, fact))
    return found


def _summarize_turns(turns: list[str]) -> str:
    """One router call (Groq speed lane) to compress recent turns into L2."""
    try:
        from llm_router import get_router, safe_content
        from langchain_core.messages import HumanMessage

        joined = "\n".join(f"- {t}" for t in turns[-L2_SUMMARY_EVERY_N_TURNS:])
        prompt = SUMMARY_PROMPT.format(turns=joined)
        response, provider = get_router().invoke(
            [HumanMessage(content=prompt)],
            estimated_tokens=L2_SUMMARY_TOKENS,
            stream=False,
            session_id="consolidator",
        )
        summary = safe_content(response).strip()
        logger.info("[L2] summary written via %s (%d chars)", provider, len(summary))
        return summary
    except Exception as exc:
        logger.warning("[L2] summarization failed: %s", exc)
        return ""


def consolidate(turn_text: str, session_id: str, turn_count: int,
                layered, recent_turns: list[str] | None = None,
                user_text: str | None = None) -> dict:
    """
    Synchronous consolidation body. Call via consolidate_async() from the
    request path — this is only directly callable so tests can await the
    result deterministically instead of racing a daemon thread.

    `turn_text` is the full turn record ("user → assistant") and is what L1
    stores verbatim. `user_text` is the user's utterance alone and is the
    ONLY thing L3 scans for durable facts; see below for why that separation
    is load-bearing. Callers with just one string (migration, tests) can omit
    it and both fall back to `turn_text`.
    """
    report = {"l1": False, "l3_facts": [], "l2": False}

    if layered is None:
        return report

    # 1. L1 — always, full turn verbatim
    report["l1"] = layered.write_working(turn_text, session_id)

    # 2. L3 — durable facts, always scanned, USER TEXT ONLY.
    #
    # Scanning the combined turn lets the assistant's own reply write
    # permanent "user facts". Verified against the live patterns:
    #   "who are you → I am an AI model. I never store your personal data."
    # extracts identity "I am an AI model" and preference "I never store
    # your personal data" — both attributed to the user, in the one layer
    # that never expires and is injected into every future session's
    # [DURABLE FACTS] block. That is the model poisoning its own long-term
    # memory. It also truncates cleanly: a fact near the end of the user's
    # text otherwise runs through the " → " into the reply, which is how
    # "I want to add voice input later → acknowledged" got stored.
    for kind, fact in extract_durable_facts(user_text or turn_text):
        outcome = layered.write_durable(fact, source_session=session_id, kind=kind)
        if outcome in ("added", "updated"):
            report["l3_facts"].append({"kind": kind, "fact": fact, "outcome": outcome})

    # 3. L2 — every Nth turn
    if turn_count > 0 and turn_count % L2_SUMMARY_EVERY_N_TURNS == 0:
        turns = recent_turns or layered.retrieve_working(
            turn_text, session_id, k=L2_SUMMARY_EVERY_N_TURNS
        )
        if turns:
            summary = _summarize_turns(turns)
            if summary:
                report["l2"] = layered.write_episodic(summary, session_id, turn_count)

    return report


def consolidate_async(turn_text: str, session_id: str, turn_count: int,
                      layered, recent_turns: list[str] | None = None,
                      user_text: str | None = None) -> threading.Thread:
    """Fire-and-forget. The response path must never wait on memory writes."""
    def _run():
        try:
            consolidate(turn_text, session_id, turn_count, layered,
                        recent_turns, user_text)
        except Exception as exc:
            logger.warning("[CONSOLIDATE] failed: %s", exc)

    thread = threading.Thread(target=_run, daemon=True, name="phantom-consolidator")
    thread.start()
    return thread
