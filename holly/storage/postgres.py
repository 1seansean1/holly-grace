"""Async PostgreSQL client with tenant-isolated RLS (Task 22.5).

Implements the Postgres storage layer per ICD v0.1:

- ICD-032: Core ↔ PostgreSQL (State/History) — agents, goals, topologies,
  conversations, goals_history, idempotency_keys
- ICD-036: Observability ↔ PostgreSQL (Partitioned Logs) — logs
- ICD-038: Kernel ↔ PostgreSQL (Audit WAL) — kernel_audit_log
- ICD-039: Workflow Engine ↔ PostgreSQL (Checkpoints) — workflow_checkpoints
- ICD-040: Engine ↔ PostgreSQL (Task State) — task_state
- ICD-042: Memory System ↔ PostgreSQL (Medium-Term Memory) — memory_store
- ICD-045: KMS → PostgreSQL (DB Credentials) — credential fetch on startup

Design principles
-----------------
- Protocol-based backend abstraction: production uses ``asyncpg``;
  tests substitute mock implementations.
- Per-tenant async connection pool (``min_size=2``, ``max_size=10``),
  matching ICD-032 auth: "Connection pooling (asyncpg pool, 10 connections
  per tenant)".
- Application-enforced RLS: every acquired connection executes
  ``SET LOCAL app.current_tenant = '<tenant_id>'`` before any query,
  matching the RLS policy ``USING (tenant_id =
  current_setting('app.current_tenant')::uuid)``.
- Deadlock retry: exponential back-off (1 ms → 2 ms → 4 ms → max 100 ms),
  per ICD-032 error contract.
- 30 s query timeout, 30 s connection-acquisition timeout (ICD-032 / ICD-039).
- Audit writes non-blocking (ICD-038): failure logged but does not raise.

Usage
-----
::

    creds = TenantCredentials(
        host="postgres.internal", port=5432,
        user="holly_core_tenant_a", password="...",
        database="holly", tenant_id=uuid.UUID("..."),
    )
    backend = PostgresBackend.from_credentials(creds)
    await backend.open()
    await backend.goals.insert(goal_row)
    await backend.close()
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (ICD-032 / ICD-039 latency / pool specs)
# ---------------------------------------------------------------------------

_POOL_MIN_SIZE: int = 2
_POOL_MAX_SIZE: int = 10  # ICD-032: 10 connections per tenant
_ACQUIRE_TIMEOUT_S: float = 30.0
_QUERY_TIMEOUT_S: float = 30.0

# Deadlock retry schedule (milliseconds): ICD-032 error contract
_DEADLOCK_DELAYS_MS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 100)


# ---------------------------------------------------------------------------
# Protocol: asyncpg-compatible connection / pool
# ---------------------------------------------------------------------------


@runtime_checkable
class ConnectionProto(Protocol):
    """Subset of asyncpg.Connection used by this module."""

    async def execute(self, query: str, *args: Any, timeout: float | None = None) -> str:
        ...

    async def fetch(self, query: str, *args: Any, timeout: float | None = None) -> list[Any]:
        ...

    async def fetchrow(self, query: str, *args: Any, timeout: float | None = None) -> Any | None:
        ...

    async def fetchval(self, query: str, *args: Any, timeout: float | None = None) -> Any:
        ...


@runtime_checkable
class PoolProto(Protocol):
    """Subset of asyncpg.Pool used by this module."""

    @asynccontextmanager
    def acquire(self) -> AsyncIterator[ConnectionProto]:  # type: ignore[empty-body]
        ...

    async def close(self) -> None:
        ...


@runtime_checkable
class PoolFactory(Protocol):
    """Factory that creates a PoolProto for given DSN + pool settings."""

    async def create(
        self,
        dsn: str,
        *,
        min_size: int,
        max_size: int,
        timeout: float,
    ) -> PoolProto:
        ...


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TenantCredentials:
    """Connection credentials for one tenant (ICD-045)."""

    host: str
    port: int
    user: str
    password: str
    database: str
    tenant_id: uuid.UUID

    @property
    def dsn(self) -> str:
        """asyncpg DSN string (password embedded — never logged)."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


# ---------------------------------------------------------------------------
# Tenant-isolated pool
# ---------------------------------------------------------------------------


class TenantIsolatedPool:
    """Async connection pool with per-connection RLS context injection.

    On every ``acquire()`` the pool executes::

        SET LOCAL app.current_tenant = '<tenant_id>';

    before yielding the connection.  This activates the PostgreSQL RLS
    policy ``USING (tenant_id = current_setting('app.current_tenant')::uuid)``
    that must be defined on every tenant-scoped table.

    Parameters
    ----------
    pool:
        Underlying connection pool (asyncpg.Pool in production, mock in tests).
    tenant_id:
        UUID that identifies this tenant context.
    """

    __slots__ = ("_pool", "_tenant_id", "_tenant_str")

    def __init__(self, pool: PoolProto, tenant_id: uuid.UUID) -> None:
        self._pool = pool
        self._tenant_id = tenant_id
        self._tenant_str = str(tenant_id)

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[ConnectionProto]:
        """Yield a connection with RLS tenant context set."""
        async with self._pool.acquire() as conn:  # type: ignore[attr-defined]
            # RLS activation: atomic within connection transaction
            await conn.execute(
                "SET LOCAL app.current_tenant = $1",
                self._tenant_str,
                timeout=_QUERY_TIMEOUT_S,
            )
            yield conn

    async def close(self) -> None:
        await self._pool.close()


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


class _DeadlockError(Exception):
    """Sentinel raised by the retry wrapper when asyncpg.DeadlockDetectedError
    is caught.  Avoids a hard asyncpg import at module level.
    """


async def _with_deadlock_retry(coro_fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute ``coro_fn(*args, **kwargs)``, retrying on asyncpg deadlock.

    Retry schedule: 1 ms, 2 ms, 4 ms, 8 ms, 16 ms, 32 ms, 64 ms, 100 ms.
    After all retries exhausted, re-raises the last exception.
    """
    try:
        import asyncpg  # local import — not required at module level
        _deadlock_exc = asyncpg.DeadlockDetectedError
    except ImportError:
        _deadlock_exc = _DeadlockError  # type: ignore[assignment]

    last_exc: BaseException | None = None
    for delay_ms in _DEADLOCK_DELAYS_MS:
        try:
            return await coro_fn(*args, **kwargs)
        except _deadlock_exc as exc:  # type: ignore[misc]
            last_exc = exc
            await asyncio.sleep(delay_ms / 1000.0)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

# All CREATE TABLE statements.  RLS policies are appended by enable_rls().
# Partitioning (logs by date+tenant) is done via pg-side triggers in
# production; the schema here creates the parent table only.

DDL_TABLES: tuple[str, ...] = (
    # ICD-032 — Core state tables
    """
    CREATE TABLE IF NOT EXISTS agents (
        id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID        NOT NULL,
        type        VARCHAR(64) NOT NULL,
        config      JSONB       NOT NULL DEFAULT '{}'::jsonb,
        checkpoint  JSONB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS goals (
        id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID        NOT NULL,
        level       INT         NOT NULL,
        predicate   TEXT        NOT NULL,
        deadline    BIGINT,
        status      VARCHAR(32) NOT NULL DEFAULT 'pending',
        celestial   BOOLEAN     NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topologies (
        id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id           UUID    NOT NULL,
        agents              UUID[]  NOT NULL DEFAULT '{}',
        contracts           JSONB   NOT NULL DEFAULT '{}'::jsonb,
        eigenspectrum_state JSONB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id        UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID  NOT NULL,
        user_id   UUID  NOT NULL,
        messages  JSONB NOT NULL DEFAULT '[]'::jsonb,
        context   JSONB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS goals_history (
        id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID    NOT NULL,
        goal_id     UUID    NOT NULL REFERENCES goals(id),
        delta_state JSONB   NOT NULL,
        timestamp   BIGINT  NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS idempotency_keys (
        key         VARCHAR(128) PRIMARY KEY,
        tenant_id   UUID         NOT NULL,
        result      JSONB,
        created_at  BIGINT       NOT NULL,
        expires_at  BIGINT       NOT NULL
    )
    """,
    # ICD-036 — Observability logs (parent partition table)
    """
    CREATE TABLE IF NOT EXISTS logs (
        id            BIGSERIAL   NOT NULL,
        tenant_id     UUID        NOT NULL,
        timestamp     BIGINT      NOT NULL,
        level         VARCHAR(16) NOT NULL,
        logger        VARCHAR(128),
        message       TEXT        NOT NULL,
        trace_id      UUID,
        span_id       UUID,
        user_id       UUID,
        component     VARCHAR(64),
        event_data    JSONB,
        redacted_hash VARCHAR(64),
        PRIMARY KEY (id, tenant_id, timestamp)
    )
    """,
    # ICD-038 — Kernel audit WAL (append-only, no RLS)
    """
    CREATE TABLE IF NOT EXISTS kernel_audit_log (
        id              BIGSERIAL   NOT NULL PRIMARY KEY,
        tenant_id       UUID        NOT NULL,
        boundary_id     VARCHAR(64) NOT NULL,
        operation       VARCHAR(64) NOT NULL,
        input_hash      VARCHAR(64),
        output_hash     VARCHAR(64),
        violations      JSONB       NOT NULL DEFAULT '[]'::jsonb,
        timestamp       BIGINT      NOT NULL,
        trace_id        UUID,
        user_id         UUID,
        permission_mask VARCHAR(32)
    )
    """,
    # ICD-039 — Workflow checkpoints
    """
    CREATE TABLE IF NOT EXISTS workflow_checkpoints (
        workflow_id          UUID    NOT NULL,
        node_id              UUID    NOT NULL,
        output_state         JSONB,
        checkpoint_timestamp BIGINT  NOT NULL,
        idempotency_key      VARCHAR(128),
        output_hash          VARCHAR(64),
        execution_time_ms    INT,
        parent_node_ids      UUID[]  NOT NULL DEFAULT '{}',
        tenant_id            UUID    NOT NULL,
        user_id              UUID,
        trace_id             UUID,
        PRIMARY KEY (workflow_id, node_id)
    )
    """,
    # ICD-040 — Engine task state projection
    """
    CREATE TABLE IF NOT EXISTS task_state (
        task_id           UUID        PRIMARY KEY,
        execution_id      UUID        NOT NULL,
        status            VARCHAR(32) NOT NULL DEFAULT 'enqueued',
        started_at        BIGINT,
        completed_at      BIGINT,
        result            JSONB,
        error             JSONB,
        retries_attempted INT         NOT NULL DEFAULT 0,
        next_retry_time   BIGINT,
        lane_type         VARCHAR(32),
        tenant_id         UUID        NOT NULL,
        user_id           UUID,
        trace_id          UUID
    )
    """,
    # ICD-042 — Memory store (medium-term memory)
    """
    CREATE TABLE IF NOT EXISTS memory_store (
        id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID,
        agent_id        UUID,
        memory_type     VARCHAR(32) NOT NULL CHECK (
            memory_type IN ('conversation', 'decision', 'fact')
        ),
        content         TEXT        NOT NULL,
        embedding_id    UUID,
        timestamp       BIGINT      NOT NULL,
        tenant_id       UUID        NOT NULL,
        retention_days  INT         NOT NULL DEFAULT 30
    )
    """,
)

# Tables that get RLS policies (all except kernel_audit_log which is append-only)
_RLS_TABLES: tuple[str, ...] = (
    "agents",
    "goals",
    "topologies",
    "conversations",
    "goals_history",
    "idempotency_keys",
    "logs",
    "workflow_checkpoints",
    "task_state",
    "memory_store",
)

# Indexes for common query patterns
DDL_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_goals_tenant ON goals(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_goals_history_goal ON goals_history(goal_id)",
    "CREATE INDEX IF NOT EXISTS idx_idempotency_tenant ON idempotency_keys(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_logs_trace ON logs(trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_logs_tenant_ts ON logs(tenant_id, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_tenant ON kernel_audit_log(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_trace ON kernel_audit_log(trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_checkpoints_tenant ON workflow_checkpoints(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_task_state_tenant ON task_state(tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_task_state_trace ON task_state(trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_tenant ON memory_store(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_conv ON memory_store(conversation_id)",
)


# ---------------------------------------------------------------------------
# Schema manager
# ---------------------------------------------------------------------------


class SchemaManager:
    """Creates tables, indexes, and RLS policies.

    Parameters
    ----------
    conn:
        An open database connection (must have superuser or CREATE TABLE rights).
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: ConnectionProto) -> None:
        self._conn = conn

    async def create_tables(self) -> None:
        """Execute all CREATE TABLE IF NOT EXISTS statements."""
        for ddl in DDL_TABLES:
            await self._conn.execute(ddl.strip(), timeout=_QUERY_TIMEOUT_S)

    async def create_indexes(self) -> None:
        """Create all performance indexes."""
        for ddl in DDL_INDEXES:
            await self._conn.execute(ddl, timeout=_QUERY_TIMEOUT_S)

    async def enable_rls(self) -> None:
        """Enable RLS on all tenant-scoped tables and create isolation policy."""
        for table in _RLS_TABLES:
            await self._conn.execute(
                f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                timeout=_QUERY_TIMEOUT_S,
            )
            await self._conn.execute(
                f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
                timeout=_QUERY_TIMEOUT_S,
            )
            # Drop old policy if it exists (idempotent migration)
            await self._conn.execute(
                f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
                timeout=_QUERY_TIMEOUT_S,
            )
            await self._conn.execute(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                    USING (tenant_id = current_setting(
                        'app.current_tenant', TRUE
                    )::uuid)
                """,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def run_migrations(self) -> None:
        """Full migration: tables → indexes → RLS."""
        await self.create_tables()
        await self.create_indexes()
        await self.enable_rls()


# ---------------------------------------------------------------------------
# Row dataclasses (typed wrappers around DB rows)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GoalRow:
    """One row from the ``goals`` table (ICD-032)."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    level: int = 0
    predicate: str = ""
    deadline: int | None = None
    status: str = "pending"
    celestial: bool = False


@dataclass(slots=True)
class AgentRow:
    """One row from the ``agents`` table (ICD-032)."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    type: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] | None = None


@dataclass(slots=True)
class AuditRow:
    """One row for ``kernel_audit_log`` (ICD-038)."""

    tenant_id: uuid.UUID
    boundary_id: str
    operation: str
    input_hash: str = ""
    output_hash: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)
    timestamp: int = 0
    trace_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    permission_mask: str | None = None


@dataclass(slots=True)
class CheckpointRow:
    """One row for ``workflow_checkpoints`` (ICD-039)."""

    workflow_id: uuid.UUID
    node_id: uuid.UUID
    tenant_id: uuid.UUID
    checkpoint_timestamp: int
    output_state: dict[str, Any] | None = None
    idempotency_key: str | None = None
    output_hash: str | None = None
    execution_time_ms: int | None = None
    parent_node_ids: list[uuid.UUID] = field(default_factory=list)
    user_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None


@dataclass(slots=True)
class TaskStateRow:
    """One row for ``task_state`` (ICD-040)."""

    task_id: uuid.UUID
    execution_id: uuid.UUID
    tenant_id: uuid.UUID
    status: str = "enqueued"
    started_at: int | None = None
    completed_at: int | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    retries_attempted: int = 0
    next_retry_time: int | None = None
    lane_type: str | None = None
    user_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None


@dataclass(slots=True)
class MemoryRow:
    """One row for ``memory_store`` (ICD-042)."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    memory_type: str = "conversation"
    content: str = ""
    embedding_id: uuid.UUID | None = None
    timestamp: int = 0
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    retention_days: int = 30


# ---------------------------------------------------------------------------
# Table-specific repositories
# ---------------------------------------------------------------------------


class GoalsRepo:
    """CRUD operations on the ``goals`` table (ICD-032).

    All queries enforce tenant isolation via the caller's TenantIsolatedPool
    which sets ``app.current_tenant`` before every statement.  The RLS policy
    then filters rows transparently — cross-tenant rows return 0 results.
    """

    __slots__ = ("_pool",)

    def __init__(self, pool: TenantIsolatedPool) -> None:
        self._pool = pool

    async def insert(self, row: GoalRow) -> uuid.UUID:
        """Insert a goal; return the generated id."""
        async with self._pool.acquire() as conn:
            return await _with_deadlock_retry(
                conn.fetchval,
                """
                INSERT INTO goals (id, tenant_id, level, predicate,
                                   deadline, status, celestial)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                row.id,
                row.tenant_id,
                row.level,
                row.predicate,
                row.deadline,
                row.status,
                row.celestial,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def get(self, goal_id: uuid.UUID) -> Any | None:
        """Fetch one goal by id; RLS silently denies cross-tenant rows."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM goals WHERE id = $1",
                goal_id,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def list_by_status(self, status: str) -> list[Any]:
        """Return all goals with the given status for this tenant."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM goals WHERE status = $1 ORDER BY level",
                status,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def update_status(self, goal_id: uuid.UUID, status: str) -> None:
        """Update status; RLS silently ignores cross-tenant goal_id."""
        async with self._pool.acquire() as conn:
            await _with_deadlock_retry(
                conn.execute,
                "UPDATE goals SET status = $1 WHERE id = $2",
                status,
                goal_id,
                timeout=_QUERY_TIMEOUT_S,
            )


class AuditRepo:
    """Append-only writes to ``kernel_audit_log`` (ICD-038).

    Write failures are caught and logged but do not raise — the Kernel must
    not be blocked by audit I/O (ICD-038 error contract).
    """

    __slots__ = ("_pool",)

    def __init__(self, pool: TenantIsolatedPool) -> None:
        self._pool = pool

    async def append(self, row: AuditRow) -> None:
        """Append one audit entry.  Failure is non-fatal (ICD-038)."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kernel_audit_log (
                        tenant_id, boundary_id, operation,
                        input_hash, output_hash, violations,
                        timestamp, trace_id, user_id, permission_mask
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    row.tenant_id,
                    row.boundary_id,
                    row.operation,
                    row.input_hash,
                    row.output_hash,
                    row.violations,
                    row.timestamp,
                    row.trace_id,
                    row.user_id,
                    row.permission_mask,
                    timeout=1.0,  # ICD-038: 1s timeout, non-blocking
                )
        except Exception:
            log.exception("kernel_audit_log write failed (non-fatal)")


class CheckpointsRepo:
    """UPSERT/SELECT for ``workflow_checkpoints`` (ICD-039)."""

    __slots__ = ("_pool",)

    def __init__(self, pool: TenantIsolatedPool) -> None:
        self._pool = pool

    async def upsert(self, row: CheckpointRow) -> None:
        """UPSERT checkpoint; idempotent on (workflow_id, node_id)."""
        async with self._pool.acquire() as conn:
            await _with_deadlock_retry(
                conn.execute,
                """
                INSERT INTO workflow_checkpoints (
                    workflow_id, node_id, output_state,
                    checkpoint_timestamp, idempotency_key, output_hash,
                    execution_time_ms, parent_node_ids,
                    tenant_id, user_id, trace_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (workflow_id, node_id)
                DO UPDATE SET
                    output_state         = EXCLUDED.output_state,
                    checkpoint_timestamp = EXCLUDED.checkpoint_timestamp,
                    output_hash          = EXCLUDED.output_hash,
                    execution_time_ms    = EXCLUDED.execution_time_ms
                """,
                row.workflow_id,
                row.node_id,
                row.output_state,
                row.checkpoint_timestamp,
                row.idempotency_key,
                row.output_hash,
                row.execution_time_ms,
                row.parent_node_ids,
                row.tenant_id,
                row.user_id,
                row.trace_id,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def get(self, workflow_id: uuid.UUID, node_id: uuid.UUID) -> Any | None:
        """Fetch checkpoint; returns None if not found or cross-tenant."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM workflow_checkpoints "
                "WHERE workflow_id = $1 AND node_id = $2",
                workflow_id,
                node_id,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def list_workflow(self, workflow_id: uuid.UUID) -> list[Any]:
        """Return all nodes for a workflow (for recovery scan)."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM workflow_checkpoints WHERE workflow_id = $1",
                workflow_id,
                timeout=_QUERY_TIMEOUT_S,
            )


class TaskStateRepo:
    """INSERT/UPDATE for ``task_state`` table (ICD-040)."""

    __slots__ = ("_pool",)

    def __init__(self, pool: TenantIsolatedPool) -> None:
        self._pool = pool

    async def upsert(self, row: TaskStateRow) -> None:
        """Insert or update task state (monitoring projection)."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO task_state (
                        task_id, execution_id, status, started_at,
                        completed_at, result, error, retries_attempted,
                        next_retry_time, lane_type, tenant_id, user_id, trace_id
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (task_id) DO UPDATE SET
                        status            = EXCLUDED.status,
                        completed_at      = EXCLUDED.completed_at,
                        result            = EXCLUDED.result,
                        error             = EXCLUDED.error,
                        retries_attempted = EXCLUDED.retries_attempted
                    """,
                    row.task_id,
                    row.execution_id,
                    row.status,
                    row.started_at,
                    row.completed_at,
                    row.result,
                    row.error,
                    row.retries_attempted,
                    row.next_retry_time,
                    row.lane_type,
                    row.tenant_id,
                    row.user_id,
                    row.trace_id,
                    timeout=_QUERY_TIMEOUT_S,
                )
        except Exception:
            # ICD-040: task_state is monitoring projection; failure is non-fatal
            log.exception("task_state upsert failed (non-fatal)")

    async def get(self, task_id: uuid.UUID) -> Any | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM task_state WHERE task_id = $1",
                task_id,
                timeout=_QUERY_TIMEOUT_S,
            )


class MemoryRepo:
    """INSERT/SELECT for ``memory_store`` (ICD-042)."""

    __slots__ = ("_pool",)

    def __init__(self, pool: TenantIsolatedPool) -> None:
        self._pool = pool

    async def insert(self, row: MemoryRow) -> uuid.UUID:
        """Insert a memory entry; return the id."""
        async with self._pool.acquire() as conn:
            return await _with_deadlock_retry(
                conn.fetchval,
                """
                INSERT INTO memory_store (
                    id, conversation_id, agent_id, memory_type,
                    content, embedding_id, timestamp, tenant_id, retention_days
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
                """,
                row.id,
                row.conversation_id,
                row.agent_id,
                row.memory_type,
                row.content,
                row.embedding_id,
                row.timestamp,
                row.tenant_id,
                row.retention_days,
                timeout=_QUERY_TIMEOUT_S,
            )

    async def list_for_agent(self, agent_id: uuid.UUID) -> list[Any]:
        """Return all memories for a given agent (scoped by RLS to tenant)."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM memory_store WHERE agent_id = $1 "
                "ORDER BY timestamp DESC",
                agent_id,
                timeout=_QUERY_TIMEOUT_S,
            )


# ---------------------------------------------------------------------------
# High-level backend
# ---------------------------------------------------------------------------


class PostgresBackend:
    """Facade over all table repositories.

    Opened once per tenant; exposes ``goals``, ``audit``, ``checkpoints``,
    ``task_state``, and ``memory`` repositories.

    Parameters
    ----------
    pool:
        Underlying asyncpg pool (injected for testability).
    tenant_id:
        The tenant this backend serves.
    """

    __slots__ = (
        "_raw_pool",
        "_tenant_pool",
        "audit",
        "checkpoints",
        "goals",
        "memory",
        "task_state",
    )

    def __init__(self, pool: PoolProto, tenant_id: uuid.UUID) -> None:
        self._raw_pool = pool
        self._tenant_pool = TenantIsolatedPool(pool, tenant_id)
        self.goals = GoalsRepo(self._tenant_pool)
        self.audit = AuditRepo(self._tenant_pool)
        self.checkpoints = CheckpointsRepo(self._tenant_pool)
        self.task_state = TaskStateRepo(self._tenant_pool)
        self.memory = MemoryRepo(self._tenant_pool)

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_pool.tenant_id

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await self._raw_pool.close()

    @classmethod
    async def from_credentials(
        cls,
        creds: TenantCredentials,
        *,
        pool_factory: PoolFactory | None = None,
    ) -> PostgresBackend:
        """Create and open a PostgresBackend from TenantCredentials.

        Parameters
        ----------
        creds:
            Per-tenant DB credentials (ICD-045).
        pool_factory:
            Optional pool factory for dependency injection in tests.
            If None, uses the real asyncpg.create_pool.
        """
        if pool_factory is None:
            import asyncpg  # deferred import

            class _AsyncpgFactory:
                async def create(
                    self,
                    dsn: str,
                    *,
                    min_size: int,
                    max_size: int,
                    timeout: float,
                ) -> PoolProto:
                    return await asyncpg.create_pool(  # type: ignore[return-value]
                        dsn,
                        min_size=min_size,
                        max_size=max_size,
                        timeout=timeout,
                    )

            pool_factory = _AsyncpgFactory()

        pool = await pool_factory.create(
            creds.dsn,
            min_size=_POOL_MIN_SIZE,
            max_size=_POOL_MAX_SIZE,
            timeout=_ACQUIRE_TIMEOUT_S,
        )
        return cls(pool, creds.tenant_id)
