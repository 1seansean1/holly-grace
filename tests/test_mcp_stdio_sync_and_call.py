from __future__ import annotations

import sys
import uuid
from pathlib import Path

from src.mcp.manager import get_mcp_manager
from src.mcp.store import create_server, delete_server, init_mcp_tables, list_tools
from src.tool_registry import ToolRegistry


def test_mcp_stdio_sync_and_call():
    init_mcp_tables()

    repo_root = Path(__file__).resolve().parents[1]
    server_id = f"pytest_echo_{uuid.uuid4().hex[:8]}"

    create_server(
        server_id=server_id,
        display_name="Pytest Echo",
        description="pytest stdio echo MCP server",
        transport="stdio",
        enabled=True,
        stdio_command=sys.executable,
        stdio_args=["-m", "tests.mcp_echo_server"],
        stdio_cwd=str(repo_root),
    )

    try:
        mgr = get_mcp_manager()
        synced = mgr.sync_tools(server_id)
        assert synced["tools_synced"] == 1

        discovered = list_tools(server_id)
        echo_row = next(r for r in discovered if r.get("mcp_tool_name") == "echo")
        tool_id = echo_row["tool_id"]

        out = mgr.call_tool(server_id, "echo", {"text": "hi"})
        assert out.strip() == "echo:hi"

        reg = ToolRegistry(mcp_cache_ttl_s=0.0)
        lc_tool = reg.get_tools_for_agent([tool_id])[0]
        out2 = lc_tool.invoke({"text": "hello"})
        assert "echo:hello" in str(out2)
    finally:
        delete_server(server_id)

