"""
OS Middleware — sandboxed OS command execution with resource limits.

Vedika's module. Provides:
- Blocked pattern check before every execution
- Resource-limited subprocess (CPU + RAM caps on POSIX; timeout on Windows)
- Filesystem diff tracking before/after each command
- Rollback stack population after each execution
- Dry-run description for every command
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import subprocess

from utils.exceptions import CommandBlockedError
from utils.models import ExecutionResult
from middleware.blocked_commands import assert_not_blocked
from middleware.risk_classifier import classify_command_risk
from middleware.rollback_stack import RollbackStack, infer_inverse
from middleware.command_mapper import dry_run_description

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


class OSMiddleware:
    """
    Sandboxed command execution for HELIX local operations.

    All commands pass through:
    1. Blocked pattern check (hard abort)
    2. Risk classification (logged)
    3. Resource-limited subprocess
    4. Rollback stack update
    """

    def __init__(self, rollback_stack: RollbackStack | None = None):
        self._rollback = rollback_stack or RollbackStack()

    @property
    def rollback_stack(self) -> RollbackStack:
        return self._rollback

    def execute(
        self,
        command: str,
        intent: str = "",
        entities: list[str] | None = None,
        timeout: int = 10,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """
        Execute a command safely.

        dry_run=True: compute description and snapshot but do not run.
        """
        entities = entities or []

        # 1. Blocked check
        try:
            assert_not_blocked(command)
        except CommandBlockedError as e:
            return ExecutionResult(
                status="blocked",
                stderr=str(e),
                command=command,
                dry_run_description=str(e),
            )

        # 2. Build human-readable preview
        preview = dry_run_description(command, intent, entities)

        if dry_run:
            return ExecutionResult(
                status="dry_run",
                command=command,
                dry_run_description=preview,
            )

        # 3. Filesystem snapshot before execution
        snapshot_before = self._snapshot_cwd()

        # 4. Execute with resource constraints
        try:
            result = self._run(command, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status="error",
                stderr=f"Command timed out after {timeout}s",
                command=command,
                dry_run_description=preview,
            )
        except Exception as e:
            return ExecutionResult(
                status="error",
                stderr=str(e),
                command=command,
                dry_run_description=preview,
            )

        # 5. Filesystem diff
        snapshot_after = self._snapshot_cwd()
        diff = self._compute_diff(snapshot_before, snapshot_after)

        # 6. Push to rollback stack
        inverse = infer_inverse(command)
        if inverse:
            self._rollback.push(command, inverse, description=preview)

        # 7. Log command risk
        risk = classify_command_risk(command)
        logger.debug(f"Executed '{command[:60]}' | risk={risk} | rc={result.returncode}")

        return ExecutionResult(
            status="success" if result.returncode == 0 else "error",
            stdout=result.stdout[:5000],
            stderr=result.stderr[:1000],
            returncode=result.returncode,
            command=command,
            dry_run_description=preview,
            filesystem_diff=diff,
        )

    def _run(self, command: str, timeout: int = 10) -> subprocess.CompletedProcess:
        """Run the command with platform-appropriate resource limits."""
        kwargs: dict = dict(
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.expanduser("~"),
        )

        if not _IS_WINDOWS:
            # POSIX: apply CPU and RAM limits via resource module
            import resource

            def limit_resources():
                resource.setrlimit(resource.RLIMIT_CPU, (5, 10))       # 5s soft, 10s hard
                resource.setrlimit(
                    resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)
                )  # 512 MB RAM

            kwargs["preexec_fn"] = limit_resources

        return subprocess.run(command, **kwargs)

    def _snapshot_cwd(self) -> dict[str, str]:
        """
        Take a lightweight snapshot of the home directory's immediate children.
        Returns dict of {relative_path: md5_or_dir}.
        """
        try:
            home = os.path.expanduser("~")
            snapshot: dict[str, str] = {}
            for entry in os.scandir(home):
                if entry.is_file():
                    try:
                        with open(entry.path, "rb") as f:
                            snapshot[entry.name] = hashlib.md5(f.read(4096)).hexdigest()
                    except (PermissionError, OSError):
                        snapshot[entry.name] = "unreadable"
                elif entry.is_dir():
                    snapshot[entry.name] = "dir"
            return snapshot
        except Exception:
            return {}

    def _compute_diff(
        self, before: dict[str, str], after: dict[str, str]
    ) -> dict:
        """Compute what changed between two filesystem snapshots."""
        added = {k: v for k, v in after.items() if k not in before}
        removed = {k: v for k, v in before.items() if k not in after}
        modified = {
            k: {"before": before[k], "after": after[k]}
            for k in after
            if k in before and before[k] != after[k]
        }
        return {"added": added, "removed": removed, "modified": modified}
