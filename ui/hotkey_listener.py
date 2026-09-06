"""
PHANTOM Global Hotkey — Ctrl+Space
"""
from PyQt6.QtCore import QThread, pyqtSignal


class HotkeyListener(QThread):
    triggered = pyqtSignal()

    def run(self):
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+space', lambda: self.triggered.emit())
            keyboard.wait()
        except Exception as e:
            print(f'[PHANTOM] Hotkey listener error: {e}')
