"""
HELIX — Main Entry Point

Startup sequence:
  1. Health check (abort on critical failure)
  2. Backup ChromaDB (if running in persistent mode)
  3. Launch helix_app.py (LangGraph interactive CLI)

Voice HUD (PyQt6) has been descoped in the revised architecture.
OS Middleware has been replaced by the MCP stub in mcp_tools/clipboard_stub.py.

To run the old GUI (for reference only):
    python -c "from hud.voice_hud import VoiceHUD; ..."
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    from utils.health_check import run_health_check

    health = run_health_check()
    print(health.report())

    # Abort on critical service failures only
    critical = {"Ollama + LLM", "ChromaDB"}
    failed_critical = {
        k for k, v in health.checks.items() if not v["ok"] and k in critical
    }
    if failed_critical:
        print(f"[HELIX] Critical services unavailable: {failed_critical}")
        print("[HELIX] Fix the above errors before starting HELIX.")
        sys.exit(1)

    # Backup ChromaDB before any writes this session (persistent mode only)
    if os.environ.get("HELIX_SESSION_ONLY", "").lower() != "true":
        try:
            from memory.chroma_manager import ChromaManager
            cm = ChromaManager()
            backup_path = cm.backup()
            print(f"[HELIX] ChromaDB backed up → {backup_path}")
        except Exception as e:
            print(f"[HELIX] ChromaDB backup skipped: {e}")

    # Launch LangGraph CLI
    from helix_app import interactive_mode
    import uuid
    interactive_mode(thread_id=str(uuid.uuid4()))


if __name__ == "__main__":
    main()

