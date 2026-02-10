"""PostgreSQL persistence for APS observations, metrics, switches, and theta cache.

Uses psycopg (sync) — the same driver already installed for LangGraph checkpoints.
All functions are safe to call from sync threads (APScheduler, instrument wrapper).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import psycopg

logger = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://holly:holly_dev_password@localhost:5434/holly_grace"
)


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(_DB_URL, autocommit=True)


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS aps_observations (
    id              BIGSERIAL PRIMARY KEY,
    channel_id      VARCHAR(16) NOT NULL,
    theta_id        VARCHAR(64) NOT NULL,
    sigma_in        VARCHAR(128) NOT NULL,
    sigma_out       VARCHAR(128) NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms      REAL,
    cost_usd        REAL DEFAULT 0.0,
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    total_tokens    INTEGER,
    model_id        VARCHAR(64),
    trace_id        UUID,
    path_id         VARCHAR(128),
    run_metadata    JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_aps_obs_channel_time
    ON aps_observations (channel_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aps_obs_theta_time
    ON aps_observations (theta_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aps_obs_trace
    ON aps_observations (trace_id);

CREATE TABLE IF NOT EXISTS aps_metrics (
    id              BIGSERIAL PRIMARY KEY,
    channel_id      VARCHAR(16) NOT NULL,
    theta_id        VARCHAR(64) NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    p_fail          REAL NOT NULL,
    p_fail_ucb      REAL,
    mutual_info     REAL NOT NULL,
    capacity        REAL NOT NULL,
    eta_usd         REAL NOT NULL,
    eta_token       REAL,
    eta_time        REAL,
    n_observations  INTEGER NOT NULL,
    total_cost_usd  REAL DEFAULT 0.0,
    total_tokens    INTEGER DEFAULT 0,
    total_time_s    REAL DEFAULT 0.0,
    confusion_matrix JSONB,
    window_seconds  REAL
);

CREATE INDEX IF NOT EXISTS idx_aps_metrics_channel_time
    ON aps_metrics (channel_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS aps_theta_switches (
    id              BIGSERIAL PRIMARY KEY,
    channel_id      VARCHAR(16) NOT NULL,
    from_theta      VARCHAR(64) NOT NULL,
    to_theta        VARCHAR(64) NOT NULL,
    direction       VARCHAR(16) NOT NULL,
    from_level      INTEGER NOT NULL,
    to_level        INTEGER NOT NULL,
    model_changed   BOOLEAN DEFAULT FALSE,
    protocol_changed BOOLEAN DEFAULT FALSE,
    trigger_p_fail  REAL NOT NULL,
    trigger_epsilon REAL NOT NULL,
    goal_id         VARCHAR(64) NOT NULL,
    switched_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aps_switches_channel
    ON aps_theta_switches (channel_id, switched_at DESC);

CREATE TABLE IF NOT EXISTS agent_configs (
    agent_id        TEXT PRIMARY KEY,
    channel_id      TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    model_id        TEXT NOT NULL,
    system_prompt   TEXT NOT NULL,
    tool_ids        TEXT[] DEFAULT '{}',
    is_builtin      BOOLEAN DEFAULT FALSE,
    version         INTEGER NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS agent_config_versions (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    version         INTEGER NOT NULL,
    channel_id      TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    model_id        TEXT NOT NULL,
    system_prompt   TEXT NOT NULL,
    tool_ids        TEXT[] DEFAULT '{}',
    change_summary  TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_id, version)
);
CREATE INDEX IF NOT EXISTS idx_agent_versions_agent
    ON agent_config_versions (agent_id, version DESC);

CREATE TABLE IF NOT EXISTS tool_registry (
    tool_id         TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    module_path     TEXT NOT NULL,
    function_name   TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    workflow_id     TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    version         INTEGER NOT NULL DEFAULT 1,
    is_active       BOOLEAN DEFAULT FALSE,
    is_builtin      BOOLEAN DEFAULT FALSE,
    definition      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS workflow_versions (
    id              BIGSERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    version         INTEGER NOT NULL,
    definition      JSONB NOT NULL,
    change_summary  TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workflow_id, version)
);
CREATE INDEX IF NOT EXISTS idx_workflow_versions
    ON workflow_versions (workflow_id, version DESC);

CREATE TABLE IF NOT EXISTS agent_efficacy (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    channel_id      VARCHAR(16) NOT NULL,
    version         INTEGER NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    invocations     INTEGER DEFAULT 0,
    successes       INTEGER DEFAULT 0,
    failures        INTEGER DEFAULT 0,
    avg_latency_ms  REAL DEFAULT 0,
    total_cost_usd  REAL DEFAULT 0,
    p_fail          REAL DEFAULT 0,
    capacity        REAL DEFAULT 0,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_efficacy ON agent_efficacy (agent_id, version, period_start DESC);

CREATE TABLE IF NOT EXISTS aps_theta_cache (
    id              BIGSERIAL PRIMARY KEY,
    channel_id      VARCHAR(16) NOT NULL,
    context_hash    VARCHAR(128) NOT NULL,
    theta_id        VARCHAR(64) NOT NULL,
    p_fail_at_cache REAL NOT NULL,
    cached_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hit_count       INTEGER DEFAULT 0,
    UNIQUE(channel_id, context_hash)
);

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id              BIGSERIAL PRIMARY KEY,
    job_id          TEXT NOT NULL,
    payload         JSONB NOT NULL,
    error           TEXT NOT NULL,
    attempts        INTEGER DEFAULT 1,
    max_attempts    INTEGER DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_retry_at   TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_dlq_pending
    ON dead_letter_queue (next_retry_at) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS approval_queue (
    id              BIGSERIAL PRIMARY KEY,
    action_type     TEXT NOT NULL,
    agent_id        TEXT,
    tool_name       TEXT NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}'::JSONB,
    risk_level      TEXT NOT NULL DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at      TIMESTAMPTZ DEFAULT NULL,
    decided_by      TEXT DEFAULT NULL,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 hour'),
    reason          TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_approval_pending
    ON approval_queue (status, requested_at DESC) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS execution_budgets (
    id              BIGSERIAL PRIMARY KEY,
    thread_id       TEXT NOT NULL,
    iterations      INTEGER DEFAULT 0,
    total_cost_usd  REAL DEFAULT 0.0,
    total_tokens    INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    terminated_at   TIMESTAMPTZ DEFAULT NULL,
    termination_reason TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS eval_results (
    id              BIGSERIAL PRIMARY KEY,
    suite_id        TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    passed          BOOLEAN NOT NULL,
    score           REAL DEFAULT 0.0,
    latency_ms      REAL DEFAULT 0.0,
    cost_usd        REAL DEFAULT 0.0,
    output_preview  TEXT DEFAULT '',
    error           TEXT DEFAULT '',
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_eval_results
    ON eval_results (suite_id, run_at DESC);

CREATE TABLE IF NOT EXISTS graph_checkpoints (
    thread_id       TEXT NOT NULL,
    checkpoint_id   TEXT NOT NULL,
    parent_id       TEXT DEFAULT NULL,
    channel_values  JSONB NOT NULL DEFAULT '{}'::JSONB,
    metadata        JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
    ON graph_checkpoints (thread_id, created_at DESC);

-- Morphogenetic Agency tables (v5)
CREATE TABLE IF NOT EXISTS morphogenetic_goals (
    id              BIGSERIAL PRIMARY KEY,
    goal_id         VARCHAR(64) UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    failure_predicate TEXT NOT NULL,
    epsilon_g       REAL NOT NULL,
    horizon_t       INTEGER NOT NULL,
    observation_map JSONB NOT NULL DEFAULT '[]'::JSONB,
    formalization_level VARCHAR(20) DEFAULT 'g1_spec',
    g0_description  TEXT DEFAULT '',
    primary_tier    INTEGER DEFAULT 0,
    priority        INTEGER DEFAULT 5,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assembly_cache (
    id                  BIGSERIAL PRIMARY KEY,
    competency_id       VARCHAR(128) UNIQUE NOT NULL,
    tier                INTEGER NOT NULL,
    competency_type     VARCHAR(32) NOT NULL,
    channel_id          VARCHAR(16),
    goal_id             VARCHAR(64),
    adaptation          JSONB NOT NULL DEFAULT '{}'::JSONB,
    context_fingerprint VARCHAR(128),
    reuse_count         INTEGER DEFAULT 0,
    success_rate        REAL DEFAULT 1.0,
    assembly_index      REAL DEFAULT 0.0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_assembly_channel_ctx
    ON assembly_cache (channel_id, context_fingerprint);

CREATE TABLE IF NOT EXISTS developmental_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_at     TIMESTAMPTZ DEFAULT NOW(),
    ai_proxy        REAL,
    clc_horizon     INTEGER,
    clc_dimensions  INTEGER,
    eta_mean        REAL,
    cp_profile      JSONB DEFAULT '{}'::JSONB,
    p_feasible_count INTEGER,
    attractor_count INTEGER,
    spec_gap_mean   REAL,
    competency_dist JSONB DEFAULT '{}'::JSONB,
    tier_usage      JSONB DEFAULT '{}'::JSONB,
    total_reuse     INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_snapshots_at
    ON developmental_snapshots (snapshot_at DESC);

CREATE TABLE IF NOT EXISTS cascade_events (
    id              BIGSERIAL PRIMARY KEY,
    cascade_id      VARCHAR(128) NOT NULL,
    goal_id         VARCHAR(64) NOT NULL,
    channel_id      VARCHAR(16),
    trigger_p_fail  REAL,
    trigger_ucb     REAL,
    trigger_epsilon REAL,
    tier_attempted  INTEGER NOT NULL,
    tier_succeeded  INTEGER,
    diagnostic      JSONB DEFAULT '{}'::JSONB,
    adaptation      JSONB DEFAULT '{}'::JSONB,
    competency_id   VARCHAR(128),
    outcome         VARCHAR(20) DEFAULT 'pending',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cascade_goal
    ON cascade_events (goal_id, started_at DESC);

CREATE TABLE IF NOT EXISTS cascade_config (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    min_observations INTEGER NOT NULL DEFAULT 20,
    delta           REAL NOT NULL DEFAULT 0.05,
    max_tier0_attempts INTEGER NOT NULL DEFAULT 3,
    max_tier1_attempts INTEGER NOT NULL DEFAULT 2,
    cascade_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    tier0_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    tier1_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    tier2_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    tier3_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    tier2_auto_approve BOOLEAN NOT NULL DEFAULT FALSE,
    tier3_auto_approve BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO cascade_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS system_images (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    image_data      JSONB NOT NULL,
    checksum        VARCHAR(128) NOT NULL,
    exported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- App Factory project state
CREATE TABLE IF NOT EXISTS app_factory_projects (
    project_id      VARCHAR(64) PRIMARY KEY,
    data            JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ======================================================================
-- Goal Hierarchy tables
-- ======================================================================

CREATE TABLE IF NOT EXISTS hierarchy_predicates (
    index           INTEGER PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    level           INTEGER NOT NULL,
    block           VARCHAR(8) NOT NULL,
    pass_condition  TEXT NOT NULL DEFAULT '',
    variance        REAL NOT NULL DEFAULT 0.0,
    epsilon_dmg     REAL NOT NULL DEFAULT 0.0,
    agent_id        VARCHAR(16) NOT NULL,
    module_id       VARCHAR(64),
    current_value   REAL,
    last_observed   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS hierarchy_blocks (
    block_id        VARCHAR(8) PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    level           INTEGER NOT NULL,
    predicate_indices INTEGER[] NOT NULL DEFAULT '{}',
    rank            INTEGER NOT NULL DEFAULT 0,
    module_id       VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS hierarchy_coupling_axes (
    id              BIGSERIAL PRIMARY KEY,
    source_idx      INTEGER NOT NULL,
    target_idx      INTEGER NOT NULL,
    rho             REAL NOT NULL,
    axis_type       VARCHAR(32) NOT NULL,
    channel_id      VARCHAR(16)
);
CREATE INDEX IF NOT EXISTS idx_hca_source ON hierarchy_coupling_axes (source_idx);
CREATE INDEX IF NOT EXISTS idx_hca_target ON hierarchy_coupling_axes (target_idx);

CREATE TABLE IF NOT EXISTS hierarchy_agents (
    agent_id        VARCHAR(16) PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    predicates      INTEGER[] NOT NULL DEFAULT '{}',
    rank            INTEGER NOT NULL DEFAULT 0,
    capacity        INTEGER NOT NULL DEFAULT 0,
    sigma_max       REAL NOT NULL DEFAULT 0.0,
    layer           VARCHAR(16) NOT NULL DEFAULT 'celestial'
);

CREATE TABLE IF NOT EXISTS hierarchy_orchestrators (
    orchestrator_id VARCHAR(16) PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    rank            INTEGER NOT NULL DEFAULT 0,
    governed_agents TEXT[] NOT NULL DEFAULT '{}',
    role            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS terrestrial_modules (
    module_id       VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    level           INTEGER NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'Active',
    predicate_indices INTEGER[] NOT NULL DEFAULT '{}',
    agent_id        VARCHAR(16) NOT NULL,
    upward_channels TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS hierarchy_eigenvalues (
    index           INTEGER PRIMARY KEY,
    value           REAL NOT NULL,
    dominant_predicates INTEGER[] NOT NULL DEFAULT '{}',
    interpretation  TEXT NOT NULL DEFAULT '',
    layer           VARCHAR(16) NOT NULL DEFAULT 'celestial'
);

CREATE TABLE IF NOT EXISTS hierarchy_feasibility_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rank_coverage   BOOLEAN NOT NULL,
    coupling_coverage BOOLEAN NOT NULL,
    epsilon_check   BOOLEAN NOT NULL,
    overall         BOOLEAN NOT NULL,
    details         JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS hierarchy_gate_status (
    level           INTEGER PRIMARY KEY,
    is_open         BOOLEAN NOT NULL DEFAULT TRUE,
    failing_predicates INTEGER[] NOT NULL DEFAULT '{}',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hierarchy_observations (
    id              BIGSERIAL PRIMARY KEY,
    predicate_index INTEGER NOT NULL,
    value           REAL NOT NULL,
    source          VARCHAR(32) NOT NULL DEFAULT 'manual',
    metadata        JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hobs_pred ON hierarchy_observations (predicate_index, created_at DESC);
"""


_MIGRATE_AGENT_CONFIGS_SQL = """
-- Add new columns to existing agent_configs table (safe to re-run)
DO $$ BEGIN
    ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS tool_ids TEXT[] DEFAULT '{}';
    ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN DEFAULT FALSE;
    ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
"""


async def init_aps_tables() -> None:
    """Create all APS tables if they don't exist, then run migrations."""
    try:
        with _get_conn() as conn:
            conn.execute(_CREATE_TABLES_SQL)
            conn.execute(_MIGRATE_AGENT_CONFIGS_SQL)
        logger.info("APS tables initialized (with migrations)")
    except Exception:
        logger.warning("Failed to initialize APS tables (DB may be unavailable)", exc_info=True)


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


def log_observation(
    *,
    channel_id: str,
    theta_id: str,
    sigma_in: str,
    sigma_out: str,
    timestamp: float,
    latency_ms: float,
    cost_usd: float = 0.0,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    model_id: str | None = None,
    trace_id: str | None = None,
    path_id: str | None = None,
    run_metadata: dict | None = None,
) -> None:
    """Insert one APS observation row."""
    try:
        observed_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO aps_observations
                (channel_id, theta_id, sigma_in, sigma_out, observed_at,
                 latency_ms, cost_usd, prompt_tokens, completion_tokens,
                 total_tokens, model_id, trace_id, path_id, run_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    channel_id, theta_id, sigma_in, sigma_out, observed_at,
                    latency_ms, cost_usd, prompt_tokens, completion_tokens,
                    total_tokens, model_id, trace_id, path_id,
                    json.dumps(run_metadata or {}),
                ),
            )
    except Exception:
        logger.warning("Failed to log APS observation for %s", channel_id, exc_info=True)


def get_recent_observations(
    channel_id: str, window_seconds: float
) -> list[dict[str, Any]]:
    """Fetch observations for a channel within a time window."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT channel_id, theta_id, sigma_in, sigma_out, observed_at,
                       latency_ms, cost_usd, prompt_tokens, completion_tokens,
                       total_tokens, model_id, trace_id, path_id
                FROM aps_observations
                WHERE channel_id = %s
                  AND observed_at > NOW() - make_interval(secs => %s)
                ORDER BY observed_at DESC""",
                (channel_id, window_seconds),
            ).fetchall()
            return [
                {
                    "channel_id": r[0], "theta_id": r[1],
                    "sigma_in": r[2], "sigma_out": r[3],
                    "observed_at": r[4], "latency_ms": r[5],
                    "cost_usd": r[6], "prompt_tokens": r[7],
                    "completion_tokens": r[8], "total_tokens": r[9],
                    "model_id": r[10], "trace_id": str(r[11]) if r[11] else None,
                    "path_id": r[12],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query APS observations for %s", channel_id, exc_info=True)
        return []


def get_observations_by_trace(trace_id: str) -> list[dict[str, Any]]:
    """Get all observations for a workflow trace."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT channel_id, theta_id, sigma_in, sigma_out, observed_at,
                       latency_ms, cost_usd, prompt_tokens, completion_tokens,
                       total_tokens, model_id, trace_id, path_id
                FROM aps_observations
                WHERE trace_id = %s::uuid
                ORDER BY observed_at""",
                (trace_id,),
            ).fetchall()
            return [
                {
                    "channel_id": r[0], "theta_id": r[1],
                    "sigma_in": r[2], "sigma_out": r[3],
                    "observed_at": str(r[4]), "latency_ms": r[5],
                    "cost_usd": r[6], "prompt_tokens": r[7],
                    "completion_tokens": r[8], "total_tokens": r[9],
                    "model_id": r[10], "trace_id": str(r[11]) if r[11] else None,
                    "path_id": r[12],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query trace %s", trace_id, exc_info=True)
        return []


def get_distinct_paths(window_seconds: float) -> list[str]:
    """Get distinct realized path_ids within a time window."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT path_id FROM aps_observations
                WHERE path_id IS NOT NULL
                  AND observed_at > NOW() - make_interval(secs => %s)""",
                (window_seconds,),
            ).fetchall()
            return [r[0] for r in rows if r[0]]
    except Exception:
        logger.warning("Failed to query distinct paths", exc_info=True)
        return []


def get_observations_by_path_and_channel(
    path_id: str, channel_id: str, window_seconds: float
) -> list[dict[str, Any]]:
    """Get observations for a specific path and channel."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT sigma_in, sigma_out FROM aps_observations
                WHERE path_id = %s AND channel_id = %s
                  AND observed_at > NOW() - make_interval(secs => %s)""",
                (path_id, channel_id, window_seconds),
            ).fetchall()
            return [{"sigma_in": r[0], "sigma_out": r[1]} for r in rows]
    except Exception:
        logger.warning("Failed to query path observations", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def store_aps_metrics(
    *,
    channel_id: str,
    theta_id: str,
    p_fail: float,
    p_fail_ucb: float | None,
    mutual_info: float,
    capacity: float,
    eta_usd: float,
    eta_token: float | None,
    eta_time: float | None,
    n_observations: int,
    total_cost_usd: float,
    total_tokens: int,
    total_time_s: float,
    confusion_matrix: dict | None,
    window_seconds: float,
) -> None:
    """Store one metrics computation."""
    try:
        # Cap infinite eta values for Postgres REAL
        _cap = 1e30
        eta_usd_safe = min(eta_usd, _cap) if eta_usd != float("inf") else _cap
        eta_token_safe = min(eta_token, _cap) if eta_token and eta_token != float("inf") else eta_token
        eta_time_safe = min(eta_time, _cap) if eta_time and eta_time != float("inf") else eta_time

        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO aps_metrics
                (channel_id, theta_id, p_fail, p_fail_ucb, mutual_info,
                 capacity, eta_usd, eta_token, eta_time, n_observations,
                 total_cost_usd, total_tokens, total_time_s,
                 confusion_matrix, window_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    channel_id, theta_id, p_fail, p_fail_ucb, mutual_info,
                    capacity, eta_usd_safe, eta_token_safe, eta_time_safe,
                    n_observations, total_cost_usd, total_tokens, total_time_s,
                    json.dumps(confusion_matrix) if confusion_matrix else None,
                    window_seconds,
                ),
            )
    except Exception:
        logger.warning("Failed to store APS metrics for %s", channel_id, exc_info=True)


def get_latest_metrics() -> list[dict[str, Any]]:
    """Get the most recent metric row per channel."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT ON (channel_id)
                    channel_id, theta_id, computed_at, p_fail, p_fail_ucb,
                    mutual_info, capacity, eta_usd, eta_token, eta_time,
                    n_observations, total_cost_usd, total_tokens, total_time_s,
                    window_seconds
                FROM aps_metrics
                ORDER BY channel_id, computed_at DESC"""
            ).fetchall()
            return [
                {
                    "channel_id": r[0], "theta_id": r[1],
                    "computed_at": str(r[2]), "p_fail": r[3],
                    "p_fail_ucb": r[4], "mutual_info": r[5],
                    "capacity": r[6], "eta_usd": r[7],
                    "eta_token": r[8], "eta_time": r[9],
                    "n_observations": r[10], "total_cost_usd": r[11],
                    "total_tokens": r[12], "total_time_s": r[13],
                    "window_seconds": r[14],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query latest APS metrics", exc_info=True)
        return []


def get_metrics_history(channel_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get metric history for one channel."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT channel_id, theta_id, computed_at, p_fail, p_fail_ucb,
                       mutual_info, capacity, eta_usd, eta_token, eta_time,
                       n_observations, total_cost_usd, total_tokens, total_time_s
                FROM aps_metrics
                WHERE channel_id = %s
                ORDER BY computed_at DESC
                LIMIT %s""",
                (channel_id, limit),
            ).fetchall()
            return [
                {
                    "channel_id": r[0], "theta_id": r[1],
                    "computed_at": str(r[2]), "p_fail": r[3],
                    "p_fail_ucb": r[4], "mutual_info": r[5],
                    "capacity": r[6], "eta_usd": r[7],
                    "eta_token": r[8], "eta_time": r[9],
                    "n_observations": r[10], "total_cost_usd": r[11],
                    "total_tokens": r[12], "total_time_s": r[13],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query metrics history for %s", channel_id, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Theta switches
# ---------------------------------------------------------------------------


def store_theta_switch_event(
    *,
    channel_id: str,
    from_theta: str,
    to_theta: str,
    direction: str,
    from_level: int,
    to_level: int,
    model_changed: bool,
    protocol_changed: bool,
    trigger_p_fail: float,
    trigger_epsilon: float,
    goal_id: str,
) -> None:
    """Log a theta switch event."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO aps_theta_switches
                (channel_id, from_theta, to_theta, direction,
                 from_level, to_level, model_changed, protocol_changed,
                 trigger_p_fail, trigger_epsilon, goal_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    channel_id, from_theta, to_theta, direction,
                    from_level, to_level, model_changed, protocol_changed,
                    trigger_p_fail, trigger_epsilon, goal_id,
                ),
            )
    except Exception:
        logger.warning("Failed to store theta switch for %s", channel_id, exc_info=True)


# ---------------------------------------------------------------------------
# Theta cache (v3)
# ---------------------------------------------------------------------------


def cache_theta(
    channel_id: str, theta_id: str, context_hash: str, p_fail: float
) -> None:
    """Cache a successful theta configuration by context fingerprint."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO aps_theta_cache
                (channel_id, context_hash, theta_id, p_fail_at_cache, cached_at, last_validated)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (channel_id, context_hash)
                DO UPDATE SET theta_id = %s, p_fail_at_cache = %s,
                              last_validated = NOW(), hit_count = aps_theta_cache.hit_count + 1""",
                (channel_id, context_hash, theta_id, p_fail, theta_id, p_fail),
            )
    except Exception:
        logger.warning("Failed to cache theta for %s", channel_id, exc_info=True)


def query_theta_cache(
    channel_id: str, context_hash: str, max_age_seconds: float = 3600
) -> dict | None:
    """Look up a cached theta for matching context. Returns None if stale or absent."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT theta_id, context_hash, p_fail_at_cache, cached_at,
                       last_validated, hit_count
                FROM aps_theta_cache
                WHERE channel_id = %s AND context_hash = %s
                  AND last_validated > NOW() - make_interval(secs => %s)""",
                (channel_id, context_hash, max_age_seconds),
            ).fetchone()
            if row:
                return {
                    "theta_id": row[0],
                    "context_hash": row[1],
                    "p_fail_at_cache": row[2],
                    "cached_at": str(row[3]),
                    "last_validated": str(row[4]),
                    "hit_count": row[5],
                }
            return None
    except Exception:
        logger.warning("Failed to query theta cache for %s", channel_id, exc_info=True)
        return None


def get_all_theta_cache() -> list[dict]:
    """Get all cached theta entries (for /aps/cache endpoint)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT channel_id, context_hash, theta_id, p_fail_at_cache,
                       cached_at, last_validated, hit_count
                FROM aps_theta_cache
                ORDER BY channel_id"""
            ).fetchall()
            return [
                {
                    "channel_id": r[0], "context_hash": r[1],
                    "theta_id": r[2], "p_fail_at_cache": r[3],
                    "cached_at": str(r[4]), "last_validated": str(r[5]),
                    "hit_count": r[6],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query theta cache", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Agent configs
# ---------------------------------------------------------------------------


def _row_to_agent_config(r: tuple) -> dict[str, Any]:
    """Convert a full agent_configs row to dict."""
    return {
        "agent_id": r[0], "channel_id": r[1],
        "display_name": r[2], "description": r[3],
        "model_id": r[4], "system_prompt": r[5],
        "tool_ids": list(r[6]) if r[6] else [],
        "is_builtin": r[7],
        "version": r[8], "updated_at": str(r[9]),
    }


_AGENT_SELECT = """SELECT agent_id, channel_id, display_name, description,
                       model_id, system_prompt, tool_ids, is_builtin, version, updated_at
                FROM agent_configs"""


def get_all_agent_configs() -> list[dict[str, Any]]:
    """Get all non-deleted agent configurations."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                f"{_AGENT_SELECT} WHERE deleted_at IS NULL ORDER BY channel_id"
            ).fetchall()
            return [_row_to_agent_config(r) for r in rows]
    except Exception:
        logger.warning("Failed to query agent configs", exc_info=True)
        return []


def get_agent_config(agent_id: str) -> dict[str, Any] | None:
    """Get a single agent configuration by id (including soft-deleted)."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                f"{_AGENT_SELECT} WHERE agent_id = %s AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
            if row:
                return _row_to_agent_config(row)
            return None
    except Exception:
        logger.warning("Failed to query agent config %s", agent_id, exc_info=True)
        return None


def create_agent_config(
    *,
    agent_id: str,
    channel_id: str,
    display_name: str,
    description: str = "",
    model_id: str,
    system_prompt: str,
    tool_ids: list[str] | None = None,
    is_builtin: bool = False,
) -> dict[str, Any] | None:
    """Create a new agent config. Returns the created row."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO agent_configs
                (agent_id, channel_id, display_name, description, model_id,
                 system_prompt, tool_ids, is_builtin)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    agent_id, channel_id, display_name, description,
                    model_id, system_prompt, tool_ids or [], is_builtin,
                ),
            )
        # Snapshot v1
        snapshot_agent_version(agent_id, change_summary="Created")
        return get_agent_config(agent_id)
    except Exception:
        logger.warning("Failed to create agent config %s", agent_id, exc_info=True)
        return None


def update_agent_config(
    agent_id: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    model_id: str | None = None,
    system_prompt: str | None = None,
    tool_ids: list[str] | None = None,
    expected_version: int,
) -> dict[str, Any] | None:
    """Update an agent config with optimistic concurrency.

    Auto-snapshots the current state before applying changes.
    Returns the updated row, or None if version mismatch or not found.
    """
    try:
        # Snapshot current state before update
        snapshot_agent_version(agent_id)

        # Build SET clause dynamically
        sets = []
        params: list[Any] = []
        if display_name is not None:
            sets.append("display_name = %s")
            params.append(display_name)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if model_id is not None:
            sets.append("model_id = %s")
            params.append(model_id)
        if system_prompt is not None:
            sets.append("system_prompt = %s")
            params.append(system_prompt)
        if tool_ids is not None:
            sets.append("tool_ids = %s")
            params.append(tool_ids)

        if not sets:
            return get_agent_config(agent_id)

        sets.append("version = version + 1")
        sets.append("updated_at = NOW()")

        params.extend([agent_id, expected_version])

        with _get_conn() as conn:
            conn.execute(
                f"""UPDATE agent_configs
                SET {', '.join(sets)}
                WHERE agent_id = %s AND version = %s AND deleted_at IS NULL""",
                params,
            )
            return get_agent_config(agent_id)
    except Exception:
        logger.warning("Failed to update agent config %s", agent_id, exc_info=True)
        return None


def soft_delete_agent_config(agent_id: str) -> bool:
    """Soft-delete an agent config. Returns True if deleted."""
    try:
        with _get_conn() as conn:
            result = conn.execute(
                """UPDATE agent_configs SET deleted_at = NOW()
                WHERE agent_id = %s AND deleted_at IS NULL AND is_builtin = FALSE""",
                (agent_id,),
            )
            return result.rowcount > 0
    except Exception:
        logger.warning("Failed to soft-delete agent config %s", agent_id, exc_info=True)
        return False


def snapshot_agent_version(agent_id: str, change_summary: str = "") -> None:
    """Snapshot the current agent config state as a version record."""
    try:
        config = get_agent_config(agent_id)
        if not config:
            return
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO agent_config_versions
                (agent_id, version, channel_id, display_name, description,
                 model_id, system_prompt, tool_ids, change_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (agent_id, version) DO NOTHING""",
                (
                    config["agent_id"], config["version"],
                    config["channel_id"], config["display_name"],
                    config["description"], config["model_id"],
                    config["system_prompt"], config.get("tool_ids", []),
                    change_summary,
                ),
            )
    except Exception:
        logger.warning("Failed to snapshot agent version %s", agent_id, exc_info=True)


def get_agent_version_history(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get version history for an agent."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT agent_id, version, channel_id, display_name, description,
                       model_id, system_prompt, tool_ids, change_summary, created_at
                FROM agent_config_versions
                WHERE agent_id = %s
                ORDER BY version DESC
                LIMIT %s""",
                (agent_id, limit),
            ).fetchall()
            return [
                {
                    "agent_id": r[0], "version": r[1],
                    "channel_id": r[2], "display_name": r[3],
                    "description": r[4], "model_id": r[5],
                    "system_prompt": r[6],
                    "tool_ids": list(r[7]) if r[7] else [],
                    "change_summary": r[8],
                    "created_at": str(r[9]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to get version history for %s", agent_id, exc_info=True)
        return []


def get_agent_version(agent_id: str, version: int) -> dict[str, Any] | None:
    """Get a specific version snapshot of an agent."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT agent_id, version, channel_id, display_name, description,
                       model_id, system_prompt, tool_ids, change_summary, created_at
                FROM agent_config_versions
                WHERE agent_id = %s AND version = %s""",
                (agent_id, version),
            ).fetchone()
            if row:
                return {
                    "agent_id": row[0], "version": row[1],
                    "channel_id": row[2], "display_name": row[3],
                    "description": row[4], "model_id": row[5],
                    "system_prompt": row[6],
                    "tool_ids": list(row[7]) if row[7] else [],
                    "change_summary": row[8],
                    "created_at": str(row[9]),
                }
            return None
    except Exception:
        logger.warning("Failed to get version %d for %s", version, agent_id, exc_info=True)
        return None


def seed_agent_configs(defaults: list[dict[str, str]]) -> None:
    """Insert or update default agent configs, ensuring is_builtin=TRUE."""
    try:
        with _get_conn() as conn:
            for d in defaults:
                conn.execute(
                    """INSERT INTO agent_configs
                    (agent_id, channel_id, display_name, description,
                     model_id, system_prompt, is_builtin)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (agent_id) DO UPDATE SET
                        is_builtin = TRUE,
                        deleted_at = NULL""",
                    (
                        d["agent_id"], d["channel_id"], d["display_name"],
                        d["description"], d["model_id"], d["system_prompt"],
                    ),
                )
            logger.info("Seeded/updated %d agent configs (is_builtin=TRUE)", len(defaults))
    except Exception:
        logger.warning("Failed to seed agent configs", exc_info=True)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


def seed_tool_registry(tools: list[dict[str, str]]) -> None:
    """Upsert tool definitions into the registry."""
    try:
        with _get_conn() as conn:
            for t in tools:
                conn.execute(
                    """INSERT INTO tool_registry
                    (tool_id, display_name, description, module_path, function_name, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tool_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        module_path = EXCLUDED.module_path,
                        function_name = EXCLUDED.function_name,
                        category = EXCLUDED.category""",
                    (
                        t["tool_id"], t["display_name"], t["description"],
                        t["module_path"], t["function_name"], t["category"],
                    ),
                )
        logger.info("Seeded %d tools into tool_registry", len(tools))
    except Exception:
        logger.warning("Failed to seed tool registry", exc_info=True)


def get_all_tools() -> list[dict[str, Any]]:
    """Get all registered tools."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT tool_id, display_name, description,
                       module_path, function_name, category
                FROM tool_registry
                ORDER BY category, tool_id"""
            ).fetchall()
            return [
                {
                    "tool_id": r[0], "display_name": r[1],
                    "description": r[2], "module_path": r[3],
                    "function_name": r[4], "category": r[5],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query tool registry", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------


def _row_to_workflow(r: tuple) -> dict[str, Any]:
    """Convert a workflow_definitions row to dict."""
    return {
        "workflow_id": r[0],
        "display_name": r[1],
        "description": r[2],
        "version": r[3],
        "is_active": r[4],
        "is_builtin": r[5],
        "definition": r[6] if isinstance(r[6], dict) else json.loads(r[6]) if r[6] else {},
        "created_at": str(r[7]),
        "updated_at": str(r[8]),
    }


_WORKFLOW_SELECT = """SELECT workflow_id, display_name, description, version,
                         is_active, is_builtin, definition, created_at, updated_at
                  FROM workflow_definitions"""


def get_all_workflows() -> list[dict[str, Any]]:
    """Get all non-deleted workflows."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                f"{_WORKFLOW_SELECT} WHERE deleted_at IS NULL ORDER BY display_name"
            ).fetchall()
            return [_row_to_workflow(r) for r in rows]
    except Exception:
        logger.warning("Failed to query workflows", exc_info=True)
        return []


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    """Get a single workflow by id."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                f"{_WORKFLOW_SELECT} WHERE workflow_id = %s AND deleted_at IS NULL",
                (workflow_id,),
            ).fetchone()
            if row:
                return _row_to_workflow(row)
            return None
    except Exception:
        logger.warning("Failed to query workflow %s", workflow_id, exc_info=True)
        return None


def create_workflow(
    *,
    workflow_id: str,
    display_name: str,
    description: str = "",
    definition: dict,
    is_builtin: bool = False,
    is_active: bool = False,
) -> dict[str, Any] | None:
    """Create a new workflow. Returns the created row."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO workflow_definitions
                (workflow_id, display_name, description, definition,
                 is_builtin, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    workflow_id, display_name, description,
                    json.dumps(definition), is_builtin, is_active,
                ),
            )
        # Snapshot v1
        snapshot_workflow_version(workflow_id, change_summary="Created")
        return get_workflow(workflow_id)
    except Exception:
        logger.warning("Failed to create workflow %s", workflow_id, exc_info=True)
        return None


def update_workflow(
    workflow_id: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    definition: dict | None = None,
    expected_version: int,
) -> dict[str, Any] | None:
    """Update a workflow with optimistic concurrency.

    Auto-snapshots before applying changes.
    """
    try:
        snapshot_workflow_version(workflow_id)

        sets = []
        params: list[Any] = []
        if display_name is not None:
            sets.append("display_name = %s")
            params.append(display_name)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if definition is not None:
            sets.append("definition = %s")
            params.append(json.dumps(definition))

        if not sets:
            return get_workflow(workflow_id)

        sets.append("version = version + 1")
        sets.append("updated_at = NOW()")

        params.extend([workflow_id, expected_version])

        with _get_conn() as conn:
            conn.execute(
                f"""UPDATE workflow_definitions
                SET {', '.join(sets)}
                WHERE workflow_id = %s AND version = %s AND deleted_at IS NULL""",
                params,
            )
            return get_workflow(workflow_id)
    except Exception:
        logger.warning("Failed to update workflow %s", workflow_id, exc_info=True)
        return None


def soft_delete_workflow(workflow_id: str) -> bool:
    """Soft-delete a workflow. Returns True if deleted."""
    try:
        with _get_conn() as conn:
            result = conn.execute(
                """UPDATE workflow_definitions SET deleted_at = NOW()
                WHERE workflow_id = %s AND deleted_at IS NULL AND is_builtin = FALSE""",
                (workflow_id,),
            )
            return result.rowcount > 0
    except Exception:
        logger.warning("Failed to soft-delete workflow %s", workflow_id, exc_info=True)
        return False


def activate_workflow(workflow_id: str) -> bool:
    """Activate a workflow (deactivate all others first). Returns True on success."""
    try:
        with _get_conn() as conn:
            # Deactivate all
            conn.execute("UPDATE workflow_definitions SET is_active = FALSE")
            # Activate the target
            result = conn.execute(
                """UPDATE workflow_definitions SET is_active = TRUE
                WHERE workflow_id = %s AND deleted_at IS NULL""",
                (workflow_id,),
            )
            return result.rowcount > 0
    except Exception:
        logger.warning("Failed to activate workflow %s", workflow_id, exc_info=True)
        return False


def get_active_workflow() -> dict[str, Any] | None:
    """Get the currently active workflow."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                f"{_WORKFLOW_SELECT} WHERE is_active = TRUE AND deleted_at IS NULL"
            ).fetchone()
            if row:
                return _row_to_workflow(row)
            return None
    except Exception:
        logger.warning("Failed to query active workflow", exc_info=True)
        return None


def snapshot_workflow_version(workflow_id: str, change_summary: str = "") -> None:
    """Snapshot the current workflow state as a version record."""
    try:
        wf = get_workflow(workflow_id)
        if not wf:
            return
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO workflow_versions
                (workflow_id, version, definition, change_summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (workflow_id, version) DO NOTHING""",
                (
                    wf["workflow_id"], wf["version"],
                    json.dumps(wf["definition"]), change_summary,
                ),
            )
    except Exception:
        logger.warning("Failed to snapshot workflow version %s", workflow_id, exc_info=True)


def get_workflow_version_history(workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get version history for a workflow."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT workflow_id, version, definition, change_summary, created_at
                FROM workflow_versions
                WHERE workflow_id = %s
                ORDER BY version DESC
                LIMIT %s""",
                (workflow_id, limit),
            ).fetchall()
            return [
                {
                    "workflow_id": r[0], "version": r[1],
                    "definition": r[2] if isinstance(r[2], dict) else json.loads(r[2]) if r[2] else {},
                    "change_summary": r[3],
                    "created_at": str(r[4]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to get workflow version history for %s", workflow_id, exc_info=True)
        return []


def get_workflow_version(workflow_id: str, version: int) -> dict[str, Any] | None:
    """Get a specific version snapshot of a workflow."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT workflow_id, version, definition, change_summary, created_at
                FROM workflow_versions
                WHERE workflow_id = %s AND version = %s""",
                (workflow_id, version),
            ).fetchone()
            if row:
                return {
                    "workflow_id": row[0], "version": row[1],
                    "definition": row[2] if isinstance(row[2], dict) else json.loads(row[2]) if row[2] else {},
                    "change_summary": row[3],
                    "created_at": str(row[4]),
                }
            return None
    except Exception:
        logger.warning("Failed to get workflow version %d for %s", version, workflow_id, exc_info=True)
        return None


def seed_workflow(
    workflow_id: str,
    display_name: str,
    description: str,
    definition: dict,
    is_builtin: bool = True,
    is_active: bool = True,
) -> None:
    """Upsert a workflow definition (used for seeding the default workflow)."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO workflow_definitions
                (workflow_id, display_name, description, definition,
                 is_builtin, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (workflow_id) DO UPDATE SET
                    is_builtin = EXCLUDED.is_builtin,
                    deleted_at = NULL""",
                (
                    workflow_id, display_name, description,
                    json.dumps(definition), is_builtin, is_active,
                ),
            )
        logger.info("Seeded workflow %s", workflow_id)
    except Exception:
        logger.warning("Failed to seed workflow %s", workflow_id, exc_info=True)


# ---------------------------------------------------------------------------
# Agent efficacy
# ---------------------------------------------------------------------------

# Map channel_id -> agent_id for the builtin agents
_CHANNEL_TO_AGENT: dict[str, str] = {
    "K1": "orchestrator",
    "K2": "sales_marketing",
    "K3": "operations",
    "K4": "revenue",
    "K5": "content_writer",
    "K6": "campaign_analyzer",
}


def compute_agent_efficacy(days: int = 30) -> int:
    """Aggregate APS observations into efficacy rows per agent+version per hour.

    Returns the number of rows inserted.
    """
    try:
        with _get_conn() as conn:
            result = conn.execute(
                """INSERT INTO agent_efficacy
                (agent_id, channel_id, version, period_start, period_end,
                 invocations, successes, failures, avg_latency_ms,
                 total_cost_usd, p_fail, capacity)
                SELECT
                    o.channel_id AS agent_id,
                    o.channel_id,
                    COALESCE(ac.version, 1) AS version,
                    date_trunc('hour', o.observed_at) AS period_start,
                    date_trunc('hour', o.observed_at) + interval '1 hour' AS period_end,
                    COUNT(*) AS invocations,
                    COUNT(*) FILTER (WHERE o.sigma_out NOT LIKE '%%error%%'
                                     AND o.sigma_out NOT LIKE '%%failure%%') AS successes,
                    COUNT(*) FILTER (WHERE o.sigma_out LIKE '%%error%%'
                                     OR o.sigma_out LIKE '%%failure%%') AS failures,
                    ROUND(AVG(o.latency_ms)::numeric, 1) AS avg_latency_ms,
                    ROUND(SUM(o.cost_usd)::numeric, 6) AS total_cost_usd,
                    CASE WHEN COUNT(*) > 0
                         THEN ROUND((COUNT(*) FILTER (WHERE o.sigma_out LIKE '%%error%%'
                                     OR o.sigma_out LIKE '%%failure%%')::numeric
                                     / COUNT(*)::numeric), 4)
                         ELSE 0 END AS p_fail,
                    0 AS capacity
                FROM aps_observations o
                LEFT JOIN agent_configs ac ON ac.channel_id = o.channel_id
                WHERE o.observed_at > NOW() - make_interval(days => %s)
                  AND NOT EXISTS (
                      SELECT 1 FROM agent_efficacy ae
                      WHERE ae.channel_id = o.channel_id
                        AND ae.period_start = date_trunc('hour', o.observed_at)
                  )
                GROUP BY o.channel_id, ac.version, date_trunc('hour', o.observed_at)""",
                (days,),
            )
            count = result.rowcount
            # Update agent_id from channel_id mapping
            for channel_id, agent_id in _CHANNEL_TO_AGENT.items():
                conn.execute(
                    """UPDATE agent_efficacy SET agent_id = %s
                    WHERE channel_id = %s AND agent_id = %s""",
                    (agent_id, channel_id, channel_id),
                )
            logger.info("Computed %d efficacy rows", count)
            return count
    except Exception:
        logger.warning("Failed to compute agent efficacy", exc_info=True)
        return 0


def get_agent_efficacy(agent_id: str, days: int = 30) -> list[dict[str, Any]]:
    """Get efficacy history for an agent."""
    try:
        with _get_conn() as conn:
            # Look up by agent_id or channel_id
            rows = conn.execute(
                """SELECT agent_id, channel_id, version, period_start, period_end,
                       invocations, successes, failures, avg_latency_ms,
                       total_cost_usd, p_fail, capacity, computed_at
                FROM agent_efficacy
                WHERE (agent_id = %s OR channel_id = %s)
                  AND period_start > NOW() - make_interval(days => %s)
                ORDER BY period_start DESC""",
                (agent_id, agent_id, days),
            ).fetchall()
            return [
                {
                    "agent_id": r[0], "channel_id": r[1], "version": r[2],
                    "period_start": str(r[3]), "period_end": str(r[4]),
                    "invocations": r[5], "successes": r[6], "failures": r[7],
                    "avg_latency_ms": r[8], "total_cost_usd": float(r[9]) if r[9] else 0,
                    "p_fail": float(r[10]) if r[10] else 0,
                    "capacity": float(r[11]) if r[11] else 0,
                    "computed_at": str(r[12]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query agent efficacy for %s", agent_id, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Dead Letter Queue
# ---------------------------------------------------------------------------


def dlq_insert(
    *, job_id: str, payload: dict, error: str, max_attempts: int = 3
) -> None:
    """Insert a failed task into the dead letter queue."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO dead_letter_queue
                (job_id, payload, error, max_attempts, next_retry_at)
                VALUES (%s, %s, %s, %s, NOW() + interval '5 minutes')""",
                (job_id, json.dumps(payload, default=str), error, max_attempts),
            )
        logger.info("DLQ: inserted failed task %s", job_id)
    except Exception:
        logger.warning("Failed to insert into DLQ for %s", job_id, exc_info=True)


def dlq_get_pending() -> list[dict[str, Any]]:
    """Get all unresolved DLQ entries ready for retry."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, job_id, payload, error, attempts, max_attempts,
                       created_at, next_retry_at
                FROM dead_letter_queue
                WHERE resolved_at IS NULL
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                  AND attempts < max_attempts
                ORDER BY created_at"""
            ).fetchall()
            return [
                {
                    "id": r[0], "job_id": r[1],
                    "payload": r[2] if isinstance(r[2], dict) else json.loads(r[2]),
                    "error": r[3], "attempts": r[4], "max_attempts": r[5],
                    "created_at": str(r[6]), "next_retry_at": str(r[7]) if r[7] else None,
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to query DLQ", exc_info=True)
        return []


def dlq_list_all() -> list[dict[str, Any]]:
    """Get all DLQ entries (for API)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, job_id, payload, error, attempts, max_attempts,
                       created_at, next_retry_at, resolved_at
                FROM dead_letter_queue
                ORDER BY created_at DESC
                LIMIT 100"""
            ).fetchall()
            return [
                {
                    "id": r[0], "job_id": r[1],
                    "payload": r[2] if isinstance(r[2], dict) else json.loads(r[2]),
                    "error": r[3], "attempts": r[4], "max_attempts": r[5],
                    "created_at": str(r[6]),
                    "next_retry_at": str(r[7]) if r[7] else None,
                    "resolved_at": str(r[8]) if r[8] else None,
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to list DLQ", exc_info=True)
        return []


def dlq_increment_attempt(dlq_id: int, error: str) -> None:
    """Increment attempt count and schedule next retry."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """UPDATE dead_letter_queue
                SET attempts = attempts + 1,
                    error = %s,
                    next_retry_at = NOW() + interval '5 minutes' * attempts
                WHERE id = %s""",
                (error, dlq_id),
            )
    except Exception:
        logger.warning("Failed to increment DLQ attempt %d", dlq_id, exc_info=True)


def dlq_resolve(dlq_id: int) -> None:
    """Mark a DLQ entry as resolved."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE dead_letter_queue SET resolved_at = NOW() WHERE id = %s",
                (dlq_id,),
            )
    except Exception:
        logger.warning("Failed to resolve DLQ entry %d", dlq_id, exc_info=True)


# ---------------------------------------------------------------------------
# Approval Queue
# ---------------------------------------------------------------------------


def approval_create(
    *,
    action_type: str,
    agent_id: str | None,
    tool_name: str,
    parameters: dict,
    risk_level: str = "medium",
) -> int | None:
    """Create an approval request. Returns the approval ID."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """INSERT INTO approval_queue
                (action_type, agent_id, tool_name, parameters, risk_level)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id""",
                (action_type, agent_id, tool_name, json.dumps(parameters, default=str), risk_level),
            ).fetchone()
            approval_id = row[0] if row else None
            logger.info("Approval request created: id=%s tool=%s risk=%s", approval_id, tool_name, risk_level)
            return approval_id
    except Exception:
        logger.warning("Failed to create approval request", exc_info=True)
        return None


def approval_list_pending() -> list[dict[str, Any]]:
    """Get all pending approval requests (not expired)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, action_type, agent_id, tool_name, parameters,
                       risk_level, status, requested_at, expires_at
                FROM approval_queue
                WHERE status = 'pending' AND expires_at > NOW()
                ORDER BY requested_at DESC"""
            ).fetchall()
            return [
                {
                    "id": r[0], "action_type": r[1], "agent_id": r[2],
                    "tool_name": r[3],
                    "parameters": r[4] if isinstance(r[4], dict) else json.loads(r[4]),
                    "risk_level": r[5], "status": r[6],
                    "requested_at": str(r[7]), "expires_at": str(r[8]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to list pending approvals", exc_info=True)
        return []


def approval_decide(approval_id: int, decision: str, decided_by: str = "console", reason: str = "") -> bool:
    """Approve or reject an approval request. decision must be 'approved' or 'rejected'."""
    if decision not in ("approved", "rejected"):
        return False
    try:
        with _get_conn() as conn:
            result = conn.execute(
                """UPDATE approval_queue
                SET status = %s, decided_at = NOW(), decided_by = %s, reason = %s
                WHERE id = %s AND status = 'pending'""",
                (decision, decided_by, reason, approval_id),
            )
            logger.info("Approval %d: %s by %s", approval_id, decision, decided_by)
            return result.rowcount > 0
    except Exception:
        logger.warning("Failed to decide approval %d", approval_id, exc_info=True)
        return False


def approval_get(approval_id: int) -> dict[str, Any] | None:
    """Get a single approval request."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT id, action_type, agent_id, tool_name, parameters,
                       risk_level, status, requested_at, decided_at,
                       decided_by, expires_at, reason
                FROM approval_queue WHERE id = %s""",
                (approval_id,),
            ).fetchone()
            if row:
                return {
                    "id": row[0], "action_type": row[1], "agent_id": row[2],
                    "tool_name": row[3],
                    "parameters": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                    "risk_level": row[5], "status": row[6],
                    "requested_at": str(row[7]),
                    "decided_at": str(row[8]) if row[8] else None,
                    "decided_by": row[9], "expires_at": str(row[10]),
                    "reason": row[11],
                }
            return None
    except Exception:
        logger.warning("Failed to get approval %d", approval_id, exc_info=True)
        return None


def approval_list_all(limit: int = 50) -> list[dict[str, Any]]:
    """Get all approval requests (for history view)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, action_type, agent_id, tool_name, parameters,
                       risk_level, status, requested_at, decided_at,
                       decided_by, expires_at, reason
                FROM approval_queue
                ORDER BY requested_at DESC
                LIMIT %s""",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r[0], "action_type": r[1], "agent_id": r[2],
                    "tool_name": r[3],
                    "parameters": r[4] if isinstance(r[4], dict) else json.loads(r[4]),
                    "risk_level": r[5], "status": r[6],
                    "requested_at": str(r[7]),
                    "decided_at": str(r[8]) if r[8] else None,
                    "decided_by": r[9], "expires_at": str(r[10]),
                    "reason": r[11],
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to list approvals", exc_info=True)
        return []


def approval_expire_stale() -> int:
    """Expire approval requests that have passed their expiry time. Returns count expired."""
    try:
        with _get_conn() as conn:
            result = conn.execute(
                """UPDATE approval_queue SET status = 'expired'
                WHERE status = 'pending' AND expires_at <= NOW()"""
            )
            return result.rowcount
    except Exception:
        logger.warning("Failed to expire stale approvals", exc_info=True)
        return 0


# ---------------------------------------------------------------------------
# Eval results
# ---------------------------------------------------------------------------


def store_eval_result(
    *,
    suite_id: str,
    task_id: str,
    passed: bool,
    score: float = 0.0,
    latency_ms: float = 0.0,
    cost_usd: float = 0.0,
    output_preview: str = "",
    error: str = "",
) -> None:
    """Store one golden evaluation result."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO eval_results
                (suite_id, task_id, passed, score, latency_ms, cost_usd,
                 output_preview, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (suite_id, task_id, passed, score, latency_ms, cost_usd,
                 output_preview[:500], error[:500]),
            )
    except Exception:
        logger.warning("Failed to store eval result", exc_info=True)


def get_eval_results(suite_id: str) -> list[dict[str, Any]]:
    """Get eval results for a suite run."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT suite_id, task_id, passed, score, latency_ms,
                       cost_usd, output_preview, error, run_at
                FROM eval_results
                WHERE suite_id = %s
                ORDER BY task_id""",
                (suite_id,),
            ).fetchall()
            return [
                {
                    "suite_id": r[0], "task_id": r[1], "passed": r[2],
                    "score": r[3], "latency_ms": r[4], "cost_usd": r[5],
                    "output_preview": r[6], "error": r[7],
                    "run_at": str(r[8]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to get eval results for %s", suite_id, exc_info=True)
        return []


def get_eval_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get summary of recent eval suite runs."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT suite_id,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE passed) as passed,
                       COUNT(*) FILTER (WHERE NOT passed) as failed,
                       ROUND(AVG(score)::numeric, 3) as avg_score,
                       ROUND(AVG(latency_ms)::numeric, 1) as avg_latency,
                       ROUND(SUM(cost_usd)::numeric, 6) as total_cost,
                       MIN(run_at) as run_at
                FROM eval_results
                GROUP BY suite_id
                ORDER BY MIN(run_at) DESC
                LIMIT %s""",
                (limit,),
            ).fetchall()
            return [
                {
                    "suite_id": r[0], "total": r[1], "passed": r[2],
                    "failed": r[3], "avg_score": float(r[4]) if r[4] else 0,
                    "avg_latency_ms": float(r[5]) if r[5] else 0,
                    "total_cost_usd": float(r[6]) if r[6] else 0,
                    "run_at": str(r[7]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to get eval history", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Graph checkpoints
# ---------------------------------------------------------------------------


def store_checkpoint(
    *,
    thread_id: str,
    checkpoint_id: str,
    parent_id: str | None,
    channel_values: dict,
    metadata: dict,
) -> None:
    """Store a graph execution checkpoint."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO graph_checkpoints
                (thread_id, checkpoint_id, parent_id, channel_values, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (thread_id, checkpoint_id) DO UPDATE SET
                    channel_values = EXCLUDED.channel_values,
                    metadata = EXCLUDED.metadata""",
                (
                    thread_id, checkpoint_id, parent_id,
                    json.dumps(channel_values, default=str),
                    json.dumps(metadata, default=str),
                ),
            )
    except Exception:
        logger.warning("Failed to store checkpoint", exc_info=True)


def get_checkpoints(thread_id: str) -> list[dict[str, Any]]:
    """Get all checkpoints for a thread."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT thread_id, checkpoint_id, parent_id,
                       channel_values, metadata, created_at
                FROM graph_checkpoints
                WHERE thread_id = %s
                ORDER BY created_at""",
                (thread_id,),
            ).fetchall()
            return [
                {
                    "thread_id": r[0], "checkpoint_id": r[1],
                    "parent_id": r[2],
                    "channel_values": r[3] if isinstance(r[3], dict) else json.loads(r[3]),
                    "metadata": r[4] if isinstance(r[4], dict) else json.loads(r[4]),
                    "created_at": str(r[5]),
                }
                for r in rows
            ]
    except Exception:
        logger.warning("Failed to get checkpoints for %s", thread_id, exc_info=True)
        return []


def get_latest_checkpoint(thread_id: str) -> dict[str, Any] | None:
    """Get the most recent checkpoint for a thread."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT thread_id, checkpoint_id, parent_id,
                       channel_values, metadata, created_at
                FROM graph_checkpoints
                WHERE thread_id = %s
                ORDER BY created_at DESC
                LIMIT 1""",
                (thread_id,),
            ).fetchone()
            if row:
                return {
                    "thread_id": row[0], "checkpoint_id": row[1],
                    "parent_id": row[2],
                    "channel_values": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                    "metadata": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                    "created_at": str(row[5]),
                }
            return None
    except Exception:
        logger.warning("Failed to get latest checkpoint for %s", thread_id, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Morphogenetic Agency store functions
# ---------------------------------------------------------------------------


def store_developmental_snapshot(snapshot: dict) -> None:
    """Store a developmental trajectory snapshot."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO developmental_snapshots
                (ai_proxy, clc_horizon, clc_dimensions, eta_mean, cp_profile,
                 p_feasible_count, attractor_count, spec_gap_mean,
                 competency_dist, tier_usage, total_reuse)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    snapshot.get("ai_proxy", 0.0),
                    snapshot.get("clc_horizon", 0),
                    snapshot.get("clc_dimensions", 0),
                    snapshot.get("eta_mean", 0.0),
                    json.dumps(snapshot.get("cp_profile", {})),
                    snapshot.get("p_feasible_count", 0),
                    snapshot.get("attractor_count", 0),
                    snapshot.get("spec_gap_mean", 0.0),
                    json.dumps(snapshot.get("competency_dist", {})),
                    json.dumps(snapshot.get("tier_usage", {})),
                    snapshot.get("total_reuse", 0),
                ),
            )
    except Exception:
        logger.warning("Failed to store developmental snapshot", exc_info=True)


def get_developmental_trajectory(limit: int = 100) -> list[dict]:
    """Get historical developmental snapshots."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT snapshot_at, ai_proxy, clc_horizon, clc_dimensions,
                          eta_mean, cp_profile, p_feasible_count, attractor_count,
                          spec_gap_mean, competency_dist, tier_usage, total_reuse
                FROM developmental_snapshots
                ORDER BY snapshot_at DESC LIMIT %s""",
                (limit,),
            ).fetchall()
        return [
            {
                "snapshot_at": str(r[0]),
                "ai_proxy": r[1], "clc_horizon": r[2], "clc_dimensions": r[3],
                "eta_mean": r[4],
                "cp_profile": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                "p_feasible_count": r[6], "attractor_count": r[7],
                "spec_gap_mean": r[8],
                "competency_dist": r[9] if isinstance(r[9], dict) else json.loads(r[9]),
                "tier_usage": r[10] if isinstance(r[10], dict) else json.loads(r[10]),
                "total_reuse": r[11],
            }
            for r in rows
        ]
    except Exception:
        logger.warning("Failed to get developmental trajectory", exc_info=True)
        return []


def store_cascade_event(event: dict) -> int | None:
    """Store a cascade event. Returns the event ID."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """INSERT INTO cascade_events
                (cascade_id, goal_id, channel_id, trigger_p_fail, trigger_ucb,
                 trigger_epsilon, tier_attempted, tier_succeeded, diagnostic,
                 adaptation, competency_id, outcome)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
                (
                    event.get("cascade_id", ""),
                    event.get("goal_id", ""),
                    event.get("channel_id"),
                    event.get("trigger_p_fail"),
                    event.get("trigger_ucb"),
                    event.get("trigger_epsilon"),
                    event.get("tier_attempted", 0),
                    event.get("tier_succeeded"),
                    json.dumps(event.get("diagnostic", {})),
                    json.dumps(event.get("adaptation", {})),
                    event.get("competency_id"),
                    event.get("outcome", "pending"),
                ),
            ).fetchone()
            return row[0] if row else None
    except Exception:
        logger.warning("Failed to store cascade event", exc_info=True)
        return None


def complete_cascade_event(event_id: int, outcome: str, tier_succeeded: int | None = None,
                           adaptation: dict | None = None, competency_id: str | None = None) -> None:
    """Mark a cascade event as completed."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """UPDATE cascade_events SET
                    outcome = %s, tier_succeeded = %s,
                    adaptation = COALESCE(%s, adaptation),
                    competency_id = COALESCE(%s, competency_id),
                    completed_at = NOW()
                WHERE id = %s""",
                (outcome, tier_succeeded,
                 json.dumps(adaptation) if adaptation else None,
                 competency_id, event_id),
            )
    except Exception:
        logger.warning("Failed to complete cascade event %s", event_id, exc_info=True)


def get_cascade_history(limit: int = 50) -> list[dict]:
    """Get recent cascade events."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, cascade_id, goal_id, channel_id, trigger_p_fail,
                          trigger_ucb, trigger_epsilon, tier_attempted,
                          tier_succeeded, diagnostic, adaptation, competency_id,
                          outcome, started_at, completed_at
                FROM cascade_events ORDER BY started_at DESC LIMIT %s""",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0], "cascade_id": r[1], "goal_id": r[2],
                "channel_id": r[3], "trigger_p_fail": r[4],
                "trigger_ucb": r[5], "trigger_epsilon": r[6],
                "tier_attempted": r[7], "tier_succeeded": r[8],
                "diagnostic": r[9] if isinstance(r[9], dict) else json.loads(r[9]),
                "adaptation": r[10] if isinstance(r[10], dict) else json.loads(r[10]),
                "competency_id": r[11], "outcome": r[12],
                "started_at": str(r[13]),
                "completed_at": str(r[14]) if r[14] else None,
            }
            for r in rows
        ]
    except Exception:
        logger.warning("Failed to get cascade history", exc_info=True)
        return []


def get_tier_usage_counts() -> dict[int, int]:
    """Get count of cascade events per tier."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT tier_attempted, COUNT(*) FROM cascade_events GROUP BY tier_attempted"
            ).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Cascade configuration
# ---------------------------------------------------------------------------

_CASCADE_DEFAULTS = {
    "min_observations": 20,
    "delta": 0.05,
    "max_tier0_attempts": 3,
    "max_tier1_attempts": 2,
    "cascade_timeout_seconds": 60,
    "tier0_enabled": True,
    "tier1_enabled": True,
    "tier2_enabled": True,
    "tier3_enabled": True,
    "tier2_auto_approve": False,
    "tier3_auto_approve": False,
}


def get_cascade_config() -> dict[str, Any]:
    """Get the current cascade configuration (single-row pattern)."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT min_observations, delta, max_tier0_attempts,
                          max_tier1_attempts, cascade_timeout_seconds,
                          tier0_enabled, tier1_enabled, tier2_enabled,
                          tier3_enabled, tier2_auto_approve, tier3_auto_approve,
                          updated_at
                FROM cascade_config WHERE id = 1"""
            ).fetchone()
        if row is None:
            return dict(_CASCADE_DEFAULTS)
        return {
            "min_observations": row[0],
            "delta": row[1],
            "max_tier0_attempts": row[2],
            "max_tier1_attempts": row[3],
            "cascade_timeout_seconds": row[4],
            "tier0_enabled": row[5],
            "tier1_enabled": row[6],
            "tier2_enabled": row[7],
            "tier3_enabled": row[8],
            "tier2_auto_approve": row[9],
            "tier3_auto_approve": row[10],
            "updated_at": str(row[11]) if row[11] else None,
        }
    except Exception:
        logger.warning("Failed to get cascade config, using defaults", exc_info=True)
        return dict(_CASCADE_DEFAULTS)


def update_cascade_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Update cascade configuration. Only updates provided fields."""
    allowed = set(_CASCADE_DEFAULTS.keys())
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return get_cascade_config()
    try:
        set_clauses = ", ".join(f"{k} = %s" for k in filtered)
        values = list(filtered.values()) + [1]
        with _get_conn() as conn:
            conn.execute(
                f"UPDATE cascade_config SET {set_clauses}, updated_at = NOW() WHERE id = %s",
                values,
            )
        return get_cascade_config()
    except Exception:
        logger.warning("Failed to update cascade config", exc_info=True)
        return get_cascade_config()


def reset_cascade_config() -> dict[str, Any]:
    """Reset cascade config to defaults."""
    return update_cascade_config(_CASCADE_DEFAULTS)


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


def get_goals() -> list[dict[str, Any]]:
    """Get all morphogenetic goals from DB."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT goal_id, display_name, failure_predicate, epsilon_g,
                          horizon_t, observation_map, formalization_level,
                          g0_description, primary_tier, priority,
                          created_at, updated_at
                FROM morphogenetic_goals ORDER BY priority DESC"""
            ).fetchall()
        return [
            {
                "goal_id": r[0], "display_name": r[1], "failure_predicate": r[2],
                "epsilon_g": r[3], "horizon_t": r[4],
                "observation_map": r[5] if isinstance(r[5], list) else json.loads(r[5]),
                "formalization_level": r[6], "g0_description": r[7],
                "primary_tier": r[8], "priority": r[9],
                "created_at": str(r[10]), "updated_at": str(r[11]),
            }
            for r in rows
        ]
    except Exception:
        logger.warning("Failed to get goals", exc_info=True)
        return []


def get_goal(goal_id: str) -> dict[str, Any] | None:
    """Get a single goal by ID."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT goal_id, display_name, failure_predicate, epsilon_g,
                          horizon_t, observation_map, formalization_level,
                          g0_description, primary_tier, priority,
                          created_at, updated_at
                FROM morphogenetic_goals WHERE goal_id = %s""",
                (goal_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "goal_id": row[0], "display_name": row[1], "failure_predicate": row[2],
            "epsilon_g": row[3], "horizon_t": row[4],
            "observation_map": row[5] if isinstance(row[5], list) else json.loads(row[5]),
            "formalization_level": row[6], "g0_description": row[7],
            "primary_tier": row[8], "priority": row[9],
            "created_at": str(row[10]), "updated_at": str(row[11]),
        }
    except Exception:
        logger.warning("Failed to get goal %s", goal_id, exc_info=True)
        return None


def upsert_goal(goal: dict[str, Any]) -> dict[str, Any] | None:
    """Create or update a morphogenetic goal."""
    try:
        obs_map = goal.get("observation_map", [])
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO morphogenetic_goals
                    (goal_id, display_name, failure_predicate, epsilon_g,
                     horizon_t, observation_map, formalization_level,
                     g0_description, primary_tier, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (goal_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    failure_predicate = EXCLUDED.failure_predicate,
                    epsilon_g = EXCLUDED.epsilon_g,
                    horizon_t = EXCLUDED.horizon_t,
                    observation_map = EXCLUDED.observation_map,
                    formalization_level = EXCLUDED.formalization_level,
                    g0_description = EXCLUDED.g0_description,
                    primary_tier = EXCLUDED.primary_tier,
                    priority = EXCLUDED.priority,
                    updated_at = NOW()""",
                (
                    goal["goal_id"], goal["display_name"], goal["failure_predicate"],
                    goal["epsilon_g"], goal["horizon_t"],
                    json.dumps(obs_map), goal.get("formalization_level", "g1_spec"),
                    goal.get("g0_description", ""), goal.get("primary_tier", 0),
                    goal.get("priority", 5),
                ),
            )
        return get_goal(goal["goal_id"])
    except Exception:
        logger.warning("Failed to upsert goal %s", goal.get("goal_id"), exc_info=True)
        return None


def delete_goal(goal_id: str) -> bool:
    """Delete a morphogenetic goal."""
    try:
        with _get_conn() as conn:
            result = conn.execute(
                "DELETE FROM morphogenetic_goals WHERE goal_id = %s", (goal_id,)
            )
            return result.rowcount > 0
    except Exception:
        logger.warning("Failed to delete goal %s", goal_id, exc_info=True)
        return False


def seed_default_goals(defaults: list[dict[str, Any]]) -> int:
    """Seed default goals into DB if table is empty. Returns count seeded."""
    existing = get_goals()
    if existing:
        return 0
    count = 0
    for goal in defaults:
        if upsert_goal(goal) is not None:
            count += 1
    return count


# ---------------------------------------------------------------------------
# System image export/import
# ---------------------------------------------------------------------------


def export_system_image() -> dict[str, Any]:
    """Export the full system configuration as a portable image."""
    import hashlib

    image: dict[str, Any] = {
        "format": "holly-grace-system-image",
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with _get_conn() as conn:
            # Agents
            rows = conn.execute(
                """SELECT agent_id, channel_id, display_name, description,
                          model_id, system_prompt, tool_ids, is_builtin, version
                FROM agent_configs WHERE deleted_at IS NULL"""
            ).fetchall()
            image["agents"] = [
                {
                    "agent_id": r[0], "channel_id": r[1], "display_name": r[2],
                    "description": r[3], "model_id": r[4], "system_prompt": r[5],
                    "tool_ids": list(r[6]) if r[6] else [], "is_builtin": r[7],
                    "version": r[8],
                }
                for r in rows
            ]

            # Workflows
            rows = conn.execute(
                """SELECT workflow_id, display_name, description, version,
                          is_active, is_builtin, definition
                FROM workflow_definitions WHERE deleted_at IS NULL"""
            ).fetchall()
            image["workflows"] = [
                {
                    "workflow_id": r[0], "display_name": r[1], "description": r[2],
                    "version": r[3], "is_active": r[4], "is_builtin": r[5],
                    "definition": r[6] if isinstance(r[6], dict) else json.loads(r[6]),
                }
                for r in rows
            ]

            # Goals
            image["goals"] = get_goals()

            # Cascade config
            image["cascade_config"] = get_cascade_config()

            # Assembly cache
            rows = conn.execute(
                """SELECT competency_id, tier, competency_type, channel_id,
                          goal_id, adaptation, context_fingerprint, reuse_count,
                          success_rate, assembly_index
                FROM assembly_cache"""
            ).fetchall()
            image["assembly_cache"] = [
                {
                    "competency_id": r[0], "tier": r[1], "competency_type": r[2],
                    "channel_id": r[3], "goal_id": r[4],
                    "adaptation": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                    "context_fingerprint": r[6], "reuse_count": r[7],
                    "success_rate": r[8], "assembly_index": r[9],
                }
                for r in rows
            ]

    except Exception:
        logger.warning("Failed to export system image", exc_info=True)

    # Compute checksum over the data content
    content = json.dumps(image, sort_keys=True, default=str)
    image["checksum"] = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    return image


def import_system_image(image: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Import a system image. Returns a summary of changes.

    If dry_run=True, only computes what would change without applying.
    """
    summary: dict[str, Any] = {"agents": [], "workflows": [], "goals": [], "cascade_config": {}, "assembly_cache": 0}

    # Validate format
    if image.get("format") != "holly-grace-system-image":
        return {"error": "Invalid image format"}

    # Count what would change
    for agent in image.get("agents", []):
        existing = _get_agent_by_id(agent.get("agent_id", ""))
        if existing:
            summary["agents"].append({"agent_id": agent["agent_id"], "action": "update"})
        else:
            summary["agents"].append({"agent_id": agent["agent_id"], "action": "create"})

    for wf in image.get("workflows", []):
        summary["workflows"].append({"workflow_id": wf.get("workflow_id", ""), "action": "upsert"})

    for goal in image.get("goals", []):
        existing = get_goal(goal.get("goal_id", ""))
        if existing:
            summary["goals"].append({"goal_id": goal["goal_id"], "action": "update"})
        else:
            summary["goals"].append({"goal_id": goal["goal_id"], "action": "create"})

    if image.get("cascade_config"):
        current = get_cascade_config()
        changes = {k: v for k, v in image["cascade_config"].items()
                   if k in _CASCADE_DEFAULTS and current.get(k) != v}
        summary["cascade_config"] = changes

    summary["assembly_cache"] = len(image.get("assembly_cache", []))

    if dry_run:
        return {"dry_run": True, "summary": summary}

    # Apply changes
    try:
        # Import agents
        for agent in image.get("agents", []):
            _import_agent(agent)

        # Import workflows
        for wf in image.get("workflows", []):
            _import_workflow(wf)

        # Import goals
        for goal in image.get("goals", []):
            upsert_goal(goal)

        # Import cascade config
        if image.get("cascade_config"):
            update_cascade_config(image["cascade_config"])

        # Import assembly cache
        for comp in image.get("assembly_cache", []):
            _import_competency(comp)

    except Exception:
        logger.warning("Failed to import system image", exc_info=True)
        return {"error": "Import failed", "summary": summary}

    return {"dry_run": False, "summary": summary, "applied": True}


def _get_agent_by_id(agent_id: str) -> dict | None:
    """Quick check if an agent exists."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT agent_id FROM agent_configs WHERE agent_id = %s AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
        return {"agent_id": row[0]} if row else None
    except Exception:
        return None


def _import_agent(agent: dict) -> None:
    """Import a single agent config (upsert)."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_configs
                (agent_id, channel_id, display_name, description,
                 model_id, system_prompt, tool_ids, is_builtin, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (agent_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                model_id = EXCLUDED.model_id,
                system_prompt = EXCLUDED.system_prompt,
                tool_ids = EXCLUDED.tool_ids,
                version = agent_configs.version + 1,
                updated_at = NOW()""",
            (
                agent["agent_id"], agent.get("channel_id", ""),
                agent["display_name"], agent.get("description", ""),
                agent["model_id"], agent["system_prompt"],
                agent.get("tool_ids", []), agent.get("is_builtin", False),
                agent.get("version", 1),
            ),
        )


def _import_workflow(wf: dict) -> None:
    """Import a single workflow definition (upsert)."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO workflow_definitions
                (workflow_id, display_name, description, version,
                 is_active, is_builtin, definition)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (workflow_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                definition = EXCLUDED.definition,
                version = workflow_definitions.version + 1,
                updated_at = NOW()""",
            (
                wf["workflow_id"], wf["display_name"], wf.get("description", ""),
                wf.get("version", 1), wf.get("is_active", False),
                wf.get("is_builtin", False), json.dumps(wf.get("definition", {})),
            ),
        )


def _import_competency(comp: dict) -> None:
    """Import a single competency (upsert)."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO assembly_cache
                (competency_id, tier, competency_type, channel_id, goal_id,
                 adaptation, context_fingerprint, reuse_count, success_rate,
                 assembly_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (competency_id) DO UPDATE SET
                reuse_count = GREATEST(assembly_cache.reuse_count, EXCLUDED.reuse_count),
                success_rate = EXCLUDED.success_rate,
                last_used_at = NOW()""",
            (
                comp["competency_id"], comp["tier"], comp["competency_type"],
                comp.get("channel_id"), comp.get("goal_id"),
                json.dumps(comp.get("adaptation", {})),
                comp.get("context_fingerprint"), comp.get("reuse_count", 0),
                comp.get("success_rate", 1.0), comp.get("assembly_index", 0.0),
            ),
        )


def store_system_image(image: dict[str, Any]) -> int | None:
    """Store a system image snapshot in the database for history."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                """INSERT INTO system_images (name, image_data, checksum, exported_at)
                VALUES (%s, %s, %s, %s) RETURNING id""",
                (
                    image.get("name", f"export-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"),
                    json.dumps(image, default=str),
                    image.get("checksum", ""),
                    image.get("exported_at", datetime.now(timezone.utc).isoformat()),
                ),
            ).fetchone()
            return row[0] if row else None
    except Exception:
        logger.warning("Failed to store system image", exc_info=True)
        return None


def list_system_images() -> list[dict]:
    """List all stored system images (metadata only, not full data)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT id, name, checksum, exported_at
                FROM system_images ORDER BY exported_at DESC"""
            ).fetchall()
        return [
            {"id": r[0], "name": r[1], "checksum": r[2], "exported_at": str(r[3])}
            for r in rows
        ]
    except Exception:
        logger.warning("Failed to list system images", exc_info=True)
        return []


def get_system_image(image_id: int) -> dict[str, Any] | None:
    """Get a full system image by ID."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT image_data FROM system_images WHERE id = %s", (image_id,)
            ).fetchone()
        if row is None:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception:
        logger.warning("Failed to get system image %s", image_id, exc_info=True)
        return None
