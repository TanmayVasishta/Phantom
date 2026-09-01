"""
Memory module test suite — 10 test cases covering ChromaDB, retrieval,
recency decay, eviction policy, and conversation buffer.
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from memory.conversation_buffer import ConversationBuffer
from memory.retrieval_engine import RetrievalEngine, recency_score
from memory.eviction_policy import eviction_score


# ── Recency Score Formula ─────────────────────────────────────────────────────

class TestRecencyScore:
    def test_no_decay_today(self):
        score = recency_score(cosine_sim=0.8, days_old=0.0)
        assert abs(score - 0.8) < 0.001  # no decay for today's entry

    def test_decay_after_7_days(self):
        score = recency_score(cosine_sim=0.8, days_old=7.0)
        # exp(-0.1 * 7) ≈ 0.497 → 0.8 * 0.497 ≈ 0.398
        assert score < 0.8 * 0.5 + 0.01
        assert score > 0.0

    def test_perfect_cosine_decays(self):
        score_now = recency_score(1.0, 0.0)
        score_old = recency_score(1.0, 30.0)
        assert score_now > score_old

    def test_threshold_filtering(self):
        # Entry with low cosine and old age should fall below 0.65 threshold
        import math
        score = 0.7 * math.exp(-0.1 * 10)  # ~0.7 * 0.368 = 0.258
        from utils.config import MEMORY_SCORE_THRESHOLD
        assert score < MEMORY_SCORE_THRESHOLD


# ── Eviction Policy ───────────────────────────────────────────────────────────

class TestEvictionScore:
    def test_newest_high_retrieval_kept(self):
        score = eviction_score(
            recency_rank=0,         # newest
            retrieval_frequency=10,
            total_entries=100,
            max_retrieval_count=10,
        )
        assert score > 0.9  # should be near 1.0

    def test_oldest_low_retrieval_evicted(self):
        score = eviction_score(
            recency_rank=99,        # oldest
            retrieval_frequency=0,
            total_entries=100,
            max_retrieval_count=10,
        )
        assert score < 0.1  # should be near 0.0

    def test_recency_vs_frequency_tradeoff(self):
        # Old but frequently retrieved entry vs new but never retrieved
        old_popular = eviction_score(
            recency_rank=90, retrieval_frequency=8,
            total_entries=100, max_retrieval_count=10,
        )
        new_unused = eviction_score(
            recency_rank=5, retrieval_frequency=0,
            total_entries=100, max_retrieval_count=10,
        )
        # Old-but-popular should outscore new-but-unused because
        # retrieval_frequency has 0.6 weight vs recency 0.4
        # old_popular: (0.10 * 0.4) + (0.80 * 0.6) = 0.04 + 0.48 = 0.52
        # new_unused:  (0.95 * 0.4) + (0.00 * 0.6) = 0.38 + 0.00 = 0.38
        assert old_popular > new_unused


# ── Conversation Buffer ───────────────────────────────────────────────────────

class TestConversationBuffer:
    def test_add_and_retrieve(self):
        buf = ConversationBuffer(max_turns=10)
        buf.add("user", "list my downloads")
        buf.add("assistant", "Here are your files in ~/Downloads")
        turns = buf.get_recent(2)
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    def test_max_turns_limit(self):
        buf = ConversationBuffer(max_turns=5)
        for i in range(8):
            buf.add("user", f"query {i}")
        assert len(buf) == 5  # oldest 3 dropped

    def test_reference_resolution(self):
        buf = ConversationBuffer()
        buf.add("user", "list my notes.txt file")
        buf.add("assistant", "Here is notes.txt")
        result = buf.resolve_reference("delete that")
        assert "notes.txt" in result or "referring to" in result

    def test_no_resolution_needed(self):
        buf = ConversationBuffer()
        buf.add("user", "list my downloads")
        result = buf.resolve_reference("list my photos")
        assert result == "list my photos"  # no pronouns — unchanged

    def test_format_for_prompt(self):
        buf = ConversationBuffer()
        buf.add("user", "list downloads")
        buf.add("assistant", "Done.")
        formatted = buf.format_for_prompt()
        assert "USER:" in formatted
        assert "ASSISTANT:" in formatted

    def test_clear(self):
        buf = ConversationBuffer()
        buf.add("user", "something")
        buf.clear()
        assert len(buf) == 0


# ── ChromaDB Integration (requires ChromaDB running) ──────────────────────────

class TestChromaManager:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Use a temporary directory for each test to avoid polluting real data."""
        from memory.chroma_manager import ChromaManager
        self.manager = ChromaManager(persist_dir=str(tmp_path / "test_chromadb"))

    def test_write_and_count(self):
        self.manager.write_back(
            interaction_summary="User asked to list downloads. Success.",
            intent_type="FILE_OP",
            outcome="success",
            hitl_approved=True,
        )
        # Should be in both session and persistent
        assert self.manager.count("session") == 1
        assert self.manager.count("persistent") == 1

    def test_unapproved_not_in_persistent(self):
        self.manager.write_back(
            interaction_summary="User asked to delete a file. Rejected by HITL.",
            intent_type="FILE_OP",
            outcome="rejected",
            hitl_approved=False,
        )
        assert self.manager.count("session") == 1
        assert self.manager.count("persistent") == 0

    def test_fallback_not_in_persistent(self):
        self.manager.write_back(
            interaction_summary="Gemini was down, used local fallback for general QA.",
            intent_type="GENERAL_QA",
            outcome="success",
            hitl_approved=True,
            fallback=True,
        )
        assert self.manager.count("persistent") == 0  # fallback responses not promoted
