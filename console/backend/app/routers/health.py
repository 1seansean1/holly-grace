"""Health API routes — proxies to ecom-agents and enriches."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    """Get combined health status from ecom-agents."""
    client = get_client()
    try:
        resp = await client.get("/health")
        data = resp.json()
        data["forge_console"] = "connected"
        return data
    except Exception:
        return JSONResponse(
            {
                "status": "disconnected",
                "service": "ecom-agents",
                "forge_console": "healthy",
                "checks": {},
                "error": "Cannot reach ecom-agents server",
            },
            status_code=503,
        )


@router.get("/circuit-breakers")
async def circuit_breakers():
    """Get circuit breaker states from ecom-agents."""
    client = get_client()
    try:
        resp = await client.get("/circuit-breakers")
        return resp.json()
    except Exception:
        return JSONResponse(
            {"error": "Cannot reach ecom-agents server"},
            status_code=503,
        )
