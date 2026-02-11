"""Naming helpers for MCP registry objects."""

from __future__ import annotations

import re


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_US = re.compile(r"_+")


def sanitize_identifier(value: str) -> str:
    """Normalize an identifier to `a-z0-9_` for tool ids."""
    v = (value or "").strip().lower()
    v = _NON_ALNUM.sub("_", v)
    v = _MULTI_US.sub("_", v).strip("_")
    return v or "tool"


def mcp_tool_id(server_id: str, tool_name: str) -> str:
    """Compute a stable tool_id for an MCP tool."""
    return f"mcp_{sanitize_identifier(server_id)}_{sanitize_identifier(tool_name)}"

