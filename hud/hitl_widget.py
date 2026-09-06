"""
HITL approval dialog widget — PyQt6 QDialog with 4 panels.

Varshitha's module.

Panels:
  1. Proposed action (human-readable)
  2. Risk level (colour-coded badge)
  3. Memory context (relevant past interactions)
  4. Approve / Reject / Modify buttons + countdown timer
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hitl.approval_states import HITLState
from utils.models import HITLDisplayData


class HITLWidget(QDialog):
    """
    Human-in-the-loop approval dialog.

    Caller receives the decision via exec() return code — check .decision
    after the dialog closes.
    """

    def __init__(self, display_data: HITLDisplayData, parent=None):
        super().__init__(parent)
        self._data = display_data
        self._remaining: int = display_data.timeout_seconds or 0
        self._timer: QTimer | None = None
        self.decision: HITLState = HITLState.REJECTED
        self.modified_command: str = ""

        self.setWindowTitle("PHANTOM — Action Approval Required")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self._build_ui()

        if display_data.timeout_seconds:
            self._start_countdown()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Panel 1: Proposed action ──────────────────────────────────────────
        action_label = QLabel("Proposed Action:")
        action_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(action_label)

        action_text = QLabel(self._data.proposed_action)
        action_text.setWordWrap(True)
        action_text.setStyleSheet("padding: 8px; background: #1e1e1e; border-radius: 4px;")
        layout.addWidget(action_text)

        # ── Panel 2: Risk level badge ─────────────────────────────────────────
        risk_row = QHBoxLayout()
        risk_label = QLabel("Risk Level:")
        risk_label.setStyleSheet("font-weight: bold;")
        risk_row.addWidget(risk_label)

        risk_badge = QLabel(
            f"  {self._data.risk_level}  (score: {self._data.risk_score}/100)  "
        )
        risk_badge.setStyleSheet(
            f"background-color: {self._data.risk_color}; color: white; "
            f"font-weight: bold; border-radius: 4px; padding: 4px 8px;"
        )
        risk_row.addWidget(risk_badge)
        risk_row.addStretch()

        if self._data.timeout_seconds:
            self._countdown_label = QLabel(
                f"Auto-reject in: {self._remaining}s"
                if not self._is_auto_approve()
                else f"Auto-approve in: {self._remaining}s"
            )
            self._countdown_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            risk_row.addWidget(self._countdown_label)
        else:
            self._countdown_label = None

        layout.addLayout(risk_row)

        # ── Command preview ───────────────────────────────────────────────────
        if self._data.command_preview:
            cmd_label = QLabel("Command Preview:")
            cmd_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(cmd_label)

            cmd_text = QLabel(self._data.command_preview)
            cmd_text.setStyleSheet(
                "font-family: monospace; background: #0d1117; padding: 6px; border-radius: 4px;"
            )
            cmd_text.setWordWrap(True)
            layout.addWidget(cmd_text)

        # ── Panel 3: Memory context ───────────────────────────────────────────
        if self._data.memory_context:
            mem_label = QLabel("Relevant Past Context:")
            mem_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(mem_label)

            mem_text = QTextEdit()
            mem_text.setReadOnly(True)
            mem_text.setMaximumHeight(120)
            mem_text.setPlainText("\n\n".join(self._data.memory_context))
            layout.addWidget(mem_text)

        # ── Modify command input ──────────────────────────────────────────────
        modify_label = QLabel("Modify command (optional):")
        modify_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
        layout.addWidget(modify_label)

        self._modify_input = QLineEdit()
        self._modify_input.setPlaceholderText(
            self._data.command_preview or "Enter modified command..."
        )
        layout.addWidget(self._modify_input)

        # ── Panel 4: Buttons ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        self._approve_btn = QPushButton("Approve")
        self._approve_btn.setStyleSheet(
            "background: #22c55e; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px;"
        )
        self._approve_btn.clicked.connect(self._on_approve)
        btn_layout.addWidget(self._approve_btn)

        self._modify_btn = QPushButton("Modify & Re-run")
        self._modify_btn.setStyleSheet(
            "background: #f59e0b; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px;"
        )
        self._modify_btn.clicked.connect(self._on_modify)
        btn_layout.addWidget(self._modify_btn)

        self._reject_btn = QPushButton("Reject")
        self._reject_btn.setStyleSheet(
            "background: #ef4444; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px;"
        )
        self._reject_btn.clicked.connect(self._on_reject)
        btn_layout.addWidget(self._reject_btn)

        layout.addLayout(btn_layout)

    def _start_countdown(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._remaining -= 1
        if self._countdown_label:
            label = (
                f"Auto-approve in: {self._remaining}s"
                if self._is_auto_approve()
                else f"Auto-reject in: {self._remaining}s"
            )
            self._countdown_label.setText(label)

        if self._remaining <= 0:
            self._timer.stop()
            if self._is_auto_approve():
                self.decision = HITLState.AUTO_APPROVED
            else:
                self.decision = HITLState.TIMEOUT_REJECTED
            self.accept()

    def _is_auto_approve(self) -> bool:
        return self._data.risk_score < 40

    def _on_approve(self) -> None:
        self.decision = HITLState.APPROVED
        if self._timer:
            self._timer.stop()
        self.accept()

    def _on_reject(self) -> None:
        self.decision = HITLState.REJECTED
        if self._timer:
            self._timer.stop()
        self.reject()

    def _on_modify(self) -> None:
        modified = self._modify_input.text().strip()
        if modified:
            self.decision = HITLState.MODIFIED
            self.modified_command = modified
            if self._timer:
                self._timer.stop()
            self.accept()
