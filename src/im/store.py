"""CRUD operations for IM workspace tables.

Pattern matches src/hierarchy/store.py — uses same Postgres connection.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.im.models import IMWorkspace

logger = logging.getLogger(__name__)


def _get_conn():
    """Reuse the APS connection helper."""
    from src.aps.store import _get_conn as aps_conn
    return aps_conn()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
    """Create IM workspace tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS im_workspaces (
                workspace_id TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                version INTEGER NOT NULL DEFAULT 1,
                stage TEXT NOT NULL DEFAULT 'created',
                raw_intent TEXT NOT NULL DEFAULT '',
                goal_tuple JSONB NOT NULL DEFAULT '{}',
                predicates JSONB NOT NULL DEFAULT '[]',
                predicate_blocks JSONB NOT NULL DEFAULT '[]',
                cross_block_coupling JSONB NOT NULL DEFAULT '[]',
                coupling_matrix JSONB NOT NULL DEFAULT '{}',
                codimension JSONB NOT NULL DEFAULT '{}',
                rank_budget JSONB NOT NULL DEFAULT '{}',
                memory JSONB NOT NULL DEFAULT '{}',
                assignment JSONB NOT NULL DEFAULT '{}',
                workflow JSONB NOT NULL DEFAULT '{}',
                feasibility JSONB NOT NULL DEFAULT '{}',
                created_by TEXT NOT NULL DEFAULT 'holly_grace',
                metadata JSONB NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS im_workspace_audit (
                id SERIAL PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES im_workspaces(workspace_id),
                stage TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                input_summary TEXT NOT NULL DEFAULT '',
                output_summary TEXT NOT NULL DEFAULT '',
                human_decision TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_im_ws_audit_ws
            ON im_workspace_audit(workspace_id)
        """)


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

def create_workspace(raw_intent: str, created_by: str = "holly_grace",
                     metadata: dict | None = None) -> str:
    """Create a new IM workspace. Returns the workspace_id."""
    ws_id = f"im_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO im_workspaces
            (workspace_id, created_at, updated_at, raw_intent, created_by, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (ws_id, now, now, raw_intent, created_by,
             json.dumps(metadata or {})),
        )
    return ws_id


def get_workspace(workspace_id: str) -> IMWorkspace | None:
    """Fetch a workspace by ID."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM im_workspaces WHERE workspace_id = %s",
            (workspace_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_workspace(row)


def list_workspaces(limit: int = 50) -> list[dict]:
    """List all workspaces (summary view)."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT workspace_id, created_at, updated_at, stage, raw_intent, created_by "
            "FROM im_workspaces ORDER BY updated_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [
        {
            "workspace_id": r[0],
            "created_at": r[1].isoformat() if r[1] else None,
            "updated_at": r[2].isoformat() if r[2] else None,
            "stage": r[3],
            "raw_intent": r[4][:120] if r[4] else "",
            "created_by": r[5],
        }
        for r in rows
    ]


def update_workspace(ws: IMWorkspace) -> None:
    """Write the full workspace back to the database."""
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        conn.execute(
            """UPDATE im_workspaces SET
                updated_at = %s,
                version = version + 1,
                stage = %s,
                raw_intent = %s,
                goal_tuple = %s,
                predicates = %s,
                predicate_blocks = %s,
                cross_block_coupling = %s,
                coupling_matrix = %s,
                codimension = %s,
                rank_budget = %s,
                memory = %s,
                assignment = %s,
                workflow = %s,
                feasibility = %s,
                metadata = %s
            WHERE workspace_id = %s""",
            (
                now, ws.stage, ws.raw_intent,
                json.dumps(ws.goal_tuple),
                json.dumps(ws.predicates),
                json.dumps(ws.predicate_blocks),
                json.dumps(ws.cross_block_coupling),
                json.dumps(ws.coupling_matrix),
                json.dumps(ws.codimension),
                json.dumps(ws.rank_budget),
                json.dumps(ws.memory),
                json.dumps(ws.assignment),
                json.dumps(ws.workflow),
                json.dumps(ws.feasibility),
                json.dumps(ws.metadata),
                ws.workspace_id,
            ),
        )


def delete_workspace(workspace_id: str) -> None:
    """Delete a workspace and its audit trail."""
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM im_workspace_audit WHERE workspace_id = %s",
            (workspace_id,),
        )
        conn.execute(
            "DELETE FROM im_workspaces WHERE workspace_id = %s",
            (workspace_id,),
        )


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

def log_audit(
    workspace_id: str,
    stage: str,
    tool_name: str,
    input_summary: str = "",
    output_summary: str = "",
    human_decision: str | None = None,
) -> None:
    """Record a tool call in the workspace audit trail."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO im_workspace_audit
            (workspace_id, stage, tool_name, input_summary, output_summary, human_decision)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (workspace_id, stage, tool_name, input_summary[:500],
             output_summary[:500], human_decision),
        )


def get_audit_trail(workspace_id: str, limit: int = 100) -> list[dict]:
    """Get the audit trail for a workspace."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, workspace_id, stage, tool_name, input_summary, "
            "output_summary, human_decision, created_at "
            "FROM im_workspace_audit WHERE workspace_id = %s "
            "ORDER BY created_at ASC LIMIT %s",
            (workspace_id, limit),
        ).fetchall()
    return [
        {
            "id": r[0],
            "workspace_id": r[1],
            "stage": r[2],
            "tool_name": r[3],
            "input_summary": r[4],
            "output_summary": r[5],
            "human_decision": r[6],
            "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_workspace(row) -> IMWorkspace:
    """Convert a database row to an IMWorkspace."""
    def _parse_json(val):
        if val is None:
            return {}
        if isinstance(val, (dict, list)):
            return val
        return json.loads(val)

    return IMWorkspace(
        workspace_id=row[0],
        created_at=row[1],
        updated_at=row[2],
        version=row[3],
        stage=row[4],
        raw_intent=row[5],
        goal_tuple=_parse_json(row[6]),
        predicates=_parse_json(row[7]) if isinstance(_parse_json(row[7]), list) else [],
        predicate_blocks=_parse_json(row[8]) if isinstance(_parse_json(row[8]), list) else [],
        cross_block_coupling=_parse_json(row[9]) if isinstance(_parse_json(row[9]), list) else [],
        coupling_matrix=_parse_json(row[10]),
        codimension=_parse_json(row[11]),
        rank_budget=_parse_json(row[12]),
        memory=_parse_json(row[13]),
        assignment=_parse_json(row[14]),
        workflow=_parse_json(row[15]),
        feasibility=_parse_json(row[16]),
        created_by=row[17],
        metadata=_parse_json(row[18]),
    )
