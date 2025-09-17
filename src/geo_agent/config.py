# src/geo_agent/config.py
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Charger le .env depuis la racine du projet
load_dotenv()

@dataclass(frozen=True)
class Settings:
    # Provider/model par défaut (agnostique)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:1b-instruct-fp16")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    LLM_TIMEOUT_S: float = float(os.getenv("LLM_TIMEOUT_S", "60"))

    # OpenAI
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL")  # ex: https://api.openai.com/v1

    # (optionnel) HuggingFace
    HF_API_KEY: str | None = os.getenv("HF_API_KEY")
    HF_MODEL: str | None = os.getenv("HF_MODEL")

    # (optionnel) Anthropic / Perplexity / Gemini
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    PPLX_API_KEY: str | None = os.getenv("PPLX_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")

settings = Settings()