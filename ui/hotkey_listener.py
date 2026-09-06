"""
PHANTOM Global Hotkey — Ctrl+Alt+P
"""
from PyQt6.QtCore import QThread, pyqtSignal


class HotkeyListener(QThread):
    triggered = pyqtSignal()

    def run(self):
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+alt+p', lambda: self.triggered.emit())
            keyboard.wait()
        except Exception as e:
            print(f'[PHANTOM] Hotkey listener error: {e}')
