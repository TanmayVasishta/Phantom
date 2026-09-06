"""
PHANTOM — Main Entry Point

Startup sequence:
  1. Auto-start Ollama if not running (non-blocking, background)
  2. Backup ChromaDB (if running in persistent mode)
  3. Launch phantom_ui.py (Spotlight overlay + tray daemon)

Usage:
    python main.py               # launch UI
    python phantom_ui.py         # same, direct
    python phantom_app.py        # CLI mode
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    # 1. Auto-start Ollama (non-blocking — just fires it off)
    try:
        from utils.ollama_autostart import is_ollama_running, start_ollama
        if not is_ollama_running(timeout=1.5):
            print("[PHANTOM] Ollama not running — starting automatically...")
            start_ollama()
            print("[PHANTOM] Ollama starting in background. UI will be ready shortly.")
        else:
            print("[PHANTOM] Ollama already running.")
    except Exception as e:
        print(f"[PHANTOM] Ollama auto-start skipped: {e}")

    # 2. Backup ChromaDB (persistent mode only)
    if os.environ.get("PHANTOM_SESSION_ONLY", "").lower() != "true":
        try:
            from phantom_graph import _get_chroma
            cm = _get_chroma()
            backup_path = cm.backup()
            print(f"[PHANTOM] ChromaDB backed up to {backup_path}")
        except Exception as e:
            print(f"[PHANTOM] ChromaDB backup skipped: {e}")

    # 3. Launch the Spotlight overlay UI
    import subprocess
    subprocess.Popen(
        [sys.executable, "phantom_ui.py"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print("[PHANTOM] UI launched. Check system tray or press Ctrl+Shift+P.")


if __name__ == "__main__":
    main()
