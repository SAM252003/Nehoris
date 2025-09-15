# src/geo_agent/config.py
from __future__ import annotations
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # ✅ important: ignore les variables non définies
    )

    ollama_host: str = Field(default="http://localhost:11434")
    ollama_timeout: int = Field(default=180)
    pplx_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    def describe(self) -> dict:
        return {
            "ollama_host": self.ollama_host,
            "ollama_timeout": self.ollama_timeout,
            "has_pplx": bool(self.pplx_api_key),
            "has_openai": bool(self.openai_api_key),
        }
