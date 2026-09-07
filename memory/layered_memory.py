"""
Layered memory architecture — three collections with different lifetimes.

  L1 working  (phantom_working_memory)  raw turns, 2h hard TTL, 10/session
  L2 episodic (phantom_episodic_memory) LLM session summaries, 7d soft TTL
  L3 durable  (phantom_durable_memory)  extracted user facts, no expiry

Retrieval assembles all three into one context block, ordered durable →
episodic → recent, so the model sees stable facts first and the live
conversation last (closest to the question it is actually answering).

Everything runs on the ChromaManager's EXISTING client. Building a second
chromadb.PersistentClient against the same path corrupts chromadb's internal
Rust binding state — reproduced live earlier in this project — so this class
never constructs one.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from memory.retrieval_engine import cosine_distance_to_similarity

logger = logging.getLogger(__name__)

L1_COLLECTION = "phantom_working_memory"
L2_COLLECTION = "phantom_episodic_memory"
L3_COLLECTION = "phantom_durable_memory"

L1_TTL_SECONDS = 7200            # 2 hours, hard delete
L2_TTL_SECONDS = 7 * 24 * 3600   # 7 days, soft delete
L1_MAX_PER_SESSION = 10
L2_MAX_PER_SESSION = 20
L3_MAX_GLOBAL = 100

L1_RETRIEVE_K = 3
L2_RETRIEVE_K = 2
L3_RETRIEVE_K = 2

L2_MIN_SIMILARITY = 0.25
L3_DEDUP_SIMILARITY = 0.85

LEGACY_SESSION = "phantom_session_memory"
LEGACY_PERSISTENT = "phantom_persistent_memory"


@dataclass
class LayeredContext:
    """What the three layers contributed for one retrieval."""
    text: str = ""
    layers_used: list[str] = field(default_factory=list)
    l1_count: int = 0
    l2_count: int = 0
    l3_count: int = 0
    elapsed_ms: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class LayeredMemoryManager:
    def __init__(self, chroma):
        """`chroma` is a live ChromaManager — its client and embedder are reused."""
        self._chroma = chroma
        self._lock = threading.RLock()
        self._l1 = None
        self._l2 = None
        self._l3 = None

    # ── collections (lazy, locked — same reason as ChromaManager's) ───────
    @property
    def l1(self):
        if self._l1 is None:
            with self._lock:
                if self._l1 is None:
                    self._l1 = self._chroma.get_collection(L1_COLLECTION)
        return self._l1

    @property
    def l2(self):
        if self._l2 is None:
            with self._lock:
                if self._l2 is None:
                    self._l2 = self._chroma.get_collection(L2_COLLECTION)
        return self._l2

    @property
    def l3(self):
        if self._l3 is None:
            with self._lock:
                if self._l3 is None:
                    self._l3 = self._chroma.get_collection(L3_COLLECTION)
        return self._l3

    def preload(self) -> dict[str, int]:
        """Force all three collections open; returns current counts."""
        return {"l1": self.l1.count(), "l2": self.l2.count(), "l3": self.l3.count()}

    # ── L1 working memory ────────────────────────────────────────────────

    def write_working(self, text: str, session_id: str, intent: str = "") -> bool:
        """Raw turn, verbatim. Surrogate/redacted text only — never restored PII."""
        if not text or not text.strip():
            return False
        try:
            emb = self._chroma.embed(text)
            meta = {
                "session_id": session_id,
                "timestamp": time.time(),
                "intent": intent or "",
                "layer": "L1",
            }
            kwargs = {
                "ids": [f"l1-{session_id}-{uuid.uuid4().hex[:10]}"],
                "documents": [text],
                "metadatas": [meta],
            }
            if emb is not None:
                kwargs["embeddings"] = [emb]
            self.l1.add(**kwargs)
            self._evict_working(session_id)
            return True
        except Exception as exc:
            logger.warning("[L1] write failed: %s", exc)
            return False

    def _evict_working(self, session_id: str) -> int:
        """Keep at most L1_MAX_PER_SESSION per session, oldest evicted first."""
        try:
            got = self.l1.get(where={"session_id": session_id}, include=["metadatas"])
            ids = got.get("ids") or []
            metas = got.get("metadatas") or []
            if len(ids) <= L1_MAX_PER_SESSION:
                return 0
            pairs = sorted(
                zip(ids, metas), key=lambda p: (p[1] or {}).get("timestamp", 0.0)
            )
            surplus = [i for i, _ in pairs[: len(ids) - L1_MAX_PER_SESSION]]
            if surplus:
                self.l1.delete(ids=surplus)
            return len(surplus)
        except Exception as exc:
            logger.warning("[L1] eviction failed: %s", exc)
            return 0

    def _expire_working(self) -> int:
        """Hard-delete anything past the 2h TTL. Called at retrieval time."""
        cutoff = time.time() - L1_TTL_SECONDS
        try:
            got = self.l1.get(include=["metadatas"])
            ids = got.get("ids") or []
            metas = got.get("metadatas") or []
            stale = [
                i for i, m in zip(ids, metas)
                if (m or {}).get("timestamp", 0.0) < cutoff
            ]
            if stale:
                self.l1.delete(ids=stale)
                logger.info("[L1] expired %d entries past TTL", len(stale))
            return len(stale)
        except Exception as exc:
            logger.warning("[L1] expiry failed: %s", exc)
            return 0

    def retrieve_working(self, query: str, session_id: str, k: int = L1_RETRIEVE_K) -> list[str]:
        """
        Most recent turns for this session. Recency-ordered, not similarity —
        the point of L1 is "what were we just saying", which a semantic score
        would happily reorder away from actual recency.
        """
        self._expire_working()
        cutoff = time.time() - L1_TTL_SECONDS
        try:
            got = self.l1.get(where={"session_id": session_id},
                              include=["documents", "metadatas"])
            docs = got.get("documents") or []
            metas = got.get("metadatas") or []
            live = [
                (d, (m or {}).get("timestamp", 0.0))
                for d, m in zip(docs, metas)
                if d and (m or {}).get("timestamp", 0.0) >= cutoff
            ]
            live.sort(key=lambda p: p[1], reverse=True)
            newest_first = [d for d, _ in live[:k]]
            return list(reversed(newest_first))  # caller wants newest LAST
        except Exception as exc:
            logger.warning("[L1] retrieve failed: %s", exc)
            return []

    # ── L2 episodic memory ───────────────────────────────────────────────

    def write_episodic(self, summary: str, session_id: str, turn_count: int = 0) -> bool:
        if not summary or not summary.strip():
            return False
        try:
            emb = self._chroma.embed(summary)
            meta = {
                "session_id": session_id,
                "timestamp": time.time(),
                "turn_count": int(turn_count),
                "expired": False,
                "layer": "L2",
            }
            kwargs = {
                "ids": [f"l2-{session_id}-{uuid.uuid4().hex[:10]}"],
                "documents": [summary],
                "metadatas": [meta],
            }
            if emb is not None:
                kwargs["embeddings"] = [emb]
            self.l2.add(**kwargs)
            self._evict_episodic(session_id)
            return True
        except Exception as exc:
            logger.warning("[L2] write failed: %s", exc)
            return False

    def _evict_episodic(self, session_id: str) -> int:
        try:
            got = self.l2.get(where={"session_id": session_id}, include=["metadatas"])
            ids = got.get("ids") or []
            metas = got.get("metadatas") or []
            if len(ids) <= L2_MAX_PER_SESSION:
                return 0
            pairs = sorted(zip(ids, metas), key=lambda p: (p[1] or {}).get("timestamp", 0.0))
            surplus = [i for i, _ in pairs[: len(ids) - L2_MAX_PER_SESSION]]
            if surplus:
                self.l2.delete(ids=surplus)
            return len(surplus)
        except Exception as exc:
            logger.warning("[L2] eviction failed: %s", exc)
            return 0

    def retrieve_episodic(self, query: str, session_id: str, k: int = L2_RETRIEVE_K) -> list[str]:
        """Semantically relevant session summaries, soft-TTL filtered."""
        cutoff = time.time() - L2_TTL_SECONDS
        try:
            if self.l2.count() == 0:
                return []
            emb = self._chroma.embed(query)
            q = {"n_results": min(k * 4, max(self.l2.count(), 1)),
                 "where": {"session_id": session_id},
                 "include": ["documents", "metadatas", "distances"]}
            if emb is not None:
                res = self.l2.query(query_embeddings=[emb], **q)
            else:
                res = self.l2.query(query_texts=[query], **q)

            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]

            kept = []
            for doc, meta, dist in zip(docs, metas, dists):
                meta = meta or {}
                if meta.get("expired"):
                    continue
                if meta.get("timestamp", 0.0) < cutoff:
                    continue
                sim = cosine_distance_to_similarity(dist, "cosine")
                if sim >= L2_MIN_SIMILARITY:
                    kept.append((sim, doc))
            kept.sort(key=lambda p: p[0], reverse=True)
            if kept:
                return [d for _, d in kept[:k]]

            # Recency fallback. L2 is already session-scoped by the where
            # filter, so every row here is from THIS conversation — the
            # similarity bar is only ranking within it, not guarding against
            # cross-session bleed. And "what have we been talking about?"
            # is exactly the query that scores worst against a content
            # summary (measured 0.205 vs the 0.25 bar) while needing this
            # layer most. Returning the newest episode beats returning
            # nothing for a follow-up in an active session.
            return self._recent_episodes(session_id, k)
        except Exception as exc:
            logger.warning("[L2] retrieve failed: %s", exc)
            return []

    def _recent_episodes(self, session_id: str, k: int) -> list[str]:
        cutoff = time.time() - L2_TTL_SECONDS
        try:
            got = self.l2.get(where={"session_id": session_id},
                              include=["documents", "metadatas"])
            rows = [
                (d, (m or {}).get("timestamp", 0.0))
                for d, m in zip(got.get("documents") or [], got.get("metadatas") or [])
                if d and not (m or {}).get("expired")
                and (m or {}).get("timestamp", 0.0) >= cutoff
            ]
            rows.sort(key=lambda p: p[1], reverse=True)
            return [d for d, _ in rows[:k]]
        except Exception:
            return []

    # ── L3 durable memory ────────────────────────────────────────────────

    def write_durable(self, fact: str, source_session: str = "", kind: str = "") -> str:
        """
        Store a persistent user fact, de-duplicated semantically.

        Returns "added", "updated", or "skipped". A near-identical fact
        (cosine > 0.85) updates the existing row rather than accumulating
        near-duplicates that would then crowd out the top-2 retrieval.
        """
        if not fact or not fact.strip():
            return "skipped"
        fact = fact.strip()
        try:
            emb = self._chroma.embed(fact)
            existing_id = self._find_duplicate_durable(fact, emb)
            meta = {
                "timestamp": time.time(),
                "source_session": source_session or "",
                "kind": kind or "",
                "layer": "L3",
            }
            if existing_id:
                kwargs = {"ids": [existing_id], "documents": [fact], "metadatas": [meta]}
                if emb is not None:
                    kwargs["embeddings"] = [emb]
                self.l3.update(**kwargs)
                return "updated"

            kwargs = {
                "ids": [f"l3-{uuid.uuid4().hex[:12]}"],
                "documents": [fact],
                "metadatas": [meta],
            }
            if emb is not None:
                kwargs["embeddings"] = [emb]
            self.l3.add(**kwargs)
            self._evict_durable()
            return "added"
        except Exception as exc:
            logger.warning("[L3] write failed: %s", exc)
            return "skipped"

    def _find_duplicate_durable(self, fact: str, emb) -> str | None:
        try:
            if self.l3.count() == 0:
                return None
            q = {"n_results": 1, "include": ["distances"]}
            if emb is not None:
                res = self.l3.query(query_embeddings=[emb], **q)
            else:
                res = self.l3.query(query_texts=[fact], **q)
            ids = (res.get("ids") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            if not ids:
                return None
            sim = cosine_distance_to_similarity(dists[0], "cosine")
            return ids[0] if sim > L3_DEDUP_SIMILARITY else None
        except Exception:
            return None

    def _evict_durable(self) -> int:
        """Global cap — oldest facts drop out first once over L3_MAX_GLOBAL."""
        try:
            got = self.l3.get(include=["metadatas"])
            ids = got.get("ids") or []
            metas = got.get("metadatas") or []
            if len(ids) <= L3_MAX_GLOBAL:
                return 0
            pairs = sorted(zip(ids, metas), key=lambda p: (p[1] or {}).get("timestamp", 0.0))
            surplus = [i for i, _ in pairs[: len(ids) - L3_MAX_GLOBAL]]
            if surplus:
                self.l3.delete(ids=surplus)
            return len(surplus)
        except Exception as exc:
            logger.warning("[L3] eviction failed: %s", exc)
            return 0

    def retrieve_durable(self, query: str, k: int = L3_RETRIEVE_K) -> list[str]:
        """Top-k persistent facts. No session scoping, no TTL — global by design."""
        try:
            if self.l3.count() == 0:
                return []
            emb = self._chroma.embed(query)
            q = {"n_results": min(k, max(self.l3.count(), 1)),
                 "include": ["documents", "distances"]}
            if emb is not None:
                res = self.l3.query(query_embeddings=[emb], **q)
            else:
                res = self.l3.query(query_texts=[query], **q)
            docs = (res.get("documents") or [[]])[0]
            return [d for d in docs if d]
        except Exception as exc:
            logger.warning("[L3] retrieve failed: %s", exc)
            return []

    # ── Combined retrieval ───────────────────────────────────────────────

    async def _retrieve_all(self, query: str, session_id: str):
        """
        The three layers are independent lookups, so they run concurrently.
        They're synchronous ChromaDB calls, so they go through an executor —
        asyncio.gather over bare sync functions would just run them serially.
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=3) as pool:
            return await asyncio.gather(
                loop.run_in_executor(pool, self.retrieve_working, query, session_id, L1_RETRIEVE_K),
                loop.run_in_executor(pool, self.retrieve_episodic, query, session_id, L2_RETRIEVE_K),
                loop.run_in_executor(pool, self.retrieve_durable, query, L3_RETRIEVE_K),
            )

    def retrieve_layered_context(self, query: str, session_id: str) -> LayeredContext:
        t0 = time.perf_counter()
        try:
            l1, l2, l3 = asyncio.run(self._retrieve_all(query, session_id))
        except Exception as exc:
            logger.warning("[MEMORY] layered retrieval failed: %s", exc)
            l1, l2, l3 = [], [], []

        blocks: list[str] = []
        layers: list[str] = []
        if l3:
            blocks.append("[DURABLE FACTS]\n" + "\n".join(f"- {f}" for f in l3))
            layers.append("L3")
        if l2:
            blocks.append("[SESSION HISTORY]\n" + "\n".join(f"- {s}" for s in l2))
            layers.append("L2")
        if l1:
            blocks.append("[RECENT TURNS]\n" + "\n".join(f"- {t}" for t in l1))
            layers.append("L1")

        return LayeredContext(
            text="\n\n".join(blocks),
            layers_used=layers,
            l1_count=len(l1), l2_count=len(l2), l3_count=len(l3),
            elapsed_ms=(time.perf_counter() - t0) * 1000,
        )

    # ── Migration ────────────────────────────────────────────────────────

    def migrate_from_legacy(self, verbose: bool = True) -> dict:
        """
        Move the old flat collections into the three layers.

        Session docs land in L1 if they are still inside the 2h window, else
        L2 (they're history at that point, not working memory). Persistent
        docs are the promoted/approved ones, so they become durable facts.

        The originals are renamed to *_legacy rather than deleted, and the
        presence of a *_legacy collection is what makes this idempotent — a
        second run finds them and stops instead of re-importing.
        """
        summary = {"l1": 0, "l2": 0, "l3": 0, "skipped": False, "reason": ""}
        client = self._chroma.client
        existing = {c if isinstance(c, str) else c.name for c in client.list_collections()}

        if f"{LEGACY_SESSION}_legacy" in existing or f"{LEGACY_PERSISTENT}_legacy" in existing:
            summary["skipped"] = True
            summary["reason"] = "already migrated (*_legacy collections present)"
            if verbose:
                print(f"[MIGRATION] Skipped — {summary['reason']}")
            return summary

        cutoff = time.time() - L1_TTL_SECONDS

        # session memory -> L1 (fresh) / L2 (older)
        if LEGACY_SESSION in existing:
            src = client.get_collection(LEGACY_SESSION)
            got = src.get(include=["documents", "metadatas"])
            for doc, meta in zip(got.get("documents") or [], got.get("metadatas") or []):
                if not doc:
                    continue
                meta = meta or {}
                sid = str(meta.get("session_id", "migrated"))
                ts = meta.get("timestamp", 0.0)
                ts = ts if isinstance(ts, (int, float)) else 0.0
                if ts >= cutoff:
                    if self.write_working(doc, sid, intent=str(meta.get("intent_type", ""))):
                        summary["l1"] += 1
                else:
                    if self.write_episodic(doc, sid):
                        summary["l2"] += 1

        # persistent memory -> L3, but only the parts that are actually FACTS.
        #
        # The legacy persistent collection holds whole conversation
        # transcripts ("Hello there -> Hello! How can I assist you today?"),
        # not extracted facts. Migrating them verbatim fills the durable
        # layer with chatter that then outranks real facts on retrieval —
        # measured: a genuine "I'm a CS student at BMSCE" fact lost the top-2
        # slots to two migrated greetings. So each doc is scanned for a
        # durable pattern; the extracted clause goes to L3 and anything with
        # no fact in it goes to L2 as history instead of being discarded.
        if LEGACY_PERSISTENT in existing:
            from memory.consolidator import extract_durable_facts

            src = client.get_collection(LEGACY_PERSISTENT)
            got = src.get(include=["documents", "metadatas"])
            for doc, meta in zip(got.get("documents") or [], got.get("metadatas") or []):
                if not doc:
                    continue
                meta = meta or {}
                sid = str(meta.get("session_id", "migrated"))
                facts = extract_durable_facts(doc)
                if facts:
                    for kind, fact in facts:
                        if self.write_durable(fact, source_session=sid,
                                              kind=f"migrated:{kind}") in ("added", "updated"):
                            summary["l3"] += 1
                else:
                    if self.write_episodic(doc, sid):
                        summary["l2"] += 1

        # rename originals, preserving their data under the legacy name
        for name in (LEGACY_SESSION, LEGACY_PERSISTENT):
            if name in existing:
                try:
                    client.get_collection(name).modify(name=f"{name}_legacy")
                except Exception as exc:
                    logger.warning("[MIGRATION] rename %s failed: %s", name, exc)

        # Report what actually SURVIVED, not how many writes were attempted.
        # The per-session L2 cap and L3's semantic dedup both drop rows on the
        # way in, so "written" and "stored" genuinely differ here and quoting
        # only the former would overstate what was migrated.
        final = self.preload()
        summary["l1_stored"] = final["l1"]
        summary["l2_stored"] = final["l2"]
        summary["l3_stored"] = final["l3"]
        if verbose:
            print(f"[MIGRATION] written -> L1: {summary['l1']}, "
                  f"L2: {summary['l2']}, L3: {summary['l3']}")
            print(f"[MIGRATION] stored  -> L1: {final['l1']}, "
                  f"L2: {final['l2']} (capped at {L2_MAX_PER_SESSION}/session), "
                  f"L3: {final['l3']} (after >{L3_DEDUP_SIMILARITY} dedup)")
        return summary
