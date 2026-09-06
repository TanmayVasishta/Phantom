"""
PHANTOM UI — Worker Thread
Wraps phantom_graph.run_query() in a QThread so the UI never freezes.

HITL architecture:
  run_query() accepts a hitl_callback(interrupt_data) → str.
  We pass a callback that:
    1. Emits hitl_required signal to the UI (non-blocking).
    2. Blocks on a threading.Event waiting for the UI to call
       worker.set_hitl_decision(decision).
    3. Returns the decision string to run_query(), which
       resumes the LangGraph graph via Command(resume=decision).

This way we never need a separate resume_query() function —
the graph stays alive on this thread, waiting for human input.

API note — run_query() actual return keys (different from spec):
  result["response"]     ← display text   (spec said "final_response")
  result["n_pii"]        ← PII count      (spec said "n_pii_redacted")
  result["hitl_required"], result["hitl_decision"], result["intent"],
  result["risk_score"], result["thread_id"] — all match spec.
  provider_used / memory_hits / latency_ms are NOT in the backend dict;
  latency_ms is measured here; others show "—".
"""

from __future__ import annotations

import time
import threading
import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class PhantomWorker(QThread):
    """
    Signals
    -------
    response_ready  : emitted when run_query() completes normally.
                      Payload is a normalised dict (see _normalise()).
    hitl_required   : emitted when the graph interrupts for HITL.
                      Payload is the interrupt_data dict from LangGraph.
    error_occurred  : emitted on any unhandled exception.
    token_received  : emitted for each streaming token chunk.
    """

    response_ready = pyqtSignal(dict)
    hitl_required  = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    token_received = pyqtSignal(str)

    def __init__(self, query: str, thread_id: str, parent=None):
        super().__init__(parent)
        self.query     = query
        self.thread_id = thread_id

        # HITL synchronisation
        self._hitl_event    = threading.Event()
        self._hitl_decision = "reject"   # safe default

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_hitl_decision(self, decision: str) -> None:
        """
        Called by the UI when the user clicks Approve or Reject.
        Unblocks the hitl_callback inside run_query().
        """
        self._hitl_decision = decision
        self._hitl_event.set()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _hitl_callback(self, interrupt_data: dict) -> str:
        """
        Passed as hitl_callback to run_query().
        Runs on THIS thread (not the UI thread).
        Emits hitl_required to the UI and then blocks until
        set_hitl_decision() is called from the UI thread.
        """
        logger.info("[Worker] HITL interrupt received, waiting for UI decision.")
        self.hitl_required.emit(interrupt_data)
        # Block this thread (graph is paused here) until UI signals us
        self._hitl_event.wait(timeout=300)   # 5-minute max wait
        self._hitl_event.clear()
        logger.info("[Worker] HITL decision: %s", self._hitl_decision)
        return self._hitl_decision

    def _token_callback(self, token: str) -> None:
        """Streaming token forwarder."""
        if token:
            self.token_received.emit(token)

    @staticmethod
    def _normalise(raw: dict, latency_ms: int) -> dict:
        """
        Normalise the backend return dict to the shape the UI expects.
        Bridges the key-name differences between spec and actual backend.
        """
        return {
            # Spec key          ← actual backend key
            "final_response":   raw.get("response", ""),
            "n_pii_redacted":   raw.get("n_pii", 0),
            "hitl_required":    raw.get("hitl_required", False),
            "hitl_decision":    raw.get("hitl_decision"),
            "intent":           raw.get("intent", ""),
            "risk_score":       raw.get("risk_score", 0.0),
            "provider_used":    raw.get("provider_used", "—"),
            "memory_hits":      raw.get("memory_hits", 0),
            "latency_ms":       latency_ms,
            "thread_id":        raw.get("thread_id", ""),
        }

    def run(self) -> None:
        """QThread entry point — runs in a background thread."""
        t0 = time.perf_counter()
        try:
            from phantom_graph import run_query

            raw = run_query(
                user_input=self.query,
                thread_id=self.thread_id,
                verbose=False,
                token_callback=self._token_callback,
                hitl_callback=self._hitl_callback,
            )

            latency_ms = int((time.perf_counter() - t0) * 1000)
            result = self._normalise(raw, latency_ms)
            self.response_ready.emit(result)

        except Exception as exc:
            logger.exception("[Worker] Unhandled error in run_query")
            self.error_occurred.emit(str(exc))
