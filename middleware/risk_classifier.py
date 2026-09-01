"""Command-level risk classifier — separate from intent-level risk_scorer."""

from __future__ import annotations

import os
import re


# System directories that should not be touched by user-level commands
_SYSTEM_DIRS = [
    "/etc", "/usr", "/bin", "/sbin", "/lib", "/boot", "/sys", "/proc",
    "C:\\Windows", "C:\\System32", "C:\\Program Files",
]

# Irreversible operation keywords
_IRREVERSIBLE = re.compile(
    r"\b(rm|rmdir|del|delete|format|shred|wipe|drop|truncate)\b",
    re.IGNORECASE,
)

# Root/admin elevation
_ELEVATION = re.compile(r"\b(sudo|su|runas|admin)\b", re.IGNORECASE)


def classify_command_risk(command: str) -> int:
    """
    Calculate command-level risk score (0–100).

    This score is additive with the intent-level risk from risk_scorer.
    Used by OSMiddleware to decide whether to proceed.
    """
    score = 0

    # Irreversible operations
    if _IRREVERSIBLE.search(command):
        score += 30

    # Privilege escalation
    if _ELEVATION.search(command):
        score += 40

    # Targeting system directories
    for sys_dir in _SYSTEM_DIRS:
        if sys_dir.lower() in command.lower():
            score += 30
            break

    # Glob patterns that could affect many files (e.g. rm *.*)
    if re.search(r"\*\.\*|\*\s*\Z", command):
        score += 25

    # Pipe chains — may execute arbitrary code
    if "|" in command and re.search(r"\b(bash|sh|cmd)\b", command, re.IGNORECASE):
        score += 40

    return min(score, 100)
