"""
Streaming Qt workers — token-by-token streaming from Ollama and Gemini.

Varshitha's module. Emits pyqtSignal per token so the HUD appends tokens
without clearing the display between them.

Rule: ALL inter-thread communication goes through pyqtSignal — never directly
update Qt widgets from a worker thread.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class OllamaStreamWorker(QThread):
    """
    Streams tokens from Ollama in a background thread.
    Emits token_received for each chunk, stream_complete when done.
    """

    token_received = pyqtSignal(str)      # one token / chunk
    stream_complete = pyqtSignal(str)     # full assembled response
    stream_error = pyqtSignal(str)        # error message

    def __init__(self, prompt: str, model: str, parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._model = model

    def run(self) -> None:
        full_response = ""
        try:
            import ollama

            for chunk in ollama.generate(
                model=self._model,
                prompt=self._prompt,
                stream=True,
                options={"temperature": 0.3},
            ):
                token = chunk.get("response", "")
                if token:
                    full_response += token
                    self.token_received.emit(token)

            self.stream_complete.emit(full_response)

        except Exception as e:
            logger.error(f"OllamaStreamWorker error: {e}")
            self.stream_error.emit(str(e))
        finally:
            self.quit()


class GeminiStreamWorker(QThread):
    """
    Streams tokens from Gemini Oracle in a background thread.
    Falls back to blocking query if streaming fails.
    """

    token_received = pyqtSignal(str)
    stream_complete = pyqtSignal(str)
    stream_error = pyqtSignal(str)

    def __init__(self, sanitised_prompt: str, parent=None):
        super().__init__(parent)
        self._prompt = sanitised_prompt

    def run(self) -> None:
        full_response = ""
        try:
            from orchestrator.gemini_oracle import GeminiOracle

            oracle = GeminiOracle()
            full_response = oracle.stream_query(
                self._prompt,
                callback=self.token_received.emit,
            )
            self.stream_complete.emit(full_response)

        except Exception as e:
            logger.error(f"GeminiStreamWorker error: {e}")
            self.stream_error.emit(str(e))
        finally:
            self.quit()
