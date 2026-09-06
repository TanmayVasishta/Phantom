"""
PHANTOM 3-Tier Risk Scorer
Replaces the broken single-tier keyword scorer.

Tier 1: Instant safe/danger rules — O(1), no LLM
Tier 2: Weighted keyword scoring with safe modifiers
Tier 3: Ollama semantic judgment (only for ambiguous 0.3–0.7 range)

Thresholds:
  >= 0.7  → HITL interrupt fires
  >= 0.3  → log only, no interrupt
  <  0.3  → completely safe, do nothing

Tanmay Vasishta — HITL Risk Module
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

INTERRUPT_THRESHOLD = 0.7
LOG_THRESHOLD       = 0.3

# Tier 1 — Instant safe word set (exact full query match or contained)
SAFE_WORDS: set[str] = {
    "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
    "sure", "got it", "yes", "no", "bye", "goodbye", "good morning",
    "good evening", "good night", "great", "nice", "cool",
    "what is", "who is", "explain", "define", "tell me", "help me",
    "how are you", "what are you", "what can you do",
    "summarize", "summarise", "describe", "list", "give me",
    "write a poem", "tell me a joke", "write a story",
}

# Tier 1 — Instant danger patterns (substring match, word-boundary safe)
INSTANT_DANGER: list[str] = [
    "rm -rf", "rm -r", "format c:", "format d:", "del /f /s",
    "deltree", ":(){:|:&};:", "sudo rm", "reg delete",
    "net user /add", "net localgroup administrators",
    "rd /s /q", "takeown /f", "icacls /grant",
]

# Tier 2 — Keyword groups
# NOTE: These are substring matches on the FULL query (lowercased).
# Use multi-word anchors where needed to prevent false positives.
DELETION_WORDS:   list[str] = [
    "delete",                          # catches delete the/my/all/file/duplicates/…
    "remove the", "remove my", "remove file", "remove all",
    "erase ", "erase all",
    "wipe ", "wipe out", "wipe all",
    "purge ", "purge all",
    "uninstall", "rm -",
]
EXECUTION_WORDS:  list[str] = [
    "execute", "run script", "run this script", "run the script",
    "run this python", "run command", "open terminal",
    "cmd.exe", "powershell", "batch file", "run the command",
    ".bat", ".ps1", ".sh",
]
EXFIL_WORDS:      list[str] = [
    "send my", "upload my", "share my", "email my",
    "post my", "transmit my", "export my", "send to",
]
FILE_INDICATORS:  list[str] = [
    ".exe", "c:\\", "d:\\", "/etc/", "/home/",
    "appdata", "system32", "c:/", "d:/",
]
SYSTEM_WORDS:     list[str] = [
    "registry", "regedit", "hkey", "run as admin",
    "elevated privilege", "uac bypass", "administrator",
]
FORMAT_WORDS:     list[str] = [
    "format my", "format the", "format c", "format d",
    "format drive", "format disk",
]
# Borderline — adds 0.3 score (logs only, no interrupt by itself)
BORDERLINE_READ_WORDS: list[str] = [
    "open the file", "open file", "read file", "read my file",
    "show file", "view file", "open my file",
    "clipboard", "paste from", "read clipboard",
]
SAFE_MODIFIERS:   list[str] = [
    "write a poem", "tell me a joke", "write a story",
    "what is", "what are", "who is", "define",
    "how does", "tell me about", "describe",
    "give me a list", "can you explain", "explain",
    "summarize", "summarise",
]

# Tool calls that always force an interrupt, regardless of text score —
# these names must stay in sync with tools.file_tools.HIGH_RISK_TOOLS.
# A worded-ambiguously destructive request (e.g. "clean up my downloads")
# can score 0.0 on text alone; without this the LLM's tool call would
# execute with no HITL confirmation at all.
SENSITIVE_TOOLS: set[str] = {"delete_files", "delete_all_duplicates", "delete_folder", "draft_email"}
BORDERLINE_TOOLS: set[str] = {"read_clipboard"}


# ── Tier 1 ─────────────────────────────────────────────────────────────────────

def _apply_tier1(query: str) -> float | None:
    """
    Returns 0.0 (instant safe) or 1.0 (instant danger), or None if ambiguous.
    This is O(1) and never calls an LLM.
    """
    q = query.strip()
    q_lower = q.lower()

    # Instant safe: very short queries (< 10 chars) are always greetings
    if len(q) < 10:
        return 0.0

    # Instant safe: full query is a known safe word/phrase
    if q_lower in SAFE_WORDS:
        return 0.0

    # Instant safe: query STARTS with a safe word (covers "what is X", "explain Y")
    for sw in SAFE_WORDS:
        if q_lower.startswith(sw):
            return 0.0

    # Instant danger: contains a known shell-level destructive command
    for pattern in INSTANT_DANGER:
        if pattern in q_lower:
            return 1.0

    return None  # proceed to Tier 2


# ── Tier 2 ─────────────────────────────────────────────────────────────────────

def _apply_tier2(query: str) -> float:
    """
    Weighted keyword scoring. Each group contributes at most once.
    Returns float in [0.0, 1.0].

    Weight design:
      - Format (0.9)    → always interrupt
      - Deletion (0.7)  → crosses INTERRUPT_THRESHOLD alone
      - Execution (0.7) → crosses threshold alone
      - Exfil (0.7)     → crosses threshold alone
      - System (0.5)    → borderline alone, over with file indicator
      - File indicator (0.3) → additive risk only
      - Borderline read (0.3) → logs only, never interrupts alone
      - Safe modifiers (-0.5) → pull clearly safe queries back to 0
    """
    q = query.lower()
    score = 0.0

    # Format/wipe commands — highest severity
    if any(w in q for w in FORMAT_WORDS):
        score += 0.9

    # Deletion words — crosses threshold on its own
    if any(w in q for w in DELETION_WORDS):
        score += 0.7

    # Execution — crosses threshold alone
    if any(w in q for w in EXECUTION_WORDS):
        score += 0.7

    # Exfiltration — crosses threshold alone
    if any(w in q for w in EXFIL_WORDS):
        score += 0.7

    # System / privilege words — high severity
    if any(w in q for w in SYSTEM_WORDS):
        score += 0.5

    # File path / extension indicators — additive risk
    if any(w in q for w in FILE_INDICATORS):
        score += 0.3

    # Borderline read/clipboard — low risk on its own (0.3 = log but no interrupt)
    if any(w in q for w in BORDERLINE_READ_WORDS):
        score += 0.3

    # Safe modifiers — subtract strongly to protect benign queries
    if any(w in q for w in SAFE_MODIFIERS):
        score -= 0.5

    return round(max(0.0, min(1.0, score)), 2)


# ── Tier 3 ─────────────────────────────────────────────────────────────────────

def _apply_tier3(query: str, tier2_score: float) -> float:
    """
    Ollama semantic judgment for ambiguous queries (tier2 in 0.3–0.7).
    Uses qwen3.5:2b — fastest local model, 5s timeout.
    Returns adjusted score.
    """
    system_prompt = (
        "You are a security classifier for an AI assistant. "
        "Classify the user query as SAFE or DANGEROUS.\n\n"
        "DANGEROUS = involves deleting files, executing system commands, "
        "sending user data externally, modifying system settings, "
        "escalating privileges, or any irreversible system action.\n\n"
        "SAFE = questions, explanations, creative writing, conversation, "
        "reading information, summarizing, or coding help with no execution.\n\n"
        "Reply with exactly one word: SAFE or DANGEROUS. "
        "No explanation. No punctuation. Just the word."
    )
    from utils.ollama_health import is_available
    if not is_available():
        logger.info("[HITL Tier3] Ollama unavailable (cached) — using Tier2 score")
        return tier2_score

    try:
        import requests
        payload = {
            "model": "qwen3.5:2b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}"},
            ],
            "stream": False,
        }
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=5,
        )
        if resp.status_code == 200:
            answer = resp.json().get("message", {}).get("content", "").strip().upper()
            if "DANGEROUS" in answer:
                result = max(tier2_score, 0.8)
            else:
                result = min(tier2_score, 0.2)
            logger.info("[HITL Tier3] Ollama verdict=%s → score=%.2f", answer, result)
            return result
    except Exception as e:
        logger.warning("[HITL Tier3] Ollama unavailable: %s — using Tier2 score", e)

    return tier2_score  # fallback: trust Tier 2


# ── Main Entry Point ───────────────────────────────────────────────────────────

def compute_risk(query: str, tool_call: dict | None = None) -> float:
    """
    3-tier risk scorer.

    Args:
        query     : The RAW user input (before PII redaction).
                    Scored locally — never sent to cloud.
        tool_call : Optional dict with {"name": "file_delete", ...} if a
                    LangGraph tool was invoked.

    Returns:
        float in [0.0, 1.0]. >= 0.7 → HITL interrupt should fire.
    """
    # Tier 1: instant safe/danger rules
    tier1 = _apply_tier1(query)
    if tier1 is not None:
        logger.info("[HITL Tier1] Instant result=%.2f for query=%r", tier1, query[:40])
        return tier1

    # Tier 2: weighted keyword scoring
    tier2_score = _apply_tier2(query)
    logger.info("[HITL Tier2] Keyword score=%.2f for query=%r", tier2_score, query[:40])

    # Tier 3: Ollama semantic judgment only for ambiguous range
    if LOG_THRESHOLD <= tier2_score <= INTERRUPT_THRESHOLD:
        final = _apply_tier3(query, tier2_score)
    else:
        final = tier2_score

    # Tool call boost: if a sensitive tool was actually invoked, force an
    # interrupt regardless of text score. A wording like "clean up my
    # downloads" can score 0.0 on text alone; a small additive boost isn't
    # enough to guarantee the interrupt threshold is crossed, and the graph
    # unconditionally executes the tool after hitl_check_node either way.
    if tool_call:
        tool_name = tool_call.get("name", "")
        if tool_name in SENSITIVE_TOOLS:
            final = max(final, INTERRUPT_THRESHOLD)
            logger.info("[HITL] Sensitive tool %r detected → forcing interrupt (score=%.2f)", tool_name, final)
        elif tool_name in BORDERLINE_TOOLS:
            final = min(1.0, final + 0.1)

    logger.info("[HITL] Final risk score=%.2f for query=%r", final, query[:40])
    return round(final, 2)
