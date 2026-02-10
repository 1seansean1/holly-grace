"""Tool registry API routes — proxies to ecom-agents."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all available tools."""
    client = get_client()
    try:
        resp = await client.get("/tools")
        return resp.json()
    except Exception:
        return JSONResponse(
            {"error": "Cannot reach ecom-agents server", "tools": [], "count": 0},
            status_code=503,
        )
