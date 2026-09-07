"""
PHANTOM Agent Window — native PyQt6 floating overlay.
Windows 11 Spotlight / PowerToys Run style. Frameless, always-on-top, no
taskbar entry, hidden until summoned by hotkey or tray. No web content —
every visual is a real Qt widget so there is no browser runtime involved.
"""
from __future__ import annotations

import os
import uuid

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, QEvent, QUrl,
)
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGraphicsDropShadowEffect, QSizePolicy, QLayout,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from ui.hitl_modal import HITLModal
from ui.worker import PhantomWorker
from utils.window_settings import WindowSettings

ACCENT = "#7c3aed"
HEALTH_URL = "http://127.0.0.1:8747/health"
HEALTH_INTERVAL_MS = 30000
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "phantom_memory", "settings.json",
)


class PhantomAgentWindow(QWidget):
    WIDTH = 680
    COLLAPSED_H = 72
    RESULTS_MAX_H = 330  # results container's animated cap; QTextEdit scrolls past this

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setObjectName("PhantomAgentWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.thread_id = str(uuid.uuid4())
        self._worker: PhantomWorker | None = None
        self._busy = False
        self._typewriter_gen = 0

        self._settings = WindowSettings(SETTINGS_PATH)
        self._pinned = bool(self._settings.get("pinned", False))

        self._build_ui()
        self._build_animation()
        self._position_window()
        self._build_health_check()

    def _build_health_check(self) -> None:
        self._net = QNetworkAccessManager(self)
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(HEALTH_INTERVAL_MS)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start()
        self._check_health()  # immediate first check, not a 30s-late one

    def _check_health(self) -> None:
        reply = self._net.get(QNetworkRequest(QUrl(HEALTH_URL)))
        reply.finished.connect(lambda: self._on_health_reply(reply))

    def _on_health_reply(self, reply) -> None:
        from PyQt6.QtNetwork import QNetworkReply
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        self.set_connected(ok)
        reply.deleteLater()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Frameless top-level widgets don't auto-size to their layout by
        # default; SetFixedSize makes this window track self._card's real
        # size on every change, which is what makes the results-area
        # animation (below) actually resize the *window*, not just an
        # inner widget clipped by a fixed outer frame.
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self._card = QWidget(self)
        self._card.setObjectName("PhantomAgentCard")
        self._card.setFixedWidth(self.WIDTH)
        self._card.setStyleSheet(f"""
            QWidget#PhantomAgentCard {{
                background: rgba(10, 10, 15, 220);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 24px;
            }}
        """)
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        card_layout.addLayout(self._build_bar_row())
        card_layout.addWidget(self._build_results_container())

    def _build_bar_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        icon = QLabel("⬡")
        icon.setStyleSheet(f"color: {ACCENT}; font-size: 20px; background: transparent; border: none;")
        row.addWidget(icon)

        self._input = QLineEdit()
        self._input.setObjectName("AgentInput")
        self._input.setPlaceholderText("Ask Phantom anything...")
        self._input.setStyleSheet(f"""
            QLineEdit#AgentInput {{
                background: transparent;
                border: none;
                color: #f1f5f9;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 16px;
            }}
        """)
        self._input.returnPressed.connect(self._submit)
        row.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(30, 30)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: #8b5cf6; }}
            QPushButton:pressed {{ background: #6d28d9; }}
        """)
        self._send_btn.clicked.connect(self._submit)
        self._send_glow = QGraphicsDropShadowEffect(self._send_btn)
        self._send_glow.setColor(QColor(124, 58, 237, 0))
        self._send_glow.setBlurRadius(18)
        self._send_glow.setOffset(0, 0)
        self._send_btn.setGraphicsEffect(self._send_glow)
        self._send_btn.installEventFilter(self)
        row.addWidget(self._send_btn)

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.setToolTip("Pin window (Ctrl+P)")
        self._pin_btn.clicked.connect(self._toggle_pin)
        row.addWidget(self._pin_btn)
        self._update_pin_style()

        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._set_dot("offline")
        row.addWidget(self._dot)

        return row

    def _build_results_container(self) -> QWidget:
        self._results = QWidget()
        self._results.setObjectName("AgentResults")
        self._results.setMaximumHeight(0)
        self._results.setStyleSheet("QWidget#AgentResults { background: transparent; border: none; }")

        layout = QVBoxLayout(self._results)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self._provider_badge = QLabel("")
        self._provider_badge.setStyleSheet("color: #a78bfa; font-size: 12px; background: transparent; border: none;")
        top_row.addWidget(self._provider_badge)
        top_row.addStretch()
        layout.addLayout(top_row)

        self._response_area = QTextEdit()
        self._response_area.setObjectName("AgentResponse")
        self._response_area.setReadOnly(True)
        self._response_area.setFrameStyle(0)
        self._response_area.setStyleSheet("""
            QTextEdit#AgentResponse {
                background: transparent;
                border: none;
                color: #f1f5f9;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 15px;
            }
        """)
        self._response_area.setMaximumHeight(220)
        self._response_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._response_area)

        self._hitl = HITLModal(self._results)
        self._hitl.approved.connect(lambda: self._resolve_hitl("approve"))
        self._hitl.rejected.connect(lambda: self._resolve_hitl("reject"))
        layout.addWidget(self._hitl)

        return self._results

    def _build_animation(self) -> None:
        self._expand_anim = QPropertyAnimation(self._results, b"maximumHeight")
        self._expand_anim.setDuration(220)
        self._expand_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._collapse_anim = QPropertyAnimation(self._results, b"maximumHeight")
        self._collapse_anim.setDuration(180)
        self._collapse_anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def _position_window(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.left() + (screen.width() - self.WIDTH) // 2
        y = screen.top() + (screen.height() - self.COLLAPSED_H) // 2
        self.move(x, y)

    # ── Status dot ───────────────────────────────────────────────────────

    def _set_dot(self, state: str) -> None:
        color = "#22c55e" if state == "connected" else "#ef4444"
        self._dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self._dot.setToolTip("Connected" if state == "connected" else "Offline")

    def set_connected(self, connected: bool) -> None:
        self._set_dot("connected" if connected else "offline")

    # ── Pin ──────────────────────────────────────────────────────────────

    def _update_pin_style(self) -> None:
        if self._pinned:
            self._pin_btn.setStyleSheet(f"""
                QPushButton {{ background: {ACCENT}; border: none; border-radius: 11px;
                               font-size: 11px; }}
            """)
        else:
            self._pin_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 11px;
                              font-size: 11px; opacity: 0.5; }
                QPushButton:hover { background: rgba(255,255,255,20); }
            """)

    def _toggle_pin(self) -> None:
        self.set_pinned(not self._pinned)

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        self._update_pin_style()
        self._settings.set("pinned", pinned)

    def _should_auto_hide(self) -> bool:
        """
        False (never auto-hide) while pinned, while a query is in flight, or
        while the cursor is anywhere over the window — the last case is what
        keeps clicking the copy button, selecting response text, or
        scrolling from dismissing the window: none of those move OS focus
        away, but a transient native popup (e.g. a right-click context menu)
        can, and this is what tells that apart from a genuine click-away.
        """
        if self._pinned or self._busy:
            return False
        return not self.geometry().contains(QCursor.pos())

    # ── Show / hide ──────────────────────────────────────────────────────

    def show_window(self) -> None:
        self._position_window()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._input.setFocus)

    def hide_window(self) -> None:
        self.hide()

    def toggle_or_show(self) -> None:
        """Hotkey entry point: show if hidden, focus if pinned, else hide."""
        if not self.isVisible():
            self.show_window()
        elif self._pinned:
            QTimer.singleShot(0, self._input.setFocus)
        else:
            self.hide_window()

    def new_session(self) -> None:
        """Start a fresh conversation thread — clears the response area."""
        self.thread_id = str(uuid.uuid4())
        self._input.clear()
        self._response_area.clear()
        self._response_area.setFixedHeight(0)
        self._provider_badge.setText("")
        self._collapse_results()

    # ── Results area open/close ──────────────────────────────────────────

    def _open_results(self) -> None:
        self._collapse_anim.stop()
        self._expand_anim.setStartValue(self._results.maximumHeight())
        self._expand_anim.setEndValue(self.RESULTS_MAX_H)
        self._expand_anim.start()

    def _collapse_results(self) -> None:
        self._expand_anim.stop()
        self._hitl.hide_animated()
        self._collapse_anim.setStartValue(self._results.maximumHeight())
        self._collapse_anim.setEndValue(0)
        self._collapse_anim.start()

    # ── Query submission ─────────────────────────────────────────────────

    def _submit(self) -> None:
        if self._busy:
            return
        query = self._input.text().strip()
        if not query:
            return

        self._busy = True
        self._input.clear()
        self._input.setEnabled(False)
        self._input.setPlaceholderText("Thinking…")
        self._send_btn.setEnabled(False)

        self._worker = PhantomWorker(query, self.thread_id, parent=self)
        self._worker.response_ready.connect(self._on_response)
        self._worker.hitl_required.connect(lambda payload: self._on_hitl(payload, query))
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _resolve_hitl(self, decision: str) -> None:
        if self._worker is not None:
            self._worker.set_hitl_decision(decision)

    def _on_response(self, result: dict) -> None:
        self._busy = False
        self._input.setEnabled(True)
        self._input.setPlaceholderText("Ask Phantom anything...")
        self._send_btn.setEnabled(True)
        self._hitl.hide_animated()

        provider = result.get("provider_used") or ""
        if provider and provider != "—":
            self._provider_badge.setText(f"via {provider[:1].upper()}{provider[1:]}")
        else:
            self._provider_badge.setText("")

        text = result.get("final_response") or "Done."
        self._size_response_area(text)
        self._open_results()
        self._typewriter_reveal(text)

    def _on_hitl(self, payload: dict, original_query: str) -> None:
        action = payload.get("action") or payload.get("raw_input") or original_query
        intent = payload.get("intent", "")
        risk = payload.get("risk_score", 0.0)

        # HITLModal (160px) needs the results container's full budget to
        # itself — leaving the response text area at its normal cap would
        # let the two compete for space and clip the approve/reject
        # buttons, so it's hidden for the duration of the approval.
        # setFixedHeight(0), not setMaximumHeight(0): _size_response_area()
        # sets both min AND max height on every real response, and a bare
        # maximumHeight(0) here would conflict with a leftover minimumHeight
        # from the previous response, leaving this taller than intended.
        self._response_area.clear()
        self._response_area.setFixedHeight(0)
        self._provider_badge.setText("")
        self._hitl.set_data(action, intent, risk)
        self._open_results()
        QTimer.singleShot(0, self._hitl.show_animated)
        # Input stays disabled — _busy stays True — until approve/reject
        # resolves and the worker either interrupts again or emits
        # response_ready.

    def _on_error(self, message: str) -> None:
        self._busy = False
        self._input.setEnabled(True)
        self._input.setPlaceholderText("Ask Phantom anything...")
        self._send_btn.setEnabled(True)
        self._provider_badge.setText("")
        self._hitl.hide_animated()
        error_text = f"Phantom is offline: {message}"
        self._size_response_area(error_text)
        self._open_results()
        self._response_area.setHtml(f'<span style="color:#f87171">{error_text}</span>')

    def _size_response_area(self, text: str) -> None:
        """
        QTextEdit's sizeHint() doesn't grow with content, so the SetFixedSize
        window-autosize (see _build_ui) never sees the extra height a long
        response needs. Measuring the laid-out document height directly and
        setting a matching fixed height (capped at the 220px scroll point)
        is what actually makes the window expand to fit real responses.
        """
        doc = self._response_area.document().clone()
        width = self._response_area.viewport().width() or (self.WIDTH - 60)
        doc.setTextWidth(width)
        doc.setPlainText(text)
        needed = int(doc.size().height()) + 8
        self._response_area.setFixedHeight(max(24, min(needed, 220)))

    # ── Typewriter reveal (15ms/word), then swap in rich formatting ───────

    def _typewriter_reveal(self, text: str) -> None:
        self._typewriter_gen += 1
        gen = self._typewriter_gen
        words = text.split(" ")
        self._response_area.setPlainText("")

        def step(i=[0]):
            if gen != self._typewriter_gen:
                return
            if i[0] >= len(words):
                self._response_area.setHtml(self._render_markdown(text))
                return
            cursor_text = self._response_area.toPlainText()
            sep = " " if cursor_text else ""
            self._response_area.setPlainText(cursor_text + sep + words[i[0]])
            i[0] += 1
            QTimer.singleShot(15, step)

        step()

    @staticmethod
    def _render_markdown(text: str) -> str:
        import html
        escaped = html.escape(text)
        escaped = escaped.replace("\n", "<br>")
        # Bold only — this project's responses rarely use more than **bold**
        # and the odd bullet; a full markdown renderer is not worth it here.
        import re
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
        return escaped

    # ── Dismiss: Escape always; losing OS focus only if the cursor is
    # actually outside the window, nothing is running, and it isn't pinned ──

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._input.clear()
            self.hide_window()
            return
        if (event.key() == Qt.Key.Key_P
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self._toggle_pin()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if self._should_auto_hide():
                self.hide_window()
        super().changeEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._send_btn:
            if event.type() == QEvent.Type.Enter:
                self._send_glow.setColor(QColor(124, 58, 237, 200))
            elif event.type() == QEvent.Type.Leave:
                self._send_glow.setColor(QColor(124, 58, 237, 0))
        return super().eventFilter(obj, event)
