from __future__ import annotations

from src.mcp.naming import mcp_tool_id, sanitize_identifier


def test_sanitize_identifier_basic():
    assert sanitize_identifier("Gmail") == "gmail"
    assert sanitize_identifier(" send-email ") == "send_email"
    assert sanitize_identifier("a__b") == "a_b"
    assert sanitize_identifier("") == "tool"


def test_mcp_tool_id():
    assert mcp_tool_id("gmail", "send_email") == "mcp_gmail_send_email"
    assert mcp_tool_id("Gmail", "send-email") == "mcp_gmail_send_email"

