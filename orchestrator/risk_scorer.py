"""
Risk scorer — calculates risk_score for an intent + command combination.

Formula (Tanmay's original contribution — Section 8.2):
  score = sum of RISK_WEIGHTS for matching keywords in sub_intent + command
  +20 if command touches paths outside ~/Documents, ~/Downloads, ~/Desktop, ~/Pictures
  capped at 100

HITL fires when risk_score > RISK_THRESHOLD_HITL (40).
"""

from __future__ import annotations

import os

from utils.config import RISK_THRESHOLD_HITL


# Keyword → weight mapping. Do not change weights without updating the paper spec.
RISK_WEIGHTS: dict[str, int] = {
    "delete":   50,
    "remove":   50,
    "format":   80,
    "wipe":     80,
    "install":  40,
    "download": 35,
    "send":     30,
    "email":    30,
    "password": 70,
    "sudo":     90,
    "chmod":    60,
    "rm":       55,
    "uninstall": 45,
    "kill":     40,
    "terminate": 40,
    "overwrite": 55,
    "truncate": 50,
    "drop":     70,
    "purge":    75,
}

# Safe directories — commands staying within these get no extra penalty
_SAFE_DIRS: list[str] = [
    "~/documents",
    "~/downloads",
    "~/desktop",
    "~/pictures",
    "~/music",
    "~/videos",
]


def calculate_risk_score(
    sub_intent: str, entities: list[str], command: str
) -> int:
    """
    Compute a numeric risk score for a proposed action.

    Returns int in range [0, 100].
    """
    combined = f"{sub_intent} {command} {' '.join(entities)}".lower()

    score = 0
    for keyword, weight in RISK_WEIGHTS.items():
        if keyword in combined:
            score += weight

    # Extra penalty for commands that target paths outside safe directories
    if command and not any(d in command.lower() for d in _SAFE_DIRS):
        # Also check expanded home dir
        home = os.path.expanduser("~").lower().replace("\\", "/")
        safe_abs = [os.path.expanduser(d).lower().replace("\\", "/") for d in _SAFE_DIRS]
        if not any(d in command.lower().replace("\\", "/") for d in safe_abs):
            score += 20

    return min(score, 100)


def risk_level(score: int) -> tuple[str, str]:
    """
    Return (level_name, hex_colour) for a given risk score.

    Used to colour-code the HITL dashboard panel.
    """
    if score < 20:
        return "LOW", "#22c55e"        # green
    elif score <= RISK_THRESHOLD_HITL:
        return "MEDIUM", "#f59e0b"     # amber
    elif score <= 70:
        return "HIGH", "#ef4444"       # red
    else:
        return "CRITICAL", "#7f1d1d"   # dark red
