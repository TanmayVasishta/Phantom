"""
PII Restorer — response-side PII control (Tanmay's original contribution).

Runs on every response before it reaches the HUD:
1. Substitutes SESSION_PII_MAP placeholders back into response text.
2. Scans restored response for leaked raw PII (Gemini hallucination check).
3. Raises alert on placeholder mismatch (pipeline bug indicator).
"""

from __future__ import annotations

import re

from sentinel.session_pii_map import SessionPIIMap


class PIIRestorer:
    """Bidirectional PII control — sanitise in, restore out."""

    def __init__(self, session_pii_map: SessionPIIMap):
        self._map = session_pii_map
        self._presidio_analyzer = None  # lazy-loaded

    def restore_and_validate(self, response_text: str) -> tuple[str, list[str]]:
        """
        Restore PII placeholders in response and validate the result.

        Returns:
            (restored_text, warnings)
            warnings is non-empty if:
            - Unknown placeholder found in response (pipeline bug)
            - Raw PII detected in response after restoration (Gemini hallucination)
        """
        warnings: list[str] = []
        known_placeholders = self._map.get_placeholders()

        # 1. Check for unknown placeholders before restoring
        found_placeholders = re.findall(r"\[PII_[A-Z]+_\d+\]", response_text)
        for ph in found_placeholders:
            if ph not in known_placeholders:
                warnings.append(
                    f"Unknown placeholder in response (pipeline bug): {ph}"
                )

        # 2. Restore known placeholders
        restored = self._map.restore(response_text)

        # 3. Scan restored text for leaked raw PII (if Presidio available)
        analyzer = self._get_presidio_analyzer()
        if analyzer is not None:
            try:
                pii_hits = analyzer.analyze(restored, language="en")
                high_conf = [h for h in pii_hits if h.score > 0.85]
                if high_conf:
                    types = list({h.entity_type for h in high_conf})
                    warnings.append(
                        f"Possible PII in response after restoration "
                        f"(Gemini hallucination?): {types}"
                    )
            except Exception:
                pass

        return restored, warnings

    def _get_presidio_analyzer(self):
        """Lazy-load Presidio AnalyzerEngine. Returns None if not installed."""
        if self._presidio_analyzer is not None:
            return self._presidio_analyzer
        try:
            from presidio_analyzer import AnalyzerEngine
            self._presidio_analyzer = AnalyzerEngine()
            return self._presidio_analyzer
        except ImportError:
            return None
