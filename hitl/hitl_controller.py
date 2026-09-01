"""
HITL Controller — approval state machine for human-in-the-loop oversight.

Tanmay's original contribution. Three timeout tiers (do not collapse):
  risk < 40   → auto-approve after 10s
  40 <= risk <= 70 → wait up to 60s, then timeout-reject
  risk > 70   → no timeout: must be manually confirmed

Integrates: ChromaManager (write-back), RollbackStack, TaskOrchestrator,
AuditLogger, PrivacyMetrics.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from hitl.approval_states import HITLState
from utils.models import HITLDisplayData, RouteDecision
from utils.audit_logger import audit
from utils.privacy_metrics import session_metrics
from orchestrator.risk_scorer import risk_level

logger = logging.getLogger(__name__)


def get_timeout_policy(risk_score: int) -> dict:
    """
    Return the timeout policy for a given risk score.

    Three tiers (must not be reduced to fewer tiers without approval):
      < 40   : auto-approve after 10s
      40–70  : wait 60s, timeout → TIMEOUT_REJECTED
      > 70   : no timeout, must confirm manually
    """
    if risk_score < 40:
        return {"auto_approve": True, "timeout_seconds": 10}
    elif risk_score <= 70:
        return {"auto_approve": False, "timeout_seconds": 60, "on_timeout": HITLState.TIMEOUT_REJECTED}
    else:
        return {"auto_approve": False, "timeout_seconds": None}


class HITLController:
    """
    Manages the approve/reject/modify flow for actions with risk_score > 40.

    Usage:
        controller = HITLController(chroma_manager, rollback_stack, orchestrator)
        display_data = controller.prepare_display(route, query, memory_context)
        # Show display_data to user via HITLWidget
        controller.on_decision(HITLState.APPROVED)
    """

    def __init__(
        self,
        chroma_manager,
        rollback_stack,
        orchestrator,
    ):
        self._chroma = chroma_manager
        self._rollback = rollback_stack
        self._orchestrator = orchestrator
        self._current_decision: Optional[RouteDecision] = None
        self._current_query: str = ""
        self._current_command: str = ""

    def prepare_display(
        self,
        route: RouteDecision,
        query: str,
        command: str = "",
        memory_context: list[str] | None = None,
    ) -> HITLDisplayData:
        """
        Build the HITLDisplayData struct for the approval dialog.
        Stores state so on_decision() can act on it.
        """
        self._current_decision = route
        self._current_query = query
        self._current_command = command

        level, colour = risk_level(route.risk_score)
        policy = get_timeout_policy(route.risk_score)

        return HITLDisplayData(
            proposed_action=_humanise_action(query, route.target),
            risk_score=route.risk_score,
            risk_level=level,
            risk_color=colour,
            memory_context=memory_context or [],
            command_preview=command,
            timeout_seconds=policy.get("timeout_seconds"),
        )

    def on_decision(
        self,
        state: HITLState,
        modified_command: Optional[str] = None,
        interaction_summary: str = "",
    ) -> Optional[str]:
        """
        Handle the user's approval decision.

        Returns:
          - None for APPROVED / TIMEOUT_REJECTED (caller handles execution)
          - modified_command string for MODIFIED (re-route this)
          - None for REJECTED
        """
        audit.log_event(
            "HITL_DECISION",
            state=state.value,
            risk_score=self._current_decision.risk_score if self._current_decision else 0,
        )
        session_metrics.record_hitl(state.value.replace("timeout_", ""))

        if state == HITLState.APPROVED or state == HITLState.AUTO_APPROVED:
            self._rollback.clear()
            self._write_back_async(interaction_summary, "approved", hitl_approved=True)
            return None

        elif state in (HITLState.REJECTED, HITLState.TIMEOUT_REJECTED):
            self._rollback.pop_and_execute()
            self._write_back_async(interaction_summary, "rejected", hitl_approved=False)
            # Invalidate cache so this rejected route isn't reused
            if self._current_decision:
                self._orchestrator.on_hitl_rejection(
                    self._current_decision.target
                )
            return None

        elif state == HITLState.MODIFIED:
            self._write_back_async(interaction_summary, "modified", hitl_approved=False)
            return modified_command

        return None

    def _write_back_async(
        self, summary: str, outcome: str, hitl_approved: bool
    ) -> None:
        """Write interaction to ChromaDB asynchronously (non-blocking)."""
        if not summary:
            return
        import threading

        def _do_write():
            try:
                route = self._current_decision
                self._chroma.write_back(
                    interaction_summary=summary,
                    intent_type=route.target if route else "unknown",
                    outcome=outcome,
                    hitl_approved=hitl_approved,
                )
            except Exception as e:
                logger.warning(f"Async write-back failed: {e}")

        threading.Thread(target=_do_write, daemon=True).start()


def _humanise_action(query: str, route: str) -> str:
    """Create a human-readable description of the proposed action."""
    route_desc = {
        "local": "Execute locally on your computer",
        "cloud": "Send to cloud AI (sanitised — no PII)",
        "memory": "Search your memory",
    }.get(route, route)
    return f"{route_desc}: {query[:100]}{'...' if len(query) > 100 else ''}"
