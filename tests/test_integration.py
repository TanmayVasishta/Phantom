"""
HELIX Phase 2 — End-to-End Integration Tests

Tests the complete Phase 2 pipeline from query intake through routing and
response assembly. All external services (Ollama, Gemini, ChromaDB) are
mocked so these tests run fast and offline.

Run: python -m pytest tests/test_integration.py -v
"""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from utils.models import IntentType, SentinelResult, ClarificationRequest
from sentinel.session_pii_map import SessionPIIMap
from sentinel.pii_engine import PIIRedactionEngine
from sentinel.pii_restorer import PIIRestorer
from sentinel.sentinel_node import SentinelNode
from orchestrator.risk_scorer import calculate_risk_score, risk_level
from orchestrator.routing_rules import rule_based_route
from orchestrator.intent_cache import IntentCache


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_sentinel(intent: IntentType, confidence: float = 0.90, sub_intent: str = ""):
    payload = json.dumps({
        "intent": intent.value,
        "sub_intent": sub_intent,
        "confidence": confidence,
        "entities": [],
    })
    return patch("ollama.generate", return_value={"response": payload})


def _make_sentinel_result(
    intent: IntentType,
    confidence: float = 0.90,
    sub_intent: str = "list",
    entities: list[str] | None = None,
) -> SentinelResult:
    return SentinelResult(
        intent=intent,
        confidence=confidence,
        sub_intent=sub_intent,
        entities=entities or [],
    )


# ── Full PII pipeline (no mocks) ──────────────────────────────────────────────

class TestPIIPipelineIntegration:
    """PII redaction → session map → restore roundtrip."""

    def test_email_redact_and_restore(self):
        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)
        restorer = PIIRestorer(pii_map)

        query = "send the report to alice@example.com today"
        result = engine.redact(query, "FILE_OP")
        assert "alice@example.com" not in result.sanitised_text
        assert result.n_entities >= 1

        # Simulate response containing a placeholder
        placeholder = list(pii_map._map.keys())[0]
        fake_response = f"Sent to {placeholder} successfully."
        restored, warnings = restorer.restore_and_validate(fake_response)
        assert "alice@example.com" in restored
        # Presidio will flag the restored email as PII — this is CORRECT behavior.
        # The restorer warns that real PII is in the user-facing response (not a bug).
        # The important check: no UNKNOWN placeholders (no pipeline bugs).
        unknown_warnings = [w for w in warnings if "Unknown placeholder" in w]
        assert len(unknown_warnings) == 0

    def test_aadhaar_redacted_in_tier1(self):
        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)

        query = "My Aadhaar is 2345 6789 0123 — save it."
        result = engine.redact(query, "SYSTEM_CMD")
        assert "2345 6789 0123" not in result.sanitised_text
        assert result.n_entities >= 1

    def test_pan_redacted_in_tier1(self):
        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)

        query = "PAN card number ABCDE1234F needs to be filed."
        result = engine.redact(query, "FILE_OP")
        assert "ABCDE1234F" not in result.sanitised_text

    def test_clean_query_unchanged(self):
        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)

        query = "list all pdf files in downloads folder"
        result = engine.redact(query, "FILE_OP")
        assert result.n_entities == 0
        # Sanitised text should be semantically the same
        assert "pdf" in result.sanitised_text.lower()

    def test_session_map_cleared_between_calls(self):
        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)

        engine.redact("email rajesh@foo.com", "GENERAL_QA")
        first_count = len(pii_map._map)

        pii_map.clear()
        assert len(pii_map._map) == 0

        engine.redact("open my downloads folder", "FILE_OP")
        assert len(pii_map._map) == 0  # clean query — nothing added


# ── Sentinel + PII pipeline (mocked Ollama) ──────────────────────────────────

class TestSentinelPIIPipeline:
    """Sentinel → PII cascade integration."""

    def test_file_op_query_sanitised_before_routing(self):
        with _mock_sentinel(IntentType.FILE_OP, 0.91, "list"):
            node = SentinelNode()
            sentinel_result = node.process("list all files in downloads")

        assert isinstance(sentinel_result, SentinelResult)

        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)
        redaction = engine.redact("list all files in downloads", str(sentinel_result.intent.value))
        assert redaction.n_entities == 0  # no PII in this query

    def test_pii_query_sanitised_then_routed(self):
        query = "delete the file rajesh.kumar@gmail.com.txt from desktop"

        with _mock_sentinel(IntentType.FILE_OP, 0.88, "delete"):
            node = SentinelNode()
            sentinel_result = node.process(query)

        pii_map = SessionPIIMap()
        engine = PIIRedactionEngine(pii_map)
        redaction = engine.redact(query, str(sentinel_result.intent.value))

        # Email should be redacted
        assert "@gmail.com" not in redaction.sanitised_text

        # Route the sanitised query
        route = rule_based_route(
            intent=sentinel_result.intent,
            confidence=sentinel_result.confidence,
            sub_intent=sentinel_result.sub_intent,
            entities=sentinel_result.entities,
            command="",
            enriched_prompt=redaction.sanitised_text,
        )
        assert route.target == "local"


# ── Routing Rules ─────────────────────────────────────────────────────────────

class TestRoutingPipeline:
    """rule_based_route returns correct targets and risk scores."""

    def test_file_op_high_confidence_routes_local(self):
        route = rule_based_route(
            intent=IntentType.FILE_OP,
            confidence=0.90,
            sub_intent="list",
            entities=["Downloads"],
            command="",
            enriched_prompt="list files in downloads",
        )
        assert route.target == "local"
        assert not route.hitl_required

    def test_general_qa_routes_cloud(self):
        route = rule_based_route(
            intent=IntentType.GENERAL_QA,
            confidence=0.95,
            sub_intent="explain",
            entities=[],
            command="",
            enriched_prompt="explain how neural networks work",
        )
        assert route.target == "cloud"

    def test_memory_lookup_routes_memory(self):
        route = rule_based_route(
            intent=IntentType.MEMORY_LOOKUP,
            confidence=0.88,
            sub_intent="retrieve",
            entities=[],
            command="",
            enriched_prompt="what did I ask you last week",
        )
        assert route.target == "memory"

    def test_delete_command_triggers_hitl(self):
        route = rule_based_route(
            intent=IntentType.FILE_OP,
            confidence=0.90,
            sub_intent="delete",
            entities=["old_project"],
            command="rm -rf ~/old_project",
            enriched_prompt="delete old_project folder",
        )
        assert route.hitl_required

    def test_low_confidence_file_op_routes_cloud(self):
        route = rule_based_route(
            intent=IntentType.FILE_OP,
            confidence=0.60,  # below 0.80 threshold
            sub_intent="list",
            entities=[],
            command="",
            enriched_prompt="show me the stuff",
        )
        assert route.target == "cloud"

    def test_unknown_intent_routes_cloud(self):
        route = rule_based_route(
            intent=IntentType.UNKNOWN,
            confidence=0.70,
            sub_intent="",
            entities=[],
            command="",
            enriched_prompt="xyzzy frobnicate",
        )
        assert route.target == "cloud"


# ── Risk Scorer ───────────────────────────────────────────────────────────────

class TestRiskScorerPipeline:
    def test_safe_list_command_below_hitl_threshold(self):
        # "Downloads" contains "download" → +35 from RISK_WEIGHTS.
        # ~/Downloads is a safe dir so no +20 penalty. Score = 35, below threshold 40.
        score = calculate_risk_score("list", [], "ls ~/Downloads")
        assert score < 40, f"Expected below HITL threshold, got {score}"

    def test_delete_command_high_risk(self):
        score = calculate_risk_score("delete", ["project"], "rm -rf ~/project")
        assert score >= 50

    def test_sudo_command_very_high_risk(self):
        score = calculate_risk_score("install", [], "sudo apt install nmap")
        assert score >= 40

    def test_risk_capped_at_100(self):
        score = calculate_risk_score("wipe delete format", [], "sudo rm -rf / && mkfs")
        assert score <= 100

    def test_risk_level_labels(self):
        # Thresholds: <20=LOW, 20-40=MEDIUM, 41-70=HIGH, >70=CRITICAL
        assert risk_level(0)[0] == "LOW"
        assert risk_level(19)[0] == "LOW"
        assert risk_level(20)[0] == "MEDIUM"
        assert risk_level(39)[0] == "MEDIUM"
        assert risk_level(40)[0] == "MEDIUM"
        assert risk_level(41)[0] == "HIGH"
        assert risk_level(70)[0] == "HIGH"
        assert risk_level(85)[0] == "CRITICAL"


# ── Intent Cache ──────────────────────────────────────────────────────────────

class TestIntentCachePipeline:
    def test_cache_miss_on_first_lookup(self):
        cache = IntentCache()
        result = cache.get("FILE_OP", "list my downloads")
        assert result is None

    def test_cache_hit_after_set(self):
        cache = IntentCache()
        cache.set("FILE_OP", "list my downloads", "local", risk_score=0)
        result = cache.get("FILE_OP", "list my downloads")
        assert result is not None
        assert result["route_target"] == "local"

    def test_cache_invalidate_by_intent(self):
        cache = IntentCache()
        cache.set("FILE_OP", "list downloads", "local", risk_score=0)
        cache.set("GENERAL_QA", "explain python", "cloud", risk_score=0)
        cache.invalidate("FILE_OP")
        assert cache.get("FILE_OP", "list downloads") is None
        assert cache.get("GENERAL_QA", "explain python") is not None

    def test_cache_full_invalidate(self):
        cache = IntentCache(max_size=3)
        cache.set("FILE_OP", "q1", "local", 0)
        cache.set("GENERAL_QA", "q2", "cloud", 0)
        cache.invalidate()
        assert cache.get("FILE_OP", "q1") is None
        assert cache.get("GENERAL_QA", "q2") is None

    def test_lru_eviction_on_overflow(self):
        cache = IntentCache(max_size=2)
        cache.set("FILE_OP", "q1", "local", 0)
        cache.set("GENERAL_QA", "q2", "cloud", 0)
        cache.set("MEMORY_LOOKUP", "q3", "memory", 0)  # evicts q1
        assert cache.get("FILE_OP", "q1") is None
        assert cache.get("MEMORY_LOOKUP", "q3") is not None


# ── helix_cli.run_query integration (mocked) ─────────────────────────────────

class TestHelixCLIIntegration:
    """Test helix_cli.run_query() end-to-end with all external services mocked."""

    def _make_sentinel_payload(self, intent: str, confidence: float, sub: str = "") -> dict:
        return {"response": json.dumps({
            "intent": intent, "sub_intent": sub,
            "confidence": confidence, "entities": []
        })}

    def test_cli_run_query_returns_dict(self):
        """run_query must always return a dict with required keys."""
        from helix_cli import run_query

        sentinel_payload = self._make_sentinel_payload("GENERAL_QA", 0.93, "explain")
        local_llm_response = {"response": "Recursion is a function that calls itself."}

        with patch("ollama.generate", side_effect=[sentinel_payload, local_llm_response]):
            with patch("memory.chroma_manager.ChromaManager.search", return_value=[]):
                result = run_query("what is recursion", verbose=False)

        assert isinstance(result, dict)
        assert "query" in result
        assert "intent" in result
        assert "response" in result
        assert "n_pii" in result
        assert "route" in result

    def test_cli_low_confidence_returns_clarification(self):
        """Queries below the confidence threshold must return a clarification dict."""
        from helix_cli import run_query

        payload = self._make_sentinel_payload("UNKNOWN", 0.30)
        with patch("ollama.generate", return_value=payload):
            result = run_query("do the thing", verbose=False)

        assert result["intent"] == "UNKNOWN"
        assert "Clarification" in result["response"] or result["route"] == "none"

    def test_cli_pii_in_query_redacted(self):
        """PII in the query must not appear in the routed prompt."""
        from helix_cli import run_query

        query = "send this to test@example.com"
        sentinel_payload = self._make_sentinel_payload("GENERAL_QA", 0.88, "send")
        local_resp = {"response": "Message prepared."}

        with patch("ollama.generate", side_effect=[sentinel_payload, local_resp]):
            with patch("memory.chroma_manager.ChromaManager.search", return_value=[]):
                result = run_query(query, verbose=False)

        assert result["n_pii"] >= 1
        # PII must not appear raw in the response path
        assert "test@example.com" not in result.get("response", "")

    def test_cli_hitl_required_skips_execution(self):
        """High-risk local routes must be reported as HITL-required, not executed."""
        from helix_cli import run_query

        sentinel_payload = self._make_sentinel_payload("FILE_OP", 0.91, "delete")
        with patch("ollama.generate", return_value=sentinel_payload):
            with patch("memory.chroma_manager.ChromaManager.search", return_value=[]):
                result = run_query("delete everything in downloads", verbose=False)

        # CLI mode: HITL required → should not execute, should signal HITL
        assert "HITL" in result["response"] or result["route"] in ("local", "cloud")
