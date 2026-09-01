import os
import requests
from providers.base import BaseProvider, ProviderError

class OllamaProvider(BaseProvider):
    name = "Ollama"
    
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3:latest")
        self.timeout = 30
        
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        try:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(base_url=self.host, model=self.model, temperature=0.3)
            formatted = [(msg["role"], msg["content"]) for msg in messages]
            response = llm.invoke(formatted)
            content = response.content if hasattr(response, "content") else str(response)
            if not content:
                raise ProviderError("Empty response")
            return content
        except Exception as e:
            raise ProviderError(f"Ollama failure: {e}")

    def health_check(self) -> bool:
        try:
            r = requests.get(self.host, timeout=3)
            return r.status_code == 200
        except Exception:
            return False
