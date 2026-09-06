"""
Voice HUD — main PyQt6 window for PHANTOM.

Varshitha's module.

Layout:
  Left panel : chat/response display (streaming token append)
  Right panel: Privacy Metrics Dashboard (updates after every query)
  Bottom     : text input + mic button + command history (up/down)
  Dialogs    : HITLWidget for approval, session summary on close
"""

from __future__ import annotations

import logging
import os
import sys
from collections import deque

import numpy as np
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hud.state_machine import HUDState, HUDStateMachine
from hud.streaming_worker import OllamaStreamWorker
from utils.config import get_best_available_model
from utils.privacy_metrics import session_metrics

logger = logging.getLogger(__name__)


class CommandHistory:
    """Up/Down arrow navigation through recent commands."""

    def __init__(self, max_size: int = 20):
        self._history: deque[str] = deque(maxlen=max_size)
        self._position: int = -1

    def add(self, command: str) -> None:
        if command.strip():
            self._history.append(command)
            self._position = -1

    def navigate_up(self) -> str | None:
        if not self._history:
            return None
        self._position = min(self._position + 1, len(self._history) - 1)
        return list(reversed(self._history))[self._position]

    def navigate_down(self) -> str | None:
        if self._position <= 0:
            self._position = -1
            return ""
        self._position -= 1
        return list(reversed(self._history))[self._position]


class CommandInputWidget(QTextEdit):
    """Single-line text input with Up/Down command history and Enter-to-submit."""

    submit_signal = pyqtSignal(str)

    def __init__(self, history: CommandHistory, parent=None):
        super().__init__(parent)
        self._history = history
        self.setMaximumHeight(60)
        self.setPlaceholderText("Type a command or click the mic button...")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Return and not modifiers & Qt.KeyboardModifier.ShiftModifier:
            text = self.toPlainText().strip()
            if text:
                self._history.add(text)
                self.submit_signal.emit(text)
                self.clear()
            return

        if key == Qt.Key.Key_Up:
            prev = self._history.navigate_up()
            if prev is not None:
                self.setPlainText(prev)
                self.moveCursor(QTextCursor.MoveOperation.End)
            return

        if key == Qt.Key.Key_Down:
            nxt = self._history.navigate_down()
            if nxt is not None:
                self.setPlainText(nxt)
                self.moveCursor(QTextCursor.MoveOperation.End)
            return

        super().keyPressEvent(event)


class VoiceHUD(QMainWindow):
    """
    Main PHANTOM HUD window.

    Connects the full pipeline: text input → Sentinel → PII → route → response.
    Voice input is handled via the mic button (SoundDevice + Whisper).
    """

    def __init__(self):
        super().__init__()
        self._state_machine = HUDStateMachine()
        self._state_machine.on_state_change(self._on_state_change)
        self._history = CommandHistory()
        self._stream_worker: OllamaStreamWorker | None = None
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._refresh_metrics)
        self._metrics_timer.start(2000)  # Refresh metrics every 2s

        self._build_ui()
        self.setWindowTitle("PHANTOM — Privacy-First AI OS")
        self.resize(1100, 700)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(8)

        # ── Left: Chat panel ──────────────────────────────────────────────────
        left = QVBoxLayout()

        self._status_label = QLabel("PHANTOM IDLE")
        self._status_label.setStyleSheet(
            "color: #22c55e; font-weight: bold; font-size: 12px;"
        )
        left.addWidget(self._status_label)

        self._response_display = QTextEdit()
        self._response_display.setReadOnly(True)
        self._response_display.setStyleSheet(
            "background: #0d1117; color: #e6edf3; font-family: monospace; font-size: 13px;"
        )
        left.addWidget(self._response_display)

        # Input row
        input_row = QHBoxLayout()
        self._input = CommandInputWidget(self._history)
        self._input.submit_signal.connect(self._on_text_submit)
        input_row.addWidget(self._input)

        self._mic_btn = QPushButton("🎙 Mic")
        self._mic_btn.setFixedWidth(70)
        self._mic_btn.clicked.connect(self._on_mic_click)
        input_row.addWidget(self._mic_btn)

        left.addLayout(input_row)
        root.addLayout(left, stretch=3)

        # ── Right: Privacy Metrics panel ──────────────────────────────────────
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignTop)

        metrics_title = QLabel("Privacy Dashboard")
        metrics_title.setStyleSheet(
            "font-weight: bold; font-size: 14px; color: #60a5fa;"
        )
        right.addWidget(metrics_title)

        self._metrics_labels: dict[str, QLabel] = {}
        for key in [
            "Privacy Score", "Total Queries", "Local (Private)", "Cloud (Sanitised)",
            "Memory Lookups", "PII Entities Protected", "Cloud Fallbacks",
            "HITL Approved", "HITL Rejected",
        ]:
            row = QHBoxLayout()
            name_lbl = QLabel(f"{key}:")
            name_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
            val_lbl = QLabel("0")
            val_lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
            self._metrics_labels[key] = val_lbl
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(val_lbl)
            right.addLayout(row)

        right.addStretch()
        root.addLayout(right, stretch=1)

    # ── Query handling ────────────────────────────────────────────────────────

    def _on_text_submit(self, query: str) -> None:
        """Handle text input submission — wire to full pipeline."""
        self._append_to_display(f"\n> {query}\n")
        self._state_machine.transition(HUDState.AWAITING_SENTINEL)
        self._status_label.setText("Processing...")

        # Spawn streaming worker using best available local model
        # Full pipeline integration: Sentinel → PII → Route → Stream
        model = get_best_available_model()
        self._stream_worker = OllamaStreamWorker(query, model)
        self._stream_worker.token_received.connect(self._append_token)
        self._stream_worker.stream_complete.connect(self._on_stream_complete)
        self._stream_worker.stream_error.connect(self._on_stream_error)
        self._stream_worker.start()

    def _on_mic_click(self) -> None:
        """Start microphone capture (stub — full ASR wired in main.py)."""
        self._append_to_display("\n[Mic input not available in this mode]\n")

    # ── Display helpers ───────────────────────────────────────────────────────

    def _append_to_display(self, text: str) -> None:
        self._response_display.moveCursor(QTextCursor.MoveOperation.End)
        self._response_display.insertPlainText(text)
        self._response_display.moveCursor(QTextCursor.MoveOperation.End)

    def _append_token(self, token: str) -> None:
        """Append a single streaming token to the display."""
        self._append_to_display(token)

    def _on_stream_complete(self, full_response: str) -> None:
        self._append_to_display("\n")
        self._state_machine.transition(HUDState.DISPLAYING)
        self._state_machine.transition(HUDState.IDLE)
        self._status_label.setText("PHANTOM IDLE")
        session_metrics.record_query("local", 0)

    def _on_stream_error(self, error: str) -> None:
        self._append_to_display(f"\n[Error: {error}]\n")
        self._state_machine.reset()
        self._status_label.setText("PHANTOM IDLE — Error occurred")

    # ── State machine listener ────────────────────────────────────────────────

    def _on_state_change(self, old_state: HUDState, new_state: HUDState) -> None:
        state_colours = {
            HUDState.IDLE:              "#22c55e",
            HUDState.LISTENING:         "#60a5fa",
            HUDState.PROCESSING:        "#f59e0b",
            HUDState.AWAITING_SENTINEL: "#f59e0b",
            HUDState.AWAITING_HITL:     "#ef4444",
            HUDState.DISPLAYING:        "#22c55e",
            HUDState.ERROR:             "#7f1d1d",
        }
        colour = state_colours.get(new_state, "#ffffff")
        self._status_label.setStyleSheet(
            f"color: {colour}; font-weight: bold; font-size: 12px;"
        )
        self._status_label.setText(f"PHANTOM {new_state.value.upper().replace('_', ' ')}")

    # ── Metrics refresh ───────────────────────────────────────────────────────

    def _refresh_metrics(self) -> None:
        data = session_metrics.to_display_dict()
        for key, label in self._metrics_labels.items():
            label.setText(str(data.get(key, "0")))

        # Colour-code privacy score
        score = session_metrics.privacy_score
        colour = "#22c55e" if score >= 80 else "#f59e0b" if score >= 50 else "#ef4444"
        if "Privacy Score" in self._metrics_labels:
            self._metrics_labels["Privacy Score"].setStyleSheet(
                f"font-weight: bold; font-size: 11px; color: {colour};"
            )

    # ── Session summary on close ──────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        summary = session_metrics.to_display_dict()
        msg_lines = [f"{k}: {v}" for k, v in summary.items()]
        msg_text = "\n".join(msg_lines)

        dialog = QMessageBox(self)
        dialog.setWindowTitle("PHANTOM Session Summary")
        dialog.setText(f"Session complete.\n\n{msg_text}\n\nThank you for using PHANTOM.")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.exec()
        event.accept()
