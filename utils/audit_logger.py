"""Privacy-respecting audit logger — logs WHAT happened, never the content."""

from __future__ import annotations

import datetime
import json
import os
import threading


# Fields that must never appear in audit log entries
_BANNED_FIELDS = frozenset({
    "query_text",
    "sanitised_text",
    "response_text",
    "entities",
    "command",
    "original_value",
    "pii_value",
    "raw_text",
})


class PrivacyAuditLogger:
    """
    Writes structured JSONL audit events without logging any PII or query content.

    Safe fields to log: intent, route, risk_score, outcome, hitl_required,
    hitl_decision, n_pii_redacted, used_cloud, fallback, execution_time_ms,
    error_type, tier_used, model_name, from_cache.
    """

    def __init__(self, log_path: str = "./data/helix_audit.jsonl"):
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        self._log_path = log_path
        self._lock = threading.Lock()

    def log_event(self, event_type: str, **kwargs) -> None:
        """
        Write one audit event. Any kwarg whose key is in the banned list is
        silently dropped to prevent accidental PII logging.
        """
        safe_kwargs = {k: v for k, v in kwargs.items() if k not in _BANNED_FIELDS}
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event_type,
            **safe_kwargs,
        }
        line = json.dumps(entry, default=str) + "\n"
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def read_recent(self, n: int = 20) -> list[dict]:
        """Return the last n audit entries for the 'audit log' CLI command."""
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except FileNotFoundError:
            return []

    def stats(self) -> dict:
        """Aggregate counts grouped by event type."""
        counts: dict[str, int] = {}
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        ev = entry.get("event", "UNKNOWN")
                        counts[ev] = counts.get(ev, 0) + 1
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return counts


# Global singleton
audit = PrivacyAuditLogger()
