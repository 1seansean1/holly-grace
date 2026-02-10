"""Forge Scope backend configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Environment-driven settings for the Forge Scope backend."""

    ecom_agents_url: str = "http://localhost:8050"
    ecom_agents_token: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "ecom-agents"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Provider admin keys for real billing data (optional)
    anthropic_admin_key: str = ""
    openai_admin_key: str = ""

    model_config = {"env_prefix": "FORGE_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
