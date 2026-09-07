"""
Single-instance enforcement for the Phantom agents.

Two copies of an agent running at once is not merely redundant: both open the
same SQLite checkpoint DB and the same ChromaDB directory, and the resulting
lock contention shows up to the user as the agent "thinking" for 12-14s on a
query that should take under 3s. Measured with two live phantom_ui.py
processes; a third concurrent process made it hang outright.

The lock is an OS byte-range lock on a file in the temp directory, not a
PID file. That distinction matters: if the process is killed (Task Manager,
power loss, crash), the kernel drops the byte-range lock when the handle
closes, so the next launch acquires cleanly. A plain PID file would be left
behind pointing at a dead PID and would need stale-entry heuristics to
recover.
"""
from __future__ import annotations

import os
import sys
import tempfile


class InstanceLock:
    """
    Ensures only one instance of an app runs at a time.

    Usage:
        lock = InstanceLock("Phantom")
        if not lock.acquire():
            lock.signal_focus()   # ask the running instance to show itself
            sys.exit(0)
        atexit.register(lock.release)
    """

    def __init__(self, app_name: str):
        self.app_name = app_name
        self.lock_file_path = os.path.join(
            tempfile.gettempdir(), f"{app_name}.lock"
        )
        self.focus_trigger_path = os.path.join(
            tempfile.gettempdir(), f"{app_name}.focus"
        )
        self.lock_file = None
        self.locked = False

    # ── acquire / release ────────────────────────────────────────────────

    def acquire(self) -> bool:
        """
        Try to take the lock.

        True  -> this is the only instance; caller should carry on.
        False -> another instance already holds it; caller should exit.
        """
        try:
            # Deliberately NOT open(path, "w"): "w" truncates on open, so a
            # second instance would wipe the first instance's recorded PID
            # before discovering it cannot have the lock. O_CREAT|O_RDWR
            # opens without truncating; the file is truncated further down,
            # only once the lock is actually ours.
            fd = os.open(self.lock_file_path, os.O_CREAT | os.O_RDWR)
            self.lock_file = os.fdopen(fd, "r+")

            if not self._platform_lock():
                self.lock_file.close()
                self.lock_file = None
                return False

            self.lock_file.seek(0)
            self.lock_file.truncate()
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            self.locked = True

            # A .focus file left over from a crashed run would otherwise make
            # this instance pop its window open the moment the watcher starts,
            # which breaks the hidden-until-summoned overlay behaviour.
            self.clear_focus_trigger()
            return True

        except Exception:
            # Fail open. Refusing to start because the lock file is
            # unwritable would be a worse failure than allowing a second
            # instance: the user would have no working agent at all.
            return True

    def _platform_lock(self) -> bool:
        """Non-blocking exclusive lock on byte 0. False if already held."""
        try:
            if sys.platform == "win32":
                import msvcrt
                # msvcrt.locking works from the CURRENT file position, so the
                # seek is required, not decorative.
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def release(self) -> None:
        """Drop the lock and remove the lock file. Safe to call twice."""
        if not (self.lock_file and self.locked):
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.lock_file.close()
        except Exception:
            pass
        try:
            os.unlink(self.lock_file_path)
        except Exception:
            pass
        self.locked = False
        self.lock_file = None

    # ── focus handoff ────────────────────────────────────────────────────

    def signal_focus(self) -> None:
        """
        Second instance -> running instance: "show yourself".

        A file touch is used rather than a socket or Qt IPC because the
        second process has not built a QApplication at this point and exits
        milliseconds later; the running instance polls for the file.
        """
        try:
            with open(self.focus_trigger_path, "w"):
                pass
        except Exception:
            pass

    def consume_focus_trigger(self) -> bool:
        """
        Running instance: True exactly once per signal_focus() call.

        The unlink is what makes it edge-triggered — without removing the
        file the window would be re-raised on every poll forever.
        """
        try:
            if os.path.exists(self.focus_trigger_path):
                os.unlink(self.focus_trigger_path)
                return True
        except Exception:
            pass
        return False

    def clear_focus_trigger(self) -> None:
        try:
            if os.path.exists(self.focus_trigger_path):
                os.unlink(self.focus_trigger_path)
        except Exception:
            pass
