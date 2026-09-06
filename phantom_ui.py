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
    # High-DPI
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')

    # MUST IMPORT WEBENGINE BEFORE QApplication!
    from ui.phantom_window import PhantomWindow, HAS_WEBENGINE

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

    window = PhantomWindow()

    from ui.tray_daemon import TrayDaemon
    from ui.hotkey_listener import HotkeyListener

    tray = TrayDaemon(window)
    tray.setup()

    hotkey = HotkeyListener()
    hotkey.triggered.connect(window.show_window)
    hotkey.start()

    # Show immediately on launch — do NOT gate this on backend readiness.
    # The frontend (index.html) independently polls /health every 2s and
    # disables its own input until that succeeds (Fix 1), so the window
    # showing early is safe. wait_for_api() below just gives the frontend a
    # head start: model warm-up (spaCy/Presidio/embedder/reranker) takes
    # ~80s cold, so this has to outlast that — but it must NOT block window
    # creation, or the window itself would be delayed by up to 120s.
    window.show_window()

    def _wait_for_backend_and_hint():
        ready = wait_for_api(timeout=120)
        if ready:
            print('[PHANTOM] API ready at http://127.0.0.1:8747')
            window.notify_backend_ready()
        else:
            print('[PHANTOM] API not ready after 120s — the frontend keeps '
                  'polling /health independently and will unlock once it is.')

    threading.Thread(target=_wait_for_backend_and_hint, daemon=True).start()

    print('[PHANTOM] Ready. Press Ctrl+Alt+P or use system tray.')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
