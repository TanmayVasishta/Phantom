"""
Global crash logging — install BEFORE QApplication() so nothing that runs
during startup is missed.

Two independent channels feed the same log:
  - sys.excepthook: catches any Python exception that escapes to the top
    of a thread (the main thread, or any QThread whose run() doesn't catch
    everything itself — see ui/worker.py, which already does).
  - Qt's message handler: catches native Qt-level critical/fatal messages
    (a bad geometry, a failed paint, an assertion) that never surface as a
    Python exception at all.

Neither of these caught anything during this bug's diagnosis (three live
reproductions, phantom_crash.log stayed empty every time) — the actual
defects were logic bugs (a window that hides with no way back, and a
timeout that doesn't actually stop waiting), not crashes. This hook stays
in permanently regardless, both because it was asked for and because it's
the first thing you want already running if a real crash shows up later.
"""
from __future__ import annotations

import os
import sys
import traceback


def install(log_path: str) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 50}\n{error_msg}")
        except Exception:
            pass  # logging the crash must never itself raise
        print(f"[PHANTOM CRASH] {error_msg}")

    sys.excepthook = handle_exception

    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

    def qt_message_handler(mode, context, message):
        level = {
            QtMsgType.QtDebugMsg: "DEBUG",
            QtMsgType.QtInfoMsg: "INFO",
            QtMsgType.QtWarningMsg: "WARNING",
            QtMsgType.QtCriticalMsg: "CRITICAL",
            QtMsgType.QtFatalMsg: "FATAL",
        }.get(mode, "UNKNOWN")
        if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[Qt {level}] {message}\n")
            except Exception:
                pass
            print(f"[Qt {level}] {message}")

    qInstallMessageHandler(qt_message_handler)
