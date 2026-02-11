"""Health API routes — proxies to Holly Grace agents and enriches."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.holly_client import get_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    """Get combined health status from Holly Grace agents."""
    url = f"{settings.agents_url}/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()
            data["holly_console"] = "connected"
            return JSONResponse(data, status_code=resp.status_code)
    except Exception as exc:
        logger.warning("Health check failed: %s", exc)
        return JSONResponse(
            {
                "status": "disconnected",
                "service": "Holly Grace agents",
                "holly_console": "healthy",
                "checks": {},
                "error": str(exc),
            },
            status_code=503,
        )


@router.get("/circuit-breakers")
async def circuit_breakers():
    """Get circuit breaker states from Holly Grace agents."""
    client = get_client()
    try:
        resp = await client.get("/circuit-breakers")
        return resp.json()
    except Exception:
        return JSONResponse(
            {"error": "Cannot reach Holly Grace agents server"},
            status_code=503,
        )
