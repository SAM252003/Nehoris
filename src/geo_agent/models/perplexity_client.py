import os, requests
from typing import List, Dict
from .base import BaseLLMClient

class PerplexityClient(BaseLLMClient):
    """Client API Perplexity (web-grounded). Nécessite PPLX_API_KEY.
    Doc: https://docs.perplexity.ai
    """
    def __init__(self, model: str = "sonar"):
        self.model = model
        self.name = f"perplexity:{model}"
        self.base_url = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai")
        self.api_key = os.getenv("PPLX_API_KEY")
        if not self.api_key:
            raise RuntimeError("PPLX_API_KEY manquant dans l'environnement")

    def answer(self, messages: List[Dict], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(temperature),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")