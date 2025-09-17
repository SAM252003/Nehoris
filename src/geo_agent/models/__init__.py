# src/geo_agent/models/__init__.py
from __future__ import annotations
import os
from typing import Optional

# Tous les imports sont LOCAUX (même dossier)
try:
    from .openai_client import OpenAIClient  # doit exposer .complete(...)
except Exception:
    OpenAIClient = None  # type: ignore

try:
    from .ollama_client import OllamaClient  # doit exposer .complete(...) OU compatible
except Exception:
    OllamaClient = None  # type: ignore

try:
    from .anthropic_client import AnthropicClient
except Exception:
    AnthropicClient = None  # type: ignore

try:
    from .perplexity_client import PerplexityClient
except Exception:
    PerplexityClient = None  # type: ignore

try:
    from .gemini_client import GeminiClient
except Exception:
    GeminiClient = None  # type: ignore


def _detect_provider_from_model(model: str) -> str:
    m = (model or "").lower()
    if m.startswith("gpt-"):           # ex: gpt-4o, gpt-4o-mini
        return "openai"
    if m.startswith("claude") or "anthropic" in m:
        return "anthropic"
    if m.startswith("sonar-") or "pplx" in m:
        return "perplexity"
    if m.startswith("gemini") or "gemini" in m:
        return "gemini"
    # Heuristique Ollama: noms locaux avec ":" (llama3.2:*, mistral:*, qwen2.5:*, etc.)
    if ":" in m or m.startswith(("llama", "mistral", "qwen", "phi", "gemma", "llava", "mixtral")):
        return "ollama"
    # fallback env
    return os.getenv("LLM_PROVIDER", "ollama").lower()


def get_llm_client(provider: Optional[str] = None, model: Optional[str] = None):
    """
    Factory agnostique:
    - Si provider est None, on détecte via le nom du modèle ou LLM_PROVIDER.
    - Retourne une instance de client avec .complete(prompt, model=?, temperature=?).
    """
    p = (provider or _detect_provider_from_model(model or os.getenv("LLM_MODEL", ""))).lower()

    if p == "openai":
        if not OpenAIClient:
            raise ImportError("OpenAIClient indisponible (fichier openai_client.py ou dépendance manquante).")
        return OpenAIClient()

    if p == "anthropic":
        if not AnthropicClient:
            raise ImportError("AnthropicClient indisponible.")
        return AnthropicClient()

    if p == "perplexity":
        if not PerplexityClient:
            raise ImportError("PerplexityClient indisponible.")
        return PerplexityClient()

    if p == "gemini":
        if not GeminiClient:
            raise ImportError("GeminiClient indisponible.")
        return GeminiClient()

    # défaut = Ollama
    if not OllamaClient:
        raise ImportError("OllamaClient indisponible.")
    return OllamaClient()


__all__ = ["get_llm_client"]