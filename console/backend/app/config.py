"""Holly Grace backend configuration."""

from __future__ import annotations

import logging
import os
import time

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _generate_service_token() -> str:
    """Generate a long-lived admin JWT for console->agents communication.

    Uses AUTH_SECRET_KEY from environment (same secret the agents server uses).
    """
    secret = os.environ.get("AUTH_SECRET_KEY")
    if not secret:
        return ""
    try:
        from jose import jwt

        payload = {
            "sub": "console-backend-service",
            "role": "admin",
            "iat": int(time.time()),
            "exp": int(time.time()) + 86400 * 365,  # 1 year
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        logger.info("Generated service JWT for agents server communication")
        return token
    except Exception as exc:
        logger.warning("Failed to generate service token: %s", exc)
        return ""


# Auto-set HOLLY_AGENTS_TOKEN if not already set
if not os.environ.get("HOLLY_AGENTS_TOKEN") and os.environ.get("AUTH_SECRET_KEY"):
    _token = _generate_service_token()
    if _token:
        os.environ["HOLLY_AGENTS_TOKEN"] = _token


class Settings(BaseSettings):
    """Environment-driven settings for the Holly Grace backend."""

    agents_url: str = "http://localhost:8050"
    agents_token: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "holly-grace"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Provider admin keys for real billing data (optional)
    anthropic_admin_key: str = ""
    openai_admin_key: str = ""

    # Console authentication
    console_user_email: str = "sean.p.allen9@gmail.com"
    console_user_password: str = "admin"
    console_jwt_secret: str = "CHANGE_ME_IN_PRODUCTION_64_CHAR_SECRET"

    model_config = {"env_prefix": "HOLLY_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
logger.info("Console backend config: agents_url=%s, has_token=%s", settings.agents_url, bool(settings.agents_token))
