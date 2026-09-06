"""
PII Redaction Engine — tiered cascade for guaranteed zero-PII cloud payloads.

Architecture (Tanmay's original contribution):
  Tier 1: Regex (always runs — fast, catches structured PII)
  Tier 2: Presidio + spaCy NER (accurate, catches names/locations)
  Tier 3: LLaMA semantic check (safety net for indirect/contextual PII)

PII_SENSITIVITY in config controls how many tiers run:
  LOW    → Tier 1 only
  MEDIUM → Tier 1 + Tier 2
  HIGH   → All three tiers
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sentinel.session_pii_map import SessionPIIMap
from utils.config import OLLAMA_MODEL, PII_SENSITIVITY, get_best_available_model
from utils.exceptions import PIILeakageError
from utils.models import PIIEntity


# ── Indian-context regex patterns (Tier 1) ────────────────────────────────────
REGEX_PATTERNS: dict[str, re.Pattern] = {
    "AADHAAR":      re.compile(r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b"),
    "PAN":          re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "PHONE_IN":     re.compile(r"(\+91[\-\s]?)?[0]?(91)?[789]\d{4}[\s\-]?\d{5}\b"),
    # UPI ID: alphanumeric handle @ bank/VPA domain (e.g. rahul@okicici, tanmay@paytm).
    # The negative lookahead stops this from swallowing the local part of a real
    # email address ("teammate@example.com" -> "teammate@example"), which left a
    # mangled "[PII_UPI_ID_1].com" behind and broke email-drafting tool calls.
    # A genuine UPI handle never carries a dotted TLD.
    "UPI_ID":       re.compile(r"\b[a-zA-Z0-9._-]{2,256}@[a-zA-Z]{2,64}\b(?!\.[a-zA-Z])"),
    # Indian PIN code: exactly 6 digits, 1xx–9xx (never 0xx)
    "IN_PIN_CODE":  re.compile(r"\b[1-9][0-9]{5}\b"),
    "EMAIL":        re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"),
    "CREDIT_CARD":  re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
    "IFSC":         re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    "BANK_ACCOUNT": re.compile(r"\b\d{9,18}\b"),
    "IP_ADDRESS":   re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

# Minimum Presidio confidence to treat as PII (Tier 2 gate)
PRESIDIO_CONFIDENCE_THRESHOLD = 0.7

# Combined confidence below this triggers Tier 3 (semantic LLM)
TIER3_TRIGGER_THRESHOLD = 0.80


@dataclass
class RedactionResult:
    """Output from the PII engine for a single query."""

    sanitised_text: str
    entities: list[PIIEntity]

    @property
    def n_entities(self) -> int:
        return len(self.entities)


class PIIRedactionEngine:
    """
    Three-tier PII cascade. Accepts a SessionPIIMap and writes all found
    entities into it so that PIIRestorer can reverse-substitute them later.
    """

    def __init__(self, pii_map: SessionPIIMap):
        self._map = pii_map
        self._presidio_analyzer = None   # lazy-loaded
        self._spacy_nlp = None           # lazy-loaded

    # ── Public API ────────────────────────────────────────────────────────────

    def redact(self, text: str, intent_context: str = "") -> RedactionResult:
        """
        Main entry point. Returns sanitised text with PII replaced by placeholders.
        intent_context helps Tier 2 decide PII likelihood (e.g. PAYMENT_OP raises
        probability that a bare number is a card number).
        """
        self._map.clear()
        entities: list[PIIEntity] = []

        # Tier 1 always runs
        text, entities = self._apply_tier1(text, entities)

        # Tier 2 if sensitivity allows and packages available
        if PII_SENSITIVITY in ("MEDIUM", "HIGH"):
            try:
                text, entities = self._apply_tier2(text, entities, intent_context)
            except ImportError:
                pass  # spaCy / Presidio not installed — skip gracefully

        # Tier 3 only if HIGH sensitivity and combined confidence still low
        if PII_SENSITIVITY == "HIGH" and self._low_confidence(entities, text):
            text, entities = self._apply_tier3(text, entities)

        return RedactionResult(sanitised_text=text, entities=entities)

    # ── Tier 1 — Regex ────────────────────────────────────────────────────────

    def _apply_tier1(
        self, text: str, entities: list[PIIEntity]
    ) -> tuple[str, list[PIIEntity]]:
        """Apply all Indian-context regex patterns."""
        # Track already-replaced spans to avoid double-replacement
        replaced_spans: list[tuple[int, int]] = []

        # Sort patterns to apply longer/more specific first
        for entity_type, pattern in REGEX_PATTERNS.items():
            for match in pattern.finditer(text):
                if self._overlaps(match.start(), match.end(), replaced_spans):
                    continue
                original = match.group()
                placeholder = self._map.add(entity_type, original)
                entities.append(
                    PIIEntity(
                        placeholder=placeholder,
                        original_value=original,
                        entity_type=entity_type,
                        tier_detected=1,
                        presidio_score=0.0,
                        start=match.start(),
                        end=match.end(),
                    )
                )
                replaced_spans.append((match.start(), match.end()))

        # Apply replacements from end to start (preserves indices)
        entities_t1 = [e for e in entities if e.tier_detected == 1]
        entities_t1.sort(key=lambda e: e.start, reverse=True)
        for entity in entities_t1:
            text = text[: entity.start] + entity.placeholder + text[entity.end :]

        return text, entities

    # ── Tier 2 — Presidio + spaCy NER ────────────────────────────────────────

    def _apply_tier2(
        self, text: str, entities: list[PIIEntity], intent_context: str
    ) -> tuple[str, list[PIIEntity]]:
        """Use Presidio AnalyzerEngine for NER-based PII detection."""
        analyzer = self._get_presidio_analyzer()
        if analyzer is None:
            return text, entities

        results = analyzer.analyze(text=text, language="en")
        new_entities: list[PIIEntity] = []

        for result in results:
            if result.score < PRESIDIO_CONFIDENCE_THRESHOLD:
                continue
            original = text[result.start : result.end]
            # Skip if already replaced by Tier 1 (placeholder in the span)
            if original.startswith("[PII_"):
                continue
            placeholder = self._map.add(result.entity_type, original)
            entity = PIIEntity(
                placeholder=placeholder,
                original_value=original,
                entity_type=result.entity_type,
                tier_detected=2,
                presidio_score=result.score,
                start=result.start,
                end=result.end,
            )
            new_entities.append(entity)

        # Apply Tier 2 replacements end-to-start
        new_entities.sort(key=lambda e: e.start, reverse=True)
        for entity in new_entities:
            text = text[: entity.start] + entity.placeholder + text[entity.end :]
            entities.append(entity)

        return text, entities

    # ── Tier 3 — LLaMA semantic check ────────────────────────────────────────

    def _apply_tier3(
        self, text: str, entities: list[PIIEntity]
    ) -> tuple[str, list[PIIEntity]]:
        """
        Ask local LLM to find indirect or contextual PII that regex and NER miss.
        Only called when Tiers 1+2 combined confidence is still low.
        """
        SEMANTIC_PROMPT = (
            "Analyse this text for ANY personally identifiable information including "
            "indirect references ('my sister\\'s address'), financial references, "
            "medical information, or any data that could identify a specific person.\n\n"
            "List ALL PII found as JSON:\n"
            '{\"pii_found\": [{\"text\": \"...\", \"type\": \"...\", '
            '\"start\": 0, \"end\": 0}]}\n'
            "If none found: {\"pii_found\": []}\n\n"
            f"Text: {text}"
        )

        try:
            import ollama
            import json

            model = get_best_available_model()
            response = ollama.generate(
                model=model,
                prompt=SEMANTIC_PROMPT,
                options={"temperature": 0.0, "num_predict": 256},
            )
            raw = response["response"].strip()

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                return text, entities
            data = json.loads(json_match.group())

            new_entities: list[PIIEntity] = []
            for item in data.get("pii_found", []):
                original = item.get("text", "")
                if not original or original.startswith("[PII_"):
                    continue
                entity_type = item.get("type", "INDIRECT").upper()
                start = text.find(original)
                if start == -1:
                    continue
                end = start + len(original)
                placeholder = self._map.add(entity_type, original)
                new_entities.append(
                    PIIEntity(
                        placeholder=placeholder,
                        original_value=original,
                        entity_type=entity_type,
                        tier_detected=3,
                        presidio_score=0.9,  # LLM found it — treat as high confidence
                        start=start,
                        end=end,
                    )
                )

            new_entities.sort(key=lambda e: e.start, reverse=True)
            for entity in new_entities:
                text = text[: entity.start] + entity.placeholder + text[entity.end :]
                entities.append(entity)

        except Exception:
            pass  # Tier 3 failure is non-fatal

        return text, entities

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _low_confidence(self, entities: list[PIIEntity], text: str) -> bool:
        """True if we should run Tier 3 (combined confidence still uncertain)."""
        if not entities:
            # No PII found by Tiers 1+2 — run Tier 3 as a final check
            return True
        avg_score = sum(e.presidio_score for e in entities) / len(entities)
        return avg_score < TIER3_TRIGGER_THRESHOLD

    def _overlaps(
        self, start: int, end: int, spans: list[tuple[int, int]]
    ) -> bool:
        """Check if a span overlaps with any already-replaced span."""
        return any(not (end <= s or start >= e) for s, e in spans)

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
