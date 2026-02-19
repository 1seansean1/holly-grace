"""Integration tests for holly.storage.partition_manager — Task 23.3.

Acceptance criteria:
  AC-1  ensure_partition issues correct CREATE TABLE DDL (auto-create).
  AC-2  ensure_partition is idempotent (IF NOT EXISTS in DDL).
  AC-3  archive_partition: COPY OUT → S3 upload → DROP TABLE, in order.
  AC-4  restore_partition: S3 download → CREATE TABLE → COPY IN, in order.
  AC-5  list_expired_partitions returns only tables older than TTL.
  AC-6  list_expired_partitions ignores tables younger than TTL.
  AC-7  run_archival_cycle archives all expired, returns correct count.
  AC-8  run_archival_cycle with no expired partitions returns 0 and is a no-op.
  AC-9  PartitionName.parse round-trips through table_name.
  AC-10 ensure_partition raises ValueError for unknown parent table.
  AC-11 ensure_partition raises ValueError when tenant_id missing for logs.
  AC-12 day_epoch_range produces non-overlapping adjacent-day ranges.
  AC-13 Hypothesis: partition DDL contains partition date's epoch bounds.
  AC-14 Hypothesis: PartitionName.table_name is deterministic for same inputs.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.storage.partition_manager import (
    PartitionManager,
    PartitionName,
    copy_in_sql,
    copy_out_sql,
    create_partition_ddl,
    day_epoch_range,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_BUCKET = "holly-archival-test"
_TENANT_A = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_TENANT_B = UUID("bbbbbbbb-0000-0000-0000-000000000002")
_DATE = date(2026, 2, 19)
_OLD_DATE = date(2025, 10, 1)     # well beyond 90 days
_RECENT_DATE = date(2026, 2, 18)  # 1 day ago — within TTL


def _make_conn(
    *,
    rows: list[dict[str, Any]] | None = None,
    copy_out_data: bytes = b"id,tenant_id\n1,aaa\n",
) -> AsyncMock:
    """Return an AsyncMock satisfying PartitionConnectionProto."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.copy_out = AsyncMock(return_value=copy_out_data)
    conn.copy_in = AsyncMock(return_value=None)
    return conn


def _make_s3(*, stored: bytes = b"id,tenant_id\n1,aaa\n") -> AsyncMock:
    """Return an AsyncMock satisfying S3ClientProto."""
    s3 = AsyncMock()
    s3.upload_bytes = AsyncMock(return_value=None)
    s3.download_bytes = AsyncMock(return_value=stored)
    return s3


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# AC-1  ensure_partition issues correct CREATE TABLE DDL
# ---------------------------------------------------------------------------

class TestEnsurePartitionCreatesDDL:
    """AC-1: correct CREATE TABLE DDL is sent to conn.execute."""

    def test_logs_ddl_contains_table_name(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        ddl: str = conn.execute.call_args[0][0]
        assert "logs_2026_02_19_aaaaaaaa" in ddl

    def test_logs_ddl_contains_create_table_if_not_exists(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        ddl: str = conn.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in ddl

    def test_logs_ddl_contains_like_clause(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        ddl: str = conn.execute.call_args[0][0]
        assert "LIKE logs INCLUDING ALL" in ddl

    def test_logs_ddl_contains_timestamp_check(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        ddl: str = conn.execute.call_args[0][0]
        start, end = day_epoch_range(_DATE)
        assert f"timestamp >= {start}" in ddl
        assert f"timestamp < {end}" in ddl

    def test_logs_ddl_contains_tenant_check(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        ddl: str = conn.execute.call_args[0][0]
        assert "aaaaaaaa" in ddl

    def test_audit_log_ddl_contains_table_name(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "kernel_audit_log", _DATE))
        ddl: str = conn.execute.call_args[0][0]
        assert "kernel_audit_log_2026_02_19" in ddl

    def test_audit_log_ddl_no_tenant_check(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "kernel_audit_log", _DATE))
        ddl: str = conn.execute.call_args[0][0]
        assert "tenant_id" not in ddl

    def test_ensure_partition_calls_execute_exactly_once(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        assert conn.execute.call_count == 1


# ---------------------------------------------------------------------------
# AC-2  ensure_partition is idempotent (IF NOT EXISTS)
# ---------------------------------------------------------------------------

class TestEnsurePartitionIdempotent:
    """AC-2: calling ensure_partition twice uses IF NOT EXISTS — idempotent."""

    def test_ddl_has_if_not_exists(self) -> None:
        pn = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        ddl = create_partition_ddl(pn)
        assert "IF NOT EXISTS" in ddl

    def test_calling_twice_does_not_raise(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        assert conn.execute.call_count == 2  # two calls, both idempotent

    def test_returns_same_partition_name_both_calls(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        n1 = _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        n2 = _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))
        assert n1 == n2


# ---------------------------------------------------------------------------
# AC-3  archive_partition: COPY OUT → S3 upload → DROP TABLE, in order
# ---------------------------------------------------------------------------

class TestArchivePartition:
    """AC-3: archive sequences COPY OUT → S3 upload → DROP TABLE."""

    def _name(self) -> PartitionName:
        return PartitionName.from_tenant_id("logs", _OLD_DATE, _TENANT_A)

    def test_copy_out_called_with_correct_sql(self) -> None:
        conn = _make_conn()
        s3 = _make_s3()
        pm = PartitionManager()
        _run(pm.archive_partition(conn, self._name(), s3, _BUCKET))
        assert conn.copy_out.call_args[0][0] == copy_out_sql(self._name())

    def test_s3_upload_called_with_correct_key(self) -> None:
        conn = _make_conn()
        s3 = _make_s3()
        pm = PartitionManager()
        name = self._name()
        _run(pm.archive_partition(conn, name, s3, _BUCKET))
        s3.upload_bytes.assert_called_once_with(_BUCKET, name.s3_key, conn.copy_out.return_value)

    def test_drop_table_called_after_upload(self) -> None:
        conn = _make_conn()
        s3 = _make_s3()
        pm = PartitionManager()
        name = self._name()
        _run(pm.archive_partition(conn, name, s3, _BUCKET))
        ddl: str = conn.execute.call_args[0][0]
        assert "DROP TABLE IF EXISTS" in ddl
        assert name.table_name in ddl

    def test_order_copy_then_upload_then_drop(self) -> None:
        """Verify call ordering via a shared call_tracker list."""
        tracker: list[str] = []

        async def fake_copy_out(_sql: str) -> bytes:
            tracker.append("copy_out")
            return b"data"

        async def fake_upload(bucket: str, key: str, data: bytes) -> None:
            tracker.append("upload")

        async def fake_execute(sql: str, *_: object) -> None:
            tracker.append("execute")

        conn = AsyncMock()
        conn.copy_out = fake_copy_out
        conn.execute = fake_execute
        s3 = AsyncMock()
        s3.upload_bytes = fake_upload

        pm = PartitionManager()
        _run(pm.archive_partition(conn, self._name(), s3, _BUCKET))
        assert tracker == ["copy_out", "upload", "execute"]

    def test_s3_key_format(self) -> None:
        name = self._name()
        assert name.s3_key.startswith("partitions/logs/")
        assert name.s3_key.endswith(".csv")


# ---------------------------------------------------------------------------
# AC-4  restore_partition: S3 download → CREATE TABLE → COPY IN, in order
# ---------------------------------------------------------------------------

class TestRestorePartition:
    """AC-4: restore sequences S3 download → CREATE TABLE → COPY IN."""

    def _name(self) -> PartitionName:
        return PartitionName.from_tenant_id("logs", _OLD_DATE, _TENANT_A)

    def test_s3_download_called_with_correct_key(self) -> None:
        conn = _make_conn()
        s3 = _make_s3()
        pm = PartitionManager()
        name = self._name()
        _run(pm.restore_partition(conn, name, s3, _BUCKET))
        s3.download_bytes.assert_called_once_with(_BUCKET, name.s3_key)

    def test_create_table_called_after_download(self) -> None:
        conn = _make_conn()
        s3 = _make_s3()
        pm = PartitionManager()
        name = self._name()
        _run(pm.restore_partition(conn, name, s3, _BUCKET))
        # First execute call should be the CREATE TABLE
        create_ddl: str = conn.execute.call_args_list[0][0][0]
        assert "CREATE TABLE IF NOT EXISTS" in create_ddl
        assert name.table_name in create_ddl

    def test_copy_in_called_with_s3_data(self) -> None:
        conn = _make_conn()
        payload = b"id,tenant_id\n42,bbb\n"
        s3 = _make_s3(stored=payload)
        pm = PartitionManager()
        name = self._name()
        _run(pm.restore_partition(conn, name, s3, _BUCKET))
        conn.copy_in.assert_called_once_with(copy_in_sql(name), payload)

    def test_order_download_then_create_then_copy_in(self) -> None:
        tracker: list[str] = []

        async def fake_download(bucket: str, key: str) -> bytes:
            tracker.append("download")
            return b"data"

        async def fake_execute(sql: str, *_: object) -> None:
            tracker.append("execute")

        async def fake_copy_in(sql: str, data: bytes) -> None:
            tracker.append("copy_in")

        conn = AsyncMock()
        conn.execute = fake_execute
        conn.copy_in = fake_copy_in
        s3 = AsyncMock()
        s3.download_bytes = fake_download

        pm = PartitionManager()
        _run(pm.restore_partition(conn, self._name(), s3, _BUCKET))
        assert tracker == ["download", "execute", "copy_in"]

    def test_copy_in_sql_format(self) -> None:
        name = self._name()
        sql = copy_in_sql(name)
        assert name.table_name in sql
        assert "COPY" in sql
        assert "FROM STDIN" in sql


# ---------------------------------------------------------------------------
# AC-5  list_expired_partitions returns only tables older than TTL
# ---------------------------------------------------------------------------

class TestListExpiredPartitions:
    """AC-5: expired partitions (date ≤ cutoff) are returned."""

    def _old_row(self, parent: str = "logs", tenant_short: str = "aaaaaaaa") -> dict[str, str]:
        ds = _OLD_DATE.strftime("%Y_%m_%d")
        return {"tablename": f"{parent}_{ds}_{tenant_short}"}

    def test_old_logs_partition_returned(self) -> None:
        rows = [self._old_row("logs")]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=date(2026, 2, 19)))
        assert len(result) == 1
        assert result[0].partition_date == _OLD_DATE

    def test_old_kernel_audit_partition_returned(self) -> None:
        ds = _OLD_DATE.strftime("%Y_%m_%d")
        rows = [{"tablename": f"kernel_audit_log_{ds}"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=date(2026, 2, 19)))
        assert len(result) == 1
        assert result[0].parent_table == "kernel_audit_log"

    def test_multiple_expired_partitions_returned(self) -> None:
        ds1 = date(2025, 9, 1).strftime("%Y_%m_%d")
        ds2 = date(2025, 8, 15).strftime("%Y_%m_%d")
        rows = [
            {"tablename": f"logs_{ds1}_aaaaaaaa"},
            {"tablename": f"logs_{ds2}_bbbbbbbb"},
        ]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=date(2026, 2, 19)))
        assert len(result) == 2

    def test_fetch_uses_pg_tables_query(self) -> None:
        conn = _make_conn(rows=[])
        pm = PartitionManager()
        _run(pm.list_expired_partitions(conn))
        sql: str = conn.fetch.call_args[0][0]
        assert "pg_tables" in sql
        assert "schemaname = 'public'" in sql


# ---------------------------------------------------------------------------
# AC-6  list_expired_partitions ignores tables within TTL
# ---------------------------------------------------------------------------

class TestListExpiredPartitionsFiltersRecent:
    """AC-6: partitions within TTL window are excluded."""

    def test_recent_partition_excluded(self) -> None:
        ds = _RECENT_DATE.strftime("%Y_%m_%d")
        rows = [{"tablename": f"logs_{ds}_aaaaaaaa"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=date(2026, 2, 19)))
        assert result == []

    def test_today_partition_excluded(self) -> None:
        ref = date(2026, 2, 19)
        ds = ref.strftime("%Y_%m_%d")
        rows = [{"tablename": f"logs_{ds}_aaaaaaaa"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=ref))
        assert result == []

    def test_boundary_exactly_ttl_days_is_expired(self) -> None:
        ref = date(2026, 2, 19)
        cutoff = ref - timedelta(days=90)
        ds = cutoff.strftime("%Y_%m_%d")
        rows = [{"tablename": f"logs_{ds}_aaaaaaaa"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=ref))
        assert len(result) == 1

    def test_one_day_before_cutoff_included(self) -> None:
        ref = date(2026, 2, 19)
        one_before = ref - timedelta(days=91)
        ds = one_before.strftime("%Y_%m_%d")
        rows = [{"tablename": f"logs_{ds}_aaaaaaaa"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=ref))
        assert len(result) == 1

    def test_mixed_returns_only_expired(self) -> None:
        ref = date(2026, 2, 19)
        cutoff = ref - timedelta(days=90)
        old_ds = (cutoff - timedelta(days=1)).strftime("%Y_%m_%d")
        new_ds = _RECENT_DATE.strftime("%Y_%m_%d")
        rows = [
            {"tablename": f"logs_{old_ds}_aaaaaaaa"},
            {"tablename": f"logs_{new_ds}_bbbbbbbb"},
        ]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=ref))
        assert len(result) == 1
        assert result[0].partition_date == cutoff - timedelta(days=1)

    def test_unparseable_tablename_skipped(self) -> None:
        rows = [{"tablename": "some_unrelated_table"}]
        conn = _make_conn(rows=rows)
        pm = PartitionManager(ttl_days=90)
        result = _run(pm.list_expired_partitions(conn, reference_date=date(2026, 2, 19)))
        assert result == []


# ---------------------------------------------------------------------------
# AC-7  run_archival_cycle archives all expired, returns correct count
# ---------------------------------------------------------------------------

class TestRunArchivalCycleArchivesAll:
    """AC-7: run_archival_cycle processes all expired partitions."""

    def test_two_expired_archived_returns_2(self) -> None:
        ds1 = _OLD_DATE.strftime("%Y_%m_%d")
        ds2 = (date(2025, 9, 1)).strftime("%Y_%m_%d")
        rows = [
            {"tablename": f"logs_{ds1}_aaaaaaaa"},
            {"tablename": f"logs_{ds2}_bbbbbbbb"},
        ]
        conn = _make_conn(rows=rows)
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        count = _run(pm.run_archival_cycle(conn, s3, _BUCKET, reference_date=date(2026, 2, 19)))
        assert count == 2

    def test_s3_upload_called_once_per_partition(self) -> None:
        ds1 = _OLD_DATE.strftime("%Y_%m_%d")
        ds2 = (date(2025, 9, 1)).strftime("%Y_%m_%d")
        rows = [
            {"tablename": f"logs_{ds1}_aaaaaaaa"},
            {"tablename": f"logs_{ds2}_bbbbbbbb"},
        ]
        conn = _make_conn(rows=rows)
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        _run(pm.run_archival_cycle(conn, s3, _BUCKET, reference_date=date(2026, 2, 19)))
        assert s3.upload_bytes.call_count == 2

    def test_drop_table_called_once_per_partition(self) -> None:
        ds = _OLD_DATE.strftime("%Y_%m_%d")
        rows = [{"tablename": f"logs_{ds}_aaaaaaaa"}]
        conn = _make_conn(rows=rows)
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        _run(pm.run_archival_cycle(conn, s3, _BUCKET, reference_date=date(2026, 2, 19)))
        # execute is called once per archive (the DROP)
        assert conn.execute.call_count == 1
        drop_sql: str = conn.execute.call_args[0][0]
        assert "DROP TABLE IF EXISTS" in drop_sql


# ---------------------------------------------------------------------------
# AC-8  run_archival_cycle with no expired partitions returns 0 (no-op)
# ---------------------------------------------------------------------------

class TestRunArchivalCycleNoop:
    """AC-8: no expired partitions → returns 0, no S3/DB writes."""

    def test_returns_0_when_no_expired(self) -> None:
        conn = _make_conn(rows=[])
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        count = _run(pm.run_archival_cycle(conn, s3, _BUCKET))
        assert count == 0

    def test_no_s3_uploads_when_no_expired(self) -> None:
        conn = _make_conn(rows=[])
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        _run(pm.run_archival_cycle(conn, s3, _BUCKET))
        s3.upload_bytes.assert_not_called()

    def test_no_db_execute_when_no_expired(self) -> None:
        conn = _make_conn(rows=[])
        s3 = _make_s3()
        pm = PartitionManager(ttl_days=90)
        _run(pm.run_archival_cycle(conn, s3, _BUCKET))
        conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# AC-9  PartitionName.parse round-trips through table_name
# ---------------------------------------------------------------------------

class TestPartitionNameParse:
    """AC-9: parse(name.table_name) round-trips correctly."""

    def test_logs_with_tenant_round_trips(self) -> None:
        name = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.table_name == name.table_name

    def test_kernel_audit_date_only_round_trips(self) -> None:
        name = PartitionName("kernel_audit_log", _DATE)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.table_name == name.table_name

    def test_parse_returns_none_for_random_string(self) -> None:
        assert PartitionName.parse("not_a_partition") is None

    def test_parse_returns_none_for_invalid_date(self) -> None:
        assert PartitionName.parse("logs_2026_13_99_aaaaaaaa") is None

    def test_parse_extracts_parent_table(self) -> None:
        name = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.parent_table == "logs"

    def test_parse_extracts_partition_date(self) -> None:
        name = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.partition_date == _DATE

    def test_parse_extracts_tenant_short(self) -> None:
        name = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.tenant_short == _TENANT_A.hex[:8]

    def test_s3_key_round_trips(self) -> None:
        name = PartitionName.from_tenant_id("logs", _DATE, _TENANT_A)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.s3_key == name.s3_key


# ---------------------------------------------------------------------------
# AC-10  ensure_partition raises ValueError for unknown parent table
# ---------------------------------------------------------------------------

class TestEnsurePartitionValidatesTable:
    """AC-10: ValueError on unknown parent_table."""

    def test_unknown_table_raises_value_error(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        with pytest.raises(ValueError, match="Unknown partitioned table"):
            _run(pm.ensure_partition(conn, "nonexistent_table", _DATE))

    def test_known_table_does_not_raise(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        # Should not raise
        _run(pm.ensure_partition(conn, "kernel_audit_log", _DATE))


# ---------------------------------------------------------------------------
# AC-11  ensure_partition raises ValueError when tenant_id missing for logs
# ---------------------------------------------------------------------------

class TestEnsurePartitionRequiresTenantForLogs:
    """AC-11: ValueError when tenant_id omitted for a tenant-partitioned table."""

    def test_logs_without_tenant_raises(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        with pytest.raises(ValueError, match="require a tenant_id"):
            _run(pm.ensure_partition(conn, "logs", _DATE))

    def test_logs_with_tenant_does_not_raise(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "logs", _DATE, _TENANT_A))

    def test_kernel_audit_log_without_tenant_does_not_raise(self) -> None:
        conn = _make_conn()
        pm = PartitionManager()
        _run(pm.ensure_partition(conn, "kernel_audit_log", _DATE))


# ---------------------------------------------------------------------------
# AC-12  day_epoch_range produces non-overlapping adjacent-day ranges
# ---------------------------------------------------------------------------

class TestDayEpochRange:
    """AC-12: adjacent day ranges are contiguous and non-overlapping."""

    def test_start_lt_end(self) -> None:
        start, end = day_epoch_range(_DATE)
        assert start < end

    def test_range_is_exactly_86400_seconds(self) -> None:
        start, end = day_epoch_range(_DATE)
        assert end - start == 86_400

    def test_adjacent_days_contiguous(self) -> None:
        _, end_feb19 = day_epoch_range(date(2026, 2, 19))
        start_feb20, _ = day_epoch_range(date(2026, 2, 20))
        assert end_feb19 == start_feb20

    def test_ranges_do_not_overlap(self) -> None:
        _, end_day1 = day_epoch_range(date(2026, 2, 19))
        start_day2, _ = day_epoch_range(date(2026, 2, 20))
        assert end_day1 == start_day2  # contiguous, not overlapping

    def test_utc_epoch_value_2026_02_19(self) -> None:
        # Known: 2026-02-19 00:00:00 UTC = 1771459200
        start, end = day_epoch_range(date(2026, 2, 19))
        assert start == 1_771_459_200
        assert end == 1_771_459_200 + 86_400


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


class TestHypothesisProperties:
    """Hypothesis-driven invariant tests (AC-13, AC-14)."""

    @given(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)),
        st.uuids(version=4),
    )
    @settings(max_examples=50)
    def test_ddl_contains_epoch_bounds(self, d: date, tenant_id: UUID) -> None:
        """AC-13: DDL timestamp CHECK bounds match day_epoch_range output."""
        name = PartitionName.from_tenant_id("logs", d, tenant_id)
        ddl = create_partition_ddl(name)
        start, end = day_epoch_range(d)
        assert str(start) in ddl
        assert str(end) in ddl

    @given(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)),
        st.uuids(version=4),
    )
    @settings(max_examples=50)
    def test_table_name_deterministic(self, d: date, tenant_id: UUID) -> None:
        """AC-14: table_name is deterministic for the same inputs."""
        name1 = PartitionName.from_tenant_id("logs", d, tenant_id)
        name2 = PartitionName.from_tenant_id("logs", d, tenant_id)
        assert name1.table_name == name2.table_name

    @given(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)),
    )
    @settings(max_examples=50)
    def test_parse_round_trip_audit_log(self, d: date) -> None:
        """Parsing audit_log partition table name recovers the same date."""
        name = PartitionName("kernel_audit_log", d)
        parsed = PartitionName.parse(name.table_name)
        assert parsed is not None
        assert parsed.partition_date == d
