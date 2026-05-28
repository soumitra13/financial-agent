"""Centralised settings — reads from .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "dev-secret-key-change-in-prod"

    # ── Agent ─────────────────────────────────────────────────────────────────
    agent_max_steps: int = 10
    agent_tool_timeout_seconds: int = 30
    agent_task_timeout_seconds: int = 300

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins for production.
    # Example: https://my-app.vercel.app,https://my-custom-domain.com
    cors_origins: str = ""

    # ── Environment ───────────────────────────────────────────────────────────
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use as a FastAPI dependency."""
    return Settings()
