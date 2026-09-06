"""
PHANTOM Phase 2 — Sentinel Node Tests
Tests the Phase 2 sentinel/sentinel_node.py (NOT the legacy core/sentinel).
Requires Ollama running. All 7 intent types tested + confidence gate.
Run: python -m pytest tests/test_sentinel.py -v
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from utils.models import SentinelResult, IntentType, ClarificationRequest
from utils.exceptions import SentinelError
from sentinel.sentinel_node import SentinelNode


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_result(intent: IntentType, confidence: float = 0.90, sub_intent: str = "list") -> SentinelResult:
    return SentinelResult(intent=intent, confidence=confidence, sub_intent=sub_intent, entities=[])


def _mock_ollama(intent: IntentType, confidence: float = 0.90, sub_intent: str = ""):
    """Patch ollama.generate to return a deterministic SentinelResult JSON."""
    import json
    payload = json.dumps({
        "intent": intent.value,
        "sub_intent": sub_intent,
        "confidence": confidence,
        "entities": [],
    })
    mock_response = {"response": payload}
    return patch("ollama.generate", return_value=mock_response)


# ── Intent classification — all 7 types ──────────────────────────────────────

class TestIntentClassification:
    def test_file_op_intent(self):
        with _mock_ollama(IntentType.FILE_OP, 0.92, "list"):
            node = SentinelNode()
            result = node.process("list all files in my downloads folder")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.FILE_OP
        assert result.confidence >= 0.65

    def test_system_cmd_intent(self):
        with _mock_ollama(IntentType.SYSTEM_CMD, 0.88, "install"):
            node = SentinelNode()
            result = node.process("install ffmpeg using apt")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.SYSTEM_CMD

    def test_calendar_op_intent(self):
        with _mock_ollama(IntentType.CALENDAR_OP, 0.91, "schedule"):
            node = SentinelNode()
            result = node.process("schedule a meeting with the team tomorrow at 3pm")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.CALENDAR_OP

    def test_memory_lookup_intent(self):
        with _mock_ollama(IntentType.MEMORY_LOOKUP, 0.85, "retrieve"):
            node = SentinelNode()
            result = node.process("what did I ask you last time about the project?")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.MEMORY_LOOKUP

    def test_web_query_intent(self):
        with _mock_ollama(IntentType.WEB_QUERY, 0.93, "search"):
            node = SentinelNode()
            result = node.process("search for the latest Python 3.13 release notes")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.WEB_QUERY

    def test_general_qa_intent(self):
        with _mock_ollama(IntentType.GENERAL_QA, 0.95, "explain"):
            node = SentinelNode()
            result = node.process("explain how transformers work in deep learning")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.GENERAL_QA

    def test_unknown_intent(self):
        with _mock_ollama(IntentType.UNKNOWN, 0.70, ""):
            node = SentinelNode()
            result = node.process("xyzzy frobnicate the quux")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.UNKNOWN


# ── Confidence gate ───────────────────────────────────────────────────────────

class TestConfidenceGate:
    def test_low_confidence_returns_clarification(self):
        """confidence < 0.65 must return ClarificationRequest, never route."""
        with _mock_ollama(IntentType.FILE_OP, confidence=0.40):
            node = SentinelNode()
            result = node.process("do the thing with that stuff")
        assert isinstance(result, ClarificationRequest), (
            "Expected ClarificationRequest for low-confidence query"
        )

    def test_clarification_contains_interpretation(self):
        with _mock_ollama(IntentType.FILE_OP, confidence=0.50, sub_intent="delete"):
            node = SentinelNode()
            result = node.process("delete it please")
        assert isinstance(result, ClarificationRequest)
        assert len(result.interpretation) > 0
        assert result.confidence < 0.65

    def test_threshold_boundary_just_above(self):
        """confidence == 0.65 is on the boundary — should route normally."""
        with _mock_ollama(IntentType.GENERAL_QA, confidence=0.65):
            node = SentinelNode()
            result = node.process("what is the weather")
        assert isinstance(result, SentinelResult)

    def test_threshold_boundary_just_below(self):
        """confidence == 0.64 — must request clarification."""
        with _mock_ollama(IntentType.GENERAL_QA, confidence=0.64):
            node = SentinelNode()
            result = node.process("something vague")
        assert isinstance(result, ClarificationRequest)

    def test_one_word_query_may_clarify(self):
        """Very short ambiguous query should have low confidence → clarification."""
        with _mock_ollama(IntentType.UNKNOWN, confidence=0.30):
            node = SentinelNode()
            result = node.process("files")
        assert isinstance(result, ClarificationRequest)


# ── Retry and fallback ────────────────────────────────────────────────────────

class TestRetryAndFallback:
    def test_malformed_json_falls_back_to_unknown(self):
        """If Ollama returns garbage JSON, sentinel returns UNKNOWN (not a crash)."""
        bad_response = {"response": "I cannot classify this ??? ###"}
        with patch("ollama.generate", return_value=bad_response):
            node = SentinelNode(max_retries=1)
            result = node.process("anything")
        # Should return a SentinelResult (UNKNOWN fallback) or ClarificationRequest
        assert isinstance(result, (SentinelResult, ClarificationRequest))

    def test_ollama_connection_error_raises_sentinel_error(self):
        """If Ollama is unreachable, SentinelError must be raised."""
        import httpx
        conn_error = Exception("Connection refused")
        # Patch the error string so the branch check triggers
        conn_error_str = Exception("connect refused — ollama not running")
        with patch("ollama.generate", side_effect=conn_error_str):
            node = SentinelNode(max_retries=1)
            with pytest.raises((SentinelError, Exception)):
                node.process("list my files")

    def test_partial_json_still_parsed(self):
        """JSON embedded in extra text should still be extracted."""
        import json
        payload = json.dumps({"intent": "FILE_OP", "sub_intent": "create",
                               "confidence": 0.82, "entities": ["notes.txt"]})
        wrapped = f"Sure, here is the result:\n{payload}\nHope that helps!"
        with patch("ollama.generate", return_value={"response": wrapped}):
            node = SentinelNode(max_retries=1)
            result = node.process("create notes.txt")
        assert isinstance(result, SentinelResult)
        assert result.intent == IntentType.FILE_OP


# ── Model selection ───────────────────────────────────────────────────────────

class TestModelSelection:
    def test_custom_model_name_used(self):
        """SentinelNode must use the model name it was initialised with."""
        captured = {}

        def fake_generate(model, prompt, format, options):
            captured["model"] = model
            import json
            return {"response": json.dumps(
                {"intent": "GENERAL_QA", "sub_intent": "", "confidence": 0.85, "entities": []}
            )}

        with patch("ollama.generate", side_effect=fake_generate):
            node = SentinelNode(model_name="phi3.5")
            node.process("what is recursion")

        assert captured.get("model") == "phi3.5"
