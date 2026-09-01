import os
from providers.base import BaseProvider, ProviderError

class NvidiaProvider(BaseProvider):
    name = "NVIDIA NIM"
    
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY")
        self.model = "meta/llama3-70b-instruct"
        self.timeout = int(os.getenv("PROVIDER_TIMEOUT", "10"))
        
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise ProviderError("Missing NVIDIA_API_KEY")
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.api_key,
                timeout=self.timeout
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3
            )
            content = response.choices[0].message.content
            if not content:
                raise ProviderError("Empty response")
            return content
        except Exception as e:
            raise ProviderError(f"Nvidia failure: {e}")

    def health_check(self) -> bool:
        return bool(self.api_key)
