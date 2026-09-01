"""
Rule-based routing — pure decision logic, no LLM calls.

Routing table (from CLAUDE.md Section 6.5):
  LOCAL  : FILE_OP / SYSTEM_CMD / CALENDAR_OP with confidence >= 0.80
  CLOUD  : GENERAL_QA / WEB_QUERY / UNKNOWN or any intent with confidence < 0.80
  MEMORY : MEMORY_LOOKUP (direct ChromaDB, no LLM)
"""

from __future__ import annotations

from utils.config import CONFIDENCE_THRESHOLD_CLARIFY, RISK_THRESHOLD_HITL
from utils.models import IntentType, RouteDecision

from orchestrator.risk_scorer import calculate_risk_score

# Confidence required to prefer local over cloud
_LOCAL_CONFIDENCE_MIN = 0.80

# Intents that route locally when confidence is sufficient
_LOCAL_INTENTS = {IntentType.FILE_OP, IntentType.SYSTEM_CMD, IntentType.CALENDAR_OP}

# Intents that always go to cloud
_CLOUD_INTENTS = {IntentType.GENERAL_QA, IntentType.WEB_QUERY, IntentType.UNKNOWN}


def rule_based_route(
    intent: IntentType | str,
    confidence: float,
    sub_intent: str = "",
    entities: list[str] | None = None,
    command: str = "",
    enriched_prompt: str = "",
) -> RouteDecision:
    """
    Determine routing target and compute risk score.

    Returns RouteDecision with target, risk_score, and hitl_required fields set.
    """
    entities = entities or []
    intent_enum = IntentType(intent) if isinstance(intent, str) else intent

    # Calculate risk score
    score = calculate_risk_score(sub_intent, entities, command)
    hitl_needed = score > RISK_THRESHOLD_HITL

    # 1. Memory lookup — direct ChromaDB, no LLM
    if intent_enum == IntentType.MEMORY_LOOKUP:
        return RouteDecision(
            target="memory",
            risk_score=score,
            hitl_required=False,  # Memory lookups never need HITL
            enriched_prompt=enriched_prompt,
        )

    # 2. Local route — structured intents with high confidence
    if intent_enum in _LOCAL_INTENTS and confidence >= _LOCAL_CONFIDENCE_MIN:
        return RouteDecision(
            target="local",
            risk_score=score,
            hitl_required=hitl_needed,
            enriched_prompt=enriched_prompt,
        )

    # 3. Cloud route — knowledge questions, web queries, unknowns, or low confidence
    return RouteDecision(
        target="cloud",
        risk_score=score,
        hitl_required=hitl_needed,
        enriched_prompt=enriched_prompt,
    )
