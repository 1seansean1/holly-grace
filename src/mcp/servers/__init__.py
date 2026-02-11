"""Built-in MCP servers — pre-seeded on startup."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_github_reader() -> None:
    """Register the github-reader MCP server and sync its tools.

    Idempotent — skips if the server already exists.
    """
    from src.mcp.store import create_server, get_server
    from src.mcp.manager import get_mcp_manager

    server_id = "github-reader"

    if get_server(server_id) is not None:
        logger.debug("MCP server '%s' already registered, skipping seed", server_id)
        return

    create_server(
        server_id=server_id,
        display_name="GitHub Reader",
        description="Read-only access to the ecom-agents GitHub repo via REST API",
        transport="stdio",
        enabled=True,
        stdio_command="python",
        stdio_args=["-m", "src.mcp.servers.github_reader"],
        env_allow=["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "GITHUB_BRANCH"],
    )
    logger.info("MCP server '%s' registered", server_id)

    try:
        result = get_mcp_manager().sync_tools(server_id)
        logger.info("MCP server '%s' tools synced: %s", server_id, result)
    except Exception:
        logger.warning("Failed to sync tools for '%s' (server registered but tools not yet available)", server_id, exc_info=True)
