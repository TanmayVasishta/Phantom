"""
Routing module test suite — 8 test cases covering routing rules, risk scoring,
intent cache, and HITL threshold behaviour.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from utils.models import IntentType, SentinelResult
from orchestrator.routing_rules import rule_based_route
from orchestrator.risk_scorer import calculate_risk_score, risk_level
from orchestrator.intent_cache import IntentCache


# ── Rule-Based Routing ────────────────────────────────────────────────────────

class TestRoutingRules:
    def test_file_op_high_confidence_routes_local(self):
        decision = rule_based_route(IntentType.FILE_OP, confidence=0.90)
        assert decision.target == "local"

    def test_file_op_low_confidence_routes_cloud(self):
        decision = rule_based_route(IntentType.FILE_OP, confidence=0.65)
        assert decision.target == "cloud"

    def test_general_qa_always_cloud(self):
        decision = rule_based_route(IntentType.GENERAL_QA, confidence=0.95)
        assert decision.target == "cloud"

    def test_unknown_always_cloud(self):
        decision = rule_based_route(IntentType.UNKNOWN, confidence=0.99)
        assert decision.target == "cloud"

    def test_memory_lookup_routes_memory(self):
        decision = rule_based_route(IntentType.MEMORY_LOOKUP, confidence=0.80)
        assert decision.target == "memory"
        assert decision.hitl_required is False

    def test_web_query_routes_cloud(self):
        decision = rule_based_route(IntentType.WEB_QUERY, confidence=0.85)
        assert decision.target == "cloud"

    def test_system_cmd_high_conf_local(self):
        decision = rule_based_route(IntentType.SYSTEM_CMD, confidence=0.82)
        assert decision.target == "local"


# ── Risk Score Formula ────────────────────────────────────────────────────────

class TestRiskScorer:
    def test_delete_keyword_high_risk(self):
        score = calculate_risk_score("delete", [], "rm ~/Documents/file.txt")
        # "delete"=50, "rm"=55, but ~/Documents is a safe dir so no +20
        assert score >= 50

    def test_low_risk_list_command(self):
        score = calculate_risk_score("list", [], "ls ~/Downloads")
        assert score <= 40  # below HITL threshold

    def test_hitl_triggers_above_threshold(self):
        decision = rule_based_route(
            IntentType.FILE_OP,
            confidence=0.90,
            sub_intent="delete",
            command="rm ~/Desktop/important.txt",
        )
        assert decision.risk_score > 40
        assert decision.hitl_required is True

    def test_safe_list_no_hitl(self):
        decision = rule_based_route(
            IntentType.FILE_OP,
            confidence=0.90,
            sub_intent="list",
            command="ls ~/Downloads",
        )
        assert decision.hitl_required is False

    def test_sudo_critical_risk(self):
        score = calculate_risk_score("install", [], "sudo apt install vim")
        assert score >= 90  # sudo=90 alone hits 90

    def test_risk_capped_at_100(self):
        score = calculate_risk_score(
            "delete wipe format",
            [],
            "sudo rm -rf / chmod 777 / password wipe format",
        )
        assert score == 100

    def test_risk_levels(self):
        assert risk_level(10)[0] == "LOW"
        assert risk_level(35)[0] == "MEDIUM"
        assert risk_level(55)[0] == "HIGH"
        assert risk_level(85)[0] == "CRITICAL"


# ── Intent Cache ──────────────────────────────────────────────────────────────

class TestIntentCache:
    def test_cache_miss_returns_none(self):
        cache = IntentCache()
        assert cache.get("FILE_OP", "list my downloads") is None

    def test_set_and_get(self):
        cache = IntentCache()
        cache.set("FILE_OP", "list downloads", "local", risk_score=0)
        result = cache.get("FILE_OP", "list downloads")
        assert result is not None
        assert result["route_target"] == "local"

    def test_high_risk_not_cached(self):
        cache = IntentCache()
        cache.set("FILE_OP", "delete everything", "local", risk_score=50)
        # High-risk (>40) should not be stored
        assert cache.get("FILE_OP", "delete everything") is None

    def test_invalidate_by_intent(self):
        cache = IntentCache()
        cache.set("FILE_OP", "list files", "local", risk_score=0)
        cache.set("GENERAL_QA", "what is python", "cloud", risk_score=0)
        cache.invalidate("FILE_OP")
        assert cache.get("FILE_OP", "list files") is None
        assert cache.get("GENERAL_QA", "what is python") is not None

    def test_ttl_expiry(self):
        import time
        cache = IntentCache(ttl=1)  # 1-second TTL for testing
        cache.set("FILE_OP", "list files", "local", risk_score=0)
        time.sleep(1.1)
        assert cache.get("FILE_OP", "list files") is None
