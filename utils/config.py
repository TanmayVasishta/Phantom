"""HELIX configuration — loads from config/settings.py with .env fallback."""

from __future__ import annotations

import os
import sys

# ── Load from config/settings.py (existing project convention) ──────────────
# The existing project stores config in config/settings.py (gitignored).
# Fall back to environment variables for CI / headless use.

_settings = None

def _load_settings():
    global _settings
    if _settings is not None:
        return _settings

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from config import settings  # noqa: F401
        _settings = settings
    except ImportError:
        _settings = None
    return _settings


def _get(attr: str, default=None):
    """Read from config/settings.py first, then environment variables."""
    s = _load_settings()
    if s is not None and hasattr(s, attr):
        return getattr(s, attr)
    return os.environ.get(attr, default)


# ── API Keys ─────────────────────────────────────────────────────────────────
NVIDIA_API_KEY: str = _get("NVIDIA_API_KEY", "")
GEMINI_API_KEY: str = _get("GEMINI_API_KEY", "")
GROQ_API_KEY: str = _get("GROQ_API_KEY", "")
DEEPSEEK_API_KEY: str = _get("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY: str = _get("OPENROUTER_API_KEY", "")

# ── NVIDIA NIM ────────────────────────────────────────────────────────────────
NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
# Best model for complex reasoning (LLaMA 3.1 70B Nemotron fine-tuned for instructions)
NVIDIA_CLOUD_MODEL: str = _get("NVIDIA_CLOUD_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_HOST: str = _get("OLLAMA_BASE_URL", _get("OLLAMA_HOST", "http://localhost:11434"))

# Model preference order — first available model wins.
# Ordered by: accuracy for intent classification, then speed, then size.
SENTINEL_MODEL_PREFERENCE: list[str] = [
    "llama3.2:3b",       # CLAUDE.md spec default — best balance for Sentinel
    "llama3:latest",     # Installed: llama3 8B — accurate, heavier
    "qwen3.5:2b",        # Installed: fast, good structured output support
    "gemma3:4b",         # Installed: solid fallback
    "phi3.5",            # Microsoft Phi-3.5 Mini — fast if available
    "gemma2:2b",         # Lightweight fallback
    "qwen2.5:3b",        # Alibaba Qwen — good structured tasks
]

OLLAMA_MODEL: str = _get("OLLAMA_MODEL", "llama3.2:3b")


def get_best_available_model() -> str:
    """Return the first model in SENTINEL_MODEL_PREFERENCE that is installed."""
    try:
        import ollama as _ollama
        available = [m.model for m in _ollama.list().models]
        for preferred in SENTINEL_MODEL_PREFERENCE:
            base = preferred.split(":")[0]
            if any(base in a for a in available):
                # Return the actual installed name to avoid tag mismatches
                match = next(a for a in available if base in a)
                return match
    except Exception:
        pass
    # Fall back to whatever is in config
    return OLLAMA_MODEL


# ── ChromaDB ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _make_absolute(path: str) -> str:
    if path.startswith("./"):
        return os.path.join(PROJECT_ROOT, path[2:])
    if not os.path.isabs(path):
        return os.path.join(PROJECT_ROOT, path)
    return path

CHROMA_PERSIST_DIR: str = _make_absolute(_get("CHROMA_DB_PATH", _get("CHROMA_PERSIST_DIR", "./data/chromadb")))
# The helix_* collections these used to default to were created before the code
# passed hnsw:space, so ChromaDB pinned them to l2 permanently. The phantom_*
# collections are cosine. Existing helix_* rows were migrated across, so this is
# a rename plus a metric fix, not a data reset.
SESSION_COLLECTION: str = _get("SESSION_COLLECTION", "phantom_session_memory")
PERSISTENT_COLLECTION: str = _get("PERSISTENT_COLLECTION", "phantom_persistent_memory")
MAX_MEMORY_ENTRIES: int = int(_get("MAX_MEMORY_ENTRIES", "1000"))

# ── Safety Thresholds ─────────────────────────────────────────────────────────
RISK_THRESHOLD_HITL: int = int(_get("RISK_THRESHOLD_HITL", "40"))
CONFIDENCE_THRESHOLD_CLARIFY: float = float(_get("CONFIDENCE_THRESHOLD_CLARIFY", "0.65"))
# 0.65 (the original CLAUDE.md spec value) was calibrated for cosine similarity
# between two natural-language queries. In practice, stored documents are
# LLM-generated 2-3 sentence SUMMARIES (privacy-safe design, see
# chroma_manager.py), which embed with much lower cosine similarity against a
# short follow-up question even when the match is exactly correct. Measured
# empirically: a verbatim-correct recall scored 0.315 against a plain
# question; unrelated entries scored -0.04 and -0.24 (opposite-direction
# vectors). 0.25 admits real matches like the first case while still
# rejecting genuine noise like the other two — the cross-encoder reranker
# downstream (memory/reranker.py) does the real precision filtering on top
# of this coarse recall-oriented cut.
MEMORY_SCORE_THRESHOLD: float = float(_get("MEMORY_SCORE_THRESHOLD", "0.25"))
MEMORY_RECENCY_LAMBDA: float = float(_get("MEMORY_RECENCY_LAMBDA", "0.1"))

# ── Prompting ─────────────────────────────────────────────────────────────────
MAX_PROMPT_TOKENS: int = int(_get("MAX_PROMPT_TOKENS", "2048"))

# ── ASR ───────────────────────────────────────────────────────────────────────
WHISPER_MODEL: str = _get("WHISPER_MODEL", "tiny")

# ── PII Sensitivity ───────────────────────────────────────────────────────────
# "LOW" = Tier 1 (regex only)
# "MEDIUM" = Tier 1 + Tier 2 (Presidio + spaCy)  [default]
# "HIGH" = All three tiers including semantic LLM
PII_SENSITIVITY: str = _get("PII_SENSITIVITY", "MEDIUM")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = _get("LOG_LEVEL", "INFO")

# ── Gemini ────────────────────────────────────────────────────────────────────
# Uses google-genai SDK (not deprecated google-generativeai)
GEMINI_MODEL: str = _get("GEMINI_MODEL", "gemini-1.5-flash")  # CLAUDE.md spec: use flash not pro
GEMINI_TIMEOUT: int = int(_get("GEMINI_TIMEOUT", "10"))

# ── Audit log path ────────────────────────────────────────────────────────────
AUDIT_LOG_PATH: str = _get("AUDIT_LOG_PATH", "./data/helix_audit.jsonl")
