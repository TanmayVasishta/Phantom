"""SESSION_PII_MAP — bidirectional PII placeholder store. RAM-only, never persisted."""

from __future__ import annotations

import re
import threading


class SessionPIIMap:
    """
    Maps PII placeholder tokens to original values for the current query.

    Key design: Presidio anonymises PII but discards originals. HELIX keeps them
    so we can restore them in the response (PII Restorer). This is Tanmay's
    original contribution — do not replace with Presidio's AnonymizerEngine alone.

    Lifecycle: cleared at the START of every new query (not at session end),
    preventing stale mappings from bleeding across unrelated queries.
    """

    def __init__(self):
        self._map: dict[str, str] = {}        # placeholder → original_value
        self._counters: dict[str, int] = {}   # entity_type → current counter
        self._lock = threading.Lock()

    def add(self, entity_type: str, original_value: str) -> str:
        """
        Register a PII entity and return its placeholder token.
        If the same original value was already registered, returns existing token.
        """
        with self._lock:
            # Deduplicate: same original value gets same placeholder
            for placeholder, stored in self._map.items():
                if stored == original_value:
                    return placeholder

            type_key = entity_type.upper()
            self._counters[type_key] = self._counters.get(type_key, 0) + 1
            placeholder = f"[PII_{type_key}_{self._counters[type_key]}]"
            self._map[placeholder] = original_value
            return placeholder

    def restore(self, text: str) -> str:
        """Replace all known placeholders in text with their original values."""
        with self._lock:
            result = text
            # Sort by length descending to avoid partial replacement conflicts
            for placeholder in sorted(self._map, key=len, reverse=True):
                result = result.replace(placeholder, self._map[placeholder])
            return result

    def get_placeholders(self) -> dict[str, str]:
        """Return a copy of the placeholder → original map (for validation only)."""
        with self._lock:
            return dict(self._map)

    def clear(self) -> None:
        """Reset for the next query. Must be called at the start of each query."""
        with self._lock:
            self._map.clear()
            self._counters.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._map)

    @property
    def placeholder_pattern(self) -> re.Pattern:
        """Regex that matches any HELIX PII placeholder token."""
        return re.compile(r"\[PII_[A-Z]+_\d+\]")
