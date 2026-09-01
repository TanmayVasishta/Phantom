"""Custom exception hierarchy for Project HELIX."""


class HELIXBaseError(Exception):
    """Base class for all HELIX exceptions."""
    pass


class PIILeakageError(HELIXBaseError):
    """Raised when raw PII is detected in a cloud-bound payload."""
    pass


class SentinelError(HELIXBaseError):
    """Raised when Sentinel Node fails to classify after max retries."""
    pass


class MemoryWriteError(HELIXBaseError):
    """Raised when ChromaDB write-back fails."""
    pass


class RouteError(HELIXBaseError):
    """Raised when task orchestrator cannot determine a valid route."""
    pass


class HITLTimeoutError(HELIXBaseError):
    """Raised when HITL approval times out on a medium-risk action."""
    pass


class CommandBlockedError(HELIXBaseError):
    """Raised when OS middleware detects a blocked command pattern."""
    pass


class GeminiRateLimitError(HELIXBaseError):
    """Raised when Gemini rate limit is exhausted and fallback is unavailable."""
    pass


class OllamaUnavailableError(HELIXBaseError):
    """Raised when Ollama service is not running."""
    pass


class ChromaDBCorruptionError(HELIXBaseError):
    """Raised when ChromaDB data cannot be loaded (possible corruption)."""
    pass
