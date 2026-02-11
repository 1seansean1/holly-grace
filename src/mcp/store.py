"""PostgreSQL persistence for MCP servers and tools."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.mcp.naming import mcp_tool_id

logger = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
)


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(_DB_URL, autocommit=True, row_factory=dict_row)


_CREATE_MCP_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS mcp_servers (
    server_id            TEXT PRIMARY KEY,
    display_name         TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    transport            TEXT NOT NULL,
    enabled              BOOLEAN NOT NULL DEFAULT TRUE,

    -- stdio transport
    stdio_command        TEXT,
    stdio_args           JSONB NOT NULL DEFAULT '[]'::JSONB,
    stdio_cwd            TEXT,
    env_allow            TEXT[] NOT NULL DEFAULT '{}',
    env_overrides        JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- http transport (Phase 2)
    http_url             TEXT,
    http_headers_template JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- health/cache
    last_health_status   TEXT NOT NULL DEFAULT 'unknown',
    last_health_error    TEXT NOT NULL DEFAULT '',
    last_health_at       TIMESTAMPTZ,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled
    ON mcp_servers (enabled, updated_at DESC);

CREATE TABLE IF NOT EXISTS mcp_tools (
    tool_id          TEXT PRIMARY KEY,
    server_id        TEXT NOT NULL REFERENCES mcp_servers(server_id) ON DELETE CASCADE,
    mcp_tool_name    TEXT NOT NULL,
    display_name     TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL DEFAULT 'mcp',
    input_schema     JSONB NOT NULL DEFAULT '{}'::JSONB,
    enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    risk_level       TEXT NOT NULL DEFAULT 'medium',
    discovered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(server_id, mcp_tool_name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_server
    ON mcp_tools (server_id, enabled, last_seen_at DESC);
"""


def init_mcp_tables() -> None:
    """Create MCP tables if they don't exist."""
    try:
        with _get_conn() as conn:
            conn.execute(_CREATE_MCP_TABLES_SQL)
        logger.info("MCP tables initialized")
    except Exception:
        logger.warning("Failed to init MCP tables", exc_info=True)


# ---------------------------------------------------------------------------
# Servers CRUD
# ---------------------------------------------------------------------------


def list_servers(*, enabled_only: bool | None = None) -> list[dict[str, Any]]:
    where = ""
    if enabled_only is True:
        where = "WHERE enabled = TRUE"
    elif enabled_only is False:
        where = "WHERE enabled = FALSE"

    with _get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM mcp_servers {where} ORDER BY updated_at DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def get_server(server_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE server_id = %s",
            (server_id,),
        ).fetchone()
    return dict(row) if row else None


def create_server(
    *,
    server_id: str,
    display_name: str,
    transport: str,
    description: str = "",
    enabled: bool = True,
    stdio_command: str | None = None,
    stdio_args: list[str] | None = None,
    stdio_cwd: str | None = None,
    env_allow: list[str] | None = None,
    env_overrides: dict[str, Any] | None = None,
    http_url: str | None = None,
    http_headers_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO mcp_servers
               (server_id, display_name, description, transport, enabled,
                stdio_command, stdio_args, stdio_cwd, env_allow, env_overrides,
                http_url, http_headers_template, updated_at)
               VALUES (%s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s,
                       %s, %s, %s)""",
            (
                server_id,
                display_name,
                description or "",
                transport,
                bool(enabled),
                stdio_command,
                json.dumps(stdio_args or []),
                stdio_cwd,
                (env_allow or []),
                json.dumps(env_overrides or {}, default=str),
                http_url,
                json.dumps(http_headers_template or {}, default=str),
                now,
            ),
        )
    return get_server(server_id) or {}


def update_server(server_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    if not fields:
        return get_server(server_id)

    allowed = {
        "display_name",
        "description",
        "transport",
        "enabled",
        "stdio_command",
        "stdio_args",
        "stdio_cwd",
        "env_allow",
        "env_overrides",
        "http_url",
        "http_headers_template",
    }
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "stdio_args":
            sets.append("stdio_args = %s")
            vals.append(json.dumps(v or []))
            continue
        if k in ("env_overrides", "http_headers_template"):
            sets.append(f"{k} = %s")
            vals.append(json.dumps(v or {}, default=str))
            continue

        sets.append(f"{k} = %s")
        vals.append(v)

    sets.append("updated_at = %s")
    vals.append(datetime.now(timezone.utc))

    if not sets:
        return get_server(server_id)

    vals.append(server_id)
    sql = "UPDATE mcp_servers SET " + ", ".join(sets) + " WHERE server_id = %s"
    with _get_conn() as conn:
        conn.execute(sql, tuple(vals))
    return get_server(server_id)


def delete_server(server_id: str) -> bool:
    with _get_conn() as conn:
        res = conn.execute(
            "DELETE FROM mcp_servers WHERE server_id = %s",
            (server_id,),
        )
    return bool(res.rowcount)


def update_server_health(
    server_id: str,
    *,
    status: str,
    error: str = "",
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """UPDATE mcp_servers
               SET last_health_status = %s,
                   last_health_error = %s,
                   last_health_at = NOW(),
                   updated_at = NOW()
               WHERE server_id = %s""",
            (status, error[:2000], server_id),
        )


# ---------------------------------------------------------------------------
# Tools CRUD
# ---------------------------------------------------------------------------


def list_tools(server_id: str) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, s.transport
               FROM mcp_tools t
               JOIN mcp_servers s ON s.server_id = t.server_id
               WHERE t.server_id = %s
               ORDER BY t.enabled DESC, t.display_name ASC""",
            (server_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_enabled_tools() -> list[dict[str, Any]]:
    """List enabled MCP tools where the server is enabled."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, s.transport
               FROM mcp_tools t
               JOIN mcp_servers s ON s.server_id = t.server_id
               WHERE t.enabled = TRUE AND s.enabled = TRUE
               ORDER BY t.category ASC, t.display_name ASC""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_tool(tool_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT t.*, s.transport
               FROM mcp_tools t
               JOIN mcp_servers s ON s.server_id = t.server_id
               WHERE t.tool_id = %s""",
            (tool_id,),
        ).fetchone()
    return dict(row) if row else None


def update_tool(tool_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    if not fields:
        return get_tool(tool_id)

    allowed = {"display_name", "description", "category", "enabled", "risk_level"}
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        vals.append(v)

    if not sets:
        return get_tool(tool_id)

    vals.append(tool_id)
    sql = "UPDATE mcp_tools SET " + ", ".join(sets) + " WHERE tool_id = %s"
    with _get_conn() as conn:
        conn.execute(sql, tuple(vals))
    return get_tool(tool_id)


def upsert_tools_for_server(server_id: str, tools: list[dict[str, Any]]) -> int:
    """Upsert tools discovered from an MCP server. Returns count processed."""
    if not tools:
        return 0

    rows = 0
    with _get_conn() as conn:
        for tool in tools:
            tool_name = str(tool.get("name", "")).strip()
            if not tool_name:
                continue

            tool_id = mcp_tool_id(server_id, tool_name)
            description = str(tool.get("description", "") or "")
            input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}

            conn.execute(
                """INSERT INTO mcp_tools
                   (tool_id, server_id, mcp_tool_name, display_name, description,
                    category, input_schema, enabled, risk_level, discovered_at, last_seen_at)
                   VALUES (%s, %s, %s, %s, %s,
                           %s, %s, TRUE, 'medium', NOW(), NOW())
                   ON CONFLICT (tool_id) DO UPDATE
                     SET description = EXCLUDED.description,
                         input_schema = EXCLUDED.input_schema,
                         last_seen_at = NOW()""",
                (
                    tool_id,
                    server_id,
                    tool_name,
                    tool_name,
                    description,
                    "mcp",
                    json.dumps(input_schema or {}, default=str),
                ),
            )
            rows += 1

    return rows

