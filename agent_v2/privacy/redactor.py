"""
3-tier PII redaction engine.

Tier 1 (regex)    — always runs, compiled at import.
Tier 2 (Presidio) — runs when sentinel risk is HIGH or MEDIUM.
Tier 3 (spaCy)    — runs when sentinel risk is HIGH only.

All three tiers analyse the ORIGINAL text and report character offsets, rather
than each tier re-scanning the previous tier's output. Chaining the tiers
textually would shift every offset after the first replacement and would feed
Presidio/spaCy the placeholder tags themselves; scoring against one common
text is also what makes the "skip what an earlier tier already caught"
overlap check meaningful.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
from utils.public_places import is_public_place_mention  # noqa: E402

# ── Tier 1: compiled once at import (spec: < 10ms per call) ──────────────────
TIER1_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
    ("URL", re.compile(r"https?://[^\s]+")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("PHONE", re.compile(r"(\+?1?\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")),
    ("DATE", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    ("ZIP", re.compile(r"\b\d{5}(?:-\d{4})?\b")),
]

TIER2_ENTITIES = [
    "PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "MEDICAL_LICENSE",
    "US_PASSPORT", "US_DRIVER_LICENSE", "CREDIT_CARD", "CRYPTO", "IBAN_CODE",
    "US_BANK_NUMBER", "US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER",
    "IP_ADDRESS", "NRP", "US_ITIN", "TITLE", "AGE", "ID",
]

TIER3_ENTITIES = {"PERSON", "ORG", "GPE", "LOC", "FAC", "PRODUCT", "EVENT", "MONEY"}


@dataclass
class Detection:
    tag: str
    original_value: str
    tier: int
    entity_type: str
    offset: int
    end: int


@dataclass
class RedactionResult:
    redacted_text: str
    detections: list[Detection] = field(default_factory=list)
    tiers_run: list[int] = field(default_factory=list)
    tiers_skipped: list[int] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    tier_error: str = ""


class _EngineCache:
    """Presidio + spaCy are loaded once and reused (spec: never on first query)."""

    def __init__(self) -> None:
        self._analyzer: Any = None
        self._nlp: Any = None

    def preload(self) -> dict[str, str]:
        status = {}
        try:
            status["presidio"] = "ok" if self.analyzer is not None else "unavailable"
        except Exception as exc:
            status["presidio"] = f"unavailable: {exc}"
        try:
            status["spacy"] = "ok" if self.nlp is not None else "unavailable"
        except Exception as exc:
            status["spacy"] = f"unavailable: {exc}"
        return status

    @property
    def analyzer(self):
        if self._analyzer is None:
            from presidio_analyzer import AnalyzerEngine
            self._analyzer = AnalyzerEngine()
        return self._analyzer

    @property
    def nlp(self):
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
        return self._nlp


ENGINES = _EngineCache()


def _overlaps(start: int, end: int, taken: list[tuple[int, int]]) -> bool:
    return any(start < t_end and end > t_start for t_start, t_end in taken)


def _tier1(text: str, taken: list[tuple[int, int]]) -> list[Detection]:
    found: list[Detection] = []
    counters: dict[str, int] = {}
    for entity_type, pattern in TIER1_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            value = match.group()
            if not value.strip():
                continue
            # The PHONE pattern's leading (\+?1?\s?)? group can swallow the
            # preceding space, which would otherwise render as "phone(555)..."
            # in the surrogate text. Trim the span back to the real value.
            lead = len(value) - len(value.lstrip())
            if lead:
                start += lead
            if _overlaps(start, end, taken):
                continue
            idx = counters.get(entity_type, 0)
            counters[entity_type] = idx + 1
            found.append(Detection(
                tag=f"<<TIER1_{entity_type}_{idx}>>",
                original_value=text[start:end],
                tier=1,
                entity_type=entity_type,
                offset=start,
                end=end,
            ))
            taken.append((start, end))
    return found


def _tier2(text: str, taken: list[tuple[int, int]]) -> list[Detection]:
    results = ENGINES.analyzer.analyze(
        text=text, entities=TIER2_ENTITIES, language="en"
    )
    found: list[Detection] = []
    counters: dict[str, int] = {}
    for res in sorted(results, key=lambda r: (r.start, -r.score)):
        if _overlaps(res.start, res.end, taken):
            continue
        value = text[res.start:res.end]
        if res.entity_type == "LOCATION" and is_public_place_mention(text, value):
            continue
        idx = counters.get(res.entity_type, 0)
        counters[res.entity_type] = idx + 1
        found.append(Detection(
            tag=f"<<TIER2_{res.entity_type}_{idx}>>",
            original_value=value,
            tier=2,
            entity_type=res.entity_type,
            offset=res.start,
            end=res.end,
        ))
        taken.append((res.start, res.end))
    return found


def _tier3(text: str, taken: list[tuple[int, int]]) -> list[Detection]:
    doc = ENGINES.nlp(text)
    found: list[Detection] = []
    counters: dict[str, int] = {}
    for ent in doc.ents:
        if ent.label_ not in TIER3_ENTITIES:
            continue
        if _overlaps(ent.start_char, ent.end_char, taken):
            continue
        if ent.label_ in ("GPE", "LOC") and is_public_place_mention(text, ent.text):
            continue
        idx = counters.get(ent.label_, 0)
        counters[ent.label_] = idx + 1
        found.append(Detection(
            tag=f"<<TIER3_{ent.label_}_{idx}>>",
            original_value=ent.text,
            tier=3,
            entity_type=ent.label_,
            offset=ent.start_char,
            end=ent.end_char,
        ))
        taken.append((ent.start_char, ent.end_char))
    return found


async def _run_tiers_2_and_3(text: str, taken: list[tuple[int, int]], need_tier3: bool):
    """
    Tier 2 and Tier 3 concurrently. Both are synchronous and CPU-bound, so
    they go through an executor — asyncio.gather over bare sync calls would
    just run them back to back on one thread.
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        # Each tier gets its own `taken` copy so they can run truly
        # concurrently; overlaps between their results are resolved after.
        t2 = loop.run_in_executor(pool, _tier2, text, list(taken))
        if need_tier3:
            t3 = loop.run_in_executor(pool, _tier3, text, list(taken))
            return await asyncio.gather(t2, t3)
        return [await t2, []]


def redact(text: str, risk_level: str = "HIGH") -> RedactionResult:
    """
    Redact `text` according to the sentinel's risk level.

    LOW takes the fast path: Tier 1 only, no model loading, no NLP.
    """
    risk = (risk_level or "HIGH").upper()
    taken: list[tuple[int, int]] = []
    timings: dict[str, float] = {}
    tiers_run: list[int] = []
    tiers_skipped: list[int] = []
    tier_error = ""

    t0 = time.perf_counter()
    detections = _tier1(text, taken)
    timings["tier1"] = (time.perf_counter() - t0) * 1000
    tiers_run.append(1)

    need_tier2 = risk in ("HIGH", "MEDIUM")
    need_tier3 = risk == "HIGH"

    if need_tier2:
        t0 = time.perf_counter()
        try:
            t2_found, t3_found = asyncio.run(_run_tiers_2_and_3(text, taken, need_tier3))
        except Exception as exc:
            # Deliberately recorded, not swallowed. A failed NER tier means
            # names/locations went undetected — the caller has to be able to
            # see that its PII coverage silently dropped to regex-only.
            t2_found, t3_found = [], []
            tier_error = f"{type(exc).__name__}: {exc}"
        # Resolve overlaps between the two concurrent tiers: Tier 2 wins.
        for det in t2_found:
            if not _overlaps(det.offset, det.end, taken):
                detections.append(det)
                taken.append((det.offset, det.end))
        tiers_run.append(2)
        timings["tier2"] = (time.perf_counter() - t0) * 1000

        if need_tier3:
            t0 = time.perf_counter()
            for det in t3_found:
                if not _overlaps(det.offset, det.end, taken):
                    detections.append(det)
                    taken.append((det.offset, det.end))
            tiers_run.append(3)
            timings["tier3"] = (time.perf_counter() - t0) * 1000
        else:
            tiers_skipped.append(3)
    else:
        tiers_skipped.extend([2, 3])

    # Replace right-to-left so earlier offsets stay valid.
    redacted = text
    for det in sorted(detections, key=lambda d: d.offset, reverse=True):
        redacted = redacted[:det.offset] + det.tag + redacted[det.end:]

    detections.sort(key=lambda d: d.offset)
    return RedactionResult(
        redacted_text=redacted,
        detections=detections,
        tiers_run=tiers_run,
        tiers_skipped=tiers_skipped,
        timings_ms=timings,
        tier_error=tier_error,
    )
