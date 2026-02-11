"""Tower persistence layer: tables + CRUD for runs, tickets, events, effects.

All Tower tables are created via init_tower_tables() called from lifespan.
Uses the same Postgres connection pattern as src/aps/store.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_TOWER_TABLES_SQL = """

-- Run registry: one row per durable workflow execution
CREATE TABLE IF NOT EXISTS tower_runs (
    run_id          TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL DEFAULT 'default',
    status          TEXT NOT NULL DEFAULT 'queued',
    priority        INT NOT NULL DEFAULT 5,
    run_name        TEXT,
    input_state     JSONB NOT NULL DEFAULT '{}'::JSONB,
    metadata        JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    last_checkpoint_id TEXT,
    last_ticket_id  BIGINT,
    last_error      TEXT
);

CREATE INDEX IF NOT EXISTS idx_tower_runs_status
    ON tower_runs (status, priority DESC, updated_at);

-- Append-only event timeline for each run
CREATE TABLE IF NOT EXISTS tower_run_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tower_events_run
    ON tower_run_events (run_id, id);

-- HITL tickets: structured approval interrupts
CREATE TABLE IF NOT EXISTS tower_tickets (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    ticket_type     TEXT NOT NULL DEFAULT 'tool_call',
    risk_level      TEXT NOT NULL DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'pending',
    proposed_action JSONB NOT NULL DEFAULT '{}'::JSONB,
    context_pack    JSONB NOT NULL DEFAULT '{}'::JSONB,
    decision_payload JSONB,
    checkpoint_id   TEXT,
    interrupt_id    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at      TIMESTAMPTZ,
    decided_by      TEXT,
    expires_at      TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_tower_tickets_run
    ON tower_tickets (run_id);
CREATE INDEX IF NOT EXISTS idx_tower_tickets_status
    ON tower_tickets (status, created_at DESC);

-- Exactly-once side effect tracking
CREATE TABLE IF NOT EXISTS tower_effects (
    effect_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    params_hash     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'prepared',
    prepared_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    result_payload  JSONB NOT NULL DEFAULT '{}'::JSONB,
    ticket_id       BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    committed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tower_effects_run
    ON tower_effects (run_id, created_at DESC);

-- Dead letter queue for unprocessable Redis Streams messages
CREATE TABLE IF NOT EXISTS bus_dead_letters (
    id          BIGSERIAL PRIMARY KEY,
    stream      TEXT NOT NULL,
    entry_id    TEXT NOT NULL,
    msg_type    TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (stream, entry_id)
);

-- Holly Grace conversation sessions
CREATE TABLE IF NOT EXISTS holly_sessions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL UNIQUE,
    messages        JSONB NOT NULL DEFAULT '[]'::JSONB,
    metadata        JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_count   INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_holly_sessions_updated
    ON holly_sessions (updated_at DESC);

-- Holly Grace notification queue (events waiting to be surfaced)
CREATE TABLE IF NOT EXISTS holly_notifications (
    id              BIGSERIAL PRIMARY KEY,
    msg_type        TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::JSONB,
    priority        TEXT NOT NULL DEFAULT 'normal',
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    surfaced_at     TIMESTAMPTZ,
    session_id      TEXT
);

CREATE INDEX IF NOT EXISTS idx_holly_notifications_status
    ON holly_notifications (status, priority, created_at);

"""


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(_DB_URL, autocommit=True, row_factory=dict_row)


def init_tower_tables() -> None:
    """Create all Tower tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute(_CREATE_TOWER_TABLES_SQL)
    logger.info("Tower tables initialized")


# ---------------------------------------------------------------------------
# Runs CRUD
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:16]}"


def create_run(
    *,
    run_id: str | None = None,
    workflow_id: str = "default",
    run_name: str | None = None,
    input_state: dict | None = None,
    metadata: dict | None = None,
    priority: int = 5,
    created_by: str | None = None,
) -> str:
    """Insert a new run in 'queued' status. Returns run_id."""
    if run_id is None:
        run_id = generate_run_id()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO tower_runs
               (run_id, workflow_id, status, priority, run_name,
                input_state, metadata, created_by)
               VALUES (%s, %s, 'queued', %s, %s, %s, %s, %s)""",
            (
                run_id,
                workflow_id,
                priority,
                run_name,
                json.dumps(input_state or {}, default=str),
                json.dumps(metadata or {}, default=str),
                created_by,
            ),
        )
    log_event(run_id, "run.queued", {"workflow_id": workflow_id})

    # Publish to message bus (fire-and-forget)
    from src.bus import STREAM_TOWER_EVENTS, publish
    publish(STREAM_TOWER_EVENTS, "run.queued", {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "status": "queued",
        "run_name": run_name,
        "created_by": created_by,
    }, source="tower.store")

    return run_id


def get_run(run_id: str) -> dict | None:
    """Fetch a single run by id."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tower_runs WHERE run_id = %s", (run_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def update_run_status(
    run_id: str,
    status: str,
    *,
    last_checkpoint_id: str | None = None,
    last_ticket_id: int | None = None,
    last_error: str | None = None,
) -> None:
    """Update run status + optional fields. Sets updated_at, started_at, finished_at as needed."""
    now = datetime.now(timezone.utc)
    sets = ["status = %s", "updated_at = %s"]
    vals: list[Any] = [status, now]

    if status == "running":
        sets.append("started_at = COALESCE(started_at, %s)")
        vals.append(now)
    # Accept both spellings; console/types currently prefer "cancelled".
    if status in ("completed", "failed", "cancelled", "canceled"):
        sets.append("finished_at = %s")
        vals.append(now)
    if last_checkpoint_id is not None:
        sets.append("last_checkpoint_id = %s")
        vals.append(last_checkpoint_id)
    if last_ticket_id is not None:
        sets.append("last_ticket_id = %s")
        vals.append(last_ticket_id)
    if last_error is not None:
        sets.append("last_error = %s")
        vals.append(last_error)

    vals.append(run_id)
    set_clauses = ", ".join(sets)
    sql = "UPDATE tower_runs SET " + set_clauses + " WHERE run_id = %s"
    with _get_conn() as conn:
        conn.execute(sql, tuple(vals))

    # Publish to message bus (fire-and-forget)
    from src.bus import STREAM_TOWER_EVENTS, publish
    publish(STREAM_TOWER_EVENTS, "run." + status, {
        "run_id": run_id,
        "status": status,
        "last_error": last_error,
    }, source="tower.store")


def list_runs(
    *,
    status: str | None = None,
    workflow_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List runs, optionally filtered by status/workflow_id."""
    conditions = []
    params: list[Any] = []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if workflow_id:
        conditions.append("workflow_id = %s")
        params.append(workflow_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    sql = "SELECT * FROM tower_runs " + where + " ORDER BY updated_at DESC LIMIT %s"
    with _get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_row_to_dict(r) for r in rows]


def claim_queued_run() -> dict | None:
    """Claim the highest-priority queued run. Returns run dict or None."""
    with _get_conn() as conn:
        row = conn.execute(
            """UPDATE tower_runs
               SET status = 'running',
                   started_at = COALESCE(started_at, NOW()),
                   updated_at = NOW()
               WHERE run_id = (
                   SELECT run_id FROM tower_runs
                   WHERE status IN ('queued')
                   ORDER BY priority DESC, updated_at
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED
               )
               RETURNING *""",
        ).fetchone()
    if row is None:
        return None
    run = _row_to_dict(row, conn)
    log_event(run["run_id"], "run.started")
    return run


def recover_stale_runs(max_age_minutes: int = 10) -> int:
    """Mark runs stuck in 'running' beyond max_age as 'failed'. Returns count."""
    with _get_conn() as conn:
        result = conn.execute(
            """UPDATE tower_runs
               SET status = 'failed',
                   last_error = 'Process crashed or timed out (recovered on startup)',
                   updated_at = NOW(),
                   finished_at = NOW()
               WHERE status = 'running'
                 AND started_at < NOW() - INTERVAL '%s minutes'""",
            (max_age_minutes,),
        )
        count = result.rowcount
    if count:
        logger.warning("Recovered %d stale tower runs", count)
    return count


# ---------------------------------------------------------------------------
# Events CRUD
# ---------------------------------------------------------------------------

def log_event(
    run_id: str,
    event_type: str,
    payload: dict | None = None,
) -> int:
    """Append an event to the run timeline. Returns event id."""
    with _get_conn() as conn:
        row = conn.execute(
            """INSERT INTO tower_run_events (run_id, event_type, payload)
               VALUES (%s, %s, %s) RETURNING id""",
            (run_id, event_type, json.dumps(payload or {}, default=str)),
        ).fetchone()
    return row["id"]


def get_events(
    run_id: str,
    *,
    after_id: int = 0,
    limit: int = 200,
) -> list[dict]:
    """Fetch events for a run, cursor-based pagination."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tower_run_events
               WHERE run_id = %s AND id > %s
               ORDER BY id LIMIT %s""",
            (run_id, after_id, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tickets CRUD
# ---------------------------------------------------------------------------

def create_ticket(
    *,
    run_id: str,
    ticket_type: str = "tool_call",
    risk_level: str = "medium",
    proposed_action: dict | None = None,
    context_pack: dict | None = None,
    checkpoint_id: str | None = None,
    interrupt_id: str | None = None,
) -> int:
    """Create a HITL ticket. Returns ticket id."""
    with _get_conn() as conn:
        row = conn.execute(
            """INSERT INTO tower_tickets
               (run_id, ticket_type, risk_level, proposed_action,
                context_pack, checkpoint_id, interrupt_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                run_id,
                ticket_type,
                risk_level,
                json.dumps(proposed_action or {}, default=str),
                json.dumps(context_pack or {}, default=str),
                checkpoint_id,
                interrupt_id,
            ),
        ).fetchone()
    ticket_id = row["id"]
    log_event(run_id, "ticket.created", {
        "ticket_id": ticket_id,
        "ticket_type": ticket_type,
        "risk_level": risk_level,
    })

    # Publish to message bus (fire-and-forget)
    from src.bus import STREAM_TOWER_TICKETS, publish
    publish(STREAM_TOWER_TICKETS, "ticket.created", {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "ticket_type": ticket_type,
        "risk_level": risk_level,
        "tldr": (context_pack or {}).get("tldr", "Approval required"),
        "proposed_action": proposed_action or {},
    }, source="tower.store")

    return ticket_id


def get_ticket(ticket_id: int) -> dict | None:
    """Fetch a single ticket by id."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tower_tickets WHERE id = %s", (ticket_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def decide_ticket(
    ticket_id: int,
    decision: str,
    *,
    decided_by: str = "console",
    decision_payload: dict | None = None,
    expected_checkpoint_id: str | None = None,
) -> dict:
    """Decide a ticket (approve/reject). Returns updated ticket.

    If expected_checkpoint_id is provided, validates against the ticket's
    checkpoint_id for optimistic concurrency. Raises ValueError on mismatch.
    """
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found")
    if ticket["status"] != "pending":
        raise ValueError(f"Ticket {ticket_id} is already {ticket['status']}")

    # Optimistic concurrency check
    if expected_checkpoint_id is not None:
        if ticket.get("checkpoint_id") != expected_checkpoint_id:
            raise ValueError(
                f"Stale ticket: expected checkpoint {expected_checkpoint_id}, "
                f"got {ticket.get('checkpoint_id')}"
            )

    status = "approved" if decision == "approve" else "rejected"
    now = datetime.now(timezone.utc)

    with _get_conn() as conn:
        conn.execute(
            """UPDATE tower_tickets
               SET status = %s, decided_at = %s, decided_by = %s,
                   decision_payload = %s
               WHERE id = %s""",
            (
                status,
                now,
                decided_by,
                json.dumps(decision_payload or {}, default=str),
                ticket_id,
            ),
        )

    log_event(ticket["run_id"], "ticket.decided", {
        "ticket_id": ticket_id,
        "decision": status,
        "decided_by": decided_by,
    })

    # Publish to message bus (fire-and-forget)
    from src.bus import STREAM_TOWER_TICKETS, publish
    publish(STREAM_TOWER_TICKETS, "ticket.decided", {
        "ticket_id": ticket_id,
        "run_id": ticket["run_id"],
        "status": status,
        "decided_by": decided_by,
    }, source="tower.store")

    return {**ticket, "status": status, "decided_at": now, "decided_by": decided_by}


def list_tickets(
    *,
    status: str | None = "pending",
    risk_level: str | None = None,
    run_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tickets with optional filters."""
    conditions = []
    params: list[Any] = []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if risk_level:
        conditions.append("risk_level = %s")
        params.append(risk_level)
    if run_id:
        conditions.append("run_id = %s")
        params.append(run_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with _get_conn() as conn:
        rows = conn.execute(
            f"""SELECT * FROM tower_tickets {where}
                ORDER BY created_at DESC LIMIT %s""",
            tuple(params),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def expire_stale_tickets() -> int:
    """Mark expired pending tickets. Returns count."""
    with _get_conn() as conn:
        result = conn.execute(
            """UPDATE tower_tickets
               SET status = 'expired'
               WHERE status = 'pending' AND expires_at < NOW()"""
        )
    return result.rowcount


# ---------------------------------------------------------------------------
# Effects CRUD (exactly-once side effects)
# ---------------------------------------------------------------------------

def compute_effect_id(run_id: str, tool_name: str, params: dict) -> str:
    """Deterministic effect id from run + tool + params."""
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    raw = f"{run_id}:{tool_name}:{params_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def prepare_effect(
    *,
    run_id: str,
    tool_name: str,
    params: dict,
    ticket_id: int | None = None,
) -> str:
    """Prepare an effect (idempotent insert). Returns effect_id."""
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    effect_id = compute_effect_id(run_id, tool_name, params)

    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO tower_effects
               (effect_id, run_id, tool_name, params_hash, status,
                prepared_payload, ticket_id)
               VALUES (%s, %s, %s, %s, 'prepared', %s, %s)
               ON CONFLICT (effect_id) DO NOTHING""",
            (
                effect_id,
                run_id,
                tool_name,
                params_hash,
                json.dumps(params, default=str),
                ticket_id,
            ),
        )
    return effect_id


def commit_effect(effect_id: str, result: dict) -> None:
    """Mark an effect as committed with its result."""
    with _get_conn() as conn:
        conn.execute(
            """UPDATE tower_effects
               SET status = 'committed',
                   result_payload = %s,
                   committed_at = NOW()
               WHERE effect_id = %s AND status = 'prepared'""",
            (json.dumps(result, default=str), effect_id),
        )


def abort_effect(effect_id: str) -> None:
    """Mark an effect as aborted (rejected)."""
    with _get_conn() as conn:
        conn.execute(
            """UPDATE tower_effects
               SET status = 'aborted'
               WHERE effect_id = %s AND status = 'prepared'""",
            (effect_id,),
        )


def get_effect(effect_id: str) -> dict | None:
    """Fetch an effect by id."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tower_effects WHERE effect_id = %s", (effect_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: Any, conn: Any = None) -> dict:
    """Convert a psycopg row to dict. With dict_row factory, rows are already dicts.

    Also converts datetime objects to ISO strings for JSON serialization.
    """
    if row is None:
        return {}
    if isinstance(row, dict):
        d = row
    elif hasattr(row, "keys"):
        d = dict(row)
    else:
        return {}
    # Convert datetime objects to ISO strings for JSON serialization
    from datetime import datetime, date
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d
