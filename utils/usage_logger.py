"""
Persistent token-usage log.

router.status() only ever showed the current 60s window. This appends one
JSON line per successful call to ./phantom_memory/usage_log.jsonl so usage
and cost can be tracked across restarts.

Never blocks or raises into the call path: a logging failure must not take
down a request that already succeeded.
"""

from __future__ import annotations

import json
import os
import threading
import time

# Anchored to the project root, NOT the process working directory. A bare
# relative path here would resolve against wherever the app happened to be
# launched from — the exact bug that put a `data` folder under System32
# earlier in this project.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE_LOG_PATH = os.path.join(_PROJECT_ROOT, "phantom_memory", "usage_log.jsonl")

_lock = threading.Lock()


def log_usage(
    provider: str,
    model: str,
    tokens_used: int,
    window_tokens: int,
    window_limit: int,
    session_id: str = "unknown",
    log_path: str = USAGE_LOG_PATH,
) -> None:
    """Append one usage record. Silently degrades on any I/O failure."""
    entry = {
        "ts": int(time.time()),
        "provider": provider,
        "model": model,
        "tokens_used": int(tokens_used),
        "window_tokens": int(window_tokens),
        "window_limit": int(window_limit),
        "session_id": session_id or "unknown",
    }
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        line = json.dumps(entry) + "\n"
        with _lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        # Usage logging is observability, never a hard dependency of a call
        # that has already succeeded.
        pass


def read_usage(since_ts: float | None = None, log_path: str = USAGE_LOG_PATH) -> list[dict]:
    """Read usage records, optionally filtered to entries at/after since_ts."""
    entries: list[dict] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # skip a torn/partial line rather than dying
                if since_ts is not None and entry.get("ts", 0) < since_ts:
                    continue
                entries.append(entry)
    except FileNotFoundError:
        return []
    except Exception:
        return entries
    return entries


def summarize(hours: float = 24.0, log_path: str = USAGE_LOG_PATH) -> dict:
    """
    Group usage over the last `hours` by provider.

    Returns: {"gemini": {"calls": 14, "tokens": 8420}, ...}
    """
    cutoff = time.time() - (hours * 3600.0)
    summary: dict[str, dict[str, int]] = {}
    for entry in read_usage(since_ts=cutoff, log_path=log_path):
        provider = entry.get("provider", "unknown")
        bucket = summary.setdefault(provider, {"calls": 0, "tokens": 0})
        bucket["calls"] += 1
        bucket["tokens"] += int(entry.get("tokens_used", 0))
    return summary
