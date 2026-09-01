import time
import os
from typing import List

from providers.base import BaseProvider, ProviderError
from providers.ollama_p import OllamaProvider
from providers.groq_p import GroqProvider
from providers.openrouter_p import OpenRouterProvider
from providers.deepseek_p import DeepSeekProvider
from providers.xai_p import XAIProvider
from providers.nvidia_p import NvidiaProvider
from providers.gemini_p import GeminiProvider
from utils.audit_logger import audit

class AllProvidersFailedError(Exception):
    pass

class ProviderRouter:
    def __init__(self):
        # Ordered by priority as requested
        self.providers: List[BaseProvider] = [
            OllamaProvider(),
            GroqProvider(),
            OpenRouterProvider(),
            DeepSeekProvider(),
            XAIProvider(),
            NvidiaProvider(),
            GeminiProvider()
        ]
        self.fallback_enabled = os.getenv("FALLBACK_ENABLED", "true").lower() == "true"
        self.log_usage = os.getenv("LOG_PROVIDER_USAGE", "true").lower() == "true"
        
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        for i, provider in enumerate(self.providers):
            start = time.time()
            try:
                # Pre-flight check: if no API key is configured (and it's not Ollama), skip it
                if not provider.health_check() and provider.name != "Ollama":
                    continue
                
                response = provider.call(messages, **kwargs)
                latency = int((time.time() - start) * 1000)
                
                if response:
                    fallback_triggered = (i > 0)
                    if self.log_usage:
                        audit.log_event(
                            "LLM_CALL",
                            provider=provider.name,
                            model=provider.model,
                            status="success",
                            fallback_triggered=fallback_triggered,
                            latency_ms=latency
                        )
                    return response
            except ProviderError as e:
                latency = int((time.time() - start) * 1000)
                if self.log_usage:
                    audit.log_event(
                        "LLM_CALL",
                        provider=provider.name,
                        model=provider.model,
                        status="failed",
                        error_type=str(e),
                        fallback_triggered=True,
                        latency_ms=latency
                    )
                
                if not self.fallback_enabled:
                    raise e
                    
                continue # Fall over to the next provider
        
        raise AllProvidersFailedError("No provider responded.")

    def run_health_checks(self):
        results = []
        for p in self.providers:
            start = time.time()
            is_live = False
            try:
                is_live = p.health_check()
            except Exception:
                pass
            latency = int((time.time() - start) * 1000)
            
            results.append({
                "name": p.name,
                "status": "LIVE" if is_live else "DOWN/UNCONFIGURED",
                "latency_ms": latency if is_live else "-"
            })
        return results
