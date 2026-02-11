"""MCP client manager and tool discovery/invocation helpers."""

from __future__ import annotations

import logging
import os
from typing import Any

from src.mcp.stdio_client import McpStdioClient, StdioServerSpec
from src.mcp.store import (
    get_server,
    update_server_health,
    upsert_tools_for_server,
)

logger = logging.getLogger(__name__)


_ESSENTIAL_ENV_KEYS = {
    # Windows essentials for subprocesses
    "SystemRoot",
    "ComSpec",
    "PATHEXT",
    "Path",
    "TEMP",
    "TMP",
    "USERNAME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
}


def _build_stdio_env(env_allow: list[str] | None, env_overrides: dict[str, Any] | None) -> dict[str, str]:
    # Default posture: do NOT inherit the full process environment.
    # Only pass OS essentials plus explicit allowlisted variables to the MCP subprocess.
    # NOTE: do NOT call os.environ.copy() here. On Windows, os.environ lookups are
    # case-insensitive, but a copied dict becomes case-sensitive and will drop keys
    # like SYSTEMROOT vs SystemRoot.
    full_env = os.environ
    base: dict[str, str] = {}
    for k in _ESSENTIAL_ENV_KEYS:
        v = full_env.get(k)
        if v is not None:
            base[k] = v
    for k in (env_allow or []):
        v = full_env.get(k)
        if v is not None:
            base[str(k)] = v

    overrides = env_overrides or {}
    for k, v in overrides.items():
        if v is None:
            continue
        base[str(k)] = str(v)
    return base


def _coerce_content_to_text(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
        if texts:
            return "\n".join(t for t in texts if t)

    import json

    try:
        return json.dumps(result, default=str)
    except Exception:
        return str(result)


def _coerce_json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


class McpClientManager:
    """Entry point for MCP operations used by API routes and tool adapters."""

    def sync_tools(self, server_id: str) -> dict[str, Any]:
        server = get_server(server_id)
        if not server:
            raise ValueError(f"MCP server '{server_id}' not found")
        if server.get("transport") != "stdio":
            raise NotImplementedError("Only stdio transport is implemented in MVP")

        cmd = server.get("stdio_command") or ""
        args = _coerce_json_list(server.get("stdio_args"))
        cwd = server.get("stdio_cwd") or None
        env_allow = server.get("env_allow") or []
        env_overrides = _coerce_json_dict(server.get("env_overrides"))

        if not cmd:
            raise ValueError("stdio_command is required for stdio MCP servers")

        env = _build_stdio_env(env_allow, env_overrides)
        spec = StdioServerSpec(command=cmd, args=list(args), cwd=cwd, env=env)

        try:
            with McpStdioClient(spec, timeout_s=15.0) as client:
                client.initialize()
                tools_result = client.list_tools()
            tools = tools_result.get("tools") or []
            count = upsert_tools_for_server(server_id, tools if isinstance(tools, list) else [])
            update_server_health(server_id, status="ok", error="")
            return {"server_id": server_id, "tools_synced": count}
        except Exception as exc:
            update_server_health(server_id, status="error", error=str(exc))
            raise

    def call_tool(self, server_id: str, tool_name: str, args: dict[str, Any]) -> str:
        server = get_server(server_id)
        if not server:
            raise ValueError(f"MCP server '{server_id}' not found")
        if server.get("transport") != "stdio":
            raise NotImplementedError("Only stdio transport is implemented in MVP")

        cmd = server.get("stdio_command") or ""
        argv = _coerce_json_list(server.get("stdio_args"))
        cwd = server.get("stdio_cwd") or None
        env_allow = server.get("env_allow") or []
        env_overrides = _coerce_json_dict(server.get("env_overrides"))

        env = _build_stdio_env(env_allow, env_overrides)
        spec = StdioServerSpec(command=cmd, args=list(argv), cwd=cwd, env=env)

        with McpStdioClient(spec, timeout_s=30.0) as client:
            client.initialize()
            result = client.call_tool(tool_name, args)
        return _coerce_content_to_text(result)

    def health_check(self, server_id: str) -> dict[str, Any]:
        server = get_server(server_id)
        if not server:
            raise ValueError(f"MCP server '{server_id}' not found")

        if server.get("transport") != "stdio":
            return {"server_id": server_id, "status": "unknown", "error": "http transport not implemented"}

        cmd = server.get("stdio_command") or ""
        argv = _coerce_json_list(server.get("stdio_args"))
        cwd = server.get("stdio_cwd") or None
        env_allow = server.get("env_allow") or []
        env_overrides = _coerce_json_dict(server.get("env_overrides"))

        env = _build_stdio_env(env_allow, env_overrides)
        spec = StdioServerSpec(command=cmd, args=list(argv), cwd=cwd, env=env)

        try:
            with McpStdioClient(spec, timeout_s=8.0) as client:
                client.initialize()
                client.ping()
            update_server_health(server_id, status="ok", error="")
            return {"server_id": server_id, "status": "ok"}
        except Exception as exc:
            update_server_health(server_id, status="error", error=str(exc))
            return {"server_id": server_id, "status": "error", "error": str(exc)}


_manager: McpClientManager | None = None


def get_mcp_manager() -> McpClientManager:
    global _manager
    if _manager is None:
        _manager = McpClientManager()
    return _manager
