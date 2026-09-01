"""
Eviction policy — LRU + relevance hybrid for ChromaDB collections.

Formula (Yukta's original contribution):
  eviction_score = (recency_rank * 0.4) + (retrieval_frequency * 0.6)
  Entries with the LOWEST eviction score are removed first.
"""

from __future__ import annotations

from utils.config import MAX_MEMORY_ENTRIES


def eviction_score(
    recency_rank: int,
    retrieval_frequency: int,
    total_entries: int,
    max_retrieval_count: int,
) -> float:
    """
    Compute the eviction score for a single memory entry.

    Higher score = keep. Lower score = evict first.

    recency_rank: 0 = newest, total_entries-1 = oldest
    retrieval_frequency: how many times this entry has been retrieved
    """
    if total_entries <= 1:
        return 1.0

    # Normalise recency: newest entry gets 1.0, oldest gets 0.0
    norm_recency = 1.0 - (recency_rank / (total_entries - 1))

    # Normalise retrieval frequency
    if max_retrieval_count > 0:
        norm_freq = retrieval_frequency / max_retrieval_count
    else:
        norm_freq = 0.0

    return (norm_recency * 0.4) + (norm_freq * 0.6)


def evict_if_needed(chroma_manager, collection: str = "persistent") -> int:
    """
    Remove lowest-score entries when the collection exceeds MAX_MEMORY_ENTRIES.
    Returns number of entries evicted.
    """
    col = (
        chroma_manager._persistent_col
        if collection == "persistent"
        else chroma_manager._session_col
    )
    count = col.count()
    if count <= MAX_MEMORY_ENTRIES:
        return 0

    # Fetch all entries to compute eviction scores
    try:
        all_entries = col.get(include=["metadatas"])
    except Exception:
        return 0

    ids = all_entries.get("ids", [])
    metas = all_entries.get("metadatas", []) or [{}] * len(ids)

    if not ids:
        return 0

    # Determine max retrieval count for normalisation
    max_ret = max(
        (int(m.get("retrieval_count", 0)) for m in metas), default=1
    )
    if max_ret == 0:
        max_ret = 1

    # Assign recency rank: sort by timestamp descending (newest = rank 0)
    indexed = list(zip(ids, metas))
    indexed.sort(
        key=lambda x: x[1].get("timestamp", ""),
        reverse=True,  # newest first
    )

    total = len(indexed)
    scored = [
        (
            doc_id,
            eviction_score(
                recency_rank=rank,
                retrieval_frequency=int(meta.get("retrieval_count", 0)),
                total_entries=total,
                max_retrieval_count=max_ret,
            ),
        )
        for rank, (doc_id, meta) in enumerate(indexed)
    ]

    # Sort by score ascending — lowest score evicted first
    scored.sort(key=lambda x: x[1])

    n_to_remove = count - MAX_MEMORY_ENTRIES
    ids_to_remove = [doc_id for doc_id, _ in scored[:n_to_remove]]

    try:
        col.delete(ids=ids_to_remove)
        return len(ids_to_remove)
    except Exception:
        return 0
