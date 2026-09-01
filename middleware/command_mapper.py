"""
Command mapper — translates NL intent + entities into safe OS command strings.

Also provides dry_run_description() for human-readable previews (shown in HITL
dialog for ALL commands, not just high-risk ones — Improvement 3 from CLAUDE.md).
"""

from __future__ import annotations

import os
import re
import subprocess

from utils.models import IntentType


# ── Intent → Command Templates ────────────────────────────────────────────────

def map_intent_to_command(
    intent: IntentType | str,
    sub_intent: str,
    entities: list[str],
) -> str:
    """
    Translate an intent + entities into a concrete OS command string.

    Returns empty string if the combination cannot be mapped.
    """
    intent_str = intent.value if isinstance(intent, IntentType) else str(intent).upper()
    sub = sub_intent.lower()
    ents = [e.strip() for e in entities if e.strip()]

    if intent_str == "FILE_OP":
        return _map_file_op(sub, ents)
    elif intent_str == "SYSTEM_CMD":
        return _map_system_cmd(sub, ents)
    return ""


def _map_file_op(sub_intent: str, entities: list[str]) -> str:
    """Map FILE_OP sub-intents to OS commands."""
    if not entities:
        return ""

    target = entities[0]
    dest = entities[1] if len(entities) > 1 else ""

    # Normalise relative paths to home-relative
    if not target.startswith(("~", "/", "C:", "D:")):
        target = f"~/{target}"

    if sub_intent in ("delete", "remove", "rm"):
        return f"rm -i {target}"  # -i = interactive confirmation as extra safety

    if sub_intent in ("list", "ls", "show", "view"):
        return f"ls -lah {target}"

    if sub_intent in ("create", "make", "new", "touch"):
        if "." in os.path.basename(target):
            return f"touch {target}"
        return f"mkdir -p {target}"

    if sub_intent in ("copy", "cp"):
        dest_path = dest if dest else "."
        return f"cp -r {target} {dest_path}"

    if sub_intent in ("move", "mv", "rename"):
        dest_path = dest if dest else "."
        return f"mv {target} {dest_path}"

    if sub_intent in ("find", "search", "locate"):
        return f"find ~/ -name '{target}' 2>/dev/null"

    if sub_intent == "open":
        return f"xdg-open {target} 2>/dev/null || start {target}"

    return ""


def _map_system_cmd(sub_intent: str, entities: list[str]) -> str:
    """Map SYSTEM_CMD sub-intents to OS commands."""
    target = entities[0] if entities else ""

    if sub_intent in ("list_processes", "processes", "ps"):
        return "ps aux" if os.name != "nt" else "tasklist"

    if sub_intent in ("disk_usage", "disk", "du"):
        return f"df -h {target}" if target else "df -h"

    if sub_intent in ("memory", "ram", "mem"):
        return "free -h" if os.name != "nt" else "wmic memorychip get capacity"

    if sub_intent in ("cpu", "top"):
        return "top -bn1 | head -20" if os.name != "nt" else "wmic cpu get loadpercentage"

    return ""


# ── Dry-Run Preview ───────────────────────────────────────────────────────────

def dry_run_description(
    command: str,
    intent: str = "",
    entities: list[str] | None = None,
) -> str:
    """
    Generate a human-readable description of what a command will do.
    Does NOT execute the command.
    """
    entities = entities or []
    cmd = command.strip()

    patterns = [
        (r"ls\s+",          lambda _: f"List contents of: {' '.join(entities) or 'directory'}"),
        (r"rm\s+",          lambda _: f"Delete: {' '.join(entities)}"),
        (r"mkdir\s+",       lambda _: f"Create directory: {' '.join(entities)}"),
        (r"touch\s+",       lambda _: f"Create empty file: {' '.join(entities)}"),
        (r"cp\s+",          lambda _: f"Copy {entities[0] if entities else '?'} to {entities[1] if len(entities)>1 else 'destination'}"),
        (r"mv\s+",          lambda _: f"Move {entities[0] if entities else '?'} to {entities[1] if len(entities)>1 else 'destination'}"),
        (r"find\s+.*-delete", lambda _: f"Delete files matching pattern: {_count_matching(command)}"),
        (r"find\s+",        lambda _: f"Search for: {' '.join(entities)}"),
    ]

    for pattern, describer in patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            try:
                return describer(None)
            except Exception:
                break

    return f"Execute: {cmd[:80]}{'...' if len(cmd) > 80 else ''}"


def _count_matching(command: str) -> str:
    """Count files that WOULD be matched without deleting them."""
    try:
        safe_cmd = re.sub(r"-delete", "", command, flags=re.IGNORECASE)
        result = subprocess.run(
            safe_cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        return f"{len(lines)} files would be affected"
    except Exception:
        return "unknown number of files"
