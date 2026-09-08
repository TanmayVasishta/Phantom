"""
PHANTOM UI Entry Point.
Launches FastAPI backend + PyQt6 overlay + tray daemon.

Usage: python phantom_ui.py
"""
from __future__ import annotations
import sys
import os
import subprocess

if sys.executable.lower().endswith("pythonw.exe"):
    vbs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'launcher.vbs')
    subprocess.Popen(['wscript.exe', vbs_path, os.path.abspath(__file__)])
    sys.exit(0)

import threading
import time

# Ensure PHANTOM root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


def start_api_server():
    """Start FastAPI in a background daemon thread."""
    try:
        from api.server import start_server
        start_server()
    except Exception as e:
        print(f'[PHANTOM] API server error: {e}')


def wait_for_api(timeout: int = 15) -> bool:
    """Poll until FastAPI is ready."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://127.0.0.1:8747/health', timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    print("Entered main")

    # Single instance, before anything expensive is built.
    #
    # Two live copies both open the same SQLite checkpoint DB and the same
    # ChromaDB directory; the lock contention surfaces to the user as the
    # agent "thinking" for 12-14s on a trivial query. This is deliberately
    # inside main() rather than at module scope: under pythonw.exe (which is
    # what the autostart registry entry uses) the block at the top of this
    # file relaunches via launcher.vbs and exits, so module scope would take
    # the lock in the bootstrap process and release it milliseconds later.
    import atexit
    from utils.instance_lock import InstanceLock

    lock = InstanceLock("Phantom")
    if not lock.acquire():
        print("[PHANTOM] Already running. Bringing the existing window to focus.")
        lock.signal_focus()
        sys.exit(0)
    atexit.register(lock.release)

    # High-DPI
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')

    # Before QApplication so a crash during Qt startup itself is still
    # captured, not just once the event loop is running. Found nothing in
    # three live reproductions of the reported disappearance (crash log
    # stayed empty each time — the real bugs were logic bugs, fixed
    # separately below), but this stays on permanently regardless.
    from utils.crash_logger import install as install_crash_logger
    install_crash_logger(os.path.join(os.path.dirname(os.path.abspath(__file__)), "phantom_crash.log"))

    from ui.phantom_window import PhantomAgentWindow

    print("Importing QApplication")
    from PyQt6.QtWidgets import QApplication
    print("Creating app")
    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('PHANTOM')
    app.setApplicationDisplayName('PHANTOM — Privacy-First AI')

    print("Starting API thread")
    # Start FastAPI backend
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    print('[PHANTOM] Starting API server...')

    window = PhantomAgentWindow()

    from ui.tray_daemon import TrayDaemon
    from ui.hotkey_listener import HotkeyListener

    tray = TrayDaemon(window)
    tray.setup()

    hotkey = HotkeyListener()
    hotkey.triggered.connect(window.toggle_or_show)
    hotkey.start()

    # Hidden on launch — this is a Spotlight-style overlay, summoned only by
    # the hotkey or the tray icon, never shown automatically. PhantomWorker
    # talks to phantom_graph.run_query() in-process (no HTTP server needed
    # for the overlay itself); the window tracks the FastAPI server's own
    # /health independently via its own QTimer. This thread is just console
    # logging for the ~80s warm-up window, not the dot's data source.
    def _log_backend_ready():
        ready = wait_for_api(timeout=120)
        print('[PHANTOM] API ready at http://127.0.0.1:8747' if ready
              else '[PHANTOM] API not ready after 120s.')

    threading.Thread(target=_log_backend_ready, daemon=True).start()

    print('[PHANTOM] Ready. Press Ctrl+Shift+Space or use system tray.')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
