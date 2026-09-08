"""
Phantom Agent 2.0 — entry point.

Self-contained privacy-first agent. Reuses the parent project's PhantomRouter
for cloud routing; everything else lives under agent_v2/.

Run: python agent_v2/main.py
Hotkey: Ctrl+Space
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(os.path.join(_PARENT, ".env"))

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from agent_v2.pipeline import PhantomPipeline
from agent_v2.ui.window import PhantomAgent2Window

# ── Preload cache ────────────────────────────────────────────────────────────
# Records that a preload has succeeded before, plus how long it took, so a
# repeat launch can start quietly and tell the user what wait to expect.
#
# What this does NOT do is make the load faster, and it deliberately does not
# short-circuit to "Ready". Measured on this machine, Presidio's AnalyzerEngine
# costs ~15.9s in EVERY process: 15.64s cold, 15.93s with a warm OS page cache,
# 15.94s on an immediate relaunch. The cost is building the recognizer registry
# and NLP engine (CPU), not reading model files (disk), so neither the OS cache
# nor a previous process helps. Printing "Ready" off the back of this file
# would advertise the agent as usable roughly 16 seconds before it is.
PRELOAD_SENTINEL = os.path.join(_HERE, "data", ".preload_complete")
SENTINEL_MAX_AGE_S = 7 * 24 * 3600


def _read_preload_sentinel() -> dict | None:
    """Previous successful preload, or None if absent/stale/unreadable."""
    try:
        import json
        with open(PRELOAD_SENTINEL, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        import time as _t
        if _t.time() - data.get("timestamp", 0) > SENTINEL_MAX_AGE_S:
            return None
        if not data.get("engines_ok"):
            return None
        return data
    except Exception:
        return None


def _write_preload_sentinel(duration_s: float, status: dict) -> None:
    try:
        import json
        import time as _t
        os.makedirs(os.path.dirname(PRELOAD_SENTINEL), exist_ok=True)
        with open(PRELOAD_SENTINEL, "w", encoding="utf-8") as fh:
            json.dump({
                "version": 1,
                "timestamp": _t.time(),
                "duration_s": round(duration_s, 2),
                "status": status,
                "engines_ok": all(v == "ok" for v in status.values()),
                "python": sys.version.split()[0],
            }, fh, indent=2)
    except Exception:
        pass  # a cache file failing to write must never break startup


class PreloadWorker(QThread):
    """Warms Presidio, spaCy and the Chroma embedder off the GUI thread."""
    done = pyqtSignal(dict, float)   # status, duration_seconds

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self._pipeline = pipeline

    def run(self) -> None:
        import time as _t
        t0 = _t.perf_counter()
        try:
            status = self._pipeline.preload()
        except Exception as exc:
            status = {"error": str(exc)}
        self.done.emit(status, _t.perf_counter() - t0)


class HotkeyListener(QThread):
    """Global Ctrl+Space (v1 moved to Ctrl+Shift+Space so the two don't collide)."""
    triggered = pyqtSignal()

    def run(self) -> None:
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+space", lambda: self.triggered.emit())
            keyboard.wait()
        except Exception as exc:
            print(f"[PHANTOM 2.0] Hotkey listener error: {exc}")


def _tray_icon() -> QIcon:
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    p.setPen(QColor("#7c3aed"))
    p.drawText(0, 0, 22, 22, Qt.AlignmentFlag.AlignCenter, "⬡")
    p.end()
    return QIcon(px)


def main() -> int:
    # Single instance — see utils/instance_lock.py. Agent 2.0 keeps its own
    # lock name so it never contends with, or surfaces, Agent 1.0.
    import atexit
    from utils.instance_lock import InstanceLock

    lock = InstanceLock("Phantom2")
    if not lock.acquire():
        print("[PHANTOM 2.0] Already running. Bringing the existing window to focus.")
        lock.signal_focus()
        return 0
    atexit.register(lock.release)

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    # Before QApplication — see utils/crash_logger.py and the identical
    # placement in phantom_ui.py (v1). Same threading architecture, same
    # diagnostic added for parity.
    from utils.crash_logger import install as install_crash_logger
    install_crash_logger(os.path.join(_HERE, "phantom_crash.log"))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("PHANTOM 2.0")

    cached = _read_preload_sentinel()
    if cached:
        # Warm start: the engines have loaded successfully before, so skip the
        # per-component announcement and just say what wait to expect.
        print(f"[PHANTOM 2.0] Warm start — engines verified previously "
              f"(last preload {cached['duration_s']:.0f}s). Loading...")
    else:
        print("[PHANTOM 2.0] Privacy engine loading...")

    pipeline = PhantomPipeline()
    window = PhantomAgent2Window(pipeline)

    tray = QSystemTrayIcon(_tray_icon())
    tray.setToolTip("Phantom 2.0 — Initializing privacy engine...")
    menu = QMenu()
    menu.setStyleSheet("""
        QMenu { background: #14141a; color: #e5e5e5; border: 1px solid #2e2e2e;
                border-radius: 8px; padding: 4px; font-size: 13px; }
        QMenu::item:selected { background: #2e2e2e; border-radius: 4px; }
    """)
    menu.addAction("Show").triggered.connect(window.show_window)
    menu.addAction("New Session").triggered.connect(window.new_session)
    menu.addSeparator()
    menu.addAction("Quit").triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.show_window()
        if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.show()

    def on_preloaded(status: dict, duration_s: float) -> None:
        tray.setToolTip("Phantom 2.0 — Ctrl+Space")
        _write_preload_sentinel(duration_s, status)

        # On a warm start the component banner is suppressed; the engines are
        # the same ones the sentinel already recorded as working.
        if not cached:
            print(f"[PHANTOM 2.0] Engines: {status}")
            print("[PHANTOM 2.0] Sentinel: Ollama llama3:latest")
            print("[PHANTOM 2.0] Redaction: Tier1(regex) + Tier2(Presidio) + Tier3(spaCy)")
            print("[PHANTOM 2.0] Router: PhantomRouter (Gemini primary, Groq speed lane)")
        # Printed only once preload has actually returned — never predicted
        # from the cache file, or the agent would claim to be usable ~16s early.
        print(f"[PHANTOM 2.0] Ready ({duration_s:.0f}s). Ctrl+Space to activate.")

    preloader = PreloadWorker(pipeline)
    preloader.done.connect(on_preloaded)
    preloader.start()

    hotkey = HotkeyListener()
    hotkey.triggered.connect(window.toggle_or_show)
    hotkey.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
