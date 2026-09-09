"""
Long-press drag handle for the two floating overlays, plus the saved-position
helpers that go with it.

Shared rather than inlined per window (the spec asked for inline "to keep it
simple", but the same ~90 lines of press/timer/clamp state would then exist
twice and drift the moment one agent's drag behaviour is tweaked — the same
reasoning window_settings.py already documents for its own existence).

Drag is deliberately gated behind this one small widget and a 300ms hold:
making the whole bar draggable would fight the input field for the click,
and an instant drag-on-press would make a mis-aimed click nudge the window.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtWidgets import QApplication, QLabel

LONG_PRESS_MS = 300
SNAP_MARGIN_PX = 20

_BASE = "background: transparent; border: none; font-size: 15px;"
NORMAL_STYLE = f"color: rgba(255,255,255,0.2); {_BASE}"
HOVER_STYLE = f"color: rgba(255,255,255,0.4); {_BASE}"
ACTIVE_STYLE = (
    "color: rgba(124,58,237,0.6); background: rgba(124,58,237,0.15); "
    "border: none; border-radius: 6px; font-size: 15px;"
)


def clamp_to_screen(window, pos: QPoint, snap: bool = False) -> QPoint:
    """
    Keep `pos` on the primary screen's usable area.

    Uses left()/top()/width()/height() of availableGeometry rather than
    assuming the screen starts at (0, 0): a taskbar on the left or top, or a
    non-primary arrangement, offsets that origin, and clamping against a
    hardcoded 0 would let the window sit under the taskbar.

    `snap` is on only while dragging — a saved position restored at startup
    should land exactly where it was left, not get pulled to an edge it
    happened to be sitting near.
    """
    screen = QApplication.primaryScreen().availableGeometry()
    # sizeHint(), not size(): before the first show() a QWidget still reports
    # Qt's 640x480 placeholder, and both overlays lay out under
    # QLayout.SizeConstraint.SetFixedSize, which pins the window to its
    # sizeHint anyway. Measured on this window: 640x480 vs a true 680x84
    # before show, 680x84 for both after — so taking size() (or the max of
    # the two) clamps against a box ~400px taller than the window really is,
    # and dragging hits an invisible floor well above the screen bottom.
    hint = window.sizeHint()
    w = hint.width() if hint.width() > 0 else window.width()
    h = hint.height() if hint.height() > 0 else window.height()

    max_x = screen.left() + max(0, screen.width() - w)
    max_y = screen.top() + max(0, screen.height() - h)
    x = max(screen.left(), min(pos.x(), max_x))
    y = max(screen.top(), min(pos.y(), max_y))

    if snap:
        if x - screen.left() < SNAP_MARGIN_PX:
            x = screen.left()
        elif max_x - x < SNAP_MARGIN_PX:
            x = max_x
        if y - screen.top() < SNAP_MARGIN_PX:
            y = screen.top()
        elif max_y - y < SNAP_MARGIN_PX:
            y = max_y

    return QPoint(x, y)


def apply_saved_position(window, settings) -> bool:
    """
    Move `window` to its saved position. Returns False if none is stored, so
    the caller can fall back to its own default placement.

    Re-validated against the current screen every time rather than trusted
    blind: the position may have been saved on a larger monitor, or with a
    second display attached that is no longer there, and a window restored
    off-screen is indistinguishable from a window that failed to open.
    """
    saved = settings.get("position")
    if not isinstance(saved, dict) or "x" not in saved or "y" not in saved:
        return False
    try:
        target = QPoint(int(saved["x"]), int(saved["y"]))
    except (TypeError, ValueError):
        return False
    window.move(clamp_to_screen(window, target, snap=False))
    return True


class DragHandle(QLabel):
    """
    ⠿ grip. Hold for 300ms to pick the window up; release to drop and save.

    Owns no window state of its own beyond the in-flight drag: position is
    written straight to the same WindowSettings file the pin toggle uses, so
    both agents keep their own placement without extra plumbing.
    """

    def __init__(self, window, settings, parent=None):
        super().__init__("⠿", parent)
        self.setObjectName("drag_handle")
        self.setFixedSize(20, 40)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip("Hold to move")
        self.setStyleSheet(NORMAL_STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._window = window
        self._settings = settings
        self._hovered = False
        self._dragging = False
        self._drag_press_pos = QPoint()
        self._drag_start_global = QPoint()
        self._window_start_pos = QPoint()

        self._drag_timer = QTimer(self)
        self._drag_timer.setSingleShot(True)
        self._drag_timer.setInterval(LONG_PRESS_MS)
        self._drag_timer.timeout.connect(self._activate_drag)

    # ── state ────────────────────────────────────────────────────────────

    @property
    def dragging(self) -> bool:
        return self._dragging

    # ── hover ────────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._hovered = True
        if not self._dragging:
            self.setStyleSheet(HOVER_STYLE)
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if not self._dragging:
            self.setStyleSheet(NORMAL_STYLE)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    # ── press / hold / drag / release ────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._drag_press_pos = event.globalPosition().toPoint()
        self._drag_timer.start()
        event.accept()

    def _activate_drag(self) -> None:
        self._dragging = True
        # Anchor on where the press landed, not on wherever the cursor is by
        # the time the 300ms elapses — otherwise any drift during the hold
        # becomes an instant jump the moment drag mode turns on.
        self._drag_start_global = self._drag_press_pos
        self._window_start_pos = self._window.pos()
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet(ACTIVE_STYLE)

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._drag_start_global
        self._window.move(
            clamp_to_screen(self._window, self._window_start_pos + delta, snap=True)
        )
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_timer.stop()
        if self._dragging:
            self._dragging = False
            self._save_position()
            self.setCursor(
                Qt.CursorShape.SizeAllCursor if self._hovered
                else Qt.CursorShape.ArrowCursor
            )
            self.setStyleSheet(HOVER_STYLE if self._hovered else NORMAL_STYLE)
        event.accept()

    def _save_position(self) -> None:
        pos = self._window.pos()
        self._settings.set("position", {"x": pos.x(), "y": pos.y()})
