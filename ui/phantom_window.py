"""
PHANTOM Window — frameless QWebEngineView overlay.
Windows 11 Spotlight-style. Always on top.
"""
from __future__ import annotations
import os
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QMainWindow

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtCore import QObject, pyqtSlot as Slot
    HAS_WEBENGINE = True
except ImportError as e:
    HAS_WEBENGINE = False
    print(f"WEBENGINE IMPORT ERROR: {e}")


if HAS_WEBENGINE:
    from PyQt6.QtCore import QObject
    class PhantomBridge(QObject):
        """JS <-> Python bridge exposed as window.phantom"""
        def __init__(self, window):
            super().__init__()
            self._window = window

        @Slot(int)
        def setHeight(self, h: int):
            # Resize window to fit content smoothly, with a solid minimum height
            new_h = min(max(h + 20, 150), 700)
            self._window.setFixedHeight(new_h)


class PhantomWindow(QMainWindow):
    WINDOW_WIDTH = 700
    COLLAPSED_H  = 64

    # Emitted from phantom_ui.py's background wait_for_api() thread once the
    # FastAPI backend is confirmed up. A plain constructor-time bool can't
    # express this because the window is shown *before* that wait completes
    # (blocking window creation on it would delay the whole UI by up to
    # 120s). Qt signals are safe to emit across threads — the connected slot
    # still runs on this window's own (GUI) thread.
    backend_ready_signal = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.backend_ready_signal.connect(self._on_backend_ready)
        try:
            self._build_window()
            self._idle_timer = QTimer(self)
            self._idle_timer.timeout.connect(self.hide)
            self._idle_timer.setSingleShot(True)
        except Exception as e:
            print(f"[FATAL] PhantomWindow init error: {e}")

    def notify_backend_ready(self) -> None:
        """Thread-safe: call from any thread once /health has confirmed up."""
        self.backend_ready_signal.emit()

    def _on_backend_ready(self) -> None:
        """Runs on the GUI thread. Gives the frontend's /health poll (Fix 1)
        a head start instead of waiting out its own 2s cadence."""
        if HAS_WEBENGINE:
            self._browser.page().runJavaScript(
                "if (typeof __phantomBackendReadyHint === 'function') "
                "{ __phantomBackendReadyHint(); }"
            )

    def _build_window(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.setFixedHeight(self.COLLAPSED_H)
        self._position_window()

        if HAS_WEBENGINE:
            self._browser = QWebEngineView(self)
            self._browser.setContextMenuPolicy(
                Qt.ContextMenuPolicy.NoContextMenu
            )

            # Register bridge
            self._channel = QWebChannel()
            self._bridge  = PhantomBridge(self)
            self._channel.registerObject('phantom', self._bridge)
            self._browser.page().setWebChannel(self._channel)

            # Transparent BG so border-radius shows
            self._browser.page().setBackgroundColor(
                QColor(Qt.GlobalColor.transparent)
            )

            # Security
            settings = self._browser.settings()
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
            )

            html_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'frontend', 'index.html'
            )
            self._browser.load(QUrl.fromLocalFile(html_path))
            self.setCentralWidget(self._browser)
        else:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel(
                'Install PyQt6-WebEngine:\npip install PyQt6-WebEngine', self
            )
            lbl.setStyleSheet('color:white;padding:20px;font-size:14px;')
            self.setCentralWidget(lbl)

    def _position_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.WINDOW_WIDTH) // 2
        y = int(screen.height() * 0.28)
        self.move(screen.left() + x, screen.top() + y)

    def _check_idle(self):
        # Auto-hide disabled to prevent accidental disappearance
        pass

    def show_window(self):
        self._position_window()
        self.show()
        self.raise_()
        self.activateWindow()
        self._idle_timer.start(90_000)  # 90s auto-hide
        if HAS_WEBENGINE:
            # Just focus — the input may still be disabled by the frontend's
            # startup gate (Fix 1) at this point, in which case this is a
            # harmless no-op until __phantomBackendReadyHint() enables it.
            QTimer.singleShot(150, lambda:
                self._browser.page().runJavaScript(
                    "document.getElementById('query-input').focus();"
                )
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self._idle_timer.stop()
        super().keyPressEvent(event)

    def changeEvent(self, event):
        # Reset idle timer on any interaction
        if self._idle_timer.isActive():
            self._idle_timer.start(90_000)
        super().changeEvent(event)
