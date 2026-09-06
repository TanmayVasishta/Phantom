"""
PHANTOM — Ollama Auto-Starter Utility

Checks if Ollama is running. If not, starts it silently in the background
and waits up to `timeout_s` seconds for it to become ready.

Call ensure_ollama_running() early in startup (phantom_ui.py, main.py).
This is a no-op if Ollama is already running — safe to call every time.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import logging

logger = logging.getLogger(__name__)

_OLLAMA_EXE = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Local", "Programs", "Ollama", "ollama.exe"
)
_OLLAMA_URL = "http://localhost:11434"


def is_ollama_running(timeout: float = 2.0) -> bool:
    """Return True if Ollama is reachable within `timeout` seconds."""
    try:
        import urllib.request
        with urllib.request.urlopen(_OLLAMA_URL, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def start_ollama() -> bool:
    """
    Start `ollama serve` in the background (hidden window, no terminal).
    Returns True if the executable was found and launched.
    """
    exe = _OLLAMA_EXE
    if not os.path.exists(exe):
        # Try PATH fallback
        import shutil
        found = shutil.which("ollama")
        if found:
            exe = found
        else:
            logger.error("[Ollama] Cannot find ollama.exe at %s or on PATH", _OLLAMA_EXE)
            return False

    logger.info("[Ollama] Starting ollama serve in background...")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [exe, "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except Exception as exc:
        logger.error("[Ollama] Failed to start: %s", exc)
        return False


def ensure_ollama_running(timeout_s: int = 20, on_status=None) -> bool:
    """
    Ensure Ollama is running before PHANTOM starts.

    Args:
        timeout_s  : seconds to wait for Ollama to become ready after launching
        on_status  : optional callable(str) — receives status messages for UI display

    Returns True if Ollama is ready, False if it could not be started in time.
    """
    def _status(msg: str) -> None:
        logger.info(msg)
        if callable(on_status):
            on_status(msg)

    # Fast path — already running
    if is_ollama_running(timeout=2.0):
        _status("[Ollama] Already running (OK)")
        return True

    _status("[Ollama] Not running — starting automatically...")
    launched = start_ollama()
    if not launched:
        _status("[Ollama] Could not launch. Please start Ollama manually.")
        return False

    # Poll until ready
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(1.5)
        if is_ollama_running(timeout=2.0):
            _status("[Ollama] Ready (OK)")
            return True
        _status(f"[Ollama] Waiting... ({int(deadline - time.time())}s)")

    _status(f"[Ollama] Did not respond within {timeout_s}s. Continuing anyway.")
    return False
