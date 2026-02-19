"""Partition lifecycle manager for time-based PostgreSQL partitions.

Implements ICD-036 (logs, partitioned by date+tenant) and ICD-038
(kernel_audit_log, partitioned by date) lifecycle operations:

- ensure_partition   — idempotent CREATE TABLE (auto-create before INSERT)
- archive_partition  — COPY → S3 upload → DROP TABLE
- restore_partition  — S3 download → CREATE TABLE → COPY FROM
- list_expired_partitions — find tables older than TTL via pg_tables
- run_archival_cycle — archive all expired partitions in one pass
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

try:
    from datetime import UTC
except ImportError:  # Python < 3.11
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

if TYPE_CHECKING:
    from uuid import UUID

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DAY_SECONDS: int = 86_400
_DEFAULT_TTL_DAYS: int = 90
_S3_PREFIX: str = "partitions"

# Parent tables subject to time-based partitioning.
# Value is True when partitions are further scoped per-tenant.
PARTITIONED_TABLES: dict[str, bool] = {
    "logs": True,            # ICD-036: date + tenant
    "kernel_audit_log": False,  # ICD-038: date only
}

# Regex that matches any canonical partition table name produced by this module.
_PARTITION_RE = re.compile(
    r"^(?P<parent>[a-z_]+)"
    r"_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})"
    r"(?:_(?P<tenant>[0-9a-f]{8}))?$"
)

# Regex for pg_tables query (filters to known partition patterns only).
_PG_TABLE_PATTERN: str = (
    r"^(logs|kernel_audit_log)_[0-9]{4}_[0-9]{2}_[0-9]{2}(_[0-9a-f]{8})?$"
)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class PartitionConnectionProto(Protocol):
    """Minimal DB connection interface required by PartitionManager."""

    async def execute(self, sql: str, *args: object) -> None:
        """Execute a DDL or DML statement."""
        ...

    async def fetch(self, sql: str, *args: object) -> list[dict[str, object]]:
        """Run a SELECT and return rows as dicts."""
        ...

    async def copy_out(self, sql: str) -> bytes:
        """Execute COPY TO STDOUT and return the raw CSV bytes."""
        ...

    async def copy_in(self, sql: str, data: bytes) -> None:
        """Execute COPY FROM STDIN using *data* as the CSV source."""
        ...


class S3ClientProto(Protocol):
    """Minimal S3 interface required by PartitionManager."""

    async def upload_bytes(self, bucket: str, key: str, data: bytes) -> None:
        """Upload *data* to ``s3://{bucket}/{key}``."""
        ...

    async def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download and return bytes from ``s3://{bucket}/{key}``."""
        ...


# ---------------------------------------------------------------------------
# PartitionNotFoundError
# ---------------------------------------------------------------------------


class PartitionNotFoundError(Exception):
    """Raised when a requested partition table does not exist (ICD-036 PartitionNotFound)."""

    def __init__(self, table_name: str) -> None:
        super().__init__(f"Partition table not found: {table_name}")
        self.table_name = table_name


# ---------------------------------------------------------------------------
# PartitionName — immutable identity value for a single partition
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartitionName:
    """Identity of a single time-based partition.

    Attributes:
        parent_table:    The unpartitioned parent table (e.g. ``"logs"``).
        partition_date:  The UTC calendar date covered by this partition.
        tenant_short:    First 8 hex characters of the tenant UUID, or ``None``
                         for date-only partitions (``kernel_audit_log``).
    """

    parent_table: str
    partition_date: date
    tenant_short: str | None = None  # 8 hex chars or None

    @property
    def table_name(self) -> str:
        """Canonical SQL table name for this partition."""
        ds = self.partition_date.strftime("%Y_%m_%d")
        if self.tenant_short is not None:
            return f"{self.parent_table}_{ds}_{self.tenant_short}"
        return f"{self.parent_table}_{ds}"

    @property
    def s3_key(self) -> str:
        """S3 object key under the archival prefix."""
        return f"{_S3_PREFIX}/{self.parent_table}/{self.table_name}.csv"

    @classmethod
    def from_tenant_id(
        cls,
        parent_table: str,
        partition_date: date,
        tenant_id: UUID,
    ) -> PartitionName:
        """Construct a per-tenant PartitionName from a full UUID."""
        return cls(
            parent_table=parent_table,
            partition_date=partition_date,
            tenant_short=tenant_id.hex[:8],
        )

    @classmethod
    def parse(cls, table_name: str) -> PartitionName | None:
        """Parse a canonical partition table name.

        Returns:
            A ``PartitionName`` if *table_name* matches the pattern, else ``None``.
        """
        m = _PARTITION_RE.match(table_name)
        if m is None:
            return None
        try:
            d = date(int(m["year"]), int(m["month"]), int(m["day"]))
        except ValueError:
            return None
        return cls(
            parent_table=m["parent"],
            partition_date=d,
            tenant_short=m["tenant"],  # may be None
        )


# ---------------------------------------------------------------------------
# SQL generation helpers (pure functions — no I/O)
# ---------------------------------------------------------------------------


def day_epoch_range(d: date) -> tuple[int, int]:
    """Return ``(start_inclusive, end_exclusive)`` Unix epoch for UTC day *d*.

    Example:
        >>> day_epoch_range(date(2026, 2, 19))
        (1771459200, 1771545600)
    """
    start = int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())
    return start, start + _DAY_SECONDS


def create_partition_ddl(name: PartitionName) -> str:
    """Generate ``CREATE TABLE IF NOT EXISTS`` DDL for *name*.

    Uses ``LIKE … INCLUDING ALL`` to inherit columns and indexes from the
    parent table, plus CHECK constraints that enforce the date (and optional
    tenant) boundary.
    """
    start, end = day_epoch_range(name.partition_date)
    checks: list[str] = [f"CHECK (timestamp >= {start} AND timestamp < {end})"]
    if name.tenant_short is not None:
        # Constrain tenant prefix bytes; full isolation via RLS at query time.
        checks.append(f"CHECK (LEFT(tenant_id::text, 8) = '{name.tenant_short}')")
    check_clauses = ",\n    ".join(checks)
    return (
        f"CREATE TABLE IF NOT EXISTS {name.table_name} (\n"
        f"    LIKE {name.parent_table} INCLUDING ALL,\n"
        f"    {check_clauses}\n"
        f")"
    )


def drop_partition_ddl(name: PartitionName) -> str:
    """Generate ``DROP TABLE IF EXISTS`` DDL for *name*."""
    return f"DROP TABLE IF EXISTS {name.table_name}"


def copy_out_sql(name: PartitionName) -> str:
    """COPY … TO STDOUT statement for archival export."""
    return f"COPY {name.table_name} TO STDOUT (FORMAT csv, HEADER)"


def copy_in_sql(name: PartitionName) -> str:
    """COPY … FROM STDIN statement for archival restore."""
    return f"COPY {name.table_name} FROM STDIN (FORMAT csv, HEADER)"


# ---------------------------------------------------------------------------
# PartitionManager
# ---------------------------------------------------------------------------


@dataclass
class PartitionManager:
    """Manages time-based PostgreSQL partition lifecycle.

    Covers both partition tables defined in ``PARTITIONED_TABLES``:

    - ``logs`` (ICD-036): partitioned per date + tenant.
    - ``kernel_audit_log`` (ICD-038): partitioned per date only.

    All DB operations are delegated to a caller-supplied
    ``PartitionConnectionProto`` connection; S3 operations go through
    ``S3ClientProto``.  Both are typed protocols, enabling full mock-based
    testing without a live DB or AWS account.

    Attributes:
        ttl_days: Partitions older than this many days are considered expired
                  and eligible for archival. Default 90 per ICD-036.
    """

    ttl_days: int = _DEFAULT_TTL_DAYS

    # ------------------------------------------------------------------
    # Partition creation
    # ------------------------------------------------------------------

    async def ensure_partition(
        self,
        conn: PartitionConnectionProto,
        parent_table: str,
        partition_date: date,
        tenant_id: UUID | None = None,
    ) -> PartitionName:
        """Idempotently create the partition table for *parent_table* on *partition_date*.

        For tables in ``PARTITIONED_TABLES`` with ``by_tenant=True``, a
        *tenant_id* must be supplied.  The operation is a no-op if the
        partition already exists (``CREATE TABLE IF NOT EXISTS``).

        Args:
            conn:            Database connection.
            parent_table:    Name of the parent table (must be in
                             ``PARTITIONED_TABLES``).
            partition_date:  UTC calendar date of the partition.
            tenant_id:       Required when ``PARTITIONED_TABLES[parent_table]``
                             is ``True``; ignored otherwise.

        Returns:
            The ``PartitionName`` for the created/existing partition.

        Raises:
            ValueError: If *parent_table* is not in ``PARTITIONED_TABLES``, or
                        if *tenant_id* is required but missing.
        """
        if parent_table not in PARTITIONED_TABLES:
            raise ValueError(f"Unknown partitioned table: {parent_table!r}")
        by_tenant = PARTITIONED_TABLES[parent_table]
        if by_tenant and tenant_id is None:
            raise ValueError(f"{parent_table} partitions require a tenant_id")

        name = (
            PartitionName.from_tenant_id(parent_table, partition_date, tenant_id)
            if (by_tenant and tenant_id is not None)
            else PartitionName(parent_table, partition_date)
        )
        await conn.execute(create_partition_ddl(name))
        return name

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    async def archive_partition(
        self,
        conn: PartitionConnectionProto,
        name: PartitionName,
        s3_client: S3ClientProto,
        bucket: str,
    ) -> None:
        """Archive a partition to S3 and drop it from Postgres.

        Sequence per ICD-036 TTL contract:
        1. ``COPY table TO STDOUT (FORMAT csv, HEADER)``
        2. ``s3_client.upload_bytes(bucket, name.s3_key, data)``
        3. ``DROP TABLE IF EXISTS table``

        Args:
            conn:      Database connection (must be able to COPY OUT).
            name:      Partition to archive.
            s3_client: S3 client for upload.
            bucket:    Destination S3 bucket name.
        """
        data = await conn.copy_out(copy_out_sql(name))
        await s3_client.upload_bytes(bucket, name.s3_key, data)
        await conn.execute(drop_partition_ddl(name))

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    async def restore_partition(
        self,
        conn: PartitionConnectionProto,
        name: PartitionName,
        s3_client: S3ClientProto,
        bucket: str,
    ) -> None:
        """Restore a previously archived partition from S3.

        Sequence:
        1. ``s3_client.download_bytes(bucket, name.s3_key)``
        2. ``CREATE TABLE IF NOT EXISTS`` via :func:`create_partition_ddl`
        3. ``COPY table FROM STDIN (FORMAT csv, HEADER)``

        Args:
            conn:      Database connection (must be able to COPY IN).
            name:      Partition to restore.
            s3_client: S3 client for download.
            bucket:    Source S3 bucket name.
        """
        data = await s3_client.download_bytes(bucket, name.s3_key)
        await conn.execute(create_partition_ddl(name))
        await conn.copy_in(copy_in_sql(name), data)

    # ------------------------------------------------------------------
    # Expiry scanning
    # ------------------------------------------------------------------

    async def list_expired_partitions(
        self,
        conn: PartitionConnectionProto,
        reference_date: date | None = None,
    ) -> list[PartitionName]:
        """Return partition names whose date is ≥ *ttl_days* before *reference_date*.

        Queries ``pg_tables`` for table names matching the canonical partition
        pattern, parses each name, and returns those whose
        ``partition_date ≤ cutoff``.

        Args:
            conn:           Database connection.
            reference_date: Date to compute TTL from; defaults to ``date.today()``.

        Returns:
            List of expired ``PartitionName`` objects (may be empty).
        """
        ref = reference_date if reference_date is not None else date.today()
        cutoff = ref - timedelta(days=self.ttl_days)

        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables"
            " WHERE schemaname = 'public'"
            f" AND tablename ~ '{_PG_TABLE_PATTERN}'"
        )
        expired: list[PartitionName] = []
        for row in rows:
            pn = PartitionName.parse(str(row["tablename"]))
            if pn is not None and pn.partition_date <= cutoff:
                expired.append(pn)
        return expired

    # ------------------------------------------------------------------
    # Full archival cycle
    # ------------------------------------------------------------------

    async def run_archival_cycle(
        self,
        conn: PartitionConnectionProto,
        s3_client: S3ClientProto,
        bucket: str,
        reference_date: date | None = None,
    ) -> int:
        """Archive all expired partitions in a single pass.

        Calls :meth:`list_expired_partitions` then :meth:`archive_partition`
        for each result.

        Args:
            conn:           Database connection.
            s3_client:      S3 client for upload.
            bucket:         Destination S3 bucket name.
            reference_date: Passed through to :meth:`list_expired_partitions`.

        Returns:
            Number of partitions archived.
        """
        expired = await self.list_expired_partitions(conn, reference_date)
        for name in expired:
            await self.archive_partition(conn, name, s3_client, bucket)
        return len(expired)
