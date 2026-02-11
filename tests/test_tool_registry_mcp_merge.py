from __future__ import annotations

from src.tool_registry import ToolRegistry


def test_tool_registry_merges_mcp_tools(monkeypatch):
    def fake_list_enabled_tools():
        return [
            {
                "tool_id": "mcp_gmail_send_email",
                "server_id": "gmail",
                "mcp_tool_name": "send_email",
                "display_name": "Send Email",
                "description": "Send an email",
                "category": "mcp",
                "transport": "stdio",
                "input_schema": {
                    "type": "object",
                    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["subject", "body"],
                },
            }
        ]

    monkeypatch.setattr("src.mcp.store.list_enabled_tools", fake_list_enabled_tools)

    reg = ToolRegistry(mcp_cache_ttl_s=0.0)
    mcp_defn = reg.get("mcp_gmail_send_email")
    assert mcp_defn is not None
    assert mcp_defn.provider == "mcp"
    assert mcp_defn.server_id == "gmail"
    assert mcp_defn.mcp_tool_name == "send_email"

    tools = reg.get_tools_for_agent(["mcp_gmail_send_email"])
    assert len(tools) == 1
    assert tools[0].name == "mcp_gmail_send_email"

