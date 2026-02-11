"""Autonomy Control API routes — proxies to Holly Grace agents server.

Provides pause/resume, queue inspection, task cancellation, and audit log.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.holly_client import get_client

router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])

_503 = {"error": "Cannot reach Holly Grace agents server"}


@router.get("/status")
async def status():
    """Get autonomy loop status and metrics."""
    client = get_client()
    try:
        resp = await client.get("/holly/autonomy/status")
        return resp.json()
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pause")
async def pause():
    """Pause the autonomy loop."""
    client = get_client()
    try:
        resp = await client.post("/holly/autonomy/pause")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/resume")
async def resume():
    """Resume the autonomy loop."""
    client = get_client()
    try:
        resp = await client.post("/holly/autonomy/resume")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/queue")
async def queue(limit: int = 50):
    """List queued tasks."""
    client = get_client()
    try:
        resp = await client.get("/holly/autonomy/queue", params={"limit": limit})
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "tasks": [], "count": 0}, status_code=503)


@router.delete("/queue/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a queued task."""
    client = get_client()
    try:
        resp = await client.delete(f"/holly/autonomy/queue/{task_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/queue")
async def clear_queue():
    """Clear entire autonomy queue."""
    client = get_client()
    try:
        resp = await client.delete("/holly/autonomy/queue")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/audit")
async def audit(limit: int = 50, offset: int = 0):
    """Query autonomy audit log."""
    client = get_client()
    try:
        resp = await client.get("/holly/autonomy/audit", params={"limit": limit, "offset": offset})
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "logs": [], "total": 0}, status_code=503)
