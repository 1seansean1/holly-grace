"""MCP registry API routes — proxies to Holly Grace agents."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.holly_client import get_client

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_503 = {"error": "Cannot reach Holly Grace agents server"}


@router.get("/servers")
async def list_servers(enabled_only: bool | None = None):
    client = get_client()
    params = {}
    if enabled_only is not None:
        params["enabled_only"] = enabled_only
    try:
        resp = await client.get("/mcp/servers", params=params)
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "servers": [], "count": 0}, status_code=503)


@router.post("/servers")
async def create_server(request: Request):
    client = get_client()
    body = await request.json()
    try:
        resp = await client.post("/mcp/servers", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.patch("/servers/{server_id}")
async def patch_server(server_id: str, request: Request):
    client = get_client()
    body = await request.json()
    try:
        resp = await client.patch(f"/mcp/servers/{server_id}", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    client = get_client()
    try:
        resp = await client.delete(f"/mcp/servers/{server_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/servers/{server_id}/sync")
async def sync_server(server_id: str):
    client = get_client()
    try:
        resp = await client.post(f"/mcp/servers/{server_id}/sync", json={})
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str):
    client = get_client()
    try:
        resp = await client.get(f"/mcp/servers/{server_id}/tools")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "tools": [], "count": 0}, status_code=503)


@router.patch("/tools/{tool_id}")
async def patch_tool(tool_id: str, request: Request):
    client = get_client()
    body = await request.json()
    try:
        resp = await client.patch(f"/mcp/tools/{tool_id}", json=body)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/health")
async def health(refresh: bool = False):
    client = get_client()
    try:
        resp = await client.get("/mcp/health", params={"refresh": refresh})
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "servers": [], "count": 0}, status_code=503)

