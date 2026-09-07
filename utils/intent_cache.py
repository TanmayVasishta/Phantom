"""
Intent classification cache (CLAUDE.md §19.1).

Ollama's Sentinel classification measures 5.4-7.0s minimum on every model
installed on this machine (verified: qwen3.5:2b 17.1s, gemma3:4b 5.4s,
llama3:latest 6.1s) — there is no locally-installed model that makes a
synchronous wait viable on the response path. A repeated or near-repeated
query should not pay that cost twice, so results are cached by normalized
text and reused instantly on a hit, with no Ollama call at all.

This is deliberately a plain dict behind a lock, not functools.lru_cache:
entries are written from a background thread (the classification result
often arrives after the request that triggered it has already moved on —
see phantom_graph._resolve_intent), so insertion and eviction have to be
safe against a concurrent get() from the graph thread.
"""
from __future__ import annotations

import hashlib
import threading


class IntentCache:
    """Cache Ollama intent results so repeated/similar queries skip Ollama."""

    def __init__(self, maxsize: int = 200):
        self._cache: dict[str, dict] = {}
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def _key(self, text: str) -> str:
        # Normalize: lowercase, strip, first 100 chars — small variations
        # (trailing punctuation, a retyped query) still hit the same entry.
        normalized = (text or "").lower().strip()[:100]
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, text: str) -> dict | None:
        with self._lock:
            return self._cache.get(self._key(text))

    def set(self, text: str, result: dict) -> None:
        if not result:
            return
        key = self._key(text)
        with self._lock:
            if key not in self._cache and len(self._cache) >= self._maxsize:
                # Evict oldest (first inserted) — dicts preserve insertion
                # order, and this only runs while holding the lock, so the
                # "changed size during iteration" race the unlocked version
                # would have is not possible here.
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = result

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


# Module-level singleton — import this, don't construct your own.
intent_cache = IntentCache()
