"""
Sentinel Node — two-pass intent classification using a local LLM.

Pass 1: Intent classification via Ollama structured output.
Pass 2: Basic PII pre-screen (entity flagging for the PII Engine).

Confidence gate (Tanmay's original contribution):
  confidence < CONFIDENCE_THRESHOLD_CLARIFY (0.65) → return ClarificationRequest.
  The HUD asks the user before any routing occurs.
"""

from __future__ import annotations

import json
import re

from utils.config import CONFIDENCE_THRESHOLD_CLARIFY, get_best_available_model
from utils.exceptions import SentinelError
from utils.models import ClarificationRequest, IntentType, SentinelResult


_SYSTEM_PROMPT = """You are an intent classifier for a privacy-first local AI assistant.
Classify the user query into EXACTLY ONE intent from:
[FILE_OP, SYSTEM_CMD, CALENDAR_OP, MEMORY_LOOKUP, WEB_QUERY, GENERAL_QA, UNKNOWN]

Intent definitions:
- FILE_OP: file or directory operations (create, delete, move, copy, list, rename)
- SYSTEM_CMD: terminal/system commands, process management, package installation
- CALENDAR_OP: schedule, reminder, calendar, meeting, alarm
- MEMORY_LOOKUP: retrieve past context, "what did I do", "last time I asked"
- WEB_QUERY: search the internet, browse, look up online
- GENERAL_QA: knowledge questions, explanations, "what is", "how does"
- UNKNOWN: anything that doesn't fit the above

Also identify:
- sub_intent: the specific action (delete, create, rename, search, list, etc.)
- confidence: your confidence as a float 0.0-1.0
- entities: list of objects/targets mentioned (file names, folder names, topics)

Respond ONLY with valid JSON. No preamble. No markdown. No code fences.
Format: {"intent": "...", "sub_intent": "...", "confidence": 0.0, "entities": [...]}"""


class SentinelNode:
    """
    Two-pass Sentinel Node using a local LLM for intent classification.

    The confidence gate is a core architectural feature — it prevents low-confidence
    intents from being routed blindly. Do not remove this gate.
    """

    def __init__(
        self,
        model_name: str | None = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD_CLARIFY,
        max_retries: int = 3,
    ):
        self._model = model_name or get_best_available_model()
        self._threshold = confidence_threshold
        self._max_retries = max_retries

    def process(self, query: str) -> SentinelResult | ClarificationRequest:
        """
        Main entry point. Returns SentinelResult if confident, else ClarificationRequest.

        Raises SentinelError if classification fails after max_retries.
        """
        result = self._classify_with_retry(query)

        if result.confidence < self._threshold:
            return ClarificationRequest(
                original_query=query,
                interpretation=self._build_interpretation(result),
                confidence=result.confidence,
            )

        return result

    def _classify_with_retry(self, query: str) -> SentinelResult:
        """Call Ollama with structured output, retrying up to max_retries times."""
        import ollama

        from utils.ollama_health import is_available, mark_down

        # Fast path when Ollama isn't running: three failed connection attempts
        # cost ~12s and were being paid on *every* query. The breaker turns that
        # into a sub-second probe, and re-checks once its cooldown lapses.
        if not is_available():
            raise SentinelError("Ollama unavailable (cached probe) — using fallback intent.")

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = ollama.generate(
                    model=self._model,
                    prompt=f"{_SYSTEM_PROMPT}\n\nQuery: {query}",
                    format=SentinelResult.model_json_schema(),
                    options={"temperature": 0.1, "num_predict": 256},
                )
                raw = response["response"].strip()

                # Try Pydantic model_validate_json first (structured output path)
                try:
                    return SentinelResult.model_validate_json(raw)
                except Exception:
                    pass

                # Fallback: extract JSON from response manually
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return SentinelResult.model_validate(data)

            except Exception as e:
                last_error = e

        # Final fallback — return UNKNOWN with low confidence rather than crashing
        if last_error is not None:
            # If Ollama is unreachable, trip the breaker so the next query
            # doesn't repeat the same expensive round of failed connections.
            if "connect" in str(last_error).lower() or "refused" in str(last_error).lower():
                mark_down()
                raise SentinelError(
                    f"Ollama unavailable after {self._max_retries} retries: {last_error}"
                )

        return SentinelResult(
            intent=IntentType.UNKNOWN,
            confidence=0.2,
            sub_intent="unknown",
            entities=[],
        )

    def _build_interpretation(self, result: SentinelResult) -> str:
        """Build a human-readable interpretation for the clarification dialog."""
        intent_descriptions = {
            IntentType.FILE_OP: f"perform a file operation ({result.sub_intent or 'unspecified'})",
            IntentType.SYSTEM_CMD: f"run a system command ({result.sub_intent or 'unspecified'})",
            IntentType.CALENDAR_OP: "manage your calendar or schedule",
            IntentType.MEMORY_LOOKUP: "search your past interactions",
            IntentType.WEB_QUERY: "search the web",
            IntentType.GENERAL_QA: "answer a general knowledge question",
            IntentType.UNKNOWN: "perform an unrecognised action",
        }
        intent_desc = intent_descriptions.get(result.intent, "do something")
        entities_str = (
            f" involving {', '.join(result.entities)}" if result.entities else ""
        )
        return f"You want to {intent_desc}{entities_str}"
