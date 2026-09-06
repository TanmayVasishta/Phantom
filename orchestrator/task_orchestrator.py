"""
Task Orchestrator — routes enriched prompts to local, cloud, or memory execution.

Uses intent_cache to skip LLM routing on repeated safe queries.
Delegates to rule_based_route for pure-logic decisions.
Plugs into LangChain ReAct agent for tool-augmented execution.
"""

from __future__ import annotations

import logging
import time

from utils.config import RISK_THRESHOLD_HITL
from utils.exceptions import RouteError
from utils.models import IntentType, RouteDecision, SentinelResult
from utils.audit_logger import audit
from orchestrator.intent_cache import IntentCache
from orchestrator.routing_rules import rule_based_route
from orchestrator.risk_scorer import risk_level

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    """
    Central routing engine for PHANTOM.

    Decision order:
    1. Check IntentCache (skip LLM if safe cached route exists).
    2. Apply rule_based_route (pure logic, no LLM).
    3. Store result in IntentCache.
    4. Return RouteDecision to the caller (HITL controller or executor).
    """

    def __init__(self):
        self._cache = IntentCache()
        self._nvidia: "NVIDIAOracle | None" = None       # lazy — priority 1
        self._gemini: "GeminiOracle | None" = None       # lazy — priority 2
        self._chroma: "ChromaManager | None" = None      # lazy
        self._middleware: "OSMiddleware | None" = None    # lazy

    # ── Primary routing ───────────────────────────────────────────────────────

    def route(
        self,
        sentinel_result: SentinelResult,
        enriched_prompt: str,
        command: str = "",
    ) -> RouteDecision:
        """
        Determine route for a processed query.

        Steps:
        1. Check intent cache.
        2. Apply routing rules.
        3. Cache the decision (if safe).
        4. Log the routing decision.
        """
        intent = sentinel_result.intent
        confidence = sentinel_result.confidence
        sub_intent = sentinel_result.sub_intent
        entities = sentinel_result.entities

        # 1. Cache lookup
        cached = self._cache.get(str(intent.value), enriched_prompt)
        if cached and cached["risk_score"] <= RISK_THRESHOLD_HITL:
            audit.log_event(
                "ROUTE_CACHE_HIT",
                intent=intent.value,
                route=cached["route_target"],
                risk_score=cached["risk_score"],
            )
            return RouteDecision(
                target=cached["route_target"],
                risk_score=cached["risk_score"],
                hitl_required=False,
                from_cache=True,
                enriched_prompt=enriched_prompt,
            )

        # 2. Rule-based routing
        decision = rule_based_route(
            intent=intent,
            confidence=confidence,
            sub_intent=sub_intent,
            entities=entities,
            command=command,
            enriched_prompt=enriched_prompt,
        )

        # 3. Cache safe decisions
        self._cache.set(
            str(intent.value), enriched_prompt, decision.target, decision.risk_score
        )

        # 4. Audit log
        level, _ = risk_level(decision.risk_score)
        audit.log_event(
            "ROUTE_DECISION",
            intent=intent.value,
            confidence=round(confidence, 3),
            route=decision.target,
            risk_score=decision.risk_score,
            risk_level=level,
            hitl_required=decision.hitl_required,
            from_cache=False,
        )

        return decision

    def execute(
        self,
        decision: RouteDecision,
        enriched_prompt: str,
        query: str = "",
    ) -> str:
        """
        Execute the routed decision and return the response text.

        Handles: local OS, cloud Gemini, memory lookup.
        Does NOT handle HITL — that is the HITL Controller's responsibility.
        """
        start_ms = time.time() * 1000

        try:
            if decision.target == "memory":
                response = self._execute_memory(query or enriched_prompt)
            elif decision.target == "cloud":
                response = self._execute_cloud(enriched_prompt)
            elif decision.target == "local":
                response = self._execute_local(enriched_prompt, query)
            else:
                raise RouteError(f"Unknown route target: {decision.target}")

        except Exception as e:
            logger.error(f"Execution error on route '{decision.target}': {e}")
            response = f"[PHANTOM] Execution failed: {e}"

        elapsed_ms = int(time.time() * 1000 - start_ms)
        audit.log_event(
            "EXECUTION_COMPLETE",
            route=decision.target,
            risk_score=decision.risk_score,
            execution_time_ms=elapsed_ms,
        )
        return response

    def on_hitl_rejection(self, intent: str) -> None:
        """Called by HITL controller on rejection — invalidates stale cache entries."""
        self._cache.invalidate(intent)
        audit.log_event("HITL_CACHE_INVALIDATED", intent=intent)

    # ── Execution backends ────────────────────────────────────────────────────

    def _execute_cloud(self, enriched_prompt: str) -> str:
        # Try NVIDIA NIM first (LLaMA 3.1 Nemotron 70B — most capable)
        nvidia = self._get_nvidia()
        if nvidia.is_available():
            text, ok = nvidia.query(enriched_prompt)
            if ok and text:
                return text
            logger.info("NVIDIA query failed or returned empty — falling back to Gemini.")

        # Fallback: Gemini 1.5 Flash
        oracle = self._get_gemini()
        text, _ = oracle.query(enriched_prompt)
        return text

    def _execute_memory(self, query: str) -> str:
        chroma = self._get_chroma()
        results = chroma.search(query, n_results=3)
        if not results:
            return "[PHANTOM] No relevant past interactions found."
        snippets = [r["document"] for r in results[:3]]
        return "From memory:\n" + "\n\n".join(f"- {s}" for s in snippets)

    def _execute_local(self, enriched_prompt: str, query: str) -> str:
        """
        Local execution: query the local LLM for GENERAL_QA/conversational intents,
        or return a dry-run command description for FILE_OP/SYSTEM_CMD.
        Full OS subprocess execution requires HITL approval and happens in os_middleware.
        """
        try:
            import ollama
            from utils.config import get_best_available_model

            model = get_best_available_model()
            resp = ollama.generate(
                model=model,
                prompt=enriched_prompt,
                options={"temperature": 0.3, "num_predict": 512},
            )
            return resp.get("response", "").strip() or "[LOCAL] No response."
        except Exception as e:
            logger.warning(f"Local LLM execution failed: {e}")
            return f"[LOCAL] {query or enriched_prompt}"

    # ── Lazy service accessors ────────────────────────────────────────────────

    def _get_nvidia(self):
        if self._nvidia is None:
            from orchestrator.nvidia_oracle import NVIDIAOracle
            self._nvidia = NVIDIAOracle()
        return self._nvidia

    def _get_gemini(self):
        if self._gemini is None:
            from orchestrator.gemini_oracle import GeminiOracle
            self._gemini = GeminiOracle()
        return self._gemini

    def _get_chroma(self):
        if self._chroma is None:
            from memory.chroma_manager import ChromaManager
            self._chroma = ChromaManager()
        return self._chroma
