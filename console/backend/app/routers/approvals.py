"""Approval queue API routes — proxies to ecom-agents /approvals endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("")
async def list_approvals(status: str = "pending"):
    """List approval requests."""
    client = get_client()
    try:
        resp = await client.get("/approvals", params={"status": status})
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "approvals": []}, status_code=503)


@router.get("/{approval_id}")
async def get_approval(approval_id: int):
    """Get a single approval request."""
    client = get_client()
    try:
        resp = await client.get(f"/approvals/{approval_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{approval_id}/approve")
async def approve(approval_id: int, request: Request):
    """Approve a pending request."""
    client = get_client()
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        resp = await client.post(f"/approvals/{approval_id}/approve", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{approval_id}/reject")
async def reject(approval_id: int, request: Request):
    """Reject a pending request."""
    client = get_client()
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        resp = await client.post(f"/approvals/{approval_id}/reject", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/stats")
async def stats():
    """Get approval queue statistics."""
    client = get_client()
    try:
        resp = await client.get("/approvals/stats")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "total": 0}, status_code=503)
