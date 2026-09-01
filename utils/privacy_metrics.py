"""Session privacy metrics — thread-safe counters for the Privacy Dashboard."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class SessionPrivacyMetrics:
    """Thread-safe privacy counters for the current HELIX session."""

    total_queries: int = 0
    local_queries: int = 0
    cloud_queries: int = 0
    memory_queries: int = 0
    pii_entities_redacted: int = 0
    fallback_queries: int = 0   # times Gemini was unavailable, fell back to local
    hitl_approved: int = 0
    hitl_rejected: int = 0
    hitl_modified: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def privacy_score(self) -> float:
        """Percentage of queries handled locally (0–100)."""
        if self.total_queries == 0:
            return 100.0
        return round((self.local_queries / self.total_queries) * 100, 1)

    def record_query(self, route: str, n_pii: int, fallback: bool = False) -> None:
        """Call once per completed query. route: 'local' | 'cloud' | 'memory'."""
        with self._lock:
            self.total_queries += 1
            self.pii_entities_redacted += n_pii
            if route == "local":
                self.local_queries += 1
            elif route == "cloud":
                self.cloud_queries += 1
            elif route == "memory":
                self.memory_queries += 1
            if fallback:
                self.fallback_queries += 1

    def record_hitl(self, decision: str) -> None:
        """Call when HITL decision is made. decision: 'approved'|'rejected'|'modified'."""
        with self._lock:
            if decision == "approved":
                self.hitl_approved += 1
            elif decision == "rejected":
                self.hitl_rejected += 1
            elif decision == "modified":
                self.hitl_modified += 1

    def to_display_dict(self) -> dict:
        """Returns a dict safe for display in the Privacy Dashboard panel."""
        with self._lock:
            return {
                "Privacy Score": f"{self.privacy_score}%",
                "Total Queries": self.total_queries,
                "Local (Private)": self.local_queries,
                "Cloud (Sanitised)": self.cloud_queries,
                "Memory Lookups": self.memory_queries,
                "PII Entities Protected": self.pii_entities_redacted,
                "Cloud Fallbacks": self.fallback_queries,
                "HITL Approved": self.hitl_approved,
                "HITL Rejected": self.hitl_rejected,
                "HITL Modified": self.hitl_modified,
            }

    def reset(self) -> None:
        """Reset all counters (call at session start if reusing the object)."""
        with self._lock:
            self.total_queries = 0
            self.local_queries = 0
            self.cloud_queries = 0
            self.memory_queries = 0
            self.pii_entities_redacted = 0
            self.fallback_queries = 0
            self.hitl_approved = 0
            self.hitl_rejected = 0
            self.hitl_modified = 0


# Global singleton — import from anywhere in the codebase
session_metrics = SessionPrivacyMetrics()
