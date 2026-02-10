"""Async HTTP client for the ecom-agents API."""

from __future__ import annotations

import httpx

from app.config import settings

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx async client."""
    global _client
    if _client is None or _client.is_closed:
        headers = {}
        if settings.ecom_agents_token:
            headers["Authorization"] = f"Bearer {settings.ecom_agents_token}"
        _client = httpx.AsyncClient(
            base_url=settings.ecom_agents_url,
            timeout=30.0,
            headers=headers,
        )
    return _client


async def close_client() -> None:
    """Close the shared client on shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
