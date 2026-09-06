"""
PHANTOM System Tray Daemon.
"""
from __future__ import annotations
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt


def _make_tray_icon() -> QIcon:
    """Render a simple lock-on-dark icon for the tray."""
    # Try loading assets/icon.png first
    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'assets', 'icon.png'
    )
    if os.path.exists(icon_path):
        return QIcon(icon_path)

    # Fallback: paint text icon
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont('Segoe UI Emoji', 13)
    painter.setFont(font)
    painter.setPen(QColor('#ffffff'))
    painter.drawText(0, 0, 22, 22, Qt.AlignmentFlag.AlignCenter, '\U0001F512')
    painter.end()
    return QIcon(px)


class TrayDaemon:
    def __init__(self, window):
        self._window = window
        self._tray: QSystemTrayIcon | None = None

    def setup(self):
        self._tray = QSystemTrayIcon(_make_tray_icon())
        self._tray.setToolTip('PHANTOM — Privacy-First AI\nCtrl+Space to open')

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1a1a1a;
                color: #e5e5e5;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
                padding: 4px;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QMenu::item:selected { background: #2e2e2e; border-radius: 4px; }
            QMenu::separator { background: #2e2e2e; height: 1px; margin: 4px 0; }
        """)

        open_act = menu.addAction('Open PHANTOM')
        open_act.triggered.connect(self._window.show_window)

        menu.addSeparator()

        new_session_act = menu.addAction('New Session')
        new_session_act.triggered.connect(self._new_session)

        privacy_act = menu.addAction('Privacy Report')
        privacy_act.triggered.connect(self._show_privacy_report)

        menu.addSeparator()

        quit_act = menu.addAction('Quit')
        quit_act.triggered.connect(QApplication.quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._window.show_window()

    def _new_session(self):
        self._window.hide()
        if hasattr(self._window, 'new_session'):
            self._window.new_session()

    def _show_privacy_report(self):
        try:
            from ui.privacy_report import PrivacyReportDialog
            dlg = PrivacyReportDialog()
            dlg.exec()
        except Exception as e:
            QSystemTrayIcon.showMessage(
                self._tray, 'PHANTOM', f'Privacy report unavailable: {e}',
                QSystemTrayIcon.MessageIcon.Information, 3000
            )
