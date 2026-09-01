"""
HELIX App — LangGraph-backed CLI entry point.

Replaces helix_cli.py for the new architecture.
Uses helix_graph.run_query() which drives the full LangGraph pipeline:
  Sentinel → PII Redact → Memory Retrieve → LLM Call → HITL Check → PII Restore

HITL interrupt is handled inline: if the graph suspends, the user types
'approve' or 'reject' and the graph resumes via Command(resume=...).

Usage:
    python helix_app.py                            # interactive session
    python helix_app.py --query "What is my PAN?"  # single query
    python helix_app.py --session-only             # force in-memory ChromaDB
    python helix_app.py --skip-health              # skip health check
    python helix_app.py --graph                    # print graph ASCII and exit
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


# ── Entry points ──────────────────────────────────────────────────────────────

def run_single_query(query: str, thread_id: str, verbose: bool = True) -> dict:
    """Run one query through the LangGraph pipeline and return results."""
    from helix_graph import run_query
    return run_query(query, thread_id=thread_id, verbose=verbose)


def interactive_mode(thread_id: str) -> None:
    """
    Interactive session loop.

    A single thread_id is shared across the whole session so that
    LangGraph MemorySaver maintains conversation state across turns.
    """
    from utils.privacy_metrics import session_metrics

    print(
        "\n"
        "+" + "=" * 54 + "+\n"
        "|   HELIX -- Privacy-First Local AI Assistant          |\n"
        "|   All inference stays on-device. No data leaves.   |\n"
        "|   Type 'exit' to quit | 'stats' for metrics        |\n"
        "+" + "=" * 54 + "+"
    )
    print(f"\n  Session ID: {thread_id[:8]}...\n")

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[HELIX] Session ended. Goodbye.")
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit", "q", "bye"):
            print("[HELIX] Shutting down. Goodbye.")
            break

        if query.lower() in ("stats", "metrics"):
            data = session_metrics.to_display_dict()
            print("\nSession Privacy Metrics:")
            for k, v in data.items():
                print(f"   {k}: {v}")
            continue

        if query.lower() == "audit log":
            try:
                from utils.audit_logger import audit
                events = audit.read_recent(10)
                print("\nRecent audit log:")
                for e in events:
                    print(f"   {e}")
            except Exception as e:
                print(f"[HELIX] Audit log unavailable: {e}")
            continue

        if query.lower() == "clear memory":
            try:
                from helix_graph import _get_chroma
                _get_chroma().clear_session_memory()
                print("[HELIX] Session memory cleared.")
            except Exception as e:
                print(f"[HELIX] Could not clear memory: {e}")
            continue

        # Run through LangGraph pipeline
        result = run_single_query(query, thread_id=thread_id, verbose=True)

        n_pii = result.get("n_pii", 0)
        risk = result.get("risk_score", 0.0)
        intent = result.get("intent", "")

        # Privacy status line
        status_parts = [f"intent={intent}"]
        if n_pii:
            status_parts.append(f"🔒 {n_pii} PII token(s) redacted")
        if risk > 0.0:
            status_parts.append(f"risk={int(risk * 100)}%")
        print(f"\n   [{' │ '.join(status_parts)}]\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HELIX — Privacy-First Local AI (LangGraph edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python helix_app.py
  python helix_app.py --query "My Aadhaar is 4567 8901 2345. Help me draft a letter."
  python helix_app.py --session-only --query "What did we discuss last?"
  python helix_app.py --graph
        """,
    )
    parser.add_argument("--query", "-q", help="Run a single query and exit.")
    parser.add_argument(
        "--session-only",
        action="store_true",
        help="Use in-memory ChromaDB (ephemeral — no cross-session persistence).",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip health check (faster dev loop).",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Print the compiled graph ASCII and exit.",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Session thread ID (auto-generated if not provided).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=True,
        help="Verbose output (default: on).",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,  # Suppress INFO spam unless --debug
        format="%(levelname)s [%(name)s]: %(message)s",
    )

    # Session-only mode
    if args.session_only:
        os.environ["HELIX_SESSION_ONLY"] = "true"
        print("[HELIX] Running in session-only mode (in-memory ChromaDB).")

    # Health check
    if not args.skip_health:
        try:
            from utils.health_check import run_health_check
            health = run_health_check()
            print(health.report())
            critical = {"Ollama + LLM", "ChromaDB"}
            failed = {k for k, v in health.checks.items() if not v["ok"] and k in critical}
            if failed:
                print(f"[HELIX] ❌ Critical services unavailable: {failed}")
                print("[HELIX] Fix the above errors and retry.")
                sys.exit(1)
        except Exception as e:
            print(f"[HELIX] Health check skipped: {e}")

    # Print graph and exit
    if args.graph:
        from helix_graph import build_graph
        print("\nBuilding HELIX LangGraph...\n")
        g = build_graph()
        print("[OK] Graph compiled.\n")
        g.get_graph().print_ascii()
        return

    # Thread ID for this session
    thread_id = args.thread_id or str(uuid.uuid4())

    # Single query or interactive
    if args.query:
        run_single_query(args.query, thread_id=thread_id, verbose=args.verbose)
    else:
        interactive_mode(thread_id=thread_id)


if __name__ == "__main__":
    main()
