"""
Session-scoped surrogate <-> real mapping store.

This file is the only place original PII is ever written to disk. It stays
local (./agent_v2/data/surrogate_maps/), never goes to ChromaDB, and never
leaves the machine. Entries expire after 24h.
"""
from __future__ import annotations

import json
import os
import time

MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "surrogate_maps")
TTL_SECONDS = 24 * 3600


class SurrogateMap:
    """
    Bidirectional lookup for one session.

    Lookups are dict-backed (spec: O(1), never a list scan) — a turn with 20
    entities would otherwise do 20 linear scans per restoration pass.
    """

    def __init__(self, session_id: str, wipe_on_close: bool = False):
        self.session_id = session_id
        self.wipe_on_close = wipe_on_close
        self._by_tag: dict[str, dict] = {}
        self._surrogate_to_original: dict[str, str] = {}
        os.makedirs(MAP_DIR, exist_ok=True)
        self._path = os.path.join(MAP_DIR, f"{session_id}.json")
        self._load()

    # ── persistence ──────────────────────────────────────────────────────
    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                records = json.load(fh)
        except Exception:
            return
        now = time.time()
        for rec in records:
            if now - rec.get("timestamp", 0) > TTL_SECONDS:
                continue
            self._by_tag[rec["tag"]] = rec
            self._surrogate_to_original[rec["surrogate"]] = rec["original"]

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(list(self._by_tag.values()), fh, indent=2)
        except Exception:
            pass

    def wipe(self) -> None:
        self._by_tag.clear()
        self._surrogate_to_original.clear()
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except Exception:
            pass

    def close(self) -> None:
        if self.wipe_on_close:
            self.wipe()
        else:
            self.save()

    # ── mapping ──────────────────────────────────────────────────────────
    def add(self, tag: str, surrogate: str, original: str, entity_type: str) -> dict:
        rec = {
            "tag": tag,
            "surrogate": surrogate,
            "original": original,
            "entity_type": entity_type,
            "session_id": self.session_id,
            "timestamp": time.time(),
        }
        self._by_tag[tag] = rec
        self._surrogate_to_original[surrogate] = original
        return rec

    def surrogate_for_original(self, original: str, entity_type: str) -> str | None:
        """
        Reuse an existing surrogate when the same real value shows up again,
        so one person keeps one alias across turns.
        """
        for rec in self._by_tag.values():
            if rec["original"] == original and rec["entity_type"] == entity_type:
                return rec["surrogate"]
        return None

    @property
    def pairs(self) -> dict[str, str]:
        """surrogate -> original, for the restorer."""
        return dict(self._surrogate_to_original)

    def records(self) -> list[dict]:
        return list(self._by_tag.values())

    def entity_types(self) -> list[str]:
        return [r["entity_type"] for r in self._by_tag.values()]

    def __len__(self) -> int:
        return len(self._by_tag)


def purge_expired() -> int:
    """Delete map files older than the TTL. Returns how many were removed."""
    if not os.path.isdir(MAP_DIR):
        return 0
    removed = 0
    now = time.time()
    for name in os.listdir(MAP_DIR):
        path = os.path.join(MAP_DIR, name)
        try:
            if now - os.path.getmtime(path) > TTL_SECONDS:
                os.remove(path)
                removed += 1
        except Exception:
            continue
    return removed
