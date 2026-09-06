"""
PHANTOM Global Hotkey — Ctrl+Shift+Space

(Ctrl+Space moved to Phantom 2.0 / agent_v2 — the two agents run
simultaneously, so they need distinct hotkeys.)
"""
from PyQt6.QtCore import QThread, pyqtSignal


class HotkeyListener(QThread):
    triggered = pyqtSignal()

    def run(self):
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+shift+space', lambda: self.triggered.emit())
            keyboard.wait()
        except Exception as e:
            print(f'[PHANTOM] Hotkey listener error: {e}')
