import os
from typing import List, Dict, Union, Optional, Any

class AnthropicClient:
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("pip install anthropic required for Claude support")

    def answer(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Compatible avec l'interface commune: retourne juste le texte
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        used_model = model or self.model

        message = self.client.messages.create(
            model=used_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            **kwargs
        )
        return message.content[0].text

    def answer_with_meta(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compatible avec l'interface commune: retourne {"text": str, "sources": []}
        """
        text = self.answer(messages, model, temperature, **kwargs)
        return {"text": text, "sources": []}

    def health(self) -> bool:
        """Vérifie si l'API Anthropic est accessible"""
        try:
            # Test simple avec un prompt minimal
            self.answer("Hi", max_tokens=5)
            return True
        except Exception:
            return False