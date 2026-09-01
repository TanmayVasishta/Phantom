"""
Retrieval Engine — cosine similarity + recency decay scoring.

Original formula (Yukta's contribution):
  final_score = cosine_sim * exp(-λ * days_old)
  λ = MEMORY_RECENCY_LAMBDA = 0.1
  Threshold: only return results with final_score > MEMORY_SCORE_THRESHOLD (0.65)
"""

from __future__ import annotations

import math
import time

from utils.config import MEMORY_RECENCY_LAMBDA, MEMORY_SCORE_THRESHOLD


def cosine_distance_to_similarity(distance: float) -> float:
    """
    ChromaDB returns cosine DISTANCE (0=identical, 2=opposite).
    Convert to cosine SIMILARITY (1=identical, -1=opposite).
    """
    return 1.0 - distance


def recency_score(cosine_sim: float, days_old: float, lambda_: float = MEMORY_RECENCY_LAMBDA) -> float:
    """
    Apply exponential recency decay to cosine similarity.

    recency_score = cosine_sim * exp(-λ * days_old)

    A document from today (days_old=0) keeps its full similarity score.
    After 7 days with λ=0.1, the score is ~50% of its cosine similarity.
    """
    return cosine_sim * math.exp(-lambda_ * days_old)


def _days_since(iso_timestamp: str) -> float:
    """Parse ISO timestamp and return how many days have elapsed."""
    try:
        stored = time.mktime(time.strptime(iso_timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f"))
    except ValueError:
        try:
            stored = time.mktime(time.strptime(iso_timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return 0.0
    return (time.time() - stored) / 86400.0


class RetrievalEngine:
    """
    Wraps ChromaManager to apply recency-weighted scoring on top of cosine results.

    Returns up to top_k results with final_score > MEMORY_SCORE_THRESHOLD.
    """

    def __init__(self, chroma_manager):
        self._chroma = chroma_manager

    def retrieve_relevant(
        self,
        query: str,
        top_k: int = 5,
        collection: str = "persistent",
    ) -> list[tuple[float, str, dict]]:
        """
        Retrieve top_k candidates from ChromaDB and apply recency decay.

        Returns: list of (final_score, document_text, metadata) sorted descending.
        Only entries with final_score > MEMORY_SCORE_THRESHOLD are included.
        """
        raw = self._chroma.search(query, n_results=top_k, collection=collection)
        if not raw:
            return []

        scored: list[tuple[float, str, dict]] = []
        for entry in raw:
            distance = entry.get("distance", 1.0)
            cosine_sim = cosine_distance_to_similarity(distance)
            cosine_sim = max(0.0, cosine_sim)  # clamp to [0, 1]

            meta = entry.get("metadata", {})
            timestamp = meta.get("timestamp", "")
            days_old = _days_since(timestamp) if timestamp else 0.0

            final = recency_score(cosine_sim, days_old)
            if final >= MEMORY_SCORE_THRESHOLD:
                scored.append((final, entry.get("document", ""), meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]
