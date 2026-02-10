"""Workflow CRUD API routes — proxies to ecom-agents."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("")
async def list_workflows():
    """List all workflows."""
    client = get_client()
    try:
        resp = await client.get("/workflows")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "workflows": [], "count": 0}, status_code=503)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a single workflow."""
    client = get_client()
    try:
        resp = await client.get(f"/workflows/{workflow_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("")
async def create_workflow(request: Request):
    """Create a new workflow."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/workflows", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, request: Request):
    """Update a workflow."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.put(f"/workflows/{workflow_id}", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Soft-delete a workflow."""
    client = get_client()
    try:
        resp = await client.delete(f"/workflows/{workflow_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{workflow_id}/activate")
async def activate_workflow(workflow_id: str):
    """Activate a workflow."""
    client = get_client()
    try:
        resp = await client.post(f"/workflows/{workflow_id}/activate")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{workflow_id}/compile")
async def compile_workflow(workflow_id: str):
    """Dry-run compile a workflow."""
    client = get_client()
    try:
        resp = await client.post(f"/workflows/{workflow_id}/compile")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{workflow_id}/versions")
async def list_workflow_versions(workflow_id: str):
    """Get version history for a workflow."""
    client = get_client()
    try:
        resp = await client.get(f"/workflows/{workflow_id}/versions")
        return resp.json()
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/{workflow_id}/versions/{version}")
async def get_workflow_version(workflow_id: str, version: int):
    """Get a specific version snapshot."""
    client = get_client()
    try:
        resp = await client.get(f"/workflows/{workflow_id}/versions/{version}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/{workflow_id}/rollback")
async def rollback_workflow(workflow_id: str, request: Request):
    """Rollback a workflow to a previous version."""
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post(f"/workflows/{workflow_id}/rollback", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
