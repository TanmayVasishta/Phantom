"""
PHANTOM UI — HITL Modal Widget
An inline widget that slides into the PhantomWindow when a high-risk
action is detected. NOT a separate window.

Signals
-------
approved : user clicked Approve
rejected : user clicked Reject
"""

from __future__ import annotations

from PyQt6.QtCore    import QPropertyAnimation, QEasingCurve, pyqtSignal, Qt, QSize
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame, QSizePolicy)
from PyQt6.QtGui     import QFont, QColor


class HITLModal(QWidget):
    """Slides in from the top of the response area on HITL interrupt."""

    approved = pyqtSignal()
    rejected = pyqtSignal()

    # Fully expanded height in px
    _EXPANDED_H = 160

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HITLModal")
        self._build_ui()
        self._build_animation()
        # Start collapsed / hidden
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QWidget#HITLModal {
                background-color: #1f1f1f;
                border: 1px solid #ef4444;
                border-radius: 12px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # ── Header row ───────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        warn_icon = QLabel("⚠")
        warn_icon.setStyleSheet("color: #f59e0b; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        warn_icon.setFixedWidth(24)

        warn_label = QLabel("High-risk action detected")
        warn_label.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: bold; background: transparent; border: none;")

        header.addWidget(warn_icon)
        header.addWidget(warn_label)
        header.addStretch()
        outer.addLayout(header)

        # ── Detail grid ──────────────────────────────────────────────
        detail_frame = QFrame()
        detail_frame.setStyleSheet("background: transparent; border: none;")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(3)

        self._action_label = QLabel()
        self._action_label.setWordWrap(True)
        self._action_label.setStyleSheet(
            "color: #a1a1aa; font-size: 12px; font-family: 'Segoe UI'; background: transparent; border: none;")

        self._intent_label = QLabel()
        self._intent_label.setStyleSheet(
            "color: #71717a; font-size: 11px; font-family: 'Segoe UI'; background: transparent; border: none;")

        self._risk_label = QLabel()
        self._risk_label.setStyleSheet(
            "font-size: 12px; font-family: 'Segoe UI'; font-weight: bold; background: transparent; border: none;")

        detail_layout.addWidget(self._action_label)
        detail_layout.addWidget(self._intent_label)
        detail_layout.addWidget(self._risk_label)
        outer.addWidget(detail_frame)

        # ── Button row ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self._approve_btn = QPushButton("  Approve  ")
        self._approve_btn.setObjectName("ApproveBtn")
        self._approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._approve_btn.setStyleSheet("""
            QPushButton#ApproveBtn {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QPushButton#ApproveBtn:hover { background-color: #16a34a; }
            QPushButton#ApproveBtn:pressed { background-color: #15803d; }
        """)

        self._reject_btn = QPushButton("  Reject  ")
        self._reject_btn.setObjectName("RejectBtn")
        self._reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reject_btn.setStyleSheet("""
            QPushButton#RejectBtn {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QPushButton#RejectBtn:hover { background-color: #dc2626; }
            QPushButton#RejectBtn:pressed { background-color: #b91c1c; }
        """)

        btn_row.addWidget(self._approve_btn)
        btn_row.addWidget(self._reject_btn)
        outer.addLayout(btn_row)

        # ── Signal wiring ─────────────────────────────────────────────
        self._approve_btn.clicked.connect(self._on_approve)
        self._reject_btn.clicked.connect(self._on_reject)

    def _build_animation(self) -> None:
        self._show_anim = QPropertyAnimation(self, b"maximumHeight")
        self._show_anim.setDuration(180)
        self._show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hide_anim = QPropertyAnimation(self, b"maximumHeight")
        self._hide_anim.setDuration(140)
        self._hide_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._hide_anim.finished.connect(self._on_hide_finished)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_data(self, query: str, intent: str, risk: float) -> None:
        """Populate the modal with data before showing it."""
        action_text = query[:80] + ("…" if len(query) > 80 else "")
        self._action_label.setText(f"Action : {action_text}")
        self._intent_label.setText(f"Intent  : {intent}")

        risk_pct = int(risk * 100)
        if risk >= 0.8:
            risk_color = "#ef4444"
        elif risk >= 0.5:
            risk_color = "#f59e0b"
        else:
            risk_color = "#a1a1aa"
        self._risk_label.setText(f"Risk     : {risk_pct}%")
        self._risk_label.setStyleSheet(
            f"color: {risk_color}; font-size: 12px; font-family: 'Segoe UI'; "
            f"font-weight: bold; background: transparent; border: none;")

        # Disable buttons until slide-in completes
        self._set_buttons_enabled(True)

    def show_animated(self) -> None:
        """Slide the modal into view."""
        self._hide_anim.stop()
        self._show_anim.setStartValue(self.maximumHeight())
        self._show_anim.setEndValue(self._EXPANDED_H)
        self.setMinimumHeight(0)
        self._show_anim.start()

    def hide_animated(self) -> None:
        """Slide the modal out of view."""
        self._show_anim.stop()
        self._hide_anim.setStartValue(self.maximumHeight())
        self._hide_anim.setEndValue(0)
        self._hide_anim.start()

    # ── Internal slots ─────────────────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._approve_btn.setEnabled(enabled)
        self._reject_btn.setEnabled(enabled)

    def _on_approve(self) -> None:
        self._set_buttons_enabled(False)
        self.hide_animated()
        self.approved.emit()

    def _on_reject(self) -> None:
        self._set_buttons_enabled(False)
        self.hide_animated()
        self.rejected.emit()

    def _on_hide_finished(self) -> None:
        self.setMinimumHeight(0)
