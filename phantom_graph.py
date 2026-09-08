"""
PHANTOM LangGraph Orchestrator — stateful pipeline graph.

Architecture (Section 2 of spec):
  User Input
    → sentinel_node       (intent classify, empty/None guard)
    → pii_redact_node     (3-tier cascade, stores placeholder↔real in state)
    → memory_retrieve_node (ChromaDB top-k, injects into memory_context)
    → llm_call_node       (ChatOllama, uses memory_context in system prompt)
    → hitl_check_node     (risk gate; interrupt() blocks graph if risk > 0.7)
    → pii_restore_node    (de-anonymise LLM response)
    → END

State is a TypedDict (AgentState). MemorySaver checkpoints every node
transition so that interrupt/resume works correctly.

Tanmay Vasishta — LangGraph Orchestrator (Batman's module).
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import logging
import threading
import uuid
from typing import Annotated, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

def prewarm_ollama():
    try:
        import requests
        requests.post('http://localhost:11434/api/generate',
            json={'model': 'qwen3.5:2b', 'prompt': 'hi', 'stream': False, 'keep_alive': '24h'},
            timeout=30)
        print('[PHANTOM] Model pre-warmed and hot.')
    except Exception as e:
        print(f'[PHANTOM] Pre-warm skipped: {e}')


def prewarm_pipeline():
    """
    Eagerly load every heavy singleton (spaCy, Presidio, sentence-transformers,
    ChromaDB, cross-encoder, sentinel) at process startup instead of on the
    first user message. Without this, the first chat query pays 30-60s of
    cold-start cost and blows through run_query's internal timeout, making
    the UI look completely dead on the first message.
    """
    import time
    _t0 = time.time()

    # Constructing these objects is cheap; the expensive part is the FIRST real
    # call (spaCy/Presidio build their NLP engine lazily — ~60s — and the
    # embedder/cross-encoder load weights on first inference). Exercising each
    # one here is what actually moves that cost off the user's first message.
    # The three groups are independent, so warm them concurrently — the same
    # thread-parallel pattern the query path already uses.
    def _warm_pii():
        _get_pii_map()
        _get_pii_engine().redact("warm up the analyzer", intent_context="GENERAL_QA")

    def _warm_memory():
        # Warms the layered manager (the live retrieval path) — opens all
        # three collections and forces the embedder to load, so the first
        # real query doesn't pay for it.
        _get_layered().preload()
        _get_layered().retrieve_layered_context("warm up", "warmup-session")

    def _warm_models():
        _get_sentinel()
        _get_bound_llm("groq")  # constructs the client, no network call

    def _warm_fallback_providers():
        """
        Construct (never call) each fallback client so its SDK's first-time
        Python import cost is paid here, not during a live Groq failure.

        Measured live: _get_fallback_llm("openrouter") alone takes 13.4s,
        "gemini" 5.1s — almost entirely one-time module import (langchain_
        openai / langchain_google_genai and their transitive deps), since
        constructing a LangChain chat model does not itself make a network
        call. These are only ever reached from llm_call_node's fallback
        path, which normally never runs — so without this, the exact
        moment a real Groq outage first needs a fallback is also the first
        moment Python has ever imported these packages in this process,
        adding ~18s of pure import latency on top of the actual network
        attempt, right when the user is already waiting on a failure.
        """
        for provider in ("openrouter", "gemini"):
            try:
                _get_fallback_llm(provider)
            except Exception as exc:
                logger.warning("[PREWARM] Fallback provider %s warm-up failed: %s", provider, exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            "PII": pool.submit(_warm_pii),
            "Memory": pool.submit(_warm_memory),
            "Models": pool.submit(_warm_models),
            "FallbackProviders": pool.submit(_warm_fallback_providers),
        }
        for name, fut in futures.items():
            try:
                fut.result(timeout=300)
            except Exception as e:
                print(f'[PHANTOM] {name} pre-warm skipped: {e}')

    print(f'[PHANTOM] Pipeline pre-warmed in {time.time() - _t0:.1f}s.')
# ── Lazy singletons (initialised once per process) ────────────────────────────
# prewarm_pipeline() and parallel_preprocess_node() each run their own
# ThreadPoolExecutor, and a query can land while prewarm's background thread is
# still running — so two threads can call the same getter for its very first
# time within milliseconds of each other. The bare `if _x is None: _x = ...`
# check-then-act was not atomic: both threads would see None and both
# construct a ChromaManager() (or any of the others) against the same state.
# For ChromaDB specifically this doesn't just waste an object — two
# PersistentClient constructions against the same path in one process corrupt
# its internal Rust binding state, verified live: concurrent construction
# reproduced a bare KeyError(path), an AttributeError on 'bindings', and a
# "Could not connect to tenant default_tenant" error across four racing
# threads, matching the exact "ChromaDB init failed: '<path>'" report.
#
# RLock (not Lock): _get_retrieval() calls _get_chroma(), and
# _get_pii_engine()/_get_pii_restorer() call _get_pii_map() — the same thread
# re-enters the lock while already holding it. A plain Lock would deadlock a
# thread against itself on that nesting.
_singleton_lock = threading.RLock()
_pii_map = None
_pii_engine = None
_pii_restorer = None
_sentinel = None
_chroma = None
_retrieval = None
_reranker = None


def _get_pii_map():
    global _pii_map
    if _pii_map is None:
        with _singleton_lock:
            if _pii_map is None:
                from sentinel.session_pii_map import SessionPIIMap
                _pii_map = SessionPIIMap()
    return _pii_map


def _get_pii_engine():
    global _pii_engine
    if _pii_engine is None:
        with _singleton_lock:
            if _pii_engine is None:
                from sentinel.pii_engine import PIIRedactionEngine
                _pii_engine = PIIRedactionEngine(_get_pii_map())
    return _pii_engine


def _get_pii_restorer():
    global _pii_restorer
    if _pii_restorer is None:
        with _singleton_lock:
            if _pii_restorer is None:
                from sentinel.pii_restorer import PIIRestorer
                _pii_restorer = PIIRestorer(_get_pii_map())
    return _pii_restorer


def _get_sentinel():
    global _sentinel
    if _sentinel is None:
        with _singleton_lock:
            if _sentinel is None:
                from sentinel.sentinel_node import SentinelNode
                _sentinel = SentinelNode()
    return _sentinel


def _get_chroma():
    global _chroma
    if _chroma is None:
        with _singleton_lock:
            if _chroma is None:
                from memory.chroma_manager import ChromaManager
                # session_only=True → in-memory (ephemeral, no cross-session leakage)
                # session_only=False → PersistentClient (survives restarts, good for dev)
                import os
                session_only = os.environ.get("PHANTOM_SESSION_ONLY", "false").lower() == "true"
                _chroma = ChromaManager(session_only=session_only)
    return _chroma


def _get_retrieval():
    global _retrieval
    if _retrieval is None:
        with _singleton_lock:
            if _retrieval is None:
                from memory.retrieval_engine import RetrievalEngine
                _retrieval = RetrievalEngine(_get_chroma())
    return _retrieval


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _singleton_lock:
            if _reranker is None:
                from memory.reranker import MemoryReranker
                _reranker = MemoryReranker()
    return _reranker


_layered = None


def _get_layered():
    """LayeredMemoryManager, sharing _get_chroma()'s single client."""
    global _layered
    if _layered is None:
        with _singleton_lock:
            if _layered is None:
                from memory.layered_memory import LayeredMemoryManager
                _layered = LayeredMemoryManager(_get_chroma())
    return _layered


from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

class AgentState(TypedDict):
    """
    Shared state passed between every LangGraph node.
    """
    raw_input: str
    messages: Annotated[list[Any], add_messages]
    pii_map: dict[str, str]
    memory_context: str
    hitl_required: bool
    hitl_decision: str | None
    llm_response: str
    final_response: str
    intent: str
    risk_score: float
    n_pii_redacted: int
    error: str
    pending_tool_call: dict | None
    provider_used: str
    memory_hits: int
    tool_call_count: int
    blocked: bool
    block_reason: str
    mode: str
    agent_mode: bool
    guardian_tier: str
    guardian_reason: str
    memory_layers_used: list[str]
    turn_count: int
    session_id: str


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1 — parallel_preprocess_node
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from utils.intent_cache import intent_cache

# Ollama intent classification measures 5.4-7.0s minimum on every model
# installed on this machine — no locally-installed model makes a synchronous
# wait for it viable. This pool is intentionally persistent (never
# .shutdown()'d) rather than created per-request: the per-request
# ThreadPoolExecutor used for PII/memory below is opened with `with`, and
# exiting a `with ThreadPoolExecutor(...)` block calls shutdown(wait=True),
# which blocks on EVERY submitted future regardless of any timeout already
# passed to .result() on the way there — so an intent classification
# submitted to that pool would still stall the node for the full 5-7s even
# after "timing out". Dispatching to this separate, long-lived pool instead
# means the slow Ollama call keeps running in the background after this
# request has already moved on, and its eventual result still gets cached
# for the next identical query (see _resolve_intent below).
_INTENT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="phantom-intent-bg")
INTENT_TIMEOUT_SECONDS = 0.5

# Same footgun, same fix, for the PII scan and memory retrieval this node also
# dispatches: both used to run inside a per-call `with ThreadPoolExecutor()`,
# which meant a lowered .result(timeout=...) would raise on schedule but the
# enclosing `with` block's shutdown(wait=True) still blocked until the
# abandoned future finished anyway. Neither has ever measured anywhere near
# its old 60s timeout in practice (PII ~5ms, memory retrieval ~25-55ms), but
# "never measured that slow" isn't the same guarantee as "structurally can't
# block the response" — a genuine ChromaDB stall or a hung PII engine call
# would still have eaten the full 60s for nothing. 5s is generous headroom
# over anything actually observed, while still failing soft well before it
# could threaten run_query()'s own 60s ceiling.
_PREPROCESS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="phantom-preprocess-bg")
PREPROCESS_TIMEOUT_SECONDS = 5.0

def run_intent_classify(raw: str) -> dict:
    from utils.models import ClarificationRequest
    sentinel = _get_sentinel()
    try:
        result = sentinel.process(raw)
        if isinstance(result, ClarificationRequest):
            return {"intent": "CLARIFICATION_NEEDED", "error": f"Clarification needed: {result.interpretation}"}
        intent_str = result.intent.value if hasattr(result.intent, "value") else str(result.intent)
        logger.info("[PREPROCESS] Intent=%s confidence=%.2f", intent_str, result.confidence)
        return {"intent": intent_str, "error": ""}
    except Exception as exc:
        logger.error("[PREPROCESS] Classification error: %s", exc)
        return {"intent": "GENERAL_QA", "error": ""}


def _dispatch_intent_classify(raw: str):
    """
    Cache hit -> the cached result dict directly, no Ollama call at all.
    Cache miss -> a Future submitted to the persistent background pool,
    which keeps running (and warms the cache) even if the caller gives up
    on waiting for it.
    """
    cached = intent_cache.get(raw)
    if cached is not None:
        return cached

    future = _INTENT_EXECUTOR.submit(run_intent_classify, raw)
    future.add_done_callback(lambda f: _cache_intent_result(raw, f))
    return future


def _cache_intent_result(raw: str, future) -> None:
    try:
        intent_cache.set(raw, future.result())
    except Exception:
        pass  # a failed background classification just isn't cached


def _resolve_intent(raw: str, dispatched) -> dict:
    """
    Wait up to INTENT_TIMEOUT_SECONDS for the dispatched classification.

    mode_classifier already routed this query via fast regex before this
    node ever ran, so the Ollama intent is secondary enrichment (used for
    cloud model selection and logging), not a gate — proceeding without it
    on timeout is safe, and matches run_intent_classify's own existing
    fail-safe default on a real classification error.
    """
    if isinstance(dispatched, dict):
        return dispatched  # cache hit — already resolved, nothing to wait on

    try:
        return dispatched.result(timeout=INTENT_TIMEOUT_SECONDS)
    except (TimeoutError, FutureTimeoutError):
        logger.info(
            "[PREPROCESS] Intent classification exceeded %.1fs (Ollama) — "
            "proceeding without it; result will still be cached for next time.",
            INTENT_TIMEOUT_SECONDS,
        )
        return {"intent": "GENERAL_QA", "error": ""}
    except Exception as exc:
        logger.warning("[PREPROCESS] Intent dispatch failed: %s", exc)
        return {"intent": "GENERAL_QA", "error": ""}


def run_pii_scan(raw: str) -> dict:
    engine = _get_pii_engine()
    pii_map_obj = _get_pii_map()
    try:
        result = engine.redact(raw, intent_context="GENERAL_QA")
        n = result.n_entities
        if n:
            logger.info("[PREPROCESS] Redacted %d entity/entities.", n)
        return {
            "pii_map": dict(pii_map_obj.get_placeholders()),
            "anonymized": result.sanitised_text,
            "count": n
        }
    except Exception as exc:
        logger.error("[PREPROCESS] PII Redact error: %s", exc)
        return {"pii_map": {}, "anonymized": raw, "count": 0}

def run_memory_retrieve(raw: str) -> dict:
    retrieval = _get_retrieval()
    reranker = _get_reranker()
    try:
        candidates = retrieval.retrieve_relevant(raw, top_k=5)
        top = reranker.rerank(raw, candidates, top_k=3) if candidates else []
        if top:
            context_lines = [text for _, text, _ in top]
            logger.info("[PREPROCESS] Injected %d context chunk(s).", len(top))
            return {"context": "\n".join(f"• {line}" for line in context_lines), "hits": len(top)}
    except Exception as exc:
        logger.warning("[PREPROCESS] Retrieval error: %s", exc)
    return {"context": "", "hits": 0}

def mode_classifier_node(state: AgentState) -> dict:
    """
    First node in the graph — Leon-style 3-mode routing, regex only, no LLM
    call. Decides how much of the pipeline this query actually needs before
    anything else runs.
    """
    from utils.mode_classifier import classify_mode

    raw = (state.get("raw_input") or "").strip()
    mode = classify_mode(raw)
    if mode != "smart":
        logger.info("[MODE] %s -> %s", mode, raw[:60])
    return {"mode": mode, "agent_mode": mode == "agent"}


def route_after_mode(state: AgentState) -> str:
    """Controlled commands skip the guard, sentinel and LLM entirely."""
    return "deterministic_action_node" if state.get("mode") == "controlled" else "guardian_node"


def deterministic_action_node(state: AgentState) -> dict:
    """
    Controlled-mode execution — deterministic pattern, zero API calls, no
    LLM. Logged the same way an LLM call would be (provider "none", zero
    tokens) so mode/provider distribution stays visible in
    daily_summary()/`/status` without a special case there.

    Everything except the duplicate-scan branch below is still the
    original stub (acknowledgement text only, nothing actually executed) —
    duplicate-finding is the first real action wired in, and deliberately
    read-only: see _FIND_DUPLICATES's docstring in utils/mode_classifier.py
    for why "remove/delete duplicate" is NOT routed here.
    """
    from utils.usage_logger import log_usage

    command = (state.get("raw_input") or "").strip()
    command_lower = command.lower()
    logger.info("[CONTROLLED] %s", command[:60])

    try:
        log_usage(
            provider="none", model="none", tokens_used=0,
            window_tokens=0, window_limit=0,
            session_id="controlled", mode="controlled",
        )
    except Exception:
        pass

    if "duplicate" in command_lower or "dupes" in command_lower:
        response = _run_controlled_duplicate_scan(command)
        return {"final_response": response, "provider_used": "none"}

    return {
        "final_response": f"Running: {command}",
        "provider_used": "none",
    }


def _run_controlled_duplicate_scan(command: str) -> str:
    """
    Read-only duplicate scan for the controlled-mode fast path.

    Reuses find_duplicates() from tools/file_tools.py rather than a fresh
    naive implementation: that function already does content-hash (not
    filename-pattern) matching with a partial-hash pre-check and a bounded
    scan budget, verified live against a real ~44,000-file Downloads folder
    at 20.57s with a full MD5-every-byte-of-every-file approach measured at
    over three minutes on the same folder — reimplementing a simpler
    version here would reintroduce exactly the performance and correctness
    problems that one was built to fix.

    Path defaults to Downloads (the overwhelmingly common case) if the
    command doesn't name a folder; a trailing "in X" clause overrides that,
    reusing resolve_path()'s own alias handling ("desktop", "documents",
    an absolute path, ...) so this stays consistent with every other tool.
    """
    import re as _re
    from tools.file_tools import find_duplicates

    m = _re.search(r"\bin\s+(.+)$", command, _re.IGNORECASE)
    target = m.group(1).strip().strip(".!?") if m else "downloads"

    find_fn = getattr(find_duplicates, "func", find_duplicates)
    result = find_fn(target)

    if "error" in result:
        return f"Couldn't scan {target}: {result['error']}"

    if result.get("total_duplicates_found", 0) == 0:
        msg = result.get("message", f"No duplicate files found in {target}.")
        return f"✓ {msg}"

    lines = [
        f"Found {result['total_duplicates_found']} duplicate file(s) in {target} "
        f"(~{result['wasted_human']} wasted):",
        "",
    ]
    lines.extend(f"  • {p}" for p in result.get("paths_to_delete_sample", []))
    if result["total_duplicates_found"] > len(result.get("paths_to_delete_sample", [])):
        lines.append(f"  ... and {result['total_duplicates_found'] - len(result['paths_to_delete_sample'])} more")
    if result.get("incomplete_scan"):
        lines.append("")
        lines.append(result["incomplete_scan"])
    lines.append("")
    lines.append('Say "remove duplicate files" to delete them (requires your approval first).')
    return "\n".join(lines)


def guardian_node(state: AgentState) -> dict:
    """
    3-tier pre-execution risk gate (replaces the old binary input guard).

      < 0.3   proceed on the local score alone
      0.3-0.7 Guardian LLM reviews it; the two scores are averaged
      >= 0.7  interrupt() for human approval before anything runs

    Controlled mode skips the gate: those commands matched an anchored
    deterministic pattern and never reach an LLM.
    """
    from utils.guardian import assess, HITL_THRESHOLD

    raw = (state.get("raw_input") or "").strip()
    mode = state.get("mode", "smart")

    if mode == "controlled":
        return {"blocked": False, "block_reason": "",
                "risk_score": 0.0, "guardian_tier": "skipped", "guardian_reason": ""}

    result = assess(raw, mode=mode, session_id=state.get("session_id", "guardian"))
    logger.info("[GUARDIAN] score=%.2f tier=%s signals=%s",
                result.score, result.tier_used, result.signals_fired)

    base = {
        "risk_score": result.score,
        "guardian_tier": result.tier_used,
        "guardian_reason": result.reason,
        "blocked": False,
        "block_reason": "",
    }

    if result.score < HITL_THRESHOLD:
        return base

    # Tier 3 — human approval required before this input goes anywhere.
    decision = interrupt({
        "action": raw[:200],
        "raw_input": raw[:200],
        "risk_score": round(result.score, 2),
        "signals_fired": result.signals_fired,
        "guardian_reason": result.reason,
        "tier": "guardian",
        "message": (
            f"[PHANTOM] Guardian Review Required\n"
            f"Risk score: {round(result.score * 100)}%\n"
            f"Signals: {', '.join(result.signals_fired) or 'none'}\n"
            f"{('Reason: ' + result.reason) if result.reason else ''}\n\n"
            f"Type 'approve' to allow or 'reject' to cancel."
        ),
    })

    if str(decision).strip().lower() in ("reject", "no", "n", "cancel"):
        logger.warning("[GUARDIAN] Input REJECTED by user (score=%.2f).", result.score)
        return {**base,
                "blocked": True,
                "block_reason": f"rejected by user at guardian tier 3 (risk {result.score:.2f})",
                "hitl_required": True,
                "hitl_decision": "reject",
                "final_response": "Action blocked by user."}

    logger.info("[GUARDIAN] Input APPROVED by user (score=%.2f).", result.score)
    return {**base, "hitl_required": True, "hitl_decision": "approve"}


def route_after_guard(state: AgentState) -> str:
    """Blocked input goes straight to END — never reaches the LLM."""
    return END if state.get("blocked") else "parallel_preprocess_node"


def parallel_preprocess_node(state: AgentState) -> dict:
    """
    Parallel pre-processing (Fix D)
    Runs PII scan, Memory retrieval, and Intent classification concurrently.

    Intent classification is dispatched (not submitted into the `with`
    block below) so a slow Ollama response can never stall this node: see
    _dispatch_intent_classify / _resolve_intent for why the two other
    tasks and intent classification deliberately use different pools.
    """
    raw = state["raw_input"].strip()

    if not raw:
        logger.warning("[PREPROCESS] Empty input received — aborting pipeline.")
        return {"error": "Empty input. Please type a query.", "intent": "UNKNOWN"}

    if len(raw) > 8000:
        logger.warning("[PREPROCESS] Input exceeds 8000 chars — truncating.")
        raw = raw[:8000]

    # Pre-initialize singletons safely on the main thread before forking
    _get_pii_engine()
    _get_pii_map()
    _get_layered()
    _get_sentinel()

    session_id = state.get("session_id") or "default"

    def _layered_retrieve(query: str):
        return _get_layered().retrieve_layered_context(query, session_id)

    # Dispatch intent first so it gets a head start on the ~30ms that PII
    # scan + memory retrieval take, even though we won't wait on it here.
    intent_dispatched = _dispatch_intent_classify(raw)

    pii_future    = _PREPROCESS_EXECUTOR.submit(run_pii_scan, raw)
    memory_future = _PREPROCESS_EXECUTOR.submit(_layered_retrieve, raw)

    try:
        pii_result = pii_future.result(timeout=PREPROCESS_TIMEOUT_SECONDS)
    except (TimeoutError, FutureTimeoutError):
        logger.warning(
            "[PREPROCESS] PII scan exceeded %.0fs — proceeding unredacted from "
            "this node's perspective (the raw text still never leaves this "
            "process; it just skips placeholder substitution for this turn).",
            PREPROCESS_TIMEOUT_SECONDS,
        )
        pii_result = {"pii_map": {}, "anonymized": raw, "count": 0}

    try:
        layered = memory_future.result(timeout=PREPROCESS_TIMEOUT_SECONDS)
    except (TimeoutError, FutureTimeoutError):
        logger.warning(
            "[PREPROCESS] Memory retrieval exceeded %.0fs — proceeding with no "
            "layered context for this turn.", PREPROCESS_TIMEOUT_SECONDS,
        )
        from memory.layered_memory import LayeredContext
        layered = LayeredContext()

    intent_result = _resolve_intent(raw, intent_dispatched)

    # The layered context goes in as a SystemMessage ahead of the user turn,
    # so the model reads durable facts -> session history -> recent turns
    # before the question itself.
    messages: list = []
    if not layered.is_empty:
        messages.append(SystemMessage(content=layered.text))
        logger.info("[MEMORY] layers=%s (L1=%d L2=%d L3=%d) in %.0fms",
                    layered.layers_used, layered.l1_count, layered.l2_count,
                    layered.l3_count, layered.elapsed_ms)
    messages.append(HumanMessage(content=pii_result["anonymized"]))

    return {
        "pii_map": pii_result["pii_map"],
        "messages": messages,
        "n_pii_redacted": pii_result["count"],
        "memory_context": layered.text,
        "memory_hits": layered.l1_count + layered.l2_count + layered.l3_count,
        "memory_layers_used": layered.layers_used,
        "intent": intent_result["intent"],
        "error": intent_result.get("error", "")
    }

# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2 — llm_call_node
# ═══════════════════════════════════════════════════════════════════════════════

def select_model_for_task(intent: str) -> str:
    """
    Fast path: every task goes to Groq for latency.

    This has returned a constant since the fast-path change. It previously took
    a `complexity` score and ignored it; computing that score was the only thing
    keeping the old providers/ package (a third routing stack, DeepSeek included)
    in the live import graph, so both were removed. Kept as a named seam so
    reintroducing per-intent routing stays a one-line change.
    """
    return "groq"

_bound_llms = {}

# Applied to every cloud client below (Groq, Gemini, OpenRouter — Ollama has
# no equivalent field and is the local last-resort fallback anyway, where a
# slow-but-working answer beats cutting it off). Without this, a client that
# stalls rather than erroring fast (a slow/degraded endpoint, a hung TCP
# connection) never raises — so llm_call_node's own exception-triggered
# fallback cascade (backup Groq keys -> openrouter -> gemini) never fires,
# and the ONLY thing that ever stops the request is run_query()'s outer 60s
# ceiling, which does not retry anything. That is the actual mechanism
# behind "Groq timeout kills the task with no rotation": the rotation code
# was always there and correct, it just never got triggered. 15s leaves
# room for several real attempts inside the 60s outer budget.
CLOUD_CLIENT_TIMEOUT_SECONDS = 15

# Backstop for the calling-side enforcement in llm_call_node's _bounded_stream
# — see its docstring for why the client-level field above isn't trustworthy
# on its own. Persistent, not per-call `with`, for the same reason as every
# other executor in this file: exiting a `with ThreadPoolExecutor(...)` block
# blocks on shutdown(wait=True) regardless of any timeout already given up
# on, which would silently defeat the entire point of this wrapper.
_LLM_CALL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="phantom-llm-call")

def _get_bound_llm(model_choice: str):
    if model_choice in _bound_llms:
        return _bound_llms[model_choice]

    from tools.file_tools import ALL_TOOLS
    import os

    if model_choice == "groq" or model_choice == "cloud":
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # fallback to local
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model="qwen3.5:2b", temperature=0.3)
        else:
            api_key = os.getenv("GROQ_API_KEY", "")
            llm = ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, temperature=0.3,
                           request_timeout=CLOUD_CLIENT_TIMEOUT_SECONDS)
    else:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model="qwen3.5:2b", temperature=0.3)

    bound = llm.bind_tools(ALL_TOOLS)
    _bound_llms[model_choice] = bound
    return bound

PHANTOM_SYSTEM_PROMPT = """You are PHANTOM, a local AI agent that EXECUTES tasks directly on this Windows machine. You have tools. Use them.

CRITICAL RULES:
1. When the user asks you to DO something, call the appropriate tool immediately. Never describe how to do it manually, and never ask "would you like me to?" for an action you can just take — destructive actions are already gated by a separate approval step that fires automatically.
2. Tool mapping:
   - "find/search for X (by name/type/size/date/content)" -> search_files, then act on the paths it returns
   - "delete / remove / clean up duplicates in X" -> find_duplicates first, then delete_all_duplicates
   - "delete these specific files" / "delete all X files" -> search_files (if criteria given) then delete_files
   - "delete this whole folder" -> delete_folder (deletes the folder AND its contents — only for when the user clearly means the entire folder, not "empty out downloads")
   - "what's in X" / "list X" -> list_directory
   - "how big is X" / "scan X" -> scan_directory
   - "show me / read X" -> read_file
   - "open X" -> open_file
   - "move X to Y" -> move_file
   - "copy X to Y" -> copy_file
   - "rename X to Y" -> rename_file (same folder only — use move_file to relocate AND rename)
   - "create a folder called X" -> create_folder
   - "make/create/write an HTML page, note, report, summary" -> write_file (you generate the full content)
   - "email X" / "draft a mail to X" / "open gmail with..." -> draft_email (composes it, never sends)
3. FOLDER NAMES — CRITICAL: when the user names a standard folder, pass the BARE ALIAS as the path, exactly as they said it: "downloads", "desktop", "documents", "videos", "pictures", "music", "home". These resolve to THAT USER'S OWN folder (C:\\Users\\<them>\\Videos).
   NEVER invent an absolute path. Specifically NEVER use C:\\Users\\Public\\... — the Public folders are shared stubs and are almost always empty; the user means their own folder. Only pass a full path when the user typed a full path themselves.
4. write_file: pass a bare filename like 'report.html' unless the user names a folder. Write complete, self-contained HTML (inline CSS, no external assets). After creating a file, tell the user the full path.
5. Only reply with plain text when: the user asked a pure question, a tool has finished and you are reporting the result, or a tool returned an error you must explain.
6. If a tool returns an "error" field, tell the user plainly what failed and why. Never claim success after an error.
7. After a tool runs, report what actually happened using the real numbers/paths it returned. Do not invent results.
8. Be brief. You are an agent. You act, you report, you do not lecture.

Available tools: {tool_names}
Session context: {memory_context}
"""

from langchain_core.runnables import RunnableConfig

def _get_fallback_llm(provider: str, api_key: str = None):
    from tools.file_tools import ALL_TOOLS
    import os
    if provider == "groq":
        from langchain_groq import ChatGroq
        key = api_key or os.getenv("GROQ_API_KEY")
        return ChatGroq(model="openai/gpt-oss-120b", api_key=key, temperature=0.3,
                        request_timeout=CLOUD_CLIENT_TIMEOUT_SECONDS).bind_tools(ALL_TOOLS)
    elif provider == "gemini":
        # gemini-2.0-flash 404s ("no longer available") — verified live. This is
        # the LAST link in the failover chain, so a dead model here meant a Groq
        # outage took the whole response down. Kept in sync with llm_router.py's
        # gemini client, which is the model name that actually resolves.
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = os.getenv("GEMINI_API_KEY")
        return ChatGoogleGenerativeAI(model="gemini-3.6-flash", api_key=key, temperature=0.3,
                                      timeout=CLOUD_CLIENT_TIMEOUT_SECONDS).bind_tools(ALL_TOOLS)
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENROUTER_API_KEY")
        return ChatOpenAI(model="google/gemma-4-31b-it:free", openai_api_key=key,
                          openai_api_base="https://openrouter.ai/api/v1", temperature=0.3,
                          request_timeout=CLOUD_CLIENT_TIMEOUT_SECONDS).bind_tools(ALL_TOOLS)
    else:
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            from langchain_community.chat_models import ChatOllama
        return ChatOllama(model="qwen3.5:2b", temperature=0.3).bind_tools(ALL_TOOLS)

def llm_call_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Core ReAct loop node (Fix A).
    Initializes model dynamically based on intent (Fix E).
    Calls model with stream() and passes tokens to UI (Fix F).
    """
    from tools.file_tools import ALL_TOOLS
    from langchain_core.messages import SystemMessage
    import os

    intent = state.get("intent", "GENERAL_QA")
    model_choice = select_model_for_task(intent)
    llm_with_tools = _get_bound_llm(model_choice)
    
    system = PHANTOM_SYSTEM_PROMPT.format(
        tool_names=", ".join(t.name for t in ALL_TOOLS),
        memory_context=state.get("memory_context", "")
    )
    
    messages = [SystemMessage(content=system), *state["messages"]]
    
    # 1. Token Pre-flight Checks
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        total_tokens = sum(len(enc.encode(str(getattr(m, 'content', m)))) for m in messages)
        if total_tokens > 7000 and model_choice in ("groq", "cloud"):
            logger.warning(f"[LLM] Payload too large ({total_tokens} tokens). Routing to Gemini fallback.")
            llm_with_tools = _get_fallback_llm("gemini")
    except Exception as e:
        logger.warning(f"[LLM] Token pre-flight check failed: {e}")

    logger.info("[LLM] Calling %s model", model_choice)
    token_callback = config.get("configurable", {}).get("token_callback")
    
    # 2. Robust API Rotation & Execution
    groq_keys = [os.getenv("GROQ_API_KEY")]
    for i in range(2, 6):
        k = os.getenv(f"GROQ_API_KEY_{i}")
        if k: groq_keys.append(k)

    def run_stream(llm_client):
        full_res = None
        for chunk in llm_client.stream(messages):
            if token_callback and chunk.content:
                token_callback(chunk.content)
            if full_res is None:
                full_res = chunk
            else:
                full_res += chunk
        return full_res

    def _bounded_stream(llm_client):
        """
        run_stream(), but with the timeout enforced from the calling side
        rather than trusted to the client's own timeout field.

        Verified live before relying on this: ChatGroq's request_timeout is
        genuinely honored (a 0.001s setting raised APITimeoutError in
        1.855s). ChatGoogleGenerativeAI's `timeout=` is NOT reliably
        honored for a stalled connection — the same 0.001s setting took
        34.183s to raise (ConnectTimeout, stuck in the TLS handshake phase
        specifically, not the read phase the field seems to actually
        bound). Without this wrapper, a Gemini-specific stall — Gemini
        being the LAST link in the fallback chain below — would never
        raise at all within any useful window, so the fallback logic
        immediately below would never get a chance to run for that exact
        failure mode, and the only thing that would eventually stop the
        request is run_query()'s outer 60s ceiling, with zero rotation
        ever attempted. That is the literal mechanism behind "rotation
        isn't happening" for a stalled (as opposed to fast-erroring)
        provider. The abandoned call keeps running harmlessly in the
        background on this persistent pool if it does eventually resolve.
        """
        future = _LLM_CALL_EXECUTOR.submit(run_stream, llm_client)
        return future.result(timeout=CLOUD_CLIENT_TIMEOUT_SECONDS)

    full_response = None
    # Which provider actually served the response. Starts as the intended one
    # and is reassigned by the failover paths below — reporting the *intended*
    # provider after a failover mislabels both the UI badge and the usage log.
    actual_provider = "groq" if model_choice in ("groq", "cloud") else "ollama"
    try:
        full_response = _bounded_stream(llm_with_tools)
    except Exception as e:
        # Fail over on ANY provider error (rate limit, decommissioned model,
        # bad request, timeout, etc.) — never let a single provider's outage
        # or a stale hardcoded model name kill the whole response.
        logger.warning(f"[LLM] API Error caught: {e}. Attempting failover...")
        success = False

        # Rotate backup Groq keys first (cheap, same provider)
        for backup_key in groq_keys[1:]:
            try:
                logger.warning("[LLM] Trying backup Groq API Key...")
                fallback_llm = _get_fallback_llm("groq", api_key=backup_key)
                full_response = _bounded_stream(fallback_llm)
                actual_provider = "groq"
                success = True
                break
            except Exception:
                continue

        # Cross-provider fallback chain
        if not success:
            logger.warning("[LLM] All Groq keys failed. Failing over across providers...")
            for provider in ("openrouter", "gemini"):
                try:
                    fallback_llm = _get_fallback_llm(provider)
                    full_response = _bounded_stream(fallback_llm)
                    actual_provider = provider
                    success = True
                    break
                except Exception as fallback_exc:
                    logger.warning(f"[LLM] {provider} fallback failed: {fallback_exc}")
                    continue

        if not success:
            # Every provider in the cascade genuinely failed. This used to
            # re-raise the ORIGINAL exception (e.g. a raw
            # "groq.AuthenticationError: Invalid API Key" or a Gemini
            # ConnectTimeout), which propagates as an unhandled LangGraph
            # node exception — and the generic exception handler on the
            # other end of that (PhantomWorker.run() in the UI) shows
            # str(exc) straight to the user, surfacing exactly the raw
            # provider-specific text the UI is never supposed to display.
            # Logged in full here (this is the one place that's supposed to
            # know which provider said what); the user only ever sees a
            # generic message.
            logger.error("[LLM] All providers exhausted for this turn: %s", e)
            full_response = AIMessage(
                content="Unable to process request right now. Please try again."
            )
            actual_provider = "none"

    # Return update to state
    provider_used = actual_provider

    # Usage logging for THIS path too. The router (llm_router.py) logs its own
    # calls, but the app's real traffic runs through this node and never
    # touches PhantomRouter — logging only the router would leave actual
    # production usage untracked. window_limit=0 marks an entry as not
    # rate-window-managed (this path has no ProviderSlot budget).
    try:
        from utils.usage_logger import log_usage
        # bind_tools() wraps the chat model in a RunnableBinding, so the model
        # id lives on .bound rather than the wrapper itself.
        _target = getattr(llm_with_tools, "bound", llm_with_tools)
        _model = getattr(_target, "model_name", None) or getattr(_target, "model", None)
        log_usage(
            provider=provider_used,
            model=str(_model) if _model else "unknown",
            tokens_used=int(locals().get("total_tokens", 0) or 0),
            window_tokens=0,
            window_limit=0,
            session_id=str(config.get("configurable", {}).get("thread_id", "unknown")),
            mode=state.get("mode", "smart"),
        )
    except Exception:
        pass

    # safe_content(), not .content: the Gemini failover path returns content as
    # a list of structured parts, and handing that list to pii_restore_node
    # (which does regex substitution on a string) breaks the response path
    # exactly when a provider outage has already put it under stress.
    from llm_router import safe_content

    return {
        "messages": [full_response],
        "llm_response": safe_content(full_response),
        "provider_used": provider_used
    }

def _extract_pending_tool_call(state: AgentState) -> dict | None:
    """
    Pull the high-risk tool call (if any) out of the last assistant message.

    This must be derived from the message itself rather than read from a
    state key: conditional-edge functions cannot persist state mutations in
    LangGraph, so anything assigned to `state[...]` inside should_use_tool()
    is silently discarded before hitl_check_node runs.
    """
    from tools.file_tools import HIGH_RISK_TOOLS

    messages = state.get("messages") or []
    if not messages:
        return None
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None)
    if not tool_calls:
        return None

    # Restore PII placeholders so the approval prompt shows the user what
    # will really happen ("email teammate@example.com", not "[PII_EMAIL_1]").
    restored_state = _restore_pii_in_tool_args(state)
    restored_calls = getattr(restored_state["messages"][-1], "tool_calls", tool_calls)

    for tc in restored_calls:
        if tc.get("name") in HIGH_RISK_TOOLS:
            return tc
    return restored_calls[0]


def should_use_tool(state: AgentState) -> str:
    """Conditional edge logic for tool routing"""
    from tools.file_tools import HIGH_RISK_TOOLS

    # Stop after 5 tool calls — prevent infinite loop
    tool_call_count = state.get("tool_call_count", 0)
    if tool_call_count >= 5:
        return "pii_restore_node"

    messages = state.get("messages") or []
    if not messages:
        return "pii_restore_node"
    last = messages[-1]

    tool_calls = getattr(last, "tool_calls", None)
    if tool_calls:
        # Any high-risk tool must pass through the HITL gate first.
        for tc in tool_calls:
            if tc.get("name") in HIGH_RISK_TOOLS:
                return "hitl_check_node"
        return "tool_node"
    return "pii_restore_node"


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5 — hitl_check_node
# ═══════════════════════════════════════════════════════════════════════════════

# ── HITL thresholds ───────────────────────────────────────────────────────────
INTERRUPT_THRESHOLD = 0.7   # fires interrupt()
LOG_THRESHOLD       = 0.3   # logs to audit but no interrupt


def _compute_risk(raw_input: str, tool_call: dict | None = None) -> float:
    """
    3-tier risk scorer. Delegates to hitl.risk_scorer_3tier.
    Scores the RAW user input — never the LLM response.
    """
    from hitl.risk_scorer_3tier import compute_risk
    return compute_risk(raw_input, tool_call=tool_call)


def _describe_tool_call(tool_name: str, tool_args: dict) -> str:
    """Human-readable one-liner describing what a tool call will do."""
    if not tool_name:
        return ""
    args = tool_args or {}
    if tool_name == "delete_all_duplicates":
        return f"Delete all duplicate files in: {args.get('path', '?')}"
    if tool_name == "delete_files":
        paths = args.get("file_paths") or []
        if len(paths) <= 3:
            return f"Delete {len(paths)} file(s): {', '.join(str(p) for p in paths)}"
        return f"Delete {len(paths)} files (first 3: {', '.join(str(p) for p in paths[:3])} …)"
    if tool_name == "delete_folder":
        return f"Delete the ENTIRE folder and everything inside it: {args.get('path', '?')}"
    if tool_name == "write_file":
        return f"Create/overwrite file: {args.get('path', '?')}"
    if tool_name == "draft_email":
        return f"Open an email draft to: {args.get('to', '(no recipient)')}"
    arg_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:3])
    return f"{tool_name}({arg_str})"


def _affected_preview(tool_name: str, tool_args: dict) -> list[str]:
    """
    Read-only dry run: list exactly which files a destructive tool would touch.

    Runs before approval so the user sees the real blast radius instead of a
    bare tool name. Never mutates anything; failures degrade to an empty list.
    """
    args = tool_args or {}
    try:
        if tool_name == "delete_all_duplicates":
            from tools.file_tools import _get_duplicates_list
            return [str(p) for p in _get_duplicates_list(args.get("path", ""))][:25]
        if tool_name == "delete_files":
            return [str(p) for p in (args.get("file_paths") or [])][:25]
        if tool_name == "delete_folder":
            from tools.file_tools import resolve_path
            p_obj = resolve_path(args.get("path", ""))
            if p_obj.is_dir():
                return [str(f) for f in list(p_obj.rglob("*"))[:25]]
    except Exception as exc:
        logger.warning("[HITL] Preview failed for %s: %s", tool_name, exc)
    return []


def hitl_check_node(state: AgentState) -> dict | Command:
    """
    Confidence-gated HITL interrupt.
    Scores the RAW user input (not the LLM response) using the 3-tier scorer.
    """
    raw_input   = state.get("raw_input", "")
    intent      = state.get("intent", "")
    llm_response = state.get("llm_response", "")
    tool_call   = _extract_pending_tool_call(state)

    risk = _compute_risk(raw_input, tool_call=tool_call)
    logger.info(
        "[HITL] Risk score: %.2f (input=%r, tool=%s)",
        risk, raw_input[:40], (tool_call or {}).get("name"),
    )

    if risk >= INTERRUPT_THRESHOLD:
        logger.warning("[HITL] High-risk action (score=%.2f) — interrupting.", risk)

        tool_name = (tool_call or {}).get("name", "")
        tool_args = (tool_call or {}).get("args", {}) or {}
        preview = _describe_tool_call(tool_name, tool_args)

        decision = interrupt({
            "action": preview or raw_input[:200],
            "raw_input": raw_input[:200],
            "tool_name": tool_name,
            "tool_args": tool_args,
            "affected": _affected_preview(tool_name, tool_args),
            "intent": intent,
            "risk_score": round(risk, 2),
            "tier": "interrupt",
            "message": (
                f"[PHANTOM] HITL Review Required\n"
                f"Risk score: {round(risk * 100)}%\n"
                f"Proposed action: {preview or raw_input[:200]}\n\n"
                f"Type 'approve' to allow or 'reject' to cancel."
            ),
        })

        if str(decision).strip().lower() in ("reject", "no", "n", "cancel"):
            logger.info("[HITL] Action REJECTED by user.")
            return {
                "risk_score": risk,
                "hitl_required": True,
                "hitl_decision": "reject",
                "llm_response": "[PHANTOM] Action cancelled by user.",
            }
        else:
            logger.info("[HITL] Action APPROVED by user.")
            return {
                "risk_score": risk,
                "hitl_required": True,
                "hitl_decision": "approve",
            }

    elif risk >= LOG_THRESHOLD:
        from utils.audit_logger import audit
        audit.log_event(
            "HITL_BORDERLINE",
            risk_score=risk,
            intent=intent,
            query_length=len(raw_input),
        )
        logger.info("[HITL] Borderline risk (score=%.2f) — logged, no interrupt.", risk)

    return {
        "risk_score": risk,
        "hitl_required": False,
        "hitl_decision": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 6 — pii_restore_node
# ═══════════════════════════════════════════════════════════════════════════════

def pii_restore_node(state: AgentState) -> AgentState:
    """
    PII Sandwich — RESTORE phase.

    Takes the LLM response (containing [PII_TYPE_N] tokens) and substitutes
    original values back. Validates that no raw PII leaked into the response.

    Appends the restored response to messages as 'assistant' turn.
    Stores the turn in ChromaDB for future memory retrieval.
    """
    llm_response = state.get("llm_response", "")
    messages = state.get("messages", [])

    # Restore PII placeholders → original values
    try:
        restorer = _get_pii_restorer()
        restored, warnings = restorer.restore_and_validate(llm_response)
        for w in warnings:
            logger.warning("[PII RESTORE] %s", w)
    except Exception as exc:
        logger.error("[PII RESTORE] Error: %s", exc)
        restored = llm_response  # Non-fatal — show raw response

    # Write interaction to ChromaDB for future memory retrieval.
    # SAFETY: never store restored PII in vector DB — pass llm_response
    # (pre-restoration, still holding [PII_*] placeholders), never `restored`
    # (real values substituted back in). write_back()'s own summarizer is a
    # second privacy layer, but it degrades to a 3-pattern regex fallback when
    # Ollama is unreachable (the common case here — see the circuit breaker in
    # sentinel_node.py) and would let unredacted PII types it doesn't cover
    # (phone numbers, names, addresses...) reach persistent storage.
    # Placeholders are safe by construction regardless of which summarization
    # path runs.
    _write_to_memory(state, llm_response)

    # Layered consolidation — L1 always, L3 on any durable fact, L2 every 5th
    # turn. Fire-and-forget on a daemon thread: the response is already
    # assembled at this point and must not wait on memory writes or on the
    # summarisation call L2 makes.
    turn_count = int(state.get("turn_count", 0)) + 1
    try:
        from memory.consolidator import consolidate_async

        user_content = ""
        for msg in reversed(state.get("messages", [])):
            if getattr(msg, "type", "") == "human":
                user_content = getattr(msg, "content", "")
                break
        # Pre-restoration text only, same rule as _write_to_memory above.
        turn_text = f"{user_content} → {llm_response[:300]}".strip()
        consolidate_async(
            turn_text=turn_text,
            session_id=state.get("session_id") or "default",
            turn_count=turn_count,
            layered=_get_layered(),
            # L3 scans this alone — never the combined turn, or the model's
            # own replies become permanent "user facts". See consolidate().
            user_text=user_content,
        )
    except Exception as exc:
        logger.warning("[CONSOLIDATE] dispatch failed: %s", exc)

    logger.info("[PII RESTORE] Complete. Final response: %d chars.", len(restored))

    return {
        "final_response": restored,
        "turn_count": turn_count,
    }


def _write_to_memory(state: AgentState, response: str) -> None:
    """
    Async write-back: store this turn in ChromaDB session memory.

    Runs in a background thread so it never blocks the response path.
    Only writes sanitised content (no raw PII).
    """
    import threading

    user_content = ""
    for msg in reversed(state.get("messages", [])):
        if getattr(msg, "type", "") == "human":
            user_content = getattr(msg, "content", "")
            break

    summary = f"{user_content} → {response[:300]}"

    def _do_write():
        try:
            chroma = _get_chroma()
            chroma.write_back(
                interaction_summary=summary,
                intent_type=state.get("intent", "GENERAL_QA"),
                outcome="completed",
                hitl_approved=state.get("hitl_decision") == "approve" or not state.get("hitl_required", False),
            )
        except Exception as exc:
            logger.warning("[MEMORY WRITE] Write-back failed: %s", exc)

    threading.Thread(target=_do_write, daemon=True, name="phantom-memory-writeback").start()


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from tools.file_tools import ALL_TOOLS

# ── Persistent checkpointing ──────────────────────────────────────────────────

CHECKPOINT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "phantom_memory", "checkpoints.db"
)


def _build_postgres_checkpointer():
    """
    Postgres-backed checkpointer for multi-user / multi-worker deployment.

    Opt in with PHANTOM_CHECKPOINT_BACKEND=postgres and a
    PHANTOM_CHECKPOINT_DSN connection string. Requires:
        pip install langgraph-checkpoint-postgres psycopg[binary]

    NOT verified against a live server in this environment — there is no
    Postgres instance here to test against. Treat the first deployment run
    as the real integration test.
    """
    dsn = os.environ.get("PHANTOM_CHECKPOINT_DSN", "").strip()
    if not dsn:
        raise RuntimeError(
            "PHANTOM_CHECKPOINT_BACKEND=postgres but PHANTOM_CHECKPOINT_DSN is unset."
        )
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore

    checkpointer = PostgresSaver.from_conn_string(dsn)
    # from_conn_string is a contextmanager on some versions — same trap as the
    # SQLite one; unwrap it if so rather than handing compile() a CM.
    if hasattr(checkpointer, "__enter__") and not hasattr(checkpointer, "put"):
        checkpointer = checkpointer.__enter__()
    checkpointer.setup()
    print("[PHANTOM] Checkpoint backend: postgres")
    return checkpointer


def _build_checkpointer():
    """
    Persistent checkpointer so thread history survives process restarts
    (MemorySaver was RAM-only — every restart wiped every conversation).

    Backend is selected by PHANTOM_CHECKPOINT_BACKEND (default "sqlite"), so
    moving to Postgres for multi-user deployment is a config change rather
    than a code change.

    On SQLite: SqliteSaver.from_conn_string() is a @contextmanager, so
    assigning its result directly would hand graph.compile() a
    _GeneratorContextManager rather than a checkpointer. For a
    process-lifetime checkpointer the connection is opened directly instead.
    check_same_thread=False is required because run_query() executes the
    graph inside a ThreadPoolExecutor worker, not the thread that opened it.
    """
    import sqlite3

    backend = os.environ.get("PHANTOM_CHECKPOINT_BACKEND", "sqlite").strip().lower()
    if backend in ("postgres", "postgresql"):
        try:
            return _build_postgres_checkpointer()
        except Exception as exc:
            logger.error(
                "[CHECKPOINT] Postgres backend failed (%s) — falling back to SQLite.", exc
            )

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        logger.warning(
            "[CHECKPOINT] langgraph-checkpoint-sqlite not installed — falling back "
            "to in-memory MemorySaver (thread history will NOT survive restarts). "
            "Fix: pip install langgraph-checkpoint-sqlite"
        )
        return MemorySaver()

    try:
        os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        # SqliteSaver.setup() already sets journal_mode=WAL (measured: 240
        # concurrent writes across 6 processes, zero lock errors). It does NOT
        # set busy_timeout, though — the SQLite default is 0, meaning a writer
        # that finds the lock held fails instantly with "database is locked"
        # instead of waiting. Cheap insurance for heavier contention than the
        # stress test covered.
        #
        # 10s rather than 5s: this is the second line of defence behind the
        # single-instance lock (utils/instance_lock.py). It only matters at all
        # if that lock has already failed open, and in that case two agents are
        # contending — waiting is strictly better than erroring out.
        conn.execute("PRAGMA busy_timeout=10000")
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()

        thread_count = 0
        try:
            cur = conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
            row = cur.fetchone()
            thread_count = row[0] if row else 0
        except Exception:
            pass

        print(f"[PHANTOM] Checkpoint DB loaded: {CHECKPOINT_DB_PATH}, threads: {thread_count}")
        logger.info("[CHECKPOINT] DB loaded: %s, threads: %d", CHECKPOINT_DB_PATH, thread_count)
        return checkpointer
    except Exception as exc:
        logger.error(
            "[CHECKPOINT] SQLite checkpointer failed (%s) — falling back to MemorySaver.", exc
        )
        return MemorySaver()

def custom_tool_node(state: AgentState) -> AgentState:
    """Wrapper around ToolNode to prevent execution on HITL reject."""
    if state.get("hitl_decision") == "reject":
        # The user rejected the tool call. We must satisfy the tool call ID
        # with a ToolMessage so the LLM doesn't get stuck.
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            cancel_msgs = []
            for tc in last.tool_calls:
                cancel_msgs.append(ToolMessage(
                    content="Action cancelled by user.",
                    tool_call_id=tc["id"]
                ))
            # Clear the decision so it can't also cancel an unrelated
            # follow-up tool call later in the same turn.
            return {
                "messages": cancel_msgs,
                "tool_call_count": state.get("tool_call_count", 0) + 1,
                "hitl_decision": None,
            }
    
    # Tools run locally, so they must receive the REAL values — the cloud
    # model only ever saw redacted placeholders. Without this, a request like
    # "email teammate@example.com" reaches the tool as "[PII_EMAIL_1]".
    state = _restore_pii_in_tool_args(state)

    # Otherwise, execute via standard ToolNode
    result = ToolNode(ALL_TOOLS).invoke(state)
    if isinstance(result, dict):
        result["tool_call_count"] = state.get("tool_call_count", 0) + 1
    return result


def _restore_pii_in_tool_args(state: AgentState) -> AgentState:
    """
    Substitute [PII_*] placeholders back into tool-call arguments.

    The PII sandwich redacts before the cloud call and restores on the way
    out, but tool arguments travel a third path: generated by the cloud model
    (so full of placeholders) yet executed on this machine (where real values
    are required). Restoring here keeps the privacy guarantee intact — the
    provider still never saw the real value — while letting local actions
    work on real data.
    """
    messages = state.get("messages") or []
    if not messages:
        return state

    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None)
    if not tool_calls:
        return state

    try:
        pii_map = _get_pii_map()
        if not len(pii_map):
            return state
    except Exception:
        return state

    def _restore(value):
        if isinstance(value, str):
            return pii_map.restore(value)
        if isinstance(value, list):
            return [_restore(v) for v in value]
        if isinstance(value, dict):
            return {k: _restore(v) for k, v in value.items()}
        return value

    changed = False
    new_calls = []
    for tc in tool_calls:
        args = tc.get("args") or {}
        restored_args = {k: _restore(v) for k, v in args.items()}
        if restored_args != args:
            changed = True
            tc = {**tc, "args": restored_args}
        new_calls.append(tc)

    if not changed:
        return state

    logger.info("[PII] Restored placeholders in tool arguments before local execution.")
    new_last = last.model_copy(update={"tool_calls": new_calls})
    return {**state, "messages": [*messages[:-1], new_last]}

def build_graph():
    """
    Build and compile the PHANTOM LangGraph StateGraph.

    Updated Topology:
    START → mode_classifier_node (regex only, no LLM call)
        ├── controlled → deterministic_action_node → END
        └── smart/agent → input_guard_node
                ├── blocked → END
                └── parallel_preprocess_node → llm_call_node
            ↓
    should_use_tool (conditional)
        ├── tool_node (safe tools) ────────┐ (loop back)
        ├── hitl_check_node (risky tools)  │
        │       ↓                          │
        │   tool_node ─────────────────────┘ (loop back)
        └── pii_restore_node (no tool call)
                ↓
            END
    """
    checkpointer = _build_checkpointer()

    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("mode_classifier_node", mode_classifier_node)
    graph.add_node("deterministic_action_node", deterministic_action_node)
    graph.add_node("guardian_node", guardian_node)
    graph.add_node("parallel_preprocess_node", parallel_preprocess_node)
    graph.add_node("llm_call_node",      llm_call_node)
    graph.add_node("tool_node",          custom_tool_node)
    graph.add_node("hitl_check_node",    hitl_check_node)
    graph.add_node("pii_restore_node",   pii_restore_node)

    # Mode classification runs first — controlled commands skip straight to
    # a deterministic stub and END; smart/agent fall through to the guard,
    # which can still short-circuit straight to END on an injection match.
    graph.add_edge(START, "mode_classifier_node")
    graph.add_conditional_edges(
        "mode_classifier_node",
        route_after_mode,
        {"deterministic_action_node": "deterministic_action_node", "guardian_node": "guardian_node"},
    )
    graph.add_edge("deterministic_action_node", END)

    graph.add_conditional_edges(
        "guardian_node",
        route_after_guard,
        {"parallel_preprocess_node": "parallel_preprocess_node", END: END},
    )
    graph.add_edge("parallel_preprocess_node", "llm_call_node")
    
    graph.add_conditional_edges(
        "llm_call_node",
        should_use_tool,
        {
            "tool_node": "tool_node",
            "hitl_check_node": "hitl_check_node",
            "pii_restore_node": "pii_restore_node"
        }
    )
    
    graph.add_edge("tool_node", "llm_call_node")
    graph.add_edge("hitl_check_node", "tool_node")
    graph.add_edge("pii_restore_node", END)

    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


# Singleton graph — compiled once and reused
_graph = None


def get_graph():
    """Return the compiled PHANTOM graph (singleton)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def _run_query_internal(
    user_input: str,
    thread_id: str | None = None,
    verbose: bool = True,
    token_callback = None,
    hitl_callback = None,
    interactive: bool = False,
) -> dict[str, Any]:
    """
    Run a single query through the PHANTOM LangGraph pipeline.

    Handles the interrupt/resume loop for HITL automatically in CLI mode:
    - When the graph interrupts (risk > 0.7), prints the approval prompt.
    - Reads user decision from stdin.
    - Resumes the graph with Command(resume=decision).

    Args:
        user_input  : Raw user query string.
        thread_id   : Session identifier (one per conversation). Auto-generated if None.
        verbose     : Print pipeline steps to stdout.
        token_callback: Optional callable for streaming UI.

    Returns dict with keys: response, intent, risk_score, n_pii, hitl_required.
    """
    import time
    _start = time.time()

    graph = get_graph()
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id, "token_callback": token_callback}}

    initial_state: AgentState = {
        "raw_input": user_input,
        "hitl_decision": None,
        "llm_response": "",
        "final_response": "",
        "intent": "",
        "risk_score": 0.0,
        "n_pii_redacted": 0,
        "error": "",
        "pending_tool_call": None,
        # session_id drives per-session scoping for L1/L2 memory. thread_id is
        # already the conversation identity here, so they are the same thing.
        "session_id": thread_id,
    }

    final_state: dict = dict(initial_state)
    interrupt_payload: dict | None = None

    try:
        final_state, interrupt_payload = _stream_graph(graph, initial_state, config, final_state)

        # HITL loop. A single turn can interrupt more than once (multi-step
        # tool chains), so keep resolving until the graph runs to completion.
        while interrupt_payload is not None:
            decision = _resolve_hitl_decision(interrupt_payload, hitl_callback, verbose, interactive)

            if decision is None:
                # No way to ask right now (web UI): hand the decision back to
                # the caller, which shows a modal and calls resume_query().
                return _build_result(
                    final_state, thread_id, _start,
                    pending_interrupt=interrupt_payload,
                )

            if verbose:
                print(f"[HITL] Decision: {decision.upper()}")

            final_state, interrupt_payload = _stream_graph(
                graph, Command(resume=decision), config, final_state
            )

    except Exception as exc:
        logger.exception("[GRAPH] Unhandled error:")
        final_state["final_response"] = f"[PHANTOM] Pipeline error: {exc}"

    result = _build_result(final_state, thread_id, _start)

    if result.get("error") and verbose:
        print(f"[PHANTOM] Warning: {result['error']}")
    if verbose and result["response"]:
        print(f"\n[PHANTOM] {result['response']}")

    return result


def _stream_graph(graph, payload, config, prev_state: dict) -> tuple[dict, dict | None]:
    """
    Stream the graph and separate real state from an interrupt marker.

    LangGraph >= 0.2 does NOT raise GraphInterrupt out of .stream(); it ends
    the stream and emits a final event carrying "__interrupt__". Treating that
    marker as ordinary state is what made every high-risk query return an
    empty response.

    Returns (final_state, interrupt_payload_or_None).
    """
    final_state = dict(prev_state)
    interrupt_payload: dict | None = None

    for event in graph.stream(payload, config=config, stream_mode="values"):
        if isinstance(event, dict) and "__interrupt__" in event:
            interrupts = event.get("__interrupt__") or ()
            if interrupts:
                value = getattr(interrupts[0], "value", interrupts[0])
                interrupt_payload = value if isinstance(value, dict) else {"message": str(value)}
            merged = {k: v for k, v in event.items() if k != "__interrupt__"}
            if merged:
                final_state.update(merged)
        elif isinstance(event, dict):
            final_state.update(event)

    return final_state, interrupt_payload


def _resolve_hitl_decision(payload: dict, hitl_callback, verbose: bool, interactive: bool = False) -> str | None:
    """
    Get an approve/reject decision for a pending interrupt.

    Order: explicit callback → interactive terminal prompt → None.
    Returning None hands the decision back to the caller, which is what lets
    a web UI render its own approval modal. `interactive` is passed
    explicitly by the CLI rather than sniffed from stdin, so a UI process can
    never accidentally block on (or auto-reject from) a missing terminal.
    """
    if verbose:
        print("\n" + "=" * 60)
        print(payload.get("message", "PHANTOM requires approval."))
        affected = payload.get("affected") or []
        if affected:
            print(f"\nFiles affected ({len(affected)}):")
            for item in affected[:10]:
                print(f"  - {item}")
            if len(affected) > 10:
                print(f"  ... and {len(affected) - 10} more")
        print("=" * 60)

    if hitl_callback is not None:
        raw = hitl_callback(payload)
        return "approve" if str(raw).strip().lower() in ("approve", "a", "yes", "y") else "reject"

    if not (interactive and _stdin_is_interactive()):
        return None

    try:
        raw = input("\n[HITL] Your decision (approve/reject): ").strip().lower()
    except (EOFError, KeyboardInterrupt, OSError):
        return "reject"
    return "approve" if raw in ("approve", "a", "yes", "y") else "reject"


def _stdin_is_interactive() -> bool:
    """True only when a real terminal is attached (never under Streamlit/uvicorn)."""
    try:
        import sys as _sys
        return bool(_sys.stdin) and _sys.stdin.isatty()
    except Exception:
        return False


def _build_result(
    final_state: dict,
    thread_id: str,
    start_time: float,
    pending_interrupt: dict | None = None,
) -> dict[str, Any]:
    """Assemble the public result dict, guaranteeing a non-empty response."""
    import time

    response = final_state.get("final_response") or final_state.get("llm_response", "") or ""
    response = response.strip() if isinstance(response, str) else str(response)

    if pending_interrupt is not None:
        # Awaiting approval — surface the proposal as the visible message.
        action = pending_interrupt.get("action", "a high-risk action")
        affected = pending_interrupt.get("affected") or []
        lines = [f"**Approval required:** {action}"]
        if affected:
            lines.append("")
            lines.append(f"This will affect {len(affected)} file(s):")
            lines.extend(f"- `{item}`" for item in affected[:10])
            if len(affected) > 10:
                lines.append(f"- …and {len(affected) - 10} more")
        response = "\n".join(lines)

    if not response:
        # Never hand the UI a blank message — that reads as a dead app.
        err = final_state.get("error", "")
        response = (
            f"[PHANTOM] No response produced. {err}".strip()
            if err
            else "[PHANTOM] No response was produced for that request. Try rephrasing it."
        )

    return {
        "response": response,
        "final_response": response,
        "intent": final_state.get("intent", ""),
        "risk_score": (
            pending_interrupt.get("risk_score")
            if pending_interrupt else final_state.get("risk_score", 0.0)
        ),
        "n_pii": final_state.get("n_pii_redacted", 0),
        "n_pii_redacted": final_state.get("n_pii_redacted", 0),
        "provider_used": final_state.get("provider_used", "unknown"),
        "memory_hits": final_state.get("memory_hits", 0),
        "latency_ms": int((time.time() - start_time) * 1000),
        "hitl_required": pending_interrupt is not None,
        "hitl_decision": final_state.get("hitl_decision"),
        "hitl_payload": pending_interrupt,
        "error": final_state.get("error", ""),
        "thread_id": thread_id,
        "mode": final_state.get("mode", "smart"),
        "guardian_tier": final_state.get("guardian_tier", ""),
        "guardian_reason": final_state.get("guardian_reason", ""),
        "memory_layers_used": final_state.get("memory_layers_used", []),
        "turn_count": final_state.get("turn_count", 0),
    }


def resume_query(decision: str, thread_id: str, token_callback=None) -> dict:
    """
    Resume a HITL-interrupted graph with the user's decision.

    A resumed turn can interrupt again (e.g. a second destructive tool call
    later in the same chain), so this reports hitl_required back to the UI
    exactly the way run_query does.
    """
    import time
    _start = time.time()
    from langgraph.types import Command

    graph = get_graph()
    config = {'configurable': {'thread_id': thread_id, 'token_callback': token_callback}}

    normalised = "approve" if str(decision).strip().lower() in ("approve", "a", "yes", "y") else "reject"

    try:
        final_state, interrupt_payload = _stream_graph(
            graph, Command(resume=normalised), config, {}
        )
    except Exception as exc:
        logger.error('[RESUME] Error: %s', exc)
        msg = f'[PHANTOM] Resume error: {exc}'
        return {'response': msg, 'final_response': msg, 'error': str(exc),
                'hitl_required': False, 'thread_id': thread_id}

    result = _build_result(final_state, thread_id, _start, pending_interrupt=interrupt_payload)
    if interrupt_payload is None:
        result['hitl_decision'] = normalised
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST — run `python phantom_graph.py` to verify graph compiles
# ═══════════════════════════════════════════════════════════════════════════════

import concurrent.futures

# run_query() used to open `with concurrent.futures.ThreadPoolExecutor(1) as ex:`
# per call. That looks like it enforces `timeout`, but it doesn't: when
# future.result(timeout=timeout) raises TimeoutError, the `return` inside the
# `with` block still has to run `ex.__exit__()` -> shutdown(wait=True) before
# the function can actually return -- which blocks until the abandoned
# _run_query_internal call finishes for real, however long that takes.
# Measured live: a "Request timed out after 60s" message was delivered at
# 82-92s wall-clock, not 60s, because the calling thread (PhantomWorker) was
# stuck inside that shutdown the whole time. If the window is hidden during
# that stretch (Escape, or the hotkey pressed again -- neither currently
# checks _busy), the eventual response lands in an invisible widget with no
# way to bring it back, and a second query attempt silently no-ops because
# _busy never actually cleared. A persistent pool fixes the enforcement: the
# calling thread can walk away after `timeout` and the abandoned call keeps
# running in the true background rather than blocking whoever gave up on it.
_QUERY_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=3, thread_name_prefix="phantom-query"
)


def _log_abandoned_query_outcome(future: concurrent.futures.Future) -> None:
    """Best-effort visibility into a call nobody is waiting on any more."""
    try:
        future.result()
        logger.info("[QUERY] Abandoned (timed-out) call completed after the fact.")
    except Exception as exc:
        logger.warning("[QUERY] Abandoned (timed-out) call failed after the fact: %s", exc)


def run_query(user_input, thread_id=None, verbose=True, token_callback=None,
              hitl_callback=None, timeout=60, interactive=False):
    # In an interactive terminal the HITL prompt blocks on human input, which
    # a wall-clock timeout would kill mid-decision. Run inline there instead.
    if interactive:
        return _run_query_internal(
            user_input, thread_id, verbose, token_callback, hitl_callback, interactive=True
        )

    future = _QUERY_EXECUTOR.submit(
        _run_query_internal, user_input, thread_id, verbose, token_callback, hitl_callback, False
    )
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.add_done_callback(_log_abandoned_query_outcome)
        msg = f"Request timed out after {timeout}s. Groq API key may be missing or overloaded. Try again."
        return {
                "response": msg,
                "final_response": msg,
                "n_pii_redacted": 0,
                "provider_used": "timeout",
                "latency_ms": timeout * 1000,
                "hitl_required": False,
                "risk_score": 0.0,
                "memory_hits": 0,
                "intent": "ERROR",
                "thread_id": thread_id
            }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("\nBuilding PHANTOM LangGraph...")
    g = build_graph()
    print("\n[OK] Graph compiled successfully.\n")
    print("Node -> Edge wiring:")
    g.get_graph().print_ascii()
    print("\nUse phantom_app.py to run queries.")
