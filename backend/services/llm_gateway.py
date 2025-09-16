# services/llm_gateway.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import os

# On réutilise les clients existants (openai / ollama / anthropic / perplexity)
try:
    from src.geo_agent.models.openai_client import OpenAIClient  # type: ignore
except Exception:
    OpenAIClient = None  # type: ignore

try:
    from src.geo_agent.models.ollama_client import OllamaClient  # type: ignore
except Exception:
    OllamaClient = None  # type: ignore

try:
    from src.geo_agent.models.anthropic_client import AnthropicClient  # type: ignore
except Exception:
    AnthropicClient = None  # type: ignore

try:
    from src.geo_agent.models.perplexity_client import PerplexityClient  # type: ignore
except Exception:
    PerplexityClient = None  # type: ignore


Messages = Union[str, List[Dict[str, str]]]


def _to_messages(x: Messages) -> List[Dict[str, str]]:
    if isinstance(x, str):
        return [{"role": "user", "content": x}]
    return x


def _call_client(client: Any, messages: Messages, model: Optional[str], temperature: float) -> Dict[str, Any]:
    msgs = _to_messages(messages)

    if hasattr(client, "answer"):  # ex: Le OpenAIClient ou OllamaClient upgradé
        out = client.answer(msgs, model=model, temperature=temperature)  # type: ignore[arg-type]
        if isinstance(out, str):
            return {"text": out, "raw": out}
        text = getattr(out, "text", None) or ""
        return {"text": text, "raw": out}

    if hasattr(client, "answer_with_meta"):  # ex: Le model OllamaClient d’origine
        out = client.answer_with_meta(msgs, temperature=temperature)  # type: ignore[arg-type]
        if isinstance(out, dict) and "text" in out:
            return {"text": out.get("text", ""), "raw": out}
        return {"text": str(out), "raw": out}

    raise RuntimeError(f"Client {type(client)} sans answer()/answer_with_meta().")


class LLMGateway:
    """Route vers tes différents providers avec une API unifiée."""

    def _openai(self) -> Any:
        if OpenAIClient is None:
            raise RuntimeError("OpenAIClient indisponible")
        return OpenAIClient()  # lit OPENAI_API_KEY en interne

    def _ollama(self, model: Optional[str] = None) -> Any:
        if OllamaClient is None:
            raise RuntimeError("OllamaClient indisponible")
        return OllamaClient(model=model or os.getenv("OLLAMA_MODEL", "llama3.1"))

    def _anthropic(self) -> Any:
        if AnthropicClient is None:
            raise RuntimeError("AnthropicClient indisponible")
        return AnthropicClient()

    def _perplexity(self) -> Any:
        if PerplexityClient is None:
            raise RuntimeError("PerplexityClient indisponible")
        return PerplexityClient()

    def _get(self, provider: str, model: Optional[str]) -> Any:
        p = provider.lower()
        if p == "openai":
            return self._openai()
        if p == "ollama":
            return self._ollama(model=model)
        if p == "anthropic":
            return self._anthropic()
        if p == "perplexity":
            return self._perplexity()
        raise ValueError(f"Provider inconnu: {provider}")

    def ask(self, provider: str, messages: Messages, model: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        client = self._get(provider, model)
        result = _call_client(client, messages, model=model, temperature=temperature)
        return {
            "text": result["text"],
            "provider": provider,
            "model": model or getattr(client, "model", getattr(client, "default_model", "")),
            "raw": result["raw"],
        }
