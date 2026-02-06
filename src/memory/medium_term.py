"""Medium-term memory: Redis-backed session store with 30-day TTL.

Stores campaign progress, multi-step workflow state, and partial results
keyed by {task_type}:{campaign_id}:{date}.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

import redis

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 30
DEFAULT_TTL_SECONDS = DEFAULT_TTL_DAYS * 86400

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _make_key(task_type: str, campaign_id: str, dt: date | None = None) -> str:
    """Build a Redis key."""
    dt = dt or date.today()
    return f"ecom:session:{task_type}:{campaign_id}:{dt.isoformat()}"


def store_session(
    task_type: str,
    campaign_id: str,
    data: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """Store session data in Redis with TTL."""
    r = _get_redis()
    key = _make_key(task_type, campaign_id)
    r.setex(key, ttl_seconds, json.dumps(data))
    logger.info("Stored session: %s", key)
    return key


def get_session(
    task_type: str, campaign_id: str, dt: date | None = None
) -> dict[str, Any] | None:
    """Retrieve session data from Redis."""
    r = _get_redis()
    key = _make_key(task_type, campaign_id, dt)
    raw = r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


def update_session(task_type: str, campaign_id: str, updates: dict[str, Any]) -> bool:
    """Merge updates into an existing session."""
    existing = get_session(task_type, campaign_id)
    if existing is None:
        return False
    existing.update(updates)
    store_session(task_type, campaign_id, existing)
    return True


def delete_session(task_type: str, campaign_id: str, dt: date | None = None) -> bool:
    """Delete a session from Redis."""
    r = _get_redis()
    key = _make_key(task_type, campaign_id, dt)
    return bool(r.delete(key))
