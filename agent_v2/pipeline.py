"""
Phantom 2.0 pipeline orchestrator.

Every message runs through six stages in order:

  1 Sentinel   — local risk + intent screen (blocks DANGEROUS here)
  2 Redact     — 3-tier PII detection, replaces values with tier tags
  3 Surrogate  — tags become realistic fake values
  4 Cloud      — surrogate text goes to PhantomRouter
  5 Restore    — surrogates swapped back to originals for display
  6 Memory     — surrogate-side transcript persisted to ChromaDB

The only text that leaves the machine is the Stage 3 surrogate text. The only
place originals touch disk is the local surrogate map.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

# Parent project on the path so llm_router is importable. Internal modules use
# relative imports: agent_v2/memory/ and agent_v2/ui/ would otherwise collide
# with the parent project's own top-level memory/ and ui/ packages, and which
# one wins would depend on sys.path ordering.
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from .privacy.sentinel import SentinelNode, SentinelResult
from .privacy.redactor import redact, ENGINES
from .privacy.surrogate import SurrogateGenerator
from .privacy.surrogate_map import SurrogateMap, purge_expired
from .privacy.restorer import restore
from .memory.session_store import SessionStore

STAGES = ["Sentinel", "Redact", "Surrogate", "Cloud", "Restore"]

StageCallback = Callable[[str, str, str], None]  # (stage, status, detail)


@dataclass
class PipelineResult:
    restored_response: str = ""
    llm_response: str = ""          # pre-restoration; safe to log
    surrogate_text: str = ""        # safe to log
    blocked: bool = False
    block_reason: str = ""
    sentinel: SentinelResult | None = None
    entity_types: list[str] = field(default_factory=list)
    surrogate_count: int = 0
    provider: str = ""
    tokens_used: int = 0
    tiers_run: list[int] = field(default_factory=list)
    tiers_skipped: list[int] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0
    error: str = ""

    @property
    def entity_count(self) -> int:
        return len(self.entity_types)


class PhantomPipeline:
    def __init__(self, session_id: str | None = None, wipe_map_on_close: bool = False):
        self.session_id = session_id or str(uuid.uuid4())
        self.sentinel = SentinelNode()
        self.surrogates = SurrogateGenerator(self.session_id)
        self.surrogate_map = SurrogateMap(self.session_id, wipe_on_close=wipe_map_on_close)
        self.store = SessionStore(self.session_id)
        self._router = None
        purge_expired()

    # ── lazy router (constructing it reads env + builds clients) ──────────
    @property
    def router(self):
        if self._router is None:
            from .router.cloud_router import CloudRouter
            self._router = CloudRouter()
        return self._router

    def preload(self) -> dict[str, str]:
        """Warm Presidio, spaCy, Chroma and the router so no query pays cold start."""
        status = ENGINES.preload()
        status["chroma"] = self.store.preload()
        try:
            _ = self.router
            status["router"] = "ok"
        except Exception as exc:
            status["router"] = f"unavailable: {exc}"
        return status

    def new_session(self) -> None:
        self.surrogate_map.close()
        self.session_id = str(uuid.uuid4())
        self.surrogates = SurrogateGenerator(self.session_id)
        self.surrogate_map = SurrogateMap(self.session_id)
        self.store = SessionStore(self.session_id)

    # ── the pipeline ─────────────────────────────────────────────────────
    def run(self, user_text: str, on_stage: StageCallback | None = None) -> PipelineResult:
        def emit(stage: str, status: str, detail: str = "") -> None:
            if on_stage:
                try:
                    on_stage(stage, status, detail)
                except Exception:
                    pass

        result = PipelineResult()
        t_start = time.perf_counter()

        # ── STAGE 1: Sentinel ────────────────────────────────────────────
        emit("Sentinel", "running", "")
        t0 = time.perf_counter()
        sentinel = self.sentinel.classify(user_text)
        result.sentinel = sentinel
        result.timings_ms["sentinel"] = (time.perf_counter() - t0) * 1000

        if sentinel.blocked:
            emit("Sentinel", "blocked", f"intent: {sentinel.intent}")
            for stage in STAGES[1:]:
                emit(stage, "skipped", "")
            result.blocked = True
            result.block_reason = sentinel.reason or "intent classified DANGEROUS"
            result.restored_response = (
                "[PHANTOM 2.0] This request was blocked locally by the Sentinel "
                "node and was never sent to any cloud provider."
            )
            result.total_ms = (time.perf_counter() - t_start) * 1000
            return result
        emit("Sentinel", "done", f"{sentinel.risk_level} / {sentinel.intent}")

        # ── STAGE 2: Redaction ───────────────────────────────────────────
        emit("Redact", "running", "")
        t0 = time.perf_counter()
        redaction = redact(user_text, sentinel.risk_level)
        result.timings_ms["redact"] = (time.perf_counter() - t0) * 1000
        result.timings_ms.update({f"redact_{k}": v for k, v in redaction.timings_ms.items()})
        result.tiers_run = redaction.tiers_run
        result.tiers_skipped = redaction.tiers_skipped
        result.entity_types = [d.entity_type for d in redaction.detections]
        if redaction.tier_error:
            # NER coverage dropped to regex-only — surface it rather than
            # letting the run look like a clean pass.
            result.error = f"redaction tier failure: {redaction.tier_error}"
            emit("Redact", "error", redaction.tier_error[:80])
        else:
            emit("Redact", "done",
                 f"{len(redaction.detections)} entities, tiers {redaction.tiers_run}")

        # ── STAGE 3: Surrogate generation ────────────────────────────────
        emit("Surrogate", "running", "")
        t0 = time.perf_counter()
        surrogate_text = redaction.redacted_text
        for det in redaction.detections:
            existing = self.surrogate_map.surrogate_for_original(
                det.original_value, det.entity_type
            )
            surrogate = existing or self.surrogates.generate(
                det.entity_type, det.original_value
            )
            self.surrogate_map.add(det.tag, surrogate, det.original_value, det.entity_type)
            surrogate_text = surrogate_text.replace(det.tag, surrogate)
        self.surrogate_map.save()
        result.surrogate_text = surrogate_text
        result.surrogate_count = len(redaction.detections)
        result.timings_ms["surrogate"] = (time.perf_counter() - t0) * 1000
        emit("Surrogate", "done", f"{result.surrogate_count} surrogates")

        # Safety assertion: no original value may survive into cloud-bound text.
        for det in redaction.detections:
            if det.original_value and det.original_value in surrogate_text:
                result.error = "surrogate substitution incomplete — aborting before cloud"
                emit("Surrogate", "error", result.error)
                for stage in STAGES[3:]:
                    emit(stage, "skipped", "")
                result.blocked = True
                result.block_reason = result.error
                result.restored_response = f"[PHANTOM 2.0] {result.error}"
                result.total_ms = (time.perf_counter() - t_start) * 1000
                return result

        # ── STAGE 4: Cloud ───────────────────────────────────────────────
        emit("Cloud", "running", "")
        # Memory retrieval is timed separately from the provider call — folding
        # it into "cloud" made a cold embedder load look like 27s of Gemini.
        t0 = time.perf_counter()
        context = self.store.context_prefix(surrogate_text, top_k=3)
        result.timings_ms["memory_retrieve"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        cloud = self.router.ask(surrogate_text, context=context, session_id=self.session_id)
        result.timings_ms["cloud"] = (time.perf_counter() - t0) * 1000
        result.llm_response = cloud["response"]
        result.provider = cloud["provider"]
        result.tokens_used = cloud["tokens_used"]

        if cloud["error"]:
            result.error = cloud["error"]
            emit("Cloud", "error", cloud["error"][:80])
            emit("Restore", "skipped", "")
            result.restored_response = f"[PHANTOM 2.0] Cloud call failed: {cloud['error']}"
            result.total_ms = (time.perf_counter() - t_start) * 1000
            return result
        emit("Cloud", "done", f"via {cloud['provider']}")

        # ── STAGE 5: Restoration ─────────────────────────────────────────
        emit("Restore", "running", "")
        t0 = time.perf_counter()
        restored, replacements = restore(result.llm_response, self.surrogate_map.pairs)
        result.restored_response = restored
        result.timings_ms["restore"] = (time.perf_counter() - t0) * 1000
        emit("Restore", "done", f"{replacements} values restored")

        # ── STAGE 6: Memory (surrogate side only) ────────────────────────
        t0 = time.perf_counter()
        self.store.add_turn(
            surrogate_text=surrogate_text,
            llm_response_pre_restoration=result.llm_response,
            pii_risk=sentinel.risk_level,
            entities_found=result.surrogate_count,
            provider_used=result.provider,
            tokens_used=result.tokens_used,
        )
        result.timings_ms["memory"] = (time.perf_counter() - t0) * 1000

        result.total_ms = (time.perf_counter() - t_start) * 1000
        return result
