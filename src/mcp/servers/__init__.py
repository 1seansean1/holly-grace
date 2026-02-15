"""Built-in MCP servers — pre-seeded on startup."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_github_reader() -> None:
    """Register the github-reader MCP server and sync its tools.

    Idempotent — skips if the server already exists.
    """
    from src.mcp.store import create_server, get_server, update_server
    from src.mcp.manager import get_mcp_manager

    server_id = "github-reader"

    existing = get_server(server_id)
    if existing is not None:
        # Fix command if it was registered with wrong binary name
        if existing.get("stdio_command") != "python3":
            update_server(server_id, {"stdio_command": "python3"})
            logger.info("MCP server '%s' updated stdio_command to python3", server_id)
        else:
            logger.debug("MCP server '%s' already registered, skipping seed", server_id)
    else:
        create_server(
            server_id=server_id,
            display_name="GitHub Reader",
            description="Read-only access to the ecom-agents GitHub repo via REST API",
            transport="stdio",
            enabled=True,
            stdio_command="python3",
            stdio_args=["-m", "src.mcp.servers.github_reader"],
            env_allow=["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "GITHUB_BRANCH"],
        )
        logger.info("MCP server '%s' registered", server_id)

    try:
        result = get_mcp_manager().sync_tools(server_id)
        logger.info("MCP server '%s' tools synced: %s", server_id, result)
    except Exception:
        logger.warning("Failed to sync tools for '%s' (server registered but tools not yet available)", server_id, exc_info=True)


def _seed_simple_mcp(
    server_id: str,
    display_name: str,
    description: str,
    module: str,
    env_allow: list[str],
) -> None:
    """Helper to seed an MCP server. Idempotent."""
    from src.mcp.store import create_server, get_server
    from src.mcp.manager import get_mcp_manager

    existing = get_server(server_id)
    if existing is not None:
        logger.debug("MCP server '%s' already registered, skipping seed", server_id)
    else:
        create_server(
            server_id=server_id,
            display_name=display_name,
            description=description,
            transport="stdio",
            enabled=True,
            stdio_command="python3",
            stdio_args=["-m", module],
            env_allow=env_allow,
        )
        logger.info("MCP server '%s' registered", server_id)

    try:
        result = get_mcp_manager().sync_tools(server_id)
        logger.info("MCP server '%s' tools synced: %s", server_id, result)
    except Exception:
        logger.warning("Failed to sync tools for '%s'", server_id, exc_info=True)


def seed_aws_ecs() -> None:
    """Register the aws-ecs MCP server (ECS/CloudWatch observability)."""
    _seed_simple_mcp(
        server_id="aws-ecs",
        display_name="AWS ECS",
        description="AWS ECS service observability — service status, tasks, logs, task definitions",
        module="src.mcp.servers.aws_ecs",
        env_allow=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION",
                    "ECS_CLUSTER", "ECS_SERVICE", "ECS_LOG_GROUP"],
    )


def seed_api_costs() -> None:
    """Register the api-costs MCP server (LLM cost tracking)."""
    _seed_simple_mcp(
        server_id="api-costs",
        display_name="API Costs",
        description="LLM API cost tracking — Anthropic, OpenAI, and combined cost views",
        module="src.mcp.servers.api_costs",
        env_allow=[],
    )


def seed_shopify_analytics() -> None:
    """Register the shopify-analytics MCP server."""
    _seed_simple_mcp(
        server_id="shopify-analytics",
        display_name="Shopify Analytics",
        description="Shopify store analytics — orders, products, customers, revenue trends",
        module="src.mcp.servers.shopify_analytics",
        env_allow=["SHOPIFY_STORE", "SHOPIFY_ACCESS_TOKEN"],
    )

def seed_phone_control() -> None:
    """Register the phone-control MCP server (22 ADB-based phone tools)."""
    _seed_simple_mcp(
        server_id="phone-control",
        display_name="Phone Control",
        description="Android phone control via ADB — status, shell, unlock, SMS, screenshots, calls, file transfer, EC2 relay",
        module="src.mcp.servers.phone_control",
        env_allow=["ADB_PATH", "ANDROID_WIFI_IP", "ANDROID_PIN",
                    "EC2_RELAY_PUBLIC_IP", "EC2_RELAY_USER", "EC2_RELAY_KEY"],
    )


def seed_github_writer() -> None:
    """Register the github-writer MCP server and sync its tools.

    Idempotent — skips if the server already exists.
    """
    from src.mcp.store import create_server, get_server, update_server
    from src.mcp.manager import get_mcp_manager

    server_id = "github-writer"

    existing = get_server(server_id)
    if existing is not None:
        if existing.get("stdio_command") != "python3":
            update_server(server_id, {"stdio_command": "python3"})
            logger.info("MCP server '%s' updated stdio_command to python3", server_id)
        else:
            logger.debug("MCP server '%s' already registered, skipping seed", server_id)
    else:
        create_server(
            server_id=server_id,
            display_name="GitHub Writer",
            description="Read-write access to the ecom-agents GitHub repo via REST API",
            transport="stdio",
            enabled=True,
            stdio_command="python3",
            stdio_args=["-m", "src.mcp.servers.github_writer"],
            env_allow=["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "GITHUB_BRANCH"],
        )
        logger.info("MCP server '%s' registered", server_id)

    try:
        result = get_mcp_manager().sync_tools(server_id)
        logger.info("MCP server '%s' tools synced: %s", server_id, result)
    except Exception:
        logger.warning("Failed to sync tools for '%s' (server registered but tools not yet available)", server_id, exc_info=True)
