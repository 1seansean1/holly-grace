"""Health check for all external services.

Checks: Ollama, Postgres, Redis, ChromaDB, API key validity.
If Ollama is down, sets a flag to reroute TRIVIAL tasks to GPT-4o-mini.
"""

from __future__ import annotations

import logging
import os

import httpx
import redis as redis_lib

from src.resilience.circuit_breaker import get_breaker

logger = logging.getLogger(__name__)

# Global flag: if True, Ollama is down and TRIVIAL tasks use GPT-4o-mini
ollama_fallback_active = False


def check_ollama() -> bool:
    """Check if Ollama is responsive."""
    global ollama_fallback_active
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11435")
    breaker = get_breaker("ollama")
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=5.0)
        ok = resp.status_code == 200
        if ok:
            breaker.record_success()
            ollama_fallback_active = False
        else:
            breaker.record_failure()
            ollama_fallback_active = True
        return ok
    except Exception:
        breaker.record_failure()
        ollama_fallback_active = True
        return False


def check_postgres() -> bool:
    """Check if PostgreSQL is connected."""
    try:
        import psycopg

        db_url = os.environ.get(
            "DATABASE_URL", "postgresql://ecom:ecom_dev_password@localhost:5434/ecom_agents"
        )
        with psycopg.connect(db_url, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def check_redis() -> bool:
    """Check if Redis is responsive."""
    breaker = get_breaker("redis")
    try:
        url = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
        r = redis_lib.from_url(url, decode_responses=True)
        ok = r.ping()
        if ok:
            breaker.record_success()
        else:
            breaker.record_failure()
        return bool(ok)
    except Exception:
        breaker.record_failure()
        return False


def check_chromadb() -> bool:
    """Check if ChromaDB is responsive."""
    breaker = get_breaker("chromadb")
    try:
        url = os.environ.get("CHROMA_URL", "http://localhost:8100")
        resp = httpx.get(f"{url}/api/v1/heartbeat", timeout=5.0)
        ok = resp.status_code == 200
        if ok:
            breaker.record_success()
        else:
            breaker.record_failure()
        return ok
    except Exception:
        breaker.record_failure()
        return False


def check_api_keys() -> dict[str, bool]:
    """Check that required API keys are set (non-empty)."""
    keys = {
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "STRIPE_SECRET_KEY": bool(os.environ.get("STRIPE_SECRET_KEY")),
        "SHOPIFY_ACCESS_TOKEN": bool(os.environ.get("SHOPIFY_ACCESS_TOKEN")),
        "PRINTFUL_API_KEY": bool(os.environ.get("PRINTFUL_API_KEY")),
    }
    return keys


def run_health_checks() -> dict[str, bool]:
    """Run all health checks and return results."""
    results = {
        "ollama": check_ollama(),
        "postgres": check_postgres(),
        "redis": check_redis(),
        "chromadb": check_chromadb(),
    }

    api_keys = check_api_keys()
    results["api_keys_configured"] = all(api_keys.values())

    logger.info("Health check results: %s", results)
    return results
