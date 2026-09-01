"""Blocked command patterns — static list of dangerous OS operations."""

from __future__ import annotations

import re
from utils.exceptions import CommandBlockedError


# Patterns that must never be executed regardless of risk score or HITL approval
BLOCKED_PATTERNS: list[str] = [
    r"rm\s+-rf\s+/",         # rm -rf /
    r"rm\s+-rf\s+~",         # rm -rf ~
    r"mkfs",                  # format filesystem
    r"dd\s+if=/dev/zero",    # zero out device
    r"chmod\s+777\s+/",      # chmod 777 on root
    r"chown\s+root\s+/",     # chown root on root
    r":\(\)\s*\{\s*:\|:&\s*\}",  # fork bomb
    r"curl.*\|\s*bash",       # curl | bash (arbitrary code execution)
    r"wget.*\|\s*bash",       # wget | bash
    r"curl.*\|\s*sh",         # curl | sh
    r">\s*/dev/sda",          # write to raw disk
    r"shred\s+/dev",          # shred disk device
    r"dd\s+of=/dev/sd",       # write to disk device
    r"rm\s+.*--no-preserve-root",  # rm with no-preserve-root
    r"sudo\s+rm\s+-rf\s+/",  # sudo rm -rf /
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def is_blocked(command: str) -> bool:
    """Return True if the command matches any blocked pattern."""
    return any(p.search(command) for p in _COMPILED_PATTERNS)


def assert_not_blocked(command: str) -> None:
    """Raise CommandBlockedError if the command is blocked."""
    if is_blocked(command):
        raise CommandBlockedError(
            f"Command blocked by safety policy: {command[:80]}"
        )
