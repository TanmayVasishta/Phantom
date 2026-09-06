"""
Shared Ollama availability breaker.

PHANTOM is designed to run cloud-first with Ollama as an optional local
component. When Ollama isn't running, every code path that touches it used to
pay the full retry cost — the Sentinel intent classifier alone burned ~12s per
query on three failed connections, which dominated total latency.

This module does a sub-second TCP probe and caches a negative result for a
cooldown window, so a missing Ollama costs milliseconds instead of seconds.
It re-probes automatically once the cooldown expires, so starting Ollama later
in the session is picked up without a restart.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from urllib.parse import urlparse

# How long to trust a "down" verdict before probing again.
COOLDOWN_SECONDS = 60.0

_lock = threading.Lock()
_down_until: float = 0.0


def _host_port() -> tuple[str, int]:
    url = (
        os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("OLLAMA_HOST")
        or "http://localhost:11434"
    )
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or 11434


def is_available(probe_timeout: float = 0.4) -> bool:
    """True if Ollama is reachable. Cheap: cached negative + fast TCP probe."""
    global _down_until

    with _lock:
        if time.time() < _down_until:
            return False

    host, port = _host_port()
    try:
        with socket.create_connection((host, port), timeout=probe_timeout):
            return True
    except OSError:
        mark_down()
        return False


def mark_down() -> None:
    """Record that Ollama is unreachable; suppress attempts for the cooldown."""
    global _down_until
    with _lock:
        _down_until = time.time() + COOLDOWN_SECONDS


def reset() -> None:
    """Clear the breaker (used by tests)."""
    global _down_until
    with _lock:
        _down_until = 0.0
