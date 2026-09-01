from abc import ABC, abstractmethod

class ProviderError(Exception):
    """Exception raised on unrecoverable failure (timeout, network, etc.)"""
    pass

class BaseProvider(ABC):
    name: str
    model: str
    timeout: int
    
    @abstractmethod
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Execute inference call."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if provider is online/accessible."""
        pass
