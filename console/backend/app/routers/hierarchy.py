"""Goal Hierarchy API routes — proxies to Holly Grace agents.

Read-only hierarchy queries + admin write endpoints.
All requests proxy to the agents server at /hierarchy/*.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.holly_client import get_client

router = APIRouter(prefix="/api/hierarchy", tags=["hierarchy"])

_503 = {"error": "Cannot reach Holly Grace agents server"}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@router.get("/gate")
async def gate_all():
    """Get gate status for all levels."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/gate")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/gate/{level}")
async def gate_level(level: int):
    """Get gate status for a specific level."""
    client = get_client()
    try:
        resp = await client.get(f"/hierarchy/gate/{level}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


@router.get("/predicates")
async def predicates_all():
    """Get all predicates."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/predicates")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/predicates/{index}")
async def predicate_detail(index: int):
    """Get a single predicate with history."""
    client = get_client()
    try:
        resp = await client.get(f"/hierarchy/predicates/{index}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/predicates/{index}/observe")
async def observe_predicate(index: int, request: Request):
    """Submit an observation."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post(f"/hierarchy/predicates/{index}/observe", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


@router.get("/blocks")
async def blocks():
    """Get block decomposition."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/blocks")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/eigenspectrum")
async def eigenspectrum():
    """Get eigenspectrum."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/eigenspectrum")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/feasibility")
async def feasibility():
    """Run feasibility check."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/feasibility")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/agents")
async def agents():
    """Get agent assignments."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/agents")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/orchestrators")
async def orchestrators():
    """Get orchestrator assignments."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/orchestrators")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


@router.get("/modules")
async def modules_list():
    """List Terrestrial modules."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/modules")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/modules/{module_id}")
async def module_detail(module_id: str):
    """Get a single module."""
    client = get_client()
    try:
        resp = await client.get(f"/hierarchy/modules/{module_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/modules")
async def add_module(request: Request):
    """Add a new module."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/hierarchy/modules", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/modules/{module_id}")
async def delete_module(module_id: str):
    """Deactivate a module."""
    client = get_client()
    try:
        resp = await client.delete(f"/hierarchy/modules/{module_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Coupling
# ---------------------------------------------------------------------------


@router.get("/coupling")
async def coupling():
    """Get coupling data."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/coupling")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/coupling/upward-budget")
async def coupling_budget():
    """Get upward coupling budget."""
    client = get_client()
    try:
        resp = await client.get("/hierarchy/coupling/upward-budget")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


@router.post("/recompute")
async def recompute():
    """Force full recomputation."""
    client = get_client()
    try:
        resp = await client.post("/hierarchy/recompute")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
