"""
Client Ollama minimal et robuste.

Dépendances: `requests`
ENV supportés:
  - OLLAMA_HOST (ex: http://localhost:11434)
  - OLLAMA_TIMEOUT (sec)
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import requests


class OllamaClient:
    def __init__(self, model: str = "llama3.1", host: Optional[str] = None, timeout: Optional[int] = None):
        self.model = model
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.timeout = int(timeout or os.getenv("OLLAMA_TIMEOUT") or 180)

    # ----------------- API publique -----------------
    def answer_with_meta(self, messages: List[Dict[str, str]] | str, temperature: float = 0.1) -> Dict[str, Any]:
        """
        Retourne {"text": str, "sources": []}
        - Essaye d'abord /api/chat (nouvelles versions)
        - Fallback /api/generate (anciennes versions)
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        try:
            text = self._chat(messages, temperature)
            if text:
                return {"text": text, "sources": []}
        except Exception:
            # on tente le fallback
            pass

        # Fallback generate
        prompt = "\n".join([m.get("content", "") for m in messages])
        text = self._generate(prompt, temperature)
        return {"text": text, "sources": []}

    # ----------------- internes -----------------
    def _chat(self, messages: List[Dict[str, str]], temperature: float) -> str:
        url = f"{self.host}/api/chat"
        resp = requests.post(
            url,
            json={"model": self.model, "messages": messages, "options": {"temperature": float(temperature)}, "stream": False},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # formats possibles selon versions
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict):
                return data["message"].get("content", "") or ""
            # certaines versions renvoient une liste d'objets
        if isinstance(data, list) and data:
            msg = data[-1].get("message", {})
            return (msg or {}).get("content", "") or ""
        # fallback si réponse vide
        return ""

    def _generate(self, prompt: str, temperature: float) -> str:
        url = f"{self.host}/api/generate"
        resp = requests.post(
            url,
            json={"model": self.model, "prompt": prompt, "options": {"temperature": float(temperature)}, "stream": False},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # format: {"response": "...", "done": true, ...}
        return data.get("response", "") or ""
