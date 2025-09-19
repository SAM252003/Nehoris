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
        Supporte GPT-5 avec API Responses et Chat Completions
        """
        used_model = model or self.model

        # Pour GPT-5, utilise l'API Responses pour de meilleures performances
        if used_model.startswith("gpt-5"):
            if isinstance(messages, str):
                input_text = messages
            else:
                # Convertit les messages en input text pour l'API responses
                input_text = "\n".join([msg.get("content", "") for msg in messages if msg.get("content")])

            # Map temperature vers reasoning effort
            if temperature <= 0.3:
                effort = "minimal"
            elif temperature <= 0.5:
                effort = "low"
            elif temperature <= 0.8:
                effort = "medium"
            else:
                effort = "high"

            # Map temperature vers text verbosity
            if temperature <= 0.3:
                verbosity = "low"
            elif temperature <= 0.7:
                verbosity = "medium"
            else:
                verbosity = "high"

            try:
                # Prépare les paramètres pour l'API Responses
                resp_params = {
                    "model": used_model,
                    "input": input_text,
                    "reasoning": {"effort": effort},
                    "text": {"verbosity": verbosity},
                }

                # Ajoute web_search si demandé
                if web_search:
                    resp_params["tools"] = [{"type": "web_search"}]

                resp = self.client.responses.create(**resp_params)
                return resp.output_text or ""
            except Exception as e:
                print(f"⚠️ Échec API Responses pour {used_model}, fallback vers Chat Completions: {e}")
                # Fallback vers Chat Completions si l'API Responses échoue
                pass

        # API Chat Completions (standard ou fallback)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # Gestion spéciale pour les modèles o1 (pas de temperature)
        if "o1" in used_model.lower():
            kwargs_filtered = {k: v for k, v in kwargs.items() if k != 'temperature'}
            resp = self.client.chat.completions.create(
                model=used_model,
                messages=messages,
                **kwargs_filtered
            )
        else:
            # Pour les autres modèles, utilise temperature normalement
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