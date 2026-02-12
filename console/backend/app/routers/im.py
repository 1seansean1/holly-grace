"""IM (Informational Monism) workspace API routes — proxies to Holly Grace agents.

Pipeline endpoints for the Architecture Selection Rule.
All requests proxy to the agents server at /im/*.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.holly_client import get_client

router = APIRouter(prefix="/api/im", tags=["im"])

_503 = {"error": "Cannot reach Holly Grace agents server"}


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


@router.get("/workspaces")
async def workspaces_list(limit: int = 20):
    """List all IM workspaces."""
    client = get_client()
    try:
        resp = await client.get("/im/workspaces", params={"limit": limit})
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/workspaces/{workspace_id}")
async def workspace_detail(workspace_id: str):
    """Get workspace state."""
    client = get_client()
    try:
        resp = await client.get(f"/im/workspaces/{workspace_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/workspaces/{workspace_id}")
async def workspace_delete(workspace_id: str):
    """Delete a workspace."""
    client = get_client()
    try:
        resp = await client.delete(f"/im/workspaces/{workspace_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/workspaces/{workspace_id}/audit")
async def workspace_audit(workspace_id: str):
    """Get audit trail."""
    client = get_client()
    try:
        resp = await client.get(f"/im/workspaces/{workspace_id}/audit")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


@router.post("/pipeline/parse")
async def pipeline_parse(request: Request):
    """Step 1: Parse goal tuple."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/im/pipeline/parse", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/predicates")
async def pipeline_predicates(workspace_id: str, request: Request):
    """Step 2: Generate failure predicates."""
    client = get_client()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/predicates", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/coupling")
async def pipeline_coupling(workspace_id: str, request: Request):
    """Step 3: Build coupling matrix."""
    client = get_client()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/coupling", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/codimension")
async def pipeline_codimension(workspace_id: str, request: Request):
    """Step 4: Compute codimension."""
    client = get_client()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/codimension", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/rank-budget")
async def pipeline_rank_budget(workspace_id: str, request: Request):
    """Step 5: Rank budget."""
    client = get_client()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/rank-budget", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/memory")
async def pipeline_memory(workspace_id: str):
    """Step 6: Memory tier design."""
    client = get_client()
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/memory")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/agents")
async def pipeline_agents(workspace_id: str):
    """Step 7: Agent synthesis."""
    client = get_client()
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/agents")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/workflow")
async def pipeline_workflow(workspace_id: str):
    """Step 8: Workflow synthesis."""
    client = get_client()
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/workflow")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/{workspace_id}/feasibility")
async def pipeline_feasibility(workspace_id: str):
    """Step 9: Feasibility validation."""
    client = get_client()
    try:
        resp = await client.post(f"/im/pipeline/{workspace_id}/feasibility")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/pipeline/full")
async def pipeline_full(request: Request):
    """Run complete 9-step pipeline."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/im/pipeline/full", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
