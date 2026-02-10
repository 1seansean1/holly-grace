"""Agent config API routes — proxies CRUD to ecom-agents."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/agents", tags=["agents"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("")
async def list_agents():
    """List all agent configurations."""
    client = get_client()
    try:
        resp = await client.get("/agents")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "agents": []}, status_code=503)


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get a single agent configuration."""
    client = get_client()
    try:
        resp = await client.get(f"/agents/{agent_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("")
async def create_agent(request: Request):
    """Create a new agent configuration."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/agents", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.put("/{agent_id}")
async def update_agent(agent_id: str, request: Request):
    """Update an agent configuration."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.put(f"/agents/{agent_id}", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Soft-delete an agent."""
    client = get_client()
    try:
        resp = await client.delete(f"/agents/{agent_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{agent_id}/versions")
async def list_agent_versions(agent_id: str):
    """Get version history for an agent."""
    client = get_client()
    try:
        resp = await client.get(f"/agents/{agent_id}/versions")
        return resp.json()
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{agent_id}/versions/{version}")
async def get_agent_version(agent_id: str, version: int):
    """Get a specific version snapshot."""
    client = get_client()
    try:
        resp = await client.get(f"/agents/{agent_id}/versions/{version}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{agent_id}/rollback")
async def rollback_agent(agent_id: str, request: Request):
    """Rollback an agent to a previous version."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post(f"/agents/{agent_id}/rollback", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{agent_id}/default")
async def get_agent_default(agent_id: str):
    """Get the hardcoded default config for an agent."""
    client = get_client()
    try:
        resp = await client.get(f"/agents/{agent_id}/default")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{agent_id}/efficacy")
async def get_agent_efficacy(agent_id: str, days: int = 30):
    """Get efficacy history for an agent."""
    client = get_client()
    try:
        resp = await client.get(f"/agents/{agent_id}/efficacy", params={"days": days})
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "history": []}, status_code=503)
