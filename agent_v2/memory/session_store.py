"""
Session memory — in-memory turns plus ChromaDB persistence.

Only surrogate text is ever persisted. Originals live exclusively in the
local surrogate map (privacy/surrogate_map.py) and never reach this store.
"""
from __future__ import annotations

import os
import threading
import time
import uuid

CHROMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "phantom_memory",
)
COLLECTION = "phantom_v2_sessions"


class SessionStore:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.turns: list[dict] = []
        self._collection = None
        self._init_error = ""
        # preload() runs on a background thread at startup; a query fired
        # before it finishes calls this same getter from PhantomWorker's
        # thread. Two concurrent chromadb.PersistentClient() constructions
        # against the same path corrupt its internal state rather than just
        # duplicating work — verified against the identical bug in the parent
        # project's phantom_graph.py (phantom_graph.py's _singleton_lock
        # comment has the full repro). Double-checked locking closes it.
        self._collection_lock = threading.Lock()

    # ── ChromaDB ─────────────────────────────────────────────────────────
    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        with self._collection_lock:
            if self._collection is not None:
                return self._collection
            try:
                import chromadb
                from chromadb.utils import embedding_functions
                os.makedirs(CHROMA_PATH, exist_ok=True)
                client = chromadb.PersistentClient(path=CHROMA_PATH)
                embed = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                self._collection = client.get_or_create_collection(
                    name=COLLECTION,
                    embedding_function=embed,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                self._init_error = str(exc)
                self._collection = None
        return self._collection

    def preload(self) -> str:
        """
        Build the collection AND force the embedding model to load.

        get_or_create_collection() only constructs the embedding-function
        object; SentenceTransformer weights load lazily on first use, so
        without this warm-up the first user query pays ~20s of model load
        inside what looks like the cloud call.
        """
        col = self._get_collection()
        if col is None:
            return f"unavailable: {self._init_error}"
        try:
            col.query(query_texts=["warm up"], n_results=1)
        except Exception:
            pass  # empty collection is fine — the embedder still loaded
        return "ok"

    # ── write ────────────────────────────────────────────────────────────
    def add_turn(self, surrogate_text: str, llm_response_pre_restoration: str,
                 pii_risk: str, entities_found: int, provider_used: str,
                 tokens_used: int) -> bool:
        """Persist one turn. Both text fields are surrogate-side only."""
        document = f"{surrogate_text} → {llm_response_pre_restoration}"
        metadata = {
            "session_id": self.session_id,
            "timestamp": int(time.time()),
            "pii_risk": pii_risk,
            "entities_found": entities_found,
            "provider_used": provider_used,
            "tokens_used": int(tokens_used),
        }
        self.turns.append({"document": document, "metadata": metadata})

        col = self._get_collection()
        if col is None:
            return False
        try:
            col.add(
                ids=[f"{self.session_id}-{len(self.turns)}-{uuid.uuid4().hex[:8]}"],
                documents=[document],
                metadatas=[metadata],
            )
            return True
        except Exception:
            return False

    # ── read ─────────────────────────────────────────────────────────────
    def retrieve_context(self, query: str, top_k: int = 3) -> list[str]:
        """Top-k earlier turns from THIS session only."""
        col = self._get_collection()
        if col is None:
            return []
        try:
            if col.count() == 0:
                return []
            res = col.query(
                query_texts=[query],
                n_results=min(top_k, max(col.count(), 1)),
                where={"session_id": self.session_id},
            )
            docs = (res.get("documents") or [[]])[0]
            return [d for d in docs if d]
        except Exception:
            return []

    def context_prefix(self, query: str, top_k: int = 3) -> str:
        docs = self.retrieve_context(query, top_k)
        if not docs:
            return ""
        return "\n".join(f"- {d}" for d in docs)
