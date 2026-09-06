"""
PHANTOM CLI — headless pipeline mode for testing without the PyQt6 GUI.

Usage:
  python phantom_cli.py                    # interactive mode
  python phantom_cli.py --query "list my downloads"   # single query
  python phantom_cli.py --skip-health      # skip health check (faster dev loop)
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_query(query: str, verbose: bool = True) -> dict:
    """
    Run a single query through the full PHANTOM pipeline.
    Returns a result dict with keys: query, intent, response, n_pii, route.
    """
    from sentinel.session_pii_map import SessionPIIMap
    from sentinel.pii_engine import PIIRedactionEngine
    from sentinel.pii_restorer import PIIRestorer
    from sentinel.sentinel_node import SentinelNode
    from memory.chroma_manager import ChromaManager
    from memory.retrieval_engine import RetrievalEngine
    from memory.reranker import MemoryReranker
    from memory.reprompting import RepromptingModule
    from memory.conversation_buffer import ConversationBuffer
    from orchestrator.task_orchestrator import TaskOrchestrator
    from utils.models import ClarificationRequest
    from utils.audit_logger import audit

    pii_map = SessionPIIMap()
    sentinel = SentinelNode()
    pii_engine = PIIRedactionEngine(pii_map)
    restorer = PIIRestorer(pii_map)
    chroma = ChromaManager()
    retrieval = RetrievalEngine(chroma)
    reranker = MemoryReranker()
    conv_buffer = ConversationBuffer()
    reprompt = RepromptingModule(retrieval, reranker, conv_buffer)
    orchestrator = TaskOrchestrator()

    if verbose:
        print(f"\n[PHANTOM] Query: {query}")

    # Step 4: Sentinel
    sentinel_result = sentinel.process(query)
    if isinstance(sentinel_result, ClarificationRequest):
        if verbose:
            print(f"[SENTINEL] Low confidence. Did you mean: {sentinel_result.interpretation}?")
        return {
            "query": query,
            "intent": "UNKNOWN",
            "response": f"Clarification needed: {sentinel_result.interpretation}",
            "n_pii": 0,
            "route": "none",
        }

    if verbose:
        print(
            f"[SENTINEL] Intent: {sentinel_result.intent.value} "
            f"(conf: {sentinel_result.confidence:.2f}, sub: {sentinel_result.sub_intent})"
        )

    # Step 5: PII Redaction
    redaction = pii_engine.redact(query, str(sentinel_result.intent.value))
    if verbose and redaction.n_entities:
        print(f"[PII] Redacted {redaction.n_entities} entity/entities.")

    # Step 6–7: Memory retrieval + re-prompting
    enriched = reprompt.build(redaction.sanitised_text, sentinel_result.intent)

    # Step 8: Route
    route = orchestrator.route(sentinel_result, enriched)
    if verbose:
        print(
            f"[ROUTE] -> {route.target.upper()} | "
            f"Risk: {route.risk_score} | HITL: {route.hitl_required}"
        )

    if route.hitl_required:
        if verbose:
            print(f"[HITL] Action requires approval (risk={route.risk_score}). Skipped in CLI mode.")
        return {
            "query": query,
            "intent": sentinel_result.intent.value,
            "response": f"[HITL required — use GUI mode for approval] Risk: {route.risk_score}",
            "n_pii": redaction.n_entities,
            "route": route.target,
        }

    # Step 9: Execute
    response = orchestrator.execute(route, enriched, query)

    # Step 10: PII Restore
    restored, warnings = restorer.restore_and_validate(response)
    if warnings and verbose:
        for w in warnings:
            print(f"[PII WARN] {w}")

    if verbose:
        print(f"[PHANTOM] {restored}")

    audit.log_event(
        "CLI_QUERY_COMPLETE",
        intent=sentinel_result.intent.value,
        route=route.target,
        risk_score=route.risk_score,
        n_pii_redacted=redaction.n_entities,
    )
    conv_buffer.add("user", redaction.sanitised_text, sentinel_result.intent.value)
    conv_buffer.add("assistant", restored[:200])

    return {
        "query": query,
        "intent": sentinel_result.intent.value,
        "response": restored,
        "n_pii": redaction.n_entities,
        "route": route.target,
    }


def interactive_mode() -> None:
    """Run PHANTOM in interactive CLI mode."""
    from utils.privacy_metrics import session_metrics

    print(
        "\n"
        "=" * 50 + "\n"
        "  PHANTOM CLI — Privacy-First AI OS\n"
        "  Type 'exit' to quit | 'stats' for metrics\n"
        "=" * 50
    )

    while True:
        try:
            query = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[PHANTOM] Bye.")
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit", "q"):
            print("[PHANTOM] Shutting down.")
            break

        if query.lower() in ("stats", "audit stats"):
            data = session_metrics.to_display_dict()
            print("\nSession Privacy Metrics:")
            for k, v in data.items():
                print(f"  {k}: {v}")
            continue

        if query.lower() == "audit log":
            from utils.audit_logger import audit
            events = audit.read_recent(10)
            for e in events:
                print(e)
            continue

        run_query(query, verbose=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PHANTOM CLI")
    parser.add_argument("--query", "-q", help="Run a single query")
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip health check (faster dev loop)",
    )
    args = parser.parse_args()

    if not args.skip_health:
        from utils.health_check import run_health_check

        health = run_health_check()
        print(health.report())
        # Non-critical failures (spaCy, Presidio, sentence-transformers) don't block
        critical_failures = {
            k for k, v in health.checks.items()
            if not v["ok"] and k in ("Ollama + LLM", "ChromaDB")
        }
        if critical_failures:
            print(f"Critical services unavailable: {critical_failures}")
            sys.exit(1)

    if args.query:
        run_query(args.query)
    else:
        interactive_mode()
