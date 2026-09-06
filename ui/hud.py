"""
PHANTOM — GUI HUD
PyQt6 non-blocking UI with async worker threads.
Search-bar style interface: type a query, press Enter or Send, get a response.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont


# ── Worker Thread — keeps UI non-blocking ──────────────────
class PhantomWorker(QObject):
    """Runs phantom_graph.run_query() in a background thread."""
    finished = pyqtSignal(str, float, str)  # response, risk, intent
    error = pyqtSignal(str)
    token_received = pyqtSignal(str)
    hitl_requested = pyqtSignal(dict)

    def __init__(self, prompt: str, thread_id: str):
        super().__init__()
        self.prompt = prompt
        self.thread_id = thread_id
        import queue
        self.hitl_queue = queue.Queue()

    def run(self):
        try:
            from phantom_graph import run_query
            
            def on_token(token: str):
                self.token_received.emit(token)
                
            def on_hitl(data: dict):
                self.hitl_requested.emit(data)
                return self.hitl_queue.get()
                
            result = run_query(self.prompt, thread_id=self.thread_id, verbose=False, token_callback=on_token, hitl_callback=on_hitl)
            response = result.get("response", "[No response]")
            
            if response.startswith("[PHANTOM] Pipeline error"):
                self.error.emit(response)
                return
                
            risk = result.get("risk_score", 0.0)
            intent = result.get("intent", "")
            self.finished.emit(response, risk, intent)
        except Exception as e:
            self.error.emit(str(e))


# ── Main HUD Window ────────────────────────────────────────
class PhantomHUD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.session_id = str(uuid.uuid4())
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("PHANTOM — Privacy-First AI Assistant")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0f; }
            QWidget { background-color: #0a0a0f; color: #00ff88; font-family: 'Consolas'; }
            QTextEdit { background-color: #0d1117; border: 1px solid #00ff4430;
                        border-radius: 6px; padding: 8px; font-size: 13px; }
            QLineEdit { background-color: #0d1117; border: 1px solid #00ff88;
                        border-radius: 6px; padding: 8px; font-size: 13px; color: #ffffff; }
            QPushButton { background-color: #00ff4420; border: 1px solid #00ff44;
                          border-radius: 6px; padding: 8px 16px; font-size: 13px; }
            QPushButton:hover { background-color: #00ff4440; }
            QPushButton:disabled { border-color: #333; color: #555; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("PHANTOM  —  Privacy-First AI")
        title.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff88; letter-spacing: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status bar
        self.status = QLabel("● ONLINE  |  Local: Ollama  |  Cloud: Hybrid Fallback")
        self.status.setStyleSheet("color: #00ff4480; font-size: 11px;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        # Output display
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("PHANTOM responses appear here...")
        layout.addWidget(self.output)

        # Input row
        input_row = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask PHANTOM anything...")
        self.input_box.returnPressed.connect(self._on_submit)
        input_row.addWidget(self.input_box)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_btn)

        layout.addLayout(input_row)

    def _on_submit(self):
        prompt = self.input_box.text().strip()
        if not prompt:
            return
        self.input_box.clear()
        self._set_busy(True)
        self.output.append(f"\n> {prompt}")
        self.output.append("PHANTOM: ") # Start a new line for Phantom's response
        self._run_in_thread(prompt)

    def _run_in_thread(self, prompt: str):
        self.thread = QThread()
        self.worker = PhantomWorker(prompt, self.session_id)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.token_received.connect(self._on_token)
        self.worker.hitl_requested.connect(self._on_hitl_requested)
        self.worker.finished.connect(self._on_response)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.start()

    def _on_hitl_requested(self, data: dict):
        from PyQt6.QtWidgets import QMessageBox
        msg = data.get("message", "PHANTOM requires approval for a high-risk action.")
        reply = QMessageBox.question(
            self, "HITL Approval Required", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        decision = "approve" if reply == QMessageBox.StandardButton.Yes else "reject"
        self.worker.hitl_queue.put(decision)

    def _on_token(self, token: str):
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.output.setTextCursor(cursor)
        # Force UI update if needed, but Qt usually handles this via events.

    def _on_response(self, text: str, risk: float, intent: str):
        risk_pct = int(risk * 100)
        # We don't append text again since tokens were already streamed.
        self.output.append(f"\n   [intent={intent} | risk={risk_pct}%]\n")
        self._set_busy(False)

    def _on_error(self, err: str):
        self.output.append(f"\n[ERROR] {err}\n")
        self._set_busy(False)

    def _set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.input_box.setEnabled(not busy)
        self.status.setText(
            "● PROCESSING..." if busy
            else "● ONLINE  |  Local: Ollama  |  Cloud: Hybrid Fallback"
        )


def launch_hud():
    app = QApplication(sys.argv)
    window = PhantomHUD()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_hud()
