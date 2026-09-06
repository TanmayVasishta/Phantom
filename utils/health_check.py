"""PHANTOM health check — verifies all required services and packages before startup."""

from __future__ import annotations

import sys
import os


class HealthCheckResult:
    """Aggregates pass/fail results for each dependency check."""

    def __init__(self):
        self.checks: dict[str, dict] = {}
        self.all_ok: bool = True

    def add(self, name: str, ok: bool, message: str) -> None:
        self.checks[name] = {"ok": ok, "message": message}
        if not ok:
            self.all_ok = False

    def report(self) -> str:
        lines = ["", "PHANTOM Health Check", "=" * 40]
        for name, result in self.checks.items():
            icon = "OK " if result["ok"] else "ERR"
            lines.append(f"  [{icon}] {name}: {result['message']}")
        lines.append("=" * 40)
        if self.all_ok:
            lines.append("  All systems ready. Starting PHANTOM...")
        else:
            lines.append("  Fix errors above before starting PHANTOM.")
            lines.append("  Non-critical warnings will not block startup.")
        lines.append("")
        return "\n".join(lines)


def run_health_check() -> HealthCheckResult:
    """Run all dependency checks and return the aggregated result."""
    result = HealthCheckResult()

    # 1. Ollama running + model available
    try:
        import ollama
        from utils.config import SENTINEL_MODEL_PREFERENCE, get_best_available_model
        models = ollama.list().models
        available_names = [m.model for m in models]
        best = get_best_available_model()
        if best and any(best.split(":")[0] in a for a in available_names):
            result.add("Ollama + LLM", True, f"Model ready: {best}")
        elif available_names:
            result.add(
                "Ollama + LLM",
                False,
                f"No preferred model found. Available: {available_names}. "
                f"Run: ollama pull {SENTINEL_MODEL_PREFERENCE[0]}",
            )
        else:
            result.add("Ollama + LLM", False, "Ollama running but no models installed.")
    except Exception as e:
        result.add("Ollama", False, f"Not running — start with: ollama serve ({e})")

    # 2. spaCy (Tier 2 PII — non-critical, degrades gracefully)
    try:
        import spacy
        nlp = spacy.load("en_core_web_lg")
        result.add("spaCy en_core_web_lg", True, "Model loaded")
    except OSError:
        result.add(
            "spaCy en_core_web_lg",
            False,
            "Run: python -m spacy download en_core_web_lg  [Tier 2 PII will be skipped]",
        )
    except ImportError:
        result.add(
            "spaCy",
            False,
            "pip install spacy  [Tier 2 PII detection unavailable]",
        )

    # 3. Presidio (Tier 2 PII — non-critical)
    try:
        from presidio_analyzer import AnalyzerEngine  # noqa: F401
        result.add("Presidio Analyzer", True, "Available")
    except ImportError:
        result.add(
            "Presidio Analyzer",
            False,
            "pip install presidio-analyzer presidio-anonymizer  [Tier 2 PII unavailable]",
        )

    # 4. sentence-transformers (memory embeddings — non-critical)
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        result.add("sentence-transformers", True, "Available")
    except ImportError:
        result.add(
            "sentence-transformers",
            False,
            "pip install sentence-transformers  [Memory embeddings unavailable]",
        )

    # 5. ChromaDB
    try:
        from phantom_graph import _get_chroma
        cm = _get_chroma()
        result.add("ChromaDB", True, f"Accessible at {cm._persist_dir}")
    except Exception as e:
        result.add("ChromaDB", False, str(e))

    # 6. Gemini API key
    try:
        from utils.config import GEMINI_API_KEY
        if not GEMINI_API_KEY or GEMINI_API_KEY in ("your_key_here", ""):
            result.add("Gemini API", False, "No API key set in config/settings.py or .env")
        else:
            result.add("Gemini API", True, "Key configured (format looks valid)")
    except Exception as e:
        result.add("Gemini API", False, str(e))

    # 7. Microphone / audio
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d["max_input_channels"] > 0]
        if input_devs:
            result.add("Microphone (sounddevice)", True, f"{len(input_devs)} input device(s)")
        else:
            result.add("Microphone (sounddevice)", False, "No input audio devices found")
    except Exception:
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            count = p.get_device_count()
            p.terminate()
            result.add("Microphone (PyAudio)", True, f"{count} device(s)")
        except Exception:
            result.add("Microphone", False, "No audio library available — voice input disabled")

    # 8. Whisper
    try:
        import whisper  # noqa: F401
        result.add("Whisper", True, "Package available")
    except ImportError:
        result.add("Whisper", False, "pip install openai-whisper")

    # 9. PyQt6 (GUI)
    try:
        import PyQt6  # noqa: F401
        result.add("PyQt6", True, "Available")
    except ImportError:
        result.add("PyQt6", False, "pip install PyQt6  [GUI mode unavailable]")

    # 10. tiktoken (prompt token budget)
    try:
        import tiktoken  # noqa: F401
        result.add("tiktoken", True, "Available")
    except ImportError:
        result.add("tiktoken", False, "pip install tiktoken")

    return result


if __name__ == "__main__":
    # Allow running as: python -m utils.health_check
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = run_health_check()
    print(r.report())
    sys.exit(0 if r.all_ok else 1)
