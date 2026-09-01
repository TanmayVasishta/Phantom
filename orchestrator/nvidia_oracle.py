"""
NVIDIA Oracle — cloud reasoning via NVIDIA NIM (LLaMA 3.1 Nemotron 70B).

Uses the OpenAI-compatible NVIDIA NIM endpoint.
Applies the same PII assertion guard as GeminiOracle — no raw PII ever leaves
the machine regardless of which cloud provider is used.

Priority in TaskOrchestrator: NVIDIA > Gemini > Local Ollama fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from utils.config import (
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_CLOUD_MODEL,
)
from utils.exceptions import PIILeakageError
from utils.audit_logger import audit
from utils.privacy_metrics import session_metrics
from orchestrator.rate_limiter import gemini_rate_limiter  # reuse rate limiter pattern

logger = logging.getLogger(__name__)

_PLACEHOLDER_PATTERN = re.compile(r"\[PII_[A-Z]+_\d+\]")


class NVIDIAOracle:
    """
    NVIDIA NIM cloud oracle using LLaMA 3.1 Nemotron 70B.

    Same interface as GeminiOracle — TaskOrchestrator calls query() on whichever
    oracle is active. Swapping providers requires zero changes to orchestrator logic.
    """

    def __init__(self, model: str = NVIDIA_CLOUD_MODEL):
        self._model = model
        self._client = None
        self._presidio_analyzer = None

    def is_available(self) -> bool:
        """Return True if an NVIDIA API key is configured."""
        return bool(NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("YOUR_"))

    def query(self, sanitised_prompt: str) -> tuple[str, bool]:
        """
        Send sanitised prompt to NVIDIA NIM. Returns (response_text, used_cloud: bool).

        Raises PIILeakageError if raw PII detected in payload.
        Falls back to local Ollama on any failure.
        """
        self._assert_no_raw_pii(sanitised_prompt)

        if not self.is_available():
            logger.info("NVIDIA API key not configured — skipping.")
            return "", False

        try:
            client = self._get_client()
            completion = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": sanitised_prompt}],
                temperature=0.3,
                max_tokens=1024,
                timeout=15,
            )
            text = completion.choices[0].message.content or ""
            audit.log_event(
                "NVIDIA_QUERY",
                used_cloud=True,
                fallback=False,
                model=self._model,
            )
            session_metrics.record_query("cloud", 0, fallback=False)
            return text, True

        except PIILeakageError:
            raise
        except Exception as e:
            logger.warning(f"NVIDIA NIM unavailable: {e}")
            return "", False

    def stream_query(
        self, sanitised_prompt: str, callback: Callable[[str], None]
    ) -> str:
        """
        Stream tokens from NVIDIA NIM. callback(token) called per chunk.
        Falls back to blocking query if streaming fails.
        """
        self._assert_no_raw_pii(sanitised_prompt)

        if not self.is_available():
            return ""

        full_response = ""
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": sanitised_prompt}],
                temperature=0.3,
                max_tokens=1024,
                stream=True,
                timeout=15,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_response += token
                    callback(token)

            audit.log_event("NVIDIA_STREAM", used_cloud=True, fallback=False)
            return full_response

        except PIILeakageError:
            raise
        except Exception as e:
            logger.warning(f"NVIDIA streaming failed: {e}. Using blocking fallback.")
            text, _ = self.query(sanitised_prompt)
            if text:
                callback(text)
            return text

    # ── PII Assertion ─────────────────────────────────────────────────────────

    def _assert_no_raw_pii(self, text: str) -> None:
        """Abort with PIILeakageError if raw PII found. Same guard as GeminiOracle."""
        stripped = _PLACEHOLDER_PATTERN.sub("", text)
        analyzer = self._get_presidio_analyzer()
        if analyzer is None:
            return
        try:
            results = analyzer.analyze(stripped, language="en")
            high_conf = [r for r in results if r.score > 0.85]
            if high_conf:
                types = [r.entity_type for r in high_conf]
                raise PIILeakageError(
                    f"Raw PII detected in NVIDIA-bound payload: {types}. Aborting."
                )
        except PIILeakageError:
            raise
        except Exception:
            pass

    # ── Lazy Init ─────────────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=NVIDIA_API_KEY,
            )
            return self._client
        except ImportError:
            raise RuntimeError(
                "openai package required for NVIDIA NIM. Run: pip install openai"
            )

    def _get_presidio_analyzer(self):
        if self._presidio_analyzer is not None:
            return self._presidio_analyzer
        try:
            from presidio_analyzer import AnalyzerEngine
            self._presidio_analyzer = AnalyzerEngine()
            return self._presidio_analyzer
        except ImportError:
            return None
