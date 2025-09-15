# Placeholder : brancher l’API officielle si besoin
from .base import BaseLLMClient
from typing import List, Dict

class AnthropicClient(BaseLLMClient):
    def __init__(self, model: str):
        self.model = model
        self.name = f"anthropic:{model}"

def answer(self, messages: List[Dict], temperature: float = 0.2) -> str:
    raise NotImplementedError("Brancher l’API Anthropic ici.")