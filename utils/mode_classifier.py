"""
Leon-style 3-mode execution classifier.

Runs before anything else in the pipeline (regex only, no LLM call) to decide
how much of the pipeline a query actually needs:

  controlled — a deterministic OS command ("open Chrome", "volume up").
               No LLM call is needed at all; skips straight to a stub action.
  agent      — a multi-step task ("research X and Y", "step by step").
               Runs the normal pipeline with state["agent_mode"] = True,
               reserved for future multi-step planning.
  smart      — everything else. The existing sentinel → LLM → save pipeline,
               unchanged. This is the default: an ambiguous or borderline
               query should fall through to the full pipeline rather than
               risk a wrong deterministic action or a silently degraded
               multi-step run.

Ordering matters: controlled is checked first (it's the narrowest, most
literal category and the one with the biggest payoff — zero API calls), then
agent, and smart is whatever matches neither.
"""
from __future__ import annotations

import re
from typing import Literal

Mode = Literal["controlled", "smart", "agent"]

# ── Controlled: deterministic OS commands ────────────────────────────────────
_APP_ACTION = re.compile(
    r"^\s*(open|launch|start|close|quit|exit|kill|stop)\s+[\w .+#-]+\s*$",
    re.IGNORECASE,
)
_VOLUME = re.compile(
    r"^\s*(volume|sound)\s+(up|down|mute|unmute)\s*$"
    r"|^\s*(set|turn)\s+(the\s+)?volume\s+(to\s+)?\d{1,3}%?\s*$"
    r"|^\s*(mute|unmute)(\s+the\s+(volume|sound))?\s*$",
    re.IGNORECASE,
)
_BRIGHTNESS = re.compile(
    r"^\s*(brightness)\s+(up|down)\s*$"
    r"|^\s*(increase|decrease|raise|lower)\s+(the\s+)?brightness\s*$"
    r"|^\s*(set|turn)\s+(the\s+)?brightness\s+(to\s+)?\d{1,3}%?\s*$",
    re.IGNORECASE,
)
_INPUT_SIM = re.compile(
    r"^\s*(type|click|double[\s-]?click|right[\s-]?click|scroll)\b",
    re.IGNORECASE,
)
# Read-only duplicate-file scanning only — anchored to the whole input like
# every other controlled pattern here, not a bare substring match, so
# "find duplicate handling logic in my code" (about code, not files) does
# not get hijacked into a filesystem scan. Deliberately does NOT include
# "remove"/"delete duplicate" phrasings: controlled mode skips guardian_node
# entirely (see route_after_mode), so a destructive action routed through it
# would run with zero risk-scoring and zero HITL approval — exactly what
# HIGH_RISK_TOOLS (delete_all_duplicates is one) exists to prevent. Deletion
# stays on the normal smart-mode path where that gate actually runs.
_FIND_DUPLICATES = re.compile(
    r"^\s*(find|scan|check|look\s+for)\s+(for\s+)?(duplicate|duplicates|dupes)"
    r"(\s+files?)?(\s+in\s+.+)?\s*$",
    re.IGNORECASE,
)

# Radios and screen lock. Both are reversible by the user in one click, which
# is the bar for controlled mode (it skips guardian_node, so nothing routed
# here is risk-scored or approved). Anchored whole-input like the rest, so
# "explain how bluetooth pairing works" stays a normal question.
_RADIO = re.compile(
    r"^\s*(?:turn|switch|toggle)\s+(?:on|off)\s+(?:the\s+)?(?:bluetooth|bt|wi-?fi|wireless)\s*$"
    r"|^\s*(?:bluetooth|bt|wi-?fi|wireless)\s+(?:on|off)\s*$"
    r"|^\s*(?:enable|disable)\s+(?:the\s+)?(?:bluetooth|bt|wi-?fi|wireless)\s*$"
    # State questions, kept in step with _RE_RADIO in utils/system_actions.py —
    # when the two disagree the router sends it to controlled mode and the
    # dispatcher then can't parse it, which surfaces as the raw "Running: ..."
    # stub instead of an answer.
    r"|^\s*(?:is|are|what'?s|whats)\s+(?:the\s+)?(?:bluetooth|bt|wi-?fi|wireless)"
    r"(?:\s+(?:on|off|status|state))?\s*\??\s*$"
    r"|^\s*(?:bluetooth|bt|wi-?fi|wireless)(?:\s+(?:status|state))?\s*$",
    re.IGNORECASE,
)
_LOCK_SCREEN = re.compile(
    r"^\s*lock\s+(?:the\s+)?(?:screen|pc|computer|workstation|desktop)\s*$",
    re.IGNORECASE,
)

CONTROLLED_PATTERNS: list[re.Pattern] = [
    _APP_ACTION, _VOLUME, _BRIGHTNESS, _INPUT_SIM, _FIND_DUPLICATES,
    _RADIO, _LOCK_SCREEN,
]

# ── Agent: multi-step tasks ───────────────────────────────────────────────────
_RESEARCH_AND = re.compile(
    r"\bresearch\b.+\band\b", re.IGNORECASE,
)
_STEP_BY_STEP = re.compile(r"\bstep[\s-]by[\s-]step\b", re.IGNORECASE)
_CREATE_REPORT = re.compile(r"\b(create|write|generate|produce|compile)\b.+\breport\b", re.IGNORECASE)
_MULTI_STEP_CONJUNCTION = re.compile(
    r"\b(first|then|after that|next|finally)\b.*\b(then|after|finally|next)\b",
    re.IGNORECASE,
)

AGENT_PATTERNS: list[re.Pattern] = [
    _RESEARCH_AND, _STEP_BY_STEP, _CREATE_REPORT, _MULTI_STEP_CONJUNCTION,
]


def classify_mode(text: str) -> Mode:
    """
    Classify `text` into one of the three execution modes. Pure regex, no
    LLM call — this has to be fast and free, since its whole purpose is
    deciding whether an LLM call is needed at all.
    """
    text = (text or "").strip()
    if not text:
        return "smart"

    for pattern in CONTROLLED_PATTERNS:
        if pattern.search(text):
            return "controlled"

    for pattern in AGENT_PATTERNS:
        if pattern.search(text):
            return "agent"

    return "smart"
