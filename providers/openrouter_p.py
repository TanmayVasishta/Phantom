import os
from providers.base import BaseProvider, ProviderError

class OpenRouterProvider(BaseProvider):
    name = "OpenRouter"
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = "meta-llama/llama-3-70b-instruct"
        self.timeout = int(os.getenv("PROVIDER_TIMEOUT", "10"))
        
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise ProviderError("Missing OPENROUTER_API_KEY")
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                timeout=self.timeout
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                extra_headers={
                    "HTTP-Referer": "https://phantom-local.ai",
                    "X-Title": "PHANTOM"
                }
            )
            content = response.choices[0].message.content
            if not content:
                raise ProviderError("Empty response")
            return content
        except Exception as e:
            raise ProviderError(f"OpenRouter failure: {e}")

    def health_check(self) -> bool:
        return bool(self.api_key)
