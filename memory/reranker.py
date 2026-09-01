"""
Cross-encoder re-ranker — Tanmay's original contribution on top of ChromaDB.

Takes the top-5 candidates from RetrievalEngine (cosine + recency scored) and
re-scores them against the actual query using a cross-encoder model.
This catches cases where cosine similarity disagrees with true semantic relevance.

Falls back gracefully to the original ordering if sentence-transformers is unavailable.
"""

from __future__ import annotations


class MemoryReranker:
    """
    Cross-encoder re-ranker using ms-marco-MiniLM-L-6-v2.

    Input:  query + list of (score, text, metadata) from RetrievalEngine
    Output: top-2 (rerank_score, text, metadata) sorted descending
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None  # lazy-loaded

    def rerank(
        self,
        query: str,
        candidates: list[tuple[float, str, dict]],
        top_k: int = 2,
    ) -> list[tuple[float, str, dict]]:
        """
        Re-rank candidates using cross-encoder scores.

        Returns top_k entries as (score, text, metadata) sorted descending.
        Falls back to original order if cross-encoder unavailable.
        """
        if not candidates:
            return []

        model = self._get_model()
        if model is None:
            # Graceful degradation: return top_k from original cosine+recency order
            return candidates[:top_k]

        texts = [text for _, text, _ in candidates]
        pairs = [(query, text) for text in texts]

        try:
            scores = model.predict(pairs)
            reranked = [
                (float(score), text, meta)
                for score, (_, text, meta) in zip(scores, candidates)
            ]
            reranked.sort(key=lambda x: x[0], reverse=True)
            return reranked[:top_k]
        except Exception:
            return candidates[:top_k]

    def _get_model(self):
        """Lazy-load cross-encoder. Returns None if sentence-transformers not installed."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)
            return self._model
        except ImportError:
            return None
