import os
from providers.base import BaseProvider, ProviderError

class GeminiProvider(BaseProvider):
    name = "Gemini"
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-1.5-flash"
        self.timeout = int(os.getenv("PROVIDER_TIMEOUT", "10"))
        
    def call(self, messages: list[dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise ProviderError("Missing GEMINI_API_KEY")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            
            gemini_msgs = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Gemini format mapping: 'system' -> prepended 'user' message
                if role == "system":
                    gemini_msgs.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    gemini_msgs.append({"role": "model", "parts": [content]})
                else:
                    gemini_msgs.append({"role": "user", "parts": [content]})
            
            # Gemini requires alternating roles, merge adjacent roles
            merged = []
            for m in gemini_msgs:
                if merged and merged[-1]["role"] == m["role"]:
                    merged[-1]["parts"][0] += "\n\n" + m["parts"][0]
                else:
                    merged.append(m)
                    
            response = model.generate_content(merged)
            content = response.text
            if not content:
                raise ProviderError("Empty response")
            return content
        except Exception as e:
            raise ProviderError(f"Gemini failure: {e}")

    def health_check(self) -> bool:
        return bool(self.api_key)
