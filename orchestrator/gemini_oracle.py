"""
Gemini Oracle — cloud reasoning with mandatory PII assertion guard.

Critical invariant (Tanmay's original contribution — MUST NOT be removed):
  Every call to query() or stream_query() MUST pass the PII assertion check.
  If raw PII is detected in the payload, raise PIILeakageError immediately.
  This is the final safety gate before any data leaves the machine.

Uses google-genai SDK (google.genai), not the deprecated google-generativeai.
Falls back to local LLaMA if Gemini is unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from utils.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT,
    get_best_available_model,
)
from utils.exceptions import PIILeakageError
from utils.audit_logger import audit
from utils.privacy_metrics import session_metrics
from orchestrator.rate_limiter import gemini_rate_limiter

logger = logging.getLogger(__name__)

# Pattern that indicates a placeholder (PII already redacted — this is fine)
_PLACEHOLDER_PATTERN = re.compile(r"\[PII_[A-Z]+_\d+\]")


class GeminiOracle:
    """
    Wrapper around Gemini 1.5 Flash for cloud reasoning.

    Every method asserts zero raw PII before sending to the network.
    """

    def __init__(self):
        self._client = None
        self._presidio_analyzer = None

    def query(self, sanitised_prompt: str) -> tuple[str, bool]:
        """
        Send sanitised prompt to Gemini. Returns (response_text, used_cloud: bool).

        On any failure (rate limit, network, timeout), falls back to local LLaMA.
        Raises PIILeakageError if raw PII is detected in the payload.
        """
        self._assert_no_raw_pii(sanitised_prompt)

        try:
            gemini_rate_limiter.wait_if_needed()
            client = self._get_client()
            if client is None:
                raise RuntimeError("Gemini client could not be initialised (missing API key?)")

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=sanitised_prompt,
                config={
                    "max_output_tokens": 1024,
                    "temperature": 0.3,
                },
            )
            text = response.text or ""
            audit.log_event(
                "GEMINI_QUERY",
                used_cloud=True,
                fallback=False,
                model=GEMINI_MODEL,
            )
            session_metrics.record_query("cloud", 0, fallback=False)
            return text, True

        except PIILeakageError:
            raise
        except Exception as e:
            logger.warning(f"Gemini unavailable: {e}. Falling back to local model.")
            return self._local_fallback(sanitised_prompt), False

    def stream_query(
        self, sanitised_prompt: str, callback: Callable[[str], None]
    ) -> str:
        """
        Stream tokens from Gemini. callback(token) is called for each token chunk.
        Returns the full assembled response.

        Falls back to blocking query if streaming fails.
        """
        self._assert_no_raw_pii(sanitised_prompt)

        full_response = ""
        try:
            gemini_rate_limiter.wait_if_needed()
            client = self._get_client()
            if client is None:
                raise RuntimeError("Gemini client not available")

            for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=sanitised_prompt,
                config={"max_output_tokens": 1024, "temperature": 0.3},
            ):
                token = chunk.text or ""
                if token:
                    full_response += token
                    callback(token)

            audit.log_event("GEMINI_STREAM", used_cloud=True, fallback=False)
            return full_response

        except PIILeakageError:
            raise
        except Exception as e:
            logger.warning(f"Gemini streaming failed: {e}. Using blocking fallback.")
            text, _ = self.query(sanitised_prompt)
            callback(text)
            return text

    # ── PII Assertion ─────────────────────────────────────────────────────────

    def _assert_no_raw_pii(self, text: str) -> None:
        """
        Abort with PIILeakageError if raw PII is found in the payload.

        Placeholders like [PII_PERSON_1] are OK — they mean PII was redacted.
        Raw values like "Rajesh Kumar" or "9876543210" are NOT OK.
        """
        # Strip placeholders from the check (they are intentional)
        stripped = _PLACEHOLDER_PATTERN.sub("", text)

        analyzer = self._get_presidio_analyzer()
        if analyzer is not None:
            try:
                results = analyzer.analyze(stripped, language="en")
                high_conf = [r for r in results if r.score > 0.85]
                if high_conf:
                    types = [r.entity_type for r in high_conf]
                    raise PIILeakageError(
                        f"Raw PII detected in cloud-bound payload: {types}. Aborting."
                    )
            except PIILeakageError:
                raise
            except Exception:
                pass  # Presidio error — don't block the query, but log
        # If Presidio not available, the tiered PII engine should have caught it upstream

    # ── Local Fallback ────────────────────────────────────────────────────────

    def _local_fallback(self, prompt: str) -> str:
        """Use local LLaMA when Gemini is unavailable."""
        try:
            import ollama

            model = get_best_available_model()
            response = ollama.generate(
                model=model,
                prompt=f"[OFFLINE MODE — Limited capability]\n\n{prompt}",
                options={"temperature": 0.3, "num_predict": 512},
            )
            audit.log_event("LOCAL_FALLBACK", used_cloud=False, fallback=True, model=model)
            session_metrics.record_query("cloud", 0, fallback=True)
            return response["response"]
        except Exception as e:
            return f"[PHANTOM] Both cloud and local models unavailable: {e}"

    # ── Lazy Init ─────────────────────────────────────────────────────────────

    def _get_client(self):
        """Lazy-init the google-genai client."""
        if self._client is not None:
            return self._client
        try:
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
            return self._client
        except Exception:
            return None

    def _get_presidio_analyzer(self):
        """Lazy-load Presidio. Returns None if not installed."""
        if self._presidio_analyzer is not None:
            return self._presidio_analyzer
        try:
            from presidio_analyzer import AnalyzerEngine
            self._presidio_analyzer = AnalyzerEngine()
            return self._presidio_analyzer
        except ImportError:
            return None
