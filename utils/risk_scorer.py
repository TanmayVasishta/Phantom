"""
Tier 1 risk scorer — local, pure Python, zero API calls.

Weighted signal sum over the raw user input. Every weight is additive and the
result is clamped to [0.0, 1.0]. This runs on every non-controlled turn, so
it must stay in the single-digit-millisecond range: compiled patterns only,
no NLP, no network.

Bands the Guardian acts on:
    < 0.3   proceed
    0.3-0.7 escalate to the Guardian LLM (Tier 2)
    > 0.7   escalate to the human (Tier 3)
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from utils.input_guard import INJECTION_PATTERNS

# ── Signal weights ───────────────────────────────────────────────────────────
W_INJECTION = 0.9
W_DESTRUCTIVE = 0.8
W_DESTRUCTIVE_INTENT = 0.4
W_WRITE_OUTSIDE_HOME = 0.6
W_CREDENTIALS = 0.5
W_EXCESSIVE_LENGTH = 0.2
W_ALL_CAPS = 0.1
W_SYSTEM_INTERNALS = 0.3
W_KNOWN_SAFE = -0.3

EXCESSIVE_LENGTH_CHARS = 2000

# Literal shell/SQL destruction. No trailing \b: "rm -rf" ends mid-token
# ("rm -r" + "f"), so a closing boundary there never matches and the whole
# signal silently never fires — verified against `rm -rf C:\...` scoring 0.00.
DESTRUCTIVE_COMMANDS = re.compile(
    r"\b(rm\s+-[rf]+|rmdir\b|del\s+/[sq]|format\s+[a-z]:|mkfs|dd\s+if="
    r"|drop\s+(table|database)\b|truncate\s+table\b|shred\b|diskpart\b)",
    re.IGNORECASE,
)

# Natural-language destructive intent. Deliberately scored well below the
# literal-command weight: "delete the old log files" is an ordinary request
# that deserves a second look (Tier 2), not an automatic human interrupt,
# whereas a typed `rm -rf` is unambiguous on its face.
DESTRUCTIVE_INTENT = re.compile(
    r"\b(delete|remove|erase|wipe|purge|destroy|uninstall)\b[^.?!]{0,40}?"
    r"\b(file|files|folder|folders|directory|directories|everything|all|"
    r"data|backup|backups|log|logs|disk|drive|partition)\b",
    re.IGNORECASE,
)

# A path that is clearly outside the user's own profile directory.
WRITE_OUTSIDE_HOME = re.compile(
    r"(?:[A-Za-z]:\\(?!Users\\)[^\s\"']{2,}"          # C:\Windows\..., D:\...
    r"|(?<![\w.])/(?:etc|usr|bin|sbin|var|boot|sys|proc)(?:/[^\s\"']*)?)",
)

CREDENTIALS = re.compile(
    r"\b(password|passwd|api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token|"
    r"bearer\s+token|private[_\s-]?key|credential|\.env\b|ssh[_\s-]?key)\b",
    re.IGNORECASE,
)

SYSTEM_INTERNALS = re.compile(
    r"\b(system\s+prompt|your\s+(instructions|prompt|rules|guidelines)|"
    r"initial\s+prompt|reveal\s+your|print\s+your\s+(prompt|instructions)|"
    r"what\s+are\s+your\s+instructions)\b",
    re.IGNORECASE,
)

KNOWN_SAFE = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank\s+you|good\s+(morning|afternoon|evening))\b"
    r"|^\s*(what|who|when|where|why|how)\s+(is|are|was|were|do|does|did|can|much|many)\b"
    r"|^\s*(tell\s+me\s+about|explain|summarize|summarise|define)\b",
    re.IGNORECASE,
)

ALL_CAPS_AGGRESSIVE = re.compile(r"\b[A-Z]{4,}\b")


@dataclass
class RiskResult:
    score: float
    signals_fired: list[str] = field(default_factory=list)
    tier_used: str = "local"
    reason: str = ""
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "signals_fired": list(self.signals_fired),
            "tier_used": self.tier_used,
            "reason": self.reason,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


def _all_caps_aggressive(text: str) -> bool:
    """
    Shouty phrasing — but only when it is actually shouting, not when the
    text merely contains an acronym like SSN or PDF.
    """
    caps_words = ALL_CAPS_AGGRESSIVE.findall(text)
    if not caps_words:
        return False
    words = [w for w in re.findall(r"[A-Za-z]{2,}", text)]
    if not words:
        return False
    return (len(caps_words) / len(words)) > 0.3


def score(text: str, mode: str = "smart") -> RiskResult:
    """Score `text` for risk. `mode` == 'controlled' short-circuits to safe."""
    import time
    t0 = time.perf_counter()
    text = text or ""
    signals: list[str] = []
    total = 0.0

    if mode == "controlled":
        # Deterministic OS commands were already matched by an anchored
        # pattern in the mode classifier; they never reach an LLM.
        return RiskResult(score=0.0, signals_fired=["controlled_mode"],
                          tier_used="local",
                          elapsed_ms=(time.perf_counter() - t0) * 1000)

    for pattern, reason in INJECTION_PATTERNS:
        if pattern.search(text):
            total += W_INJECTION
            signals.append(f"injection:{reason.split('(')[0].strip()}")
            break  # one injection hit already maxes this signal

    if DESTRUCTIVE_COMMANDS.search(text):
        total += W_DESTRUCTIVE
        signals.append("destructive_command")
    elif DESTRUCTIVE_INTENT.search(text):
        # elif: a literal command already covers the intent — don't stack both.
        total += W_DESTRUCTIVE_INTENT
        signals.append("destructive_intent")

    if WRITE_OUTSIDE_HOME.search(text):
        total += W_WRITE_OUTSIDE_HOME
        signals.append("path_outside_home")

    if CREDENTIALS.search(text):
        total += W_CREDENTIALS
        signals.append("credentials_mentioned")

    if len(text) > EXCESSIVE_LENGTH_CHARS:
        total += W_EXCESSIVE_LENGTH
        signals.append("excessive_length")

    if _all_caps_aggressive(text):
        total += W_ALL_CAPS
        signals.append("all_caps_phrasing")

    if SYSTEM_INTERNALS.search(text):
        total += W_SYSTEM_INTERNALS
        signals.append("system_internals_probe")

    # Only discount when nothing risky fired. A blanket bonus lets a
    # question-shaped probe ("what is my api key password") buy back 0.3 and
    # slip under the review threshold purely for opening with "what is" —
    # the safe-phrasing bonus is meant for genuinely unremarkable input, not
    # as a discount on input that already tripped a real signal.
    if not signals and KNOWN_SAFE.search(text):
        total += W_KNOWN_SAFE
        signals.append("known_safe_pattern")

    final = max(0.0, min(1.0, total))
    return RiskResult(
        score=final,
        signals_fired=signals,
        tier_used="local",
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
