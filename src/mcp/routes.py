"""FastAPI routes for MCP server/tool registry."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.mcp.manager import get_mcp_manager
from src.mcp.store import (
    create_server,
    delete_server,
    get_server,
    init_mcp_tables,
    list_servers,
    list_tools,
    update_server,
    update_tool,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class McpServerCreate(BaseModel):
    server_id: str
    display_name: str
    description: str = ""
    transport: Literal["stdio", "http"] = "stdio"
    enabled: bool = True

    stdio_command: str | None = None
    stdio_args: list[str] = Field(default_factory=list)
    stdio_cwd: str | None = None
    env_allow: list[str] = Field(default_factory=list)
    env_overrides: dict[str, Any] = Field(default_factory=dict)

    http_url: str | None = None
    http_headers_template: dict[str, Any] = Field(default_factory=dict)


class McpServerPatch(BaseModel):
    display_name: str | None = None
    description: str | None = None
    transport: Literal["stdio", "http"] | None = None
    enabled: bool | None = None

    stdio_command: str | None = None
    stdio_args: list[str] | None = None
    stdio_cwd: str | None = None
    env_allow: list[str] | None = None
    env_overrides: dict[str, Any] | None = None

    http_url: str | None = None
    http_headers_template: dict[str, Any] | None = None


class McpToolPatch(BaseModel):
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    enabled: bool | None = None
    risk_level: Literal["low", "medium", "high"] | None = None


@router.get("/servers")
def mcp_list_servers(enabled_only: bool | None = None):
    try:
        servers = list_servers(enabled_only=enabled_only)
        return {"servers": servers, "count": len(servers)}
    except Exception as exc:
        return JSONResponse({"error": str(exc), "servers": [], "count": 0}, status_code=500)


@router.post("/servers")
def mcp_create_server(body: McpServerCreate):
    try:
        init_mcp_tables()
        created = create_server(**body.model_dump())
        return {"server": created}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.patch("/servers/{server_id}")
def mcp_patch_server(server_id: str, body: McpServerPatch):
    try:
        updated = update_server(server_id, body.model_dump(exclude_unset=True))
        if not updated:
            return JSONResponse({"error": "Server not found"}, status_code=404)
        return {"server": updated}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.delete("/servers/{server_id}")
def mcp_delete_server(server_id: str):
    try:
        ok = delete_server(server_id)
        if not ok:
            return JSONResponse({"error": "Server not found"}, status_code=404)
        return {"status": "deleted", "server_id": server_id}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/servers/{server_id}/sync")
def mcp_sync_server(server_id: str):
    try:
        result = get_mcp_manager().sync_tools(server_id)
        return result
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/servers/{server_id}/tools")
def mcp_list_server_tools(server_id: str):
    try:
        server = get_server(server_id)
        if not server:
            return JSONResponse({"error": "Server not found"}, status_code=404)
        tools = list_tools(server_id)
        return {"server": server, "tools": tools, "count": len(tools)}
    except Exception as exc:
        return JSONResponse({"error": str(exc), "tools": [], "count": 0}, status_code=500)


@router.patch("/tools/{tool_id}")
def mcp_patch_tool(tool_id: str, body: McpToolPatch):
    try:
        updated = update_tool(tool_id, body.model_dump(exclude_unset=True))
        if not updated:
            return JSONResponse({"error": "Tool not found"}, status_code=404)
        return {"tool": updated}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/health")
def mcp_health(refresh: bool = Query(default=False)):
    """Return health for enabled servers. If refresh=true, run a live ping."""
    try:
        servers = list_servers(enabled_only=True)
        if not refresh:
            return {
                "servers": [
                    {
                        "server_id": s["server_id"],
                        "display_name": s["display_name"],
                        "transport": s["transport"],
                        "enabled": s["enabled"],
                        "last_health_status": s.get("last_health_status", "unknown"),
                        "last_health_error": s.get("last_health_error", ""),
                        "last_health_at": s.get("last_health_at"),
                    }
                    for s in servers
                ],
                "count": len(servers),
            }

        mgr = get_mcp_manager()
        statuses = [mgr.health_check(s["server_id"]) for s in servers]
        return {"servers": statuses, "count": len(statuses)}
    except Exception as exc:
        return JSONResponse({"error": str(exc), "servers": [], "count": 0}, status_code=500)

