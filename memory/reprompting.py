"""
Memory-Augmented Re-prompting — builds enriched prompts with token budget management.

Pipeline:
  1. RetrievalEngine → top-5 candidates (cosine + recency)
  2. MemoryReranker  → top-2 after cross-encoder re-scoring
  3. ConversationBuffer → last 5 turns
  4. build_enriched_prompt() → token-budgeted final prompt

Token budget management (Tanmay's original contribution):
  - Never truncate the current query.
  - Truncate older memory snippets first if over budget.
  - Buffer: 100 tokens reserved for safety margin.
"""

from __future__ import annotations

import tiktoken

from memory.conversation_buffer import ConversationBuffer
from memory.reranker import MemoryReranker
from memory.retrieval_engine import RetrievalEngine
from utils.config import MAX_PROMPT_TOKENS
from utils.models import IntentType


_SYSTEM_PROMPT = """You are HELIX, a privacy-first AI assistant for local system management.
You have access to local OS commands and cloud reasoning.
Use the context below ONLY if directly relevant to the current task.
Never reveal PII. Never execute irreversible actions without flagging them."""


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens using tiktoken. Falls back to word count estimate on failure."""
    try:
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


class RepromptingModule:
    """
    Constructs enriched prompts by injecting relevant memory context.

    Respects a configurable token budget — older, lower-scoring snippets
    are dropped before the query is ever truncated.
    """

    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        reranker: MemoryReranker | None = None,
        conversation_buffer: ConversationBuffer | None = None,
        max_tokens: int = MAX_PROMPT_TOKENS,
    ):
        self._retrieval = retrieval_engine
        self._reranker = reranker or MemoryReranker()
        self._buffer = conversation_buffer or ConversationBuffer()
        self._max_tokens = max_tokens

    @property
    def conversation_buffer(self) -> ConversationBuffer:
        return self._buffer

    def build(self, sanitised_query: str, intent: IntentType | str = "") -> str:
        """
        Main entry point — returns the full enriched prompt.

        Steps:
        1. Retrieve top-5 memory candidates.
        2. Re-rank to top-2.
        3. Inject conversation history.
        4. Apply token budget.
        5. Return formatted prompt.
        """
        # 1. Retrieve
        candidates = self._retrieval.retrieve_relevant(sanitised_query, top_k=5)

        # 2. Re-rank
        top_snippets = self._reranker.rerank(sanitised_query, candidates, top_k=2)

        # 3. Conversation context
        conversation_ctx = self._buffer.format_for_prompt(n=5)

        # 4. Build within token budget
        return self._build_within_budget(
            query=sanitised_query,
            memory_snippets=[text for _, text, _ in top_snippets],
            conversation_context=conversation_ctx,
        )

    def _build_within_budget(
        self,
        query: str,
        memory_snippets: list[str],
        conversation_context: str,
    ) -> str:
        """
        Assemble prompt while respecting MAX_PROMPT_TOKENS.

        Priority: system_prompt > current_query > conversation > memory (newest first).
        """
        system_tokens = _count_tokens(_SYSTEM_PROMPT)
        query_tokens = _count_tokens(query)
        overhead = 100  # safety buffer

        budget = self._max_tokens - system_tokens - query_tokens - overhead

        # Try to fit conversation context
        parts: list[str] = []
        if conversation_context:
            conv_tokens = _count_tokens(conversation_context)
            if budget - conv_tokens > 50:
                parts.append(f"[Recent conversation]:\n{conversation_context}")
                budget -= conv_tokens

        # Fit memory snippets (best-scored first — already sorted)
        for snippet in memory_snippets:
            formatted = f"[Past context]: {snippet}"
            snippet_tokens = _count_tokens(formatted)
            if budget - snippet_tokens > 0:
                parts.append(formatted)
                budget -= snippet_tokens

        if not parts:
            # No memory fits — use query directly
            return f"{_SYSTEM_PROMPT}\n\nCURRENT TASK: {query}"

        context_block = "\n\n".join(parts)
        return f"{_SYSTEM_PROMPT}\n\n{context_block}\n\nCURRENT TASK: {query}"
