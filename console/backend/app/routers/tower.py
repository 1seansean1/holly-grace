"""Tower (Control Tower) API routes — proxies to Holly Grace agents.

Provides durable run management, ticket inbox, and approval workflows.
All requests proxy to the agents server at /tower/*.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.holly_client import get_client

router = APIRouter(prefix="/api/tower", tags=["tower"])

_503 = {"error": "Cannot reach Holly Grace agents server"}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@router.post("/runs/start")
async def start_run(request: Request):
    """Start a new Tower run."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/tower/runs/start", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/runs")
async def list_runs(
    status: str | None = None,
    workflow_id: str | None = None,
    limit: int = 50,
):
    """List Tower runs with optional filters."""
    client = get_client()
    params = {"limit": limit}
    if status:
        params["status"] = status
    if workflow_id:
        params["workflow_id"] = workflow_id
    try:
        resp = await client.get("/tower/runs", params=params)
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "runs": [], "count": 0}, status_code=503)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get a single Tower run."""
    client = get_client()
    try:
        resp = await client.get(f"/tower/runs/{run_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str):
    """Get event timeline for a Tower run."""
    client = get_client()
    try:
        resp = await client.get(f"/tower/runs/{run_id}/events")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "events": [], "count": 0}, status_code=503)


@router.get("/runs/{run_id}/snapshot")
async def get_run_snapshot(run_id: str):
    """Get the current LangGraph state snapshot for a run."""
    client = get_client()
    try:
        resp = await client.get(f"/tower/runs/{run_id}/snapshot")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, request: Request):
    """Resume a Tower run after a ticket decision."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post(f"/tower/runs/{run_id}/resume", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Inbox / Tickets
# ---------------------------------------------------------------------------


@router.get("/inbox")
async def inbox(
    status: str = "pending",
    risk_level: str | None = None,
    limit: int = 50,
):
    """Get Tower ticket inbox (pending tickets needing decisions)."""
    client = get_client()
    params = {"status": status, "limit": limit}
    if risk_level:
        params["risk_level"] = risk_level
    try:
        resp = await client.get("/tower/inbox", params=params)
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "tickets": [], "count": 0}, status_code=503)


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """Get a Tower ticket by ID."""
    client = get_client()
    try:
        resp = await client.get(f"/tower/tickets/{ticket_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/tickets/{ticket_id}/decide")
async def decide_ticket(ticket_id: int, request: Request):
    """Decide a Tower ticket (approve/reject) and resume the run."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post(f"/tower/tickets/{ticket_id}/decide", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------


@router.get("/effects/{effect_id}")
async def get_effect(effect_id: str):
    """Get a Tower effect by ID."""
    client = get_client()
    try:
        resp = await client.get(f"/tower/effects/{effect_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
