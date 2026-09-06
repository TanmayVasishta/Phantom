"""
Cloud LLM call — thin wrapper over the parent project's PhantomRouter.

No routing logic is duplicated here: weights, budgets, the Groq speed lane,
backoff and quarantine all live in ../llm_router.py and are imported.
"""
from __future__ import annotations

import os
import sys
import time

_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

SYSTEM_PROMPT = (
    "You are Phantom, a helpful AI assistant. Answer the user's question "
    "directly and concisely. Do not comment on names, places, or identifiers "
    "in the message — treat them as given."
)


class CloudRouter:
    def __init__(self):
        from llm_router import PhantomRouter
        self._router = PhantomRouter.from_env()

    def ask(self, surrogate_text: str, context: str = "", session_id: str = "v2") -> dict:
        """
        Send surrogate text (never the original, never the tagged form) to the
        best available provider.

        Returns {response, provider, tokens_used, latency_ms, error}.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        from llm_router import safe_content, _estimate_tokens

        system = SYSTEM_PROMPT
        if context:
            system = f"{SYSTEM_PROMPT}\n\nRelevant earlier context:\n{context}"

        messages = [SystemMessage(content=system), HumanMessage(content=surrogate_text)]
        estimated = _estimate_tokens(system + " " + surrogate_text)

        t0 = time.perf_counter()
        try:
            response, provider = self._router.invoke(
                messages, estimated_tokens=estimated, session_id=session_id
            )
            # safe_content: Gemini returns .content as a list of structured
            # parts rather than a string.
            return {
                "response": safe_content(response),
                "provider": provider,
                "tokens_used": estimated,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "error": "",
            }
        except Exception as exc:
            return {
                "response": "",
                "provider": "none",
                "tokens_used": 0,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "error": str(exc),
            }

    def status(self) -> dict:
        try:
            return self._router.status_all()
        except Exception:
            return {}
