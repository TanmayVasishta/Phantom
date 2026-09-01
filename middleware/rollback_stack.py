"""
Rollback stack — inverse operation stack for partial execution undo.

Vedika's original contribution: when HITL rejects a multi-step sequence,
pop inverse operations in LIFO order to undo completed steps.

Examples:
  mkdir ~/test        → inverse: rmdir ~/test
  cp a.txt b.txt      → inverse: rm b.txt
  mv a.txt ~/docs/    → inverse: mv ~/docs/a.txt .
  touch file.txt      → inverse: rm file.txt
"""

from __future__ import annotations

import subprocess
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RollbackEntry:
    command: str
    inverse: str
    description: str = ""


class RollbackStack:
    """LIFO stack of (command, inverse_command) pairs."""

    def __init__(self):
        self._stack: list[RollbackEntry] = []

    def push(self, command: str, inverse: str, description: str = "") -> None:
        """Record a command and its inverse. Call immediately after execution."""
        self._stack.append(RollbackEntry(command=command, inverse=inverse, description=description))

    def pop_and_execute(self) -> list[tuple[str, bool]]:
        """
        Execute inverse operations in LIFO order.
        Returns list of (inverse_command, success) tuples.
        """
        results: list[tuple[str, bool]] = []

        while self._stack:
            entry = self._stack.pop()
            if not entry.inverse:
                continue
            try:
                result = subprocess.run(
                    entry.inverse,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                success = result.returncode == 0
                if not success:
                    logger.warning(
                        f"Rollback failed for '{entry.inverse}': {result.stderr}"
                    )
                results.append((entry.inverse, success))
            except Exception as e:
                logger.error(f"Rollback error for '{entry.inverse}': {e}")
                results.append((entry.inverse, False))

        return results

    def clear(self) -> None:
        """Clear without executing inverses. Call after successful HITL approval."""
        self._stack.clear()

    def peek(self) -> list[RollbackEntry]:
        """Return a copy of current stack (most recent last)."""
        return list(self._stack)

    def __len__(self) -> int:
        return len(self._stack)


def infer_inverse(command: str) -> str:
    """
    Attempt to automatically infer the inverse of a simple command.
    Returns empty string if inverse cannot be inferred.
    """
    import re, os

    cmd = command.strip()

    # mkdir → rmdir
    m = re.match(r"mkdir\s+(-p\s+)?(.+)", cmd)
    if m:
        return f"rmdir {m.group(2).strip()}"

    # touch → rm
    m = re.match(r"touch\s+(.+)", cmd)
    if m:
        return f"rm {m.group(1).strip()}"

    # cp src dest → rm dest
    m = re.match(r"cp\s+(-r\s+)?(\S+)\s+(\S+)", cmd)
    if m:
        return f"rm -r {m.group(3)}" if m.group(1) else f"rm {m.group(3)}"

    # mv src dest → mv dest src
    m = re.match(r"mv\s+(\S+)\s+(\S+)", cmd)
    if m:
        src, dest = m.group(1), m.group(2)
        # Handle case where dest is a directory
        if dest.endswith("/") or os.path.isdir(dest):
            filename = os.path.basename(src)
            return f"mv {os.path.join(dest, filename)} {os.path.dirname(src) or '.'}"
        return f"mv {dest} {src}"

    return ""
