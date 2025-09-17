import os
from typing import List, Dict, Union, Optional, Any
from openai import OpenAI

class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        base_url = os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url if base_url else None
        )

    def answer(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        web_search: bool = False,
        **kwargs
    ) -> str:
        """
        Compatible avec l'interface commune: retourne juste le texte
        Supporte GPT-5 avec recherche web
        """
        used_model = model or self.model

        # Si c'est GPT-5 et web_search activé, utilise la nouvelle API responses
        if used_model.startswith("gpt-5") and web_search:
            if isinstance(messages, str):
                input_text = messages
            else:
                # Convertit les messages en input text pour l'API responses
                input_text = "\n".join([msg.get("content", "") for msg in messages])

            resp = self.client.responses.create(
                model=used_model,
                input=input_text,
                tools=[{"type": "web_search"}],
                reasoning={"effort": "low"},
                text={"verbosity": "medium"},
                **kwargs
            )
            return resp.output_text or ""

        # Sinon utilise l'API chat standard
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        resp = self.client.chat.completions.create(
            model=used_model,
            messages=messages,
            temperature=temperature,
            **kwargs
        )
        return resp.choices[0].message.content or ""

    def answer_with_meta(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        web_search: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compatible avec l'interface commune: retourne {"text": str, "sources": []}
        """
        text = self.answer(messages, model, temperature, web_search=web_search, **kwargs)
        return {"text": text, "sources": []}

    def health(self) -> bool:
        """Vérifie si l'API OpenAI est accessible"""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False