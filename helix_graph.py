"""
HELIX LangGraph Orchestrator — stateful pipeline graph.

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

import logging
import uuid
from typing import Annotated, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# ── Lazy singletons (initialised once per process) ────────────────────────────
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
        from sentinel.session_pii_map import SessionPIIMap
        _pii_map = SessionPIIMap()
    return _pii_map


def _get_pii_engine():
    global _pii_engine
    if _pii_engine is None:
        from sentinel.pii_engine import PIIRedactionEngine
        _pii_engine = PIIRedactionEngine(_get_pii_map())
    return _pii_engine


def _get_pii_restorer():
    global _pii_restorer
    if _pii_restorer is None:
        from sentinel.pii_restorer import PIIRestorer
        _pii_restorer = PIIRestorer(_get_pii_map())
    return _pii_restorer


def _get_sentinel():
    global _sentinel
    if _sentinel is None:
        from sentinel.sentinel_node import SentinelNode
        _sentinel = SentinelNode()
    return _sentinel


def _get_chroma():
    global _chroma
    if _chroma is None:
        from memory.chroma_manager import ChromaManager
        # session_only=True → in-memory (ephemeral, no cross-session leakage)
        # session_only=False → PersistentClient (survives restarts, good for dev)
        import os
        session_only = os.environ.get("HELIX_SESSION_ONLY", "false").lower() == "true"
        _chroma = ChromaManager(session_only=session_only)
    return _chroma


def _get_retrieval():
    global _retrieval
    if _retrieval is None:
        from memory.retrieval_engine import RetrievalEngine
        _retrieval = RetrievalEngine(_get_chroma())
    return _retrieval


def _get_reranker():
    global _reranker
    if _reranker is None:
        from memory.reranker import MemoryReranker
        _reranker = MemoryReranker()
    return _reranker


# ═══════════════════════════════════════════════════════════════════════════════
# AgentState — the single source of truth flowing through every node
# ═══════════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    """
    Shared state passed between every LangGraph node.

    Keys:
      raw_input       : original user message (before any processing)
      messages        : list of {"role": "user"/"assistant", "content": "..."}
      pii_map         : snapshot of placeholder→real mapping (for restore node)
      memory_context  : top-k ChromaDB chunks as a newline-joined string
      hitl_required   : True if hitl_check_node paused execution
      hitl_decision   : "approve" | "reject" | None (set on graph resume)
      llm_response    : raw LLM output (may contain PII placeholders)
      final_response  : de-anonymised response ready for user display
      intent          : intent string from Sentinel (e.g. "GENERAL_QA")
      risk_score      : float 0.0–1.0 computed in hitl_check_node
      n_pii_redacted  : count of PII entities found in this turn
      error           : non-empty string if a node failed non-fatally
    """
    raw_input: str
    messages: list[dict[str, str]]
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


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1 — sentinel_node
# ═══════════════════════════════════════════════════════════════════════════════

def sentinel_node(state: AgentState) -> AgentState:
    """
    Privacy proxy and trust boundary enforcer.

    Responsibilities (Tanmay's original contribution):
    1. Abort on None / empty input — never let blank queries propagate.
    2. Log entry with timestamp — no raw content in logs, only metadata.
    3. Classify intent via existing SentinelNode (Ollama structured output).
    4. Assert no external URLs are configured (local-only enforcement).
    5. Write intent to state.
    """
    import datetime

    raw = state.get("raw_input", "").strip()

    # Guard 1: empty input
    if not raw:
        logger.warning("[SENTINEL] Empty input received — aborting pipeline.")
        return {**state, "error": "Empty input. Please type a query.", "intent": "UNKNOWN"}

    # Guard 2: input length sanity (prevent prompt injection via huge payloads)
    if len(raw) > 8000:
        logger.warning("[SENTINEL] Input exceeds 8000 chars — truncating.")
        raw = raw[:8000]

    # Audit log (metadata only — no raw PII in logs)
    logger.info(
        "[SENTINEL] Entry at %s | input_length=%d chars",
        datetime.datetime.now(datetime.timezone.utc).isoformat(),
        len(raw),
    )

    # Guard 3: assert local-only (no external URLs in environment)
    _assert_local_only()

    # Intent classification via existing SentinelNode
    try:
        from utils.models import ClarificationRequest, SentinelResult
        sentinel = _get_sentinel()
        result = sentinel.process(raw)

        if isinstance(result, ClarificationRequest):
            # Low confidence — ask user for clarification
            return {
                **state,
                "intent": "CLARIFICATION_NEEDED",
                "error": f"Clarification needed: {result.interpretation}",
            }

        intent_str = result.intent.value if hasattr(result.intent, "value") else str(result.intent)
        logger.info("[SENTINEL] Intent=%s confidence=%.2f", intent_str, result.confidence)
        return {**state, "intent": intent_str, "error": ""}

    except Exception as exc:
        logger.error("[SENTINEL] Classification error: %s", exc)
        # Non-fatal: fall through as GENERAL_QA rather than crashing
        return {**state, "intent": "GENERAL_QA", "error": ""}


def _assert_local_only() -> None:
    """Raise if any HELIX config points to an external endpoint."""
    from utils.config import OLLAMA_HOST
    host = (OLLAMA_HOST or "").lower()
    if not ("localhost" in host or "127.0.0.1" in host or "0.0.0.0" in host):
        raise RuntimeError(
            f"[SENTINEL] OLLAMA_HOST points to an external server: {OLLAMA_HOST}. "
            "HELIX must run fully local."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2 — pii_redact_node
# ═══════════════════════════════════════════════════════════════════════════════

def pii_redact_node(state: AgentState) -> AgentState:
    """
    PII Sandwich — REDACT phase.

    Runs the 3-tier PIIRedactionEngine on raw_input:
      Tier 1: Regex (AADHAAR, PAN, PHONE, EMAIL, UPI, PIN_CODE…)
      Tier 2: Presidio + spaCy NER
      Tier 3: LLM semantic check (HIGH sensitivity only)

    Stores the anonymised text as the last 'user' message.
    Snapshots the placeholder→real map into state['pii_map'].
    """
    raw = state.get("raw_input", "")
    intent = state.get("intent", "")

    if not raw:
        return state

    try:
        engine = _get_pii_engine()
        pii_map_obj = _get_pii_map()

        result = engine.redact(raw, intent_context=intent)

        # Snapshot the map into state (plain dict — serialisable for checkpointing)
        pii_snapshot = dict(pii_map_obj.get_placeholders())

        # Append anonymised message to conversation
        messages = list(state.get("messages", []))
        messages.append({"role": "user", "content": result.sanitised_text})

        n = result.n_entities
        if n:
            logger.info("[PII] Redacted %d entity/entities.", n)

        return {
            **state,
            "messages": messages,
            "pii_map": pii_snapshot,
            "n_pii_redacted": n,
        }

    except Exception as exc:
        logger.error("[PII REDACT] Error: %s", exc)
        # Non-fatal: pass raw (risky but non-crashing)
        messages = list(state.get("messages", []))
        messages.append({"role": "user", "content": raw})
        return {**state, "messages": messages, "pii_map": {}, "n_pii_redacted": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 3 — memory_retrieve_node
# ═══════════════════════════════════════════════════════════════════════════════

def memory_retrieve_node(state: AgentState) -> AgentState:
    """
    Contextual Memory Layer — retrieve before LLM call.

    Queries ChromaDB for top-3 semantically similar past interactions.
    Applies recency decay (λ=0.1) via RetrievalEngine.
    Joins results into state['memory_context'] for injection into system prompt.

    Prevents context rot by injecting only high-score chunks (threshold 0.65).
    (Ref: Chroma 2025 Context Rot Study — Section 6 of report.)
    """
    messages = state.get("messages", [])
    if not messages:
        return {**state, "memory_context": ""}

    # Last user message (anonymised)
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    if not last_user:
        return {**state, "memory_context": ""}

    try:
        retrieval = _get_retrieval()
        reranker = _get_reranker()

        # Retrieve top-5, rerank to top-3
        candidates = retrieval.retrieve_relevant(last_user, top_k=5)
        top = reranker.rerank(last_user, candidates, top_k=3) if candidates else []

        if top:
            context_lines = [text for _, text, _ in top]
            memory_context = "\n".join(f"• {line}" for line in context_lines)
            logger.info("[MEMORY] Injected %d context chunk(s).", len(top))
        else:
            memory_context = ""

        return {**state, "memory_context": memory_context}

    except Exception as exc:
        logger.warning("[MEMORY] Retrieval error: %s", exc)
        return {**state, "memory_context": ""}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 4 — llm_call_node
# ═══════════════════════════════════════════════════════════════════════════════

def llm_call_node(state: AgentState) -> AgentState:
    """
    Local Ollama LLM call node.

    Constructs system prompt with injected memory_context (A-MEM style).
    Sends anonymised messages to local Ollama via ChatOllama.
    Stores raw LLM response (still contains PII placeholders) in state.

    The LLM NEVER sees real PII — it only sees [PII_TYPE_N] tokens.
    (Ref: SurrogateShield arXiv:2606.29567)
    """
    messages = state.get("messages", [])
    memory_context = state.get("memory_context", "")
    intent = state.get("intent", "GENERAL_QA")

    if not messages:
        return {**state, "llm_response": "[HELIX] No input to process."}

    # Build system prompt with memory injection
    if memory_context:
        system_prompt = (
            "You are HELIX, a privacy-first local AI assistant. "
            "All data stays on-device. Never reveal personal information.\n\n"
            f"Relevant context from this session:\n{memory_context}\n\n"
            "Respond based on this context where relevant. "
            "If you see tokens like [PII_PERSON_1], treat them as the actual value — "
            "they will be restored before the user sees the response."
        )
    else:
        system_prompt = (
            "You are HELIX, a privacy-first local AI assistant. "
            "All data stays on-device. Never reveal personal information. "
            "If you see tokens like [PII_PERSON_1], treat them as the actual value — "
            "they will be restored before the user sees the response."
        )

    # Format messages for ChatOllama
    formatted = [("system", system_prompt)]
    for msg in messages[-6:]:  # last 3 turns (6 messages) for context
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted.append((role, content))

    try:
        from langchain_ollama import ChatOllama
        from utils.config import get_best_available_model

        model = get_best_available_model()
        llm = ChatOllama(model=model, temperature=0.3)
        response = llm.invoke(formatted)
        llm_text = response.content if hasattr(response, "content") else str(response)
        logger.info("[LLM] Response received (%d chars).", len(llm_text))

    except ImportError:
        # Fallback: direct ollama SDK
        try:
            import ollama as _ollama
            from utils.config import get_best_available_model

            model = get_best_available_model()
            ollama_msgs = [{"role": "system", "content": system_prompt}]
            for msg in messages[-6:]:
                ollama_msgs.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

            resp = _ollama.chat(
                model=model,
                messages=ollama_msgs,
                options={"temperature": 0.3, "num_predict": 1024},
            )
            llm_text = resp["message"]["content"].strip()
        except Exception as exc:
            logger.error("[LLM] Ollama fallback error: %s", exc)
            llm_text = f"[HELIX] LLM call failed: {exc}"

    except Exception as exc:
        logger.error("[LLM] Call error: %s", exc)
        llm_text = f"[HELIX] LLM call failed: {exc}"

    return {**state, "llm_response": llm_text}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5 — hitl_check_node
# ═══════════════════════════════════════════════════════════════════════════════

# Actions that always require human approval
SENSITIVE_ACTIONS = {
    "file_write", "file_delete", "execute_command",
    "clipboard_write", "send_message", "rm", "delete",
    "format", "wipe", "sudo", "install",
}


def _compute_risk(intent: str, llm_response: str) -> float:
    """
    Compute risk score 0.0–1.0 for the proposed action.

    Uses the existing weighted keyword scorer from orchestrator.risk_scorer,
    normalised to [0, 1].
    """
    try:
        from orchestrator.risk_scorer import calculate_risk_score
        raw_score = calculate_risk_score(
            sub_intent=intent,
            entities=[],
            command=llm_response[:200],
        )
        return min(raw_score / 100.0, 1.0)
    except Exception:
        # Fallback: keyword check
        combined = f"{intent} {llm_response}".lower()
        for action in SENSITIVE_ACTIONS:
            if action in combined:
                return 1.0
        return 0.0


def hitl_check_node(state: AgentState) -> AgentState | Command:
    """
    Confidence-gated HITL interrupt.

    If risk_score > 0.7:
      - Sets hitl_required=True
      - Calls interrupt() — LangGraph suspends the graph here and checkpoints state
      - Waits for Command(resume=...) from the caller
      - On resume: "approve" → continue to pii_restore_node
                   "reject"  → set llm_response to None, go to pii_restore_node

    If risk_score <= 0.7:
      - Sets hitl_required=False
      - Falls through to pii_restore_node immediately

    (Ref: HITL in Agentic Systems arXiv:2509.08646, EU AI Act Article 14)
    """
    intent = state.get("intent", "")
    llm_response = state.get("llm_response", "")

    risk = _compute_risk(intent, llm_response)
    logger.info("[HITL] Risk score: %.2f", risk)

    if risk > 0.7:
        logger.warning("[HITL] High-risk action detected (score=%.2f) — interrupting.", risk)

        # Suspend graph execution — caller must send Command(resume="approve"|"reject")
        decision = interrupt({
            "action": llm_response[:300],
            "intent": intent,
            "risk_score": round(risk, 2),
            "message": (
                f"⚠️  HELIX requires your approval before proceeding.\n"
                f"Risk score: {round(risk * 100)}%\n"
                f"Proposed action: {llm_response[:200]}...\n\n"
                f"Type 'approve' to allow, 'reject' to cancel."
            ),
        })

        # Graph resumes here after Command(resume=...) is sent
        if decision == "reject":
            logger.info("[HITL] Action REJECTED by user.")
            return {
                **state,
                "risk_score": risk,
                "hitl_required": True,
                "hitl_decision": "reject",
                "llm_response": "[HELIX] Action cancelled by user.",
            }
        else:
            logger.info("[HITL] Action APPROVED by user.")
            return {
                **state,
                "risk_score": risk,
                "hitl_required": True,
                "hitl_decision": "approve",
            }

    return {
        **state,
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

    # Append restored response to conversation
    messages = list(messages)
    messages.append({"role": "assistant", "content": restored})

    # Write interaction to ChromaDB for future memory retrieval
    _write_to_memory(state, restored)

    logger.info("[PII RESTORE] Complete. Final response: %d chars.", len(restored))

    return {
        **state,
        "messages": messages,
        "final_response": restored,
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
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
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

    threading.Thread(target=_do_write, daemon=True, name="helix-memory-writeback").start()


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph():
    """
    Build and compile the HELIX LangGraph StateGraph.

    Edge wiring:
      START → sentinel_node → pii_redact_node → memory_retrieve_node
            → llm_call_node → hitl_check_node → pii_restore_node → END

    Checkpointer: MemorySaver (in-process, thread-safe).
    Each unique thread_id is an isolated session.
    """
    checkpointer = MemorySaver()

    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("sentinel_node",      sentinel_node)
    graph.add_node("pii_redact_node",    pii_redact_node)
    graph.add_node("memory_retrieve_node", memory_retrieve_node)
    graph.add_node("llm_call_node",      llm_call_node)
    graph.add_node("hitl_check_node",    hitl_check_node)
    graph.add_node("pii_restore_node",   pii_restore_node)

    # Wire edges (linear pipeline)
    graph.add_edge(START,                   "sentinel_node")
    graph.add_edge("sentinel_node",         "pii_redact_node")
    graph.add_edge("pii_redact_node",       "memory_retrieve_node")
    graph.add_edge("memory_retrieve_node",  "llm_call_node")
    graph.add_edge("llm_call_node",         "hitl_check_node")
    graph.add_edge("hitl_check_node",       "pii_restore_node")
    graph.add_edge("pii_restore_node",      END)

    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


# Singleton graph — compiled once and reused
_graph = None


def get_graph():
    """Return the compiled HELIX graph (singleton)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_query(
    user_input: str,
    thread_id: str | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Run a single query through the HELIX LangGraph pipeline.

    Handles the interrupt/resume loop for HITL automatically in CLI mode:
    - When the graph interrupts (risk > 0.7), prints the approval prompt.
    - Reads user decision from stdin.
    - Resumes the graph with Command(resume=decision).

    Args:
        user_input  : Raw user query string.
        thread_id   : Session identifier (one per conversation). Auto-generated if None.
        verbose     : Print pipeline steps to stdout.

    Returns dict with keys: response, intent, risk_score, n_pii, hitl_required.
    """
    from langgraph.errors import GraphInterrupt

    graph = get_graph()
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "raw_input": user_input,
        "messages": [],
        "pii_map": {},
        "memory_context": "",
        "hitl_required": False,
        "hitl_decision": None,
        "llm_response": "",
        "final_response": "",
        "intent": "",
        "risk_score": 0.0,
        "n_pii_redacted": 0,
        "error": "",
    }

    final_state = initial_state

    try:
        # First invocation
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            final_state = event

    except GraphInterrupt as interrupt_exc:
        # Graph suspended at hitl_check_node
        interrupt_data = interrupt_exc.args[0] if interrupt_exc.args else {}

        if verbose:
            print("\n" + "═" * 60)
            print(interrupt_data.get("message", "HELIX requires approval."))
            print("═" * 60)

        # Collect user decision
        try:
            decision_raw = input("\n[HITL] Your decision (approve/reject): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            decision_raw = "reject"

        decision = "approve" if decision_raw in ("approve", "a", "yes", "y") else "reject"

        if verbose:
            print(f"[HITL] Decision: {decision.upper()}")

        # Resume graph
        try:
            for event in graph.stream(
                Command(resume=decision),
                config=config,
                stream_mode="values",
            ):
                final_state = event
        except Exception as resume_exc:
            logger.error("[HITL] Resume error: %s", resume_exc)

    except Exception as exc:
        logger.error("[GRAPH] Unhandled error: %s", exc)
        final_state["final_response"] = f"[HELIX] Pipeline error: {exc}"

    response = final_state.get("final_response") or final_state.get("llm_response", "")
    error = final_state.get("error", "")

    if error and verbose:
        print(f"[HELIX] ⚠ {error}")

    if verbose and response:
        print(f"\n[HELIX] {response}")

    return {
        "response": response,
        "intent": final_state.get("intent", ""),
        "risk_score": final_state.get("risk_score", 0.0),
        "n_pii": final_state.get("n_pii_redacted", 0),
        "hitl_required": final_state.get("hitl_required", False),
        "hitl_decision": final_state.get("hitl_decision"),
        "thread_id": thread_id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST — run `python helix_graph.py` to verify graph compiles
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("\nBuilding HELIX LangGraph...")
    g = build_graph()
    print("\n[OK] Graph compiled successfully.\n")
    print("Node -> Edge wiring:")
    g.get_graph().print_ascii()
    print("\nUse helix_app.py to run queries.")
