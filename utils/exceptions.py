"""Custom exception hierarchy for Project PHANTOM."""


class PHANTOMBaseError(Exception):
    """Base class for all PHANTOM exceptions."""
    pass


class PIILeakageError(PHANTOMBaseError):
    """Raised when raw PII is detected in a cloud-bound payload."""
    pass


class SentinelError(PHANTOMBaseError):
    """Raised when Sentinel Node fails to classify after max retries."""
    pass


class MemoryWriteError(PHANTOMBaseError):
    """Raised when ChromaDB write-back fails."""
    pass


class RouteError(PHANTOMBaseError):
    """Raised when task orchestrator cannot determine a valid route."""
    pass


class HITLTimeoutError(PHANTOMBaseError):
    """Raised when HITL approval times out on a medium-risk action."""
    pass


class CommandBlockedError(PHANTOMBaseError):
    """Raised when OS middleware detects a blocked command pattern."""
    pass


class GeminiRateLimitError(PHANTOMBaseError):
    """Raised when Gemini rate limit is exhausted and fallback is unavailable."""
    pass


class OllamaUnavailableError(PHANTOMBaseError):
    """Raised when Ollama service is not running."""
    pass


class ChromaDBCorruptionError(PHANTOMBaseError):
    """Raised when ChromaDB data cannot be loaded (possible corruption)."""
    pass
