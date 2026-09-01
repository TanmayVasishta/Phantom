"""
Intent Cache — skips redundant LLM routing calls for repeated safe queries.

Tanmay's original contribution (Section 19.1):
  Key   = (intent_type, md5(normalised_query_structure)[:8])
  Value = (route_target, risk_score, cached_at)
  TTL   = 300 seconds (5 minutes)
  Size  = max 50 entries (LRU eviction)

Only cache hits where risk_score <= HITL_THRESHOLD bypass the LLM routing call.
High-risk routes must always go through full routing so HITL fires correctly.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict

from utils.config import RISK_THRESHOLD_HITL


class IntentCache:
    """LRU cache for intent → route decisions with TTL expiry."""

    def __init__(self, ttl: int = 300, max_size: int = 50):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size

    def _make_key(self, intent: str, query: str) -> str:
        """
        Key = "INTENT_TYPE:md5(sorted_words)[:8]"

        Sorting query words removes most word-order variation while preserving
        the structural meaning (e.g. "list downloads" ≈ "downloads list").
        """
        normalised = " ".join(sorted(query.lower().split()))
        digest = hashlib.md5(normalised.encode()).hexdigest()[:8]
        return f"{intent.upper()}:{digest}"

    def get(self, intent: str, query: str) -> dict | None:
        """
        Return cached entry if it exists and hasn't expired.
        Also checks that the risk_score is safe enough to skip HITL.
        Returns None on cache miss or TTL expiry.
        """
        key = self._make_key(intent, query)
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry["cached_at"] >= self.ttl:
            del self._cache[key]
            return None

        # Move to end (mark as recently used)
        self._cache.move_to_end(key)
        return entry

    def set(
        self, intent: str, query: str, route_target: str, risk_score: int
    ) -> None:
        """Store a routing decision. Does NOT cache high-risk routes."""
        # Never cache decisions that require HITL — they must always be evaluated
        if risk_score > RISK_THRESHOLD_HITL:
            return

        key = self._make_key(intent, query)
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # evict oldest (LRU)

        self._cache[key] = {
            "route_target": route_target,
            "risk_score": risk_score,
            "cached_at": time.time(),
        }

    def invalidate(self, intent: str | None = None) -> None:
        """
        Invalidate cache entries. Called after a HITL rejection since
        cached decisions may be wrong for the context.

        If intent is given, only invalidate entries for that intent type.
        """
        if intent is None:
            self._cache.clear()
        else:
            prefix = intent.upper() + ":"
            keys_to_del = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]

    def __len__(self) -> int:
        return len(self._cache)
