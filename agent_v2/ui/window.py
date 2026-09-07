"""
PhantomAgent2Window — PyQt6 glassmorphism overlay for Phantom 2.0.

The distinguishing feature is the live privacy strip: the user watches each
pipeline stage light up as their data is screened, redacted and surrogated
before anything leaves the machine.
"""
from __future__ import annotations

import os
import sys
import time

from PyQt6.QtCore import Qt, QThread, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGraphicsDropShadowEffect, QLayout, QSizePolicy,
)

_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
from utils.window_settings import WindowSettings  # noqa: E402

ACCENT = "#7c3aed"
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "settings.json",
)
STAGES = ["Sentinel", "Redact", "Surrogate", "Cloud", "Restore"]

STATE_COLORS = {
    "idle": "#4b5563",       # grey
    "running": "#f59e0b",    # yellow (pulsed)
    "done": "#22c55e",       # green
    "error": "#ef4444",      # red
    "blocked": "#ef4444",
    "skipped": "#374151",
}


class PhantomPipelineWorker(QThread):
    """Runs the 6-stage pipeline off the GUI thread."""

    stage_complete = pyqtSignal(str, str, str)   # stage, status, detail
    finished_ok = pyqtSignal(object)             # PipelineResult
    failed = pyqtSignal(str)

    def __init__(self, pipeline, text: str, parent=None):
        super().__init__(parent)
        self._pipeline = pipeline
        self._text = text

    def run(self) -> None:
        try:
            result = self._pipeline.run(
                self._text,
                on_stage=lambda s, st, d: self.stage_complete.emit(s, st, d),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class PrivacyStrip(QWidget):
    """[ node ] -> [ node ] -> ... with per-node state colouring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._states: dict[str, str] = {s: "idle" for s in STAGES}
        self._pulse_on = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        for i, stage in enumerate(STAGES):
            lbl = QLabel(f"◉ {stage}")
            lbl.setStyleSheet(self._style("idle"))
            self._labels[stage] = lbl
            row.addWidget(lbl)
            if i < len(STAGES) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #374151; font-size: 11px; background: transparent; border: none;")
                row.addWidget(arrow)
        row.addStretch()

        self._pulse = QTimer(self)
        self._pulse.setInterval(400)
        self._pulse.timeout.connect(self._tick)

    @staticmethod
    def _style(state: str, dim: bool = False) -> str:
        color = STATE_COLORS.get(state, STATE_COLORS["idle"])
        opacity = "0.45" if dim else "1.0"
        return (f"color: {color}; font-size: 11px; font-weight: 500; "
                f"background: transparent; border: none; opacity: {opacity};")

    def _tick(self) -> None:
        self._pulse_on = not self._pulse_on
        for stage, state in self._states.items():
            if state == "running":
                self._labels[stage].setStyleSheet(self._style("running", dim=self._pulse_on))

    def reset(self) -> None:
        for stage in STAGES:
            self._states[stage] = "idle"
            self._labels[stage].setStyleSheet(self._style("idle"))
        self._pulse.stop()

    def set_state(self, stage: str, state: str) -> None:
        if stage not in self._states:
            return
        self._states[stage] = state
        self._labels[stage].setStyleSheet(self._style(state))
        if any(s == "running" for s in self._states.values()):
            if not self._pulse.isActive():
                self._pulse.start()
        else:
            self._pulse.stop()


class PhantomAgent2Window(QWidget):
    WIDTH = 720

    def __init__(self, pipeline):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pipeline = pipeline
        self._worker: PhantomPipelineWorker | None = None
        self._busy = False
        self._typewriter_gen = 0
        self._report_open = False
        self._t_start = 0.0

        self._settings = WindowSettings(SETTINGS_PATH)
        self._pinned = bool(self._settings.get("pinned", False))

        self._build_ui()
        self._position()
        self._build_focus_watcher()

    def _build_focus_watcher(self) -> None:
        """
        Watch for a second launch of Agent 2.0 asking us to surface.

        Same mechanism as Agent 1.0 but on its own "Phantom2" lock name, so
        the two agents never contend with or surface each other.
        """
        from utils.instance_lock import InstanceLock

        self._instance_lock = InstanceLock("Phantom2")
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(500)
        self._focus_timer.timeout.connect(self._check_focus_trigger)
        self._focus_timer.start()

    def _check_focus_trigger(self) -> None:
        if self._instance_lock.consume_focus_trigger():
            self.show_window()

    # ── construction ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self._card = QWidget(self)
        self._card.setObjectName("Card")
        self._card.setFixedWidth(self.WIDTH)
        self._card.setStyleSheet("""
            QWidget#Card {
                background: rgba(10, 10, 15, 225);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 24px;
            }
        """)
        outer.addWidget(self._card)

        col = QVBoxLayout(self._card)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(10)

        col.addLayout(self._build_input_row())

        self._strip = PrivacyStrip()
        col.addWidget(self._strip)

        self._summary = QLabel("")
        self._summary.setStyleSheet(
            "color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        col.addWidget(self._summary)

        col.addWidget(self._build_response_area())

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        icon = QLabel("⬡")
        icon.setStyleSheet(f"color: {ACCENT}; font-size: 20px; background: transparent; border: none;")
        row.addWidget(icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask Phantom 2.0 — your data stays private...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: transparent; border: none; color: #f1f5f9;
                font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 16px;
            }
        """)
        self._input.returnPressed.connect(self._submit)
        row.addWidget(self._input, stretch=1)

        self._send = QPushButton("➤")
        self._send.setFixedSize(30, 30)
        self._send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT}; color: white; border: none;
                           border-radius: 15px; font-size: 13px; }}
            QPushButton:hover {{ background: #8b5cf6; }}
            QPushButton:disabled {{ background: #3f3f46; }}
        """)
        self._send.clicked.connect(self._submit)
        glow = QGraphicsDropShadowEffect(self._send)
        glow.setColor(QColor(124, 58, 237, 160))
        glow.setBlurRadius(16)
        glow.setOffset(0, 0)
        self._send.setGraphicsEffect(glow)
        row.addWidget(self._send)

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.setToolTip("Pin window (Ctrl+P)")
        self._pin_btn.clicked.connect(self._toggle_pin)
        row.addWidget(self._pin_btn)
        self._update_pin_style()

        return row

    def _build_response_area(self) -> QWidget:
        self._results = QWidget()
        self._results.setStyleSheet("background: transparent; border: none;")
        self._results.setMaximumHeight(0)
        lay = QVBoxLayout(self._results)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.addStretch()
        self._badge = QLabel("🔒 PII Protected")
        self._badge.setStyleSheet(
            "color: #4ade80; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none;")
        top.addWidget(self._badge)
        lay.addLayout(top)

        self._response = QTextEdit()
        self._response.setReadOnly(True)
        self._response.setFrameStyle(0)
        self._response.setStyleSheet("""
            QTextEdit { background: transparent; border: none; color: #f1f5f9;
                        font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 15px; }
        """)
        self._response.setFixedHeight(0)
        self._response.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._response)

        self._report_toggle = QPushButton("▸ Privacy Report")
        self._report_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._report_toggle.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #64748b;
                          font-size: 11px; text-align: left; padding: 2px 0; }
            QPushButton:hover { color: #a78bfa; }
        """)
        self._report_toggle.clicked.connect(self._toggle_report)
        lay.addWidget(self._report_toggle)

        self._report = QLabel("")
        self._report.setWordWrap(True)
        self._report.setStyleSheet("""
            QLabel { color: #94a3b8; font-size: 11px; background: rgba(255,255,255,10);
                     border: 1px solid rgba(255,255,255,20); border-radius: 10px; padding: 8px; }
        """)
        self._report.setVisible(False)
        lay.addWidget(self._report)
        return self._results

    def _position(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + (screen.width() - self.WIDTH) // 2,
                  screen.top() + int(screen.height() * 0.22))

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
        False (never auto-hide) while pinned, while the pipeline is running,
        or while the cursor is anywhere over the window — see the identical
        check in ui/phantom_window.py (v1) for why cursor position, not just
        activation state, is what actually distinguishes an in-window
        interaction (copy, scroll, text selection) from a genuine click-away.
        """
        if self._pinned or self._busy:
            return False
        return not self.geometry().contains(QCursor.pos())

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

    # ── show / hide ──────────────────────────────────────────────────────
    def show_window(self) -> None:
        self._position()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._input.setFocus)

    def new_session(self) -> None:
        self._pipeline.new_session()
        self._input.clear()
        self._response.clear()
        self._response.setFixedHeight(0)
        self._summary.setText("")
        self._report.setText("")
        self._report.setVisible(False)
        self._report_open = False
        self._report_toggle.setText("▸ Privacy Report")
        self._strip.reset()
        self._results.setMaximumHeight(0)

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

    # ── pipeline run ─────────────────────────────────────────────────────
    def _submit(self) -> None:
        if self._busy:
            return
        text = self._input.text().strip()
        if not text:
            return

        self._busy = True
        self._input.clear()
        self._input.setEnabled(False)
        self._send.setEnabled(False)
        self._strip.reset()
        self._summary.setText("Running privacy pipeline…")
        self._response.clear()
        self._response.setFixedHeight(0)
        self._results.setMaximumHeight(400)
        self._t_start = time.perf_counter()

        self._worker = PhantomPipelineWorker(self._pipeline, text, parent=self)
        self._worker.stage_complete.connect(self._on_stage)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_stage(self, stage: str, status: str, detail: str) -> None:
        self._strip.set_state(stage, status)

    def _on_done(self, result) -> None:
        self._busy = False
        self._input.setEnabled(True)
        self._send.setEnabled(True)

        elapsed = time.perf_counter() - self._t_start
        if result.blocked:
            self._badge.setText("⛔ Blocked locally")
            self._badge.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 600;"
                                      "background: transparent; border: none;")
            self._summary.setText(f"Blocked at Sentinel · never sent to cloud · {elapsed:.1f}s")
        else:
            self._badge.setText("🔒 PII Protected")
            self._badge.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 600;"
                                      "background: transparent; border: none;")
            self._summary.setText(
                f"🛡 {result.entity_count} entities redacted · "
                f"via {result.provider or '—'} · {elapsed:.1f}s"
            )

        # Privacy report: entity TYPES only. Original values are never rendered
        # here — they exist only in the local surrogate map and in the answer
        # text itself.
        risk = result.sentinel.risk_level if result.sentinel else "—"
        types = ", ".join(sorted(set(result.entity_types))) or "none"
        self._report.setText(
            f"Entities detected: {types}\n"
            f"Surrogates used: {result.surrogate_count}\n"
            f"Sentinel risk: {risk}\n"
            f"Provider: {result.provider or '—'}\n"
            f"Tiers run: {result.tiers_run}  ·  skipped: {result.tiers_skipped}"
        )

        self._show_response(result.restored_response or "(no response)")

    def _on_failed(self, message: str) -> None:
        self._busy = False
        self._input.setEnabled(True)
        self._send.setEnabled(True)
        self._summary.setText("Pipeline error")
        self._show_response(f"Error: {message}")

    # ── response rendering ───────────────────────────────────────────────
    def _show_response(self, text: str) -> None:
        doc = self._response.document().clone()
        doc.setTextWidth(self._response.viewport().width() or (self.WIDTH - 60))
        doc.setPlainText(text)
        self._response.setFixedHeight(max(28, min(int(doc.size().height()) + 8, 260)))
        self._results.setMaximumHeight(500)
        self._typewriter(text)

    def _typewriter(self, text: str) -> None:
        self._typewriter_gen += 1
        gen = self._typewriter_gen
        words = text.split(" ")
        self._response.setPlainText("")
        idx = [0]

        def step():
            if gen != self._typewriter_gen:
                return
            if idx[0] >= len(words):
                return
            cur = self._response.toPlainText()
            self._response.setPlainText((cur + " " + words[idx[0]]).strip())
            idx[0] += 1
            QTimer.singleShot(15, step)

        step()

    def _toggle_report(self) -> None:
        self._report_open = not self._report_open
        self._report.setVisible(self._report_open)
        self._report_toggle.setText(
            ("▾ " if self._report_open else "▸ ") + "Privacy Report")
