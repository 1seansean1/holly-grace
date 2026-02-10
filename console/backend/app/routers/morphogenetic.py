"""Morphogenetic system API routes — proxies to ecom-agents /morphogenetic endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/morphogenetic", tags=["morphogenetic"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("/snapshot")
async def snapshot():
    """Get a live developmental snapshot."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/snapshot")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/trajectory")
async def trajectory(limit: int = 100):
    """Get the developmental trajectory."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/trajectory", params={"limit": limit})
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "trajectory": []}, status_code=503)


@router.get("/goals")
async def goals():
    """Get all morphogenetic goal specs with current status."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/goals")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "goals": []}, status_code=503)


@router.get("/assembly")
async def assembly():
    """Get cached competencies from the assembly cache."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/assembly")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "competencies": []}, status_code=503)


@router.get("/cascade")
async def cascade(limit: int = 50):
    """Get cascade event history."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/cascade", params={"limit": limit})
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "events": []}, status_code=503)


@router.post("/evaluate")
async def evaluate():
    """Trigger an immediate morphogenetic evaluation cycle."""
    client = get_client()
    try:
        resp = await client.post("/morphogenetic/evaluate", timeout=60.0)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


@router.post("/goals")
async def create_goal(request: Request):
    """Create a new morphogenetic goal."""
    client = get_client()
    try:
        body = await request.json()
        resp = await client.post("/morphogenetic/goals", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, request: Request):
    """Update a morphogenetic goal."""
    client = get_client()
    try:
        body = await request.json()
        resp = await client.put(f"/morphogenetic/goals/{goal_id}", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str):
    """Delete a morphogenetic goal."""
    client = get_client()
    try:
        resp = await client.delete(f"/morphogenetic/goals/{goal_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/goals/reset")
async def reset_goals():
    """Reset goals to hardcoded defaults."""
    client = get_client()
    try:
        resp = await client.post("/morphogenetic/goals/reset")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Cascade config
# ---------------------------------------------------------------------------


@router.get("/cascade/config")
async def cascade_config():
    """Get current cascade configuration."""
    client = get_client()
    try:
        resp = await client.get("/morphogenetic/cascade/config")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.put("/cascade/config")
async def update_cascade_config(request: Request):
    """Update cascade configuration."""
    client = get_client()
    try:
        body = await request.json()
        resp = await client.put("/morphogenetic/cascade/config", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/cascade/config/reset")
async def reset_cascade_config():
    """Reset cascade configuration to defaults."""
    client = get_client()
    try:
        resp = await client.post("/morphogenetic/cascade/config/reset")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
