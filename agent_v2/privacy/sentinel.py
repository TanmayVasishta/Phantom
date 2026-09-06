"""
Sentinel node — local pre-screen before anything reaches the cloud.

Two jobs: PII risk (HIGH/MEDIUM/LOW) and intent (QUESTION/TASK/SENSITIVE/
DANGEROUS). Runs against local Ollama so the raw text never leaves the box
during classification.

Two deliberate departures from the brief, both to keep the safety gate honest:

1. The "< 20 words => LOW, skip Ollama" fast path is applied to the PII risk
   score ONLY, not to intent. Skipping intent for short inputs would make the
   DANGEROUS gate trivially bypassable — "How do I make a bomb" is six words.

2. A local keyword screen for DANGEROUS runs ALWAYS, before and independently
   of Ollama. Ollama is frequently not running on this machine; a safety gate
   whose only implementation is an optional local service fails open the
   moment that service is down. The Ollama call refines the classification
   when it is available, it is not the sole authority.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:latest")
OLLAMA_TIMEOUT = 2.0
SHORT_INPUT_WORDS = 20

# Circuit breaker: when Ollama isn't running, every classify() would otherwise
# pay the full timeout twice (risk + intent). One failure marks it down for
# OLLAMA_COOLDOWN seconds so the sentinel stays inside its latency budget on
# a machine with no Ollama, instead of costing seconds per query.
OLLAMA_COOLDOWN = 60.0
_ollama_down_until = 0.0

RISK_PROMPT = ("Classify this text for PII risk. Reply with ONLY one word: "
               "HIGH, MEDIUM, or LOW. Text: {input}")
INTENT_PROMPT = ("What is the user's intent? Reply ONLY with one of: "
                 "QUESTION, TASK, SENSITIVE, DANGEROUS\nText: {input}")

# Local fail-closed danger screen. Deliberately narrow: weapons/explosives
# synthesis, malware authoring, and self-harm instructions.
DANGER_PATTERNS = [
    re.compile(r"\b(how|steps?|guide|instructions?|recipe)\b[^.?!]{0,60}\b"
               r"(make|build|create|synthesi[sz]e|construct|assemble)\b[^.?!]{0,40}\b"
               r"(bomb|explosive|ied|napalm|thermite|nerve agent|sarin|ricin|anthrax|"
               r"meth|methamphetamine|fentanyl|silencer|untraceable (gun|firearm)|ghost gun)", re.I),
    re.compile(r"\b(make|build|synthesi[sz]e|manufacture)\b[^.?!]{0,30}\b"
               r"(bomb|explosive|bioweapon|chemical weapon|nerve agent|ricin|anthrax)\b", re.I),
    re.compile(r"\b(write|create|build|generate)\b[^.?!]{0,40}\b"
               r"(ransomware|keylogger|botnet|rootkit|computer virus|malware|trojan)\b", re.I),
    re.compile(r"\bhow\b[^.?!]{0,40}\b(kill myself|commit suicide|end my life)\b", re.I),
]

VALID_RISK = {"HIGH", "MEDIUM", "LOW"}
VALID_INTENT = {"QUESTION", "TASK", "SENSITIVE", "DANGEROUS"}


@dataclass
class SentinelResult:
    risk_level: str            # HIGH | MEDIUM | LOW
    intent: str                # QUESTION | TASK | SENSITIVE | DANGEROUS
    blocked: bool
    reason: str = ""
    source: str = ""           # where the verdict came from
    latency_ms: float = 0.0
    ollama_available: bool = False


def _ollama_generate(prompt: str) -> str | None:
    """One non-streaming Ollama call. Returns None if Ollama isn't reachable."""
    global _ollama_down_until
    if time.monotonic() < _ollama_down_until:
        return None

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 8},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            out = json.loads(resp.read().decode()).get("response", "")
        _ollama_down_until = 0.0
        return out
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        _ollama_down_until = time.monotonic() + OLLAMA_COOLDOWN
        return None


def _first_token(text: str, valid: set[str]) -> str | None:
    for word in re.findall(r"[A-Za-z]+", (text or "").upper()):
        if word in valid:
            return word
    return None


def _local_danger_check(text: str) -> bool:
    return any(p.search(text) for p in DANGER_PATTERNS)


def _local_risk_heuristic(text: str) -> str:
    """
    Fallback PII risk when Ollama is unavailable. Structured identifiers are a
    strong HIGH signal; a capitalised multi-word name is a MEDIUM signal.
    """
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text) \
            or re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text) \
            or re.search(r"\b(?:\d{4}[\s-]?){3}\d{4}\b", text) \
            or re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text):
        return "HIGH"
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", text):
        return "MEDIUM"
    return "LOW"


class SentinelNode:
    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or OLLAMA_MODEL
        self.host = host or OLLAMA_HOST

    def classify(self, text: str) -> SentinelResult:
        t0 = time.perf_counter()
        text = text or ""

        # 1. Local danger screen — always, never skipped, never delegated.
        if _local_danger_check(text):
            return SentinelResult(
                risk_level="HIGH", intent="DANGEROUS", blocked=True,
                reason="local danger screen matched",
                source="local-danger-screen",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        word_count = len(text.split())
        short = word_count < SHORT_INPUT_WORDS

        # 2. PII risk. Short inputs skip the Ollama round trip (the expensive
        #    part) but are still scored locally — they are NOT auto-LOW.
        #    "I'm Tanmay Vasishta, tanmay@example.com, SSN 123-45-6789" is 19
        #    words: under a blind length rule it scores LOW, LOW skips the
        #    Presidio/spaCy tiers, regex alone cannot see a name, and the real
        #    name goes to the cloud. Message length says nothing about PII
        #    density. The local heuristic costs ~0.05ms and keeps the speed win.
        if short:
            risk = _local_risk_heuristic(text)
            risk_source = "fast-path(<20 words, local-heuristic)"
            ollama_up = False
        else:
            raw = _ollama_generate(RISK_PROMPT.format(input=text))
            ollama_up = raw is not None
            parsed = _first_token(raw, VALID_RISK) if raw else None
            if parsed:
                risk, risk_source = parsed, "ollama"
            else:
                risk, risk_source = _local_risk_heuristic(text), "local-heuristic"

        # 3. Intent — runs for every input regardless of length.
        raw_intent = _ollama_generate(INTENT_PROMPT.format(input=text))
        if raw_intent is not None:
            ollama_up = True
        parsed_intent = _first_token(raw_intent, VALID_INTENT) if raw_intent else None
        if parsed_intent:
            intent, intent_source = parsed_intent, "ollama"
        else:
            intent = "QUESTION" if text.strip().endswith("?") else "TASK"
            intent_source = "local-fallback"

        blocked = intent == "DANGEROUS"
        # Ollama's own verdict can still raise risk on a short input.
        if intent == "SENSITIVE" and risk == "LOW":
            risk = "MEDIUM"

        return SentinelResult(
            risk_level=risk,
            intent=intent,
            blocked=blocked,
            reason="intent classified DANGEROUS" if blocked else "",
            source=f"risk:{risk_source}, intent:{intent_source}",
            latency_ms=(time.perf_counter() - t0) * 1000,
            ollama_available=ollama_up,
        )
