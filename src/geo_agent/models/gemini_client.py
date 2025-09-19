import os
from typing import List, Dict, Union, Optional, Any

class GeminiClient:
    def __init__(self, model: str = "gemini-1.5-flash"):
        self.model = model
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError("pip install google-generativeai required for Gemini support")

    def answer(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> str:
        """
        Compatible avec l'interface commune: retourne juste le texte
        """
        if isinstance(messages, str):
            prompt = messages
        else:
            # Convert messages format to simple text for Gemini
            prompt = "\n".join([msg.get("content", "") for msg in messages])

        # Use specific model if provided
        if model and model != self.model:
            import google.generativeai as genai
            client = genai.GenerativeModel(model)
        else:
            client = self.client

        # Configure generation
        generation_config = {
            "temperature": temperature,
            **kwargs
        }

        response = client.generate_content(
            prompt,
            generation_config=generation_config
        )
        return response.text or ""

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
        """Vérifie si l'API Gemini est accessible"""
        try:
            # Test simple avec un prompt minimal
            response = self.answer("Hi")
            return len(response) > 0
        except Exception:
            return False