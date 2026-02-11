"""LangChain tool adapter for MCP tools stored in Postgres."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from src.mcp.jsonschema import jsonschema_to_pydantic_model
from src.mcp.manager import get_mcp_manager

logger = logging.getLogger(__name__)


def build_mcp_tool(
    *,
    tool_id: str,
    server_id: str,
    mcp_tool_name: str,
    description: str,
    input_schema: dict[str, Any] | None,
) -> BaseTool:
    args_schema = jsonschema_to_pydantic_model(
        f"McpArgs_{tool_id}",
        input_schema if isinstance(input_schema, dict) else {},
    )

    def _call(**kwargs: Any) -> str:
        return get_mcp_manager().call_tool(server_id, mcp_tool_name, kwargs)

    return StructuredTool.from_function(
        name=tool_id,
        description=description or f"MCP tool {tool_id}",
        func=_call,
        args_schema=args_schema,
    )

