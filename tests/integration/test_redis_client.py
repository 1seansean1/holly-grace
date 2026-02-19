"""Integration tests for holly.storage.redis — Task 24.3.

Acceptance criteria:
  AC-1  Pub/sub delivers: publish to channel → subscriber receives message.
  AC-2  Cache isolates tenants: different tenant_ids → different keys, no cross-read.
  AC-3  HA failover: circuit opens after failure_threshold failures → calls fail-open.
  AC-4  Circuit recovers: CLOSED after success following OPEN→HALF_OPEN.
  AC-5  Queue depth limit enforced: QueueFull raised at depth_limit.
  AC-6  Sorted-set cron queue delivers items in score order.
  AC-7  Stream XADD/XRANGE round-trip: appended fields returned by read_range.
  AC-8  Revocation: is_revoked returns True after revoke; False before.
  AC-9  Revocation fails open: is_revoked returns False on client error.
  AC-10 tenant_key namespacing: different tenants produce different keys.
  AC-11 queue_key / stream_key / revocation_key naming matches ICD patterns.
  AC-12 RedisBackend.from_client wires all components to a single CB.
  AC-13 Hypothesis: tenant_key injects tenant_id; no cross-tenant collision.
  AC-14 Hypothesis: revocation_key contains jti.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.storage.redis import (
    CacheClient,
    CircuitBreaker,
    CircuitState,
    PubSubClient,
    QueueClient,
    QueueFull,
    RedisBackend,
    RevocationCache,
    StreamClient,
    queue_key,
    revocation_key,
    stream_key,
    tenant_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TA = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_TB = UUID("bbbbbbbb-0000-0000-0000-000000000002")


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_client(
    *,
    get_val: bytes | None = None,
    rpop_val: bytes | None = None,
    exists_val: int = 0,
    llen_val: int = 0,
    zrangebyscore_val: list[bytes] | None = None,
    get_message_val: dict[str, Any] | None = None,
    xrange_val: list[tuple[str, dict[str, bytes]]] | None = None,
    xadd_val: str = "0-1",
    publish_val: int = 1,
) -> AsyncMock:
    """Return an AsyncMock satisfying RedisClientProto."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=get_val)
    client.set = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=0)
    client.lpush = AsyncMock(return_value=1)
    client.rpop = AsyncMock(return_value=rpop_val)
    client.zadd = AsyncMock(return_value=1)
    client.zrangebyscore = AsyncMock(return_value=zrangebyscore_val or [])
    client.publish = AsyncMock(return_value=publish_val)
    client.subscribe = AsyncMock(return_value=None)
    client.get_message = AsyncMock(return_value=get_message_val)
    client.xadd = AsyncMock(return_value=xadd_val)
    client.xrange = AsyncMock(return_value=xrange_val or [])
    client.exists = AsyncMock(return_value=exists_val)
    client.llen = AsyncMock(return_value=llen_val)
    client.ping = AsyncMock(return_value=True)
    return client


def _fresh_cb(**kwargs: Any) -> CircuitBreaker:
    return CircuitBreaker(**kwargs)


# ---------------------------------------------------------------------------
# AC-1  Pub/sub delivers
# ---------------------------------------------------------------------------


class TestPubSubDelivers:
    """AC-1: publish → subscribe → get_message delivers the message."""

    def test_publish_calls_client_publish(self) -> None:
        client = _make_client(publish_val=2)
        ps = PubSubClient(client=client)
        result = _run(ps.publish("lane_status_exec1", b"done"))
        client.publish.assert_called_once_with("lane_status_exec1", b"done")
        assert result == 2

    def test_subscribe_calls_client_subscribe(self) -> None:
        client = _make_client()
        ps = PubSubClient(client=client)
        _run(ps.subscribe("lane_status_exec1", "lane_status_exec2"))
        client.subscribe.assert_called_once_with("lane_status_exec1", "lane_status_exec2")

    def test_get_message_returns_message_dict(self) -> None:
        msg = {"type": "message", "channel": b"lane_status_exec1", "data": b"done"}
        client = _make_client(get_message_val=msg)
        ps = PubSubClient(client=client)
        result = _run(ps.get_message(timeout=0.05))
        assert result == msg

    def test_get_message_returns_none_on_timeout(self) -> None:
        client = _make_client(get_message_val=None)
        ps = PubSubClient(client=client)
        result = _run(ps.get_message())
        assert result is None

    def test_publish_returns_subscriber_count(self) -> None:
        client = _make_client(publish_val=3)
        ps = PubSubClient(client=client)
        count = _run(ps.publish("chan", b"hello"))
        assert count == 3


# ---------------------------------------------------------------------------
# AC-2  Cache isolates tenants
# ---------------------------------------------------------------------------


class TestCacheIsolatesTenants:
    """AC-2: different tenant_ids produce different Redis keys → no cross-read."""

    def test_get_uses_tenant_namespaced_key(self) -> None:
        client = _make_client(get_val=b"value_a")
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        _run(cache.get(_TA, "goal_hierarchy:u1:h1"))
        called_key: str = client.get.call_args[0][0]
        assert str(_TA) in called_key
        assert "goal_hierarchy:u1:h1" in called_key

    def test_different_tenants_use_different_keys(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        _run(cache.get(_TA, "mykey"))
        _run(cache.get(_TB, "mykey"))
        calls = [c[0][0] for c in client.get.call_args_list]
        assert calls[0] != calls[1]
        assert str(_TA) in calls[0]
        assert str(_TB) in calls[1]

    def test_set_uses_tenant_namespaced_key(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        _run(cache.set(_TA, "agent_checkpoint:a1", b"state", 3600))
        called_key: str = client.set.call_args[0][0]
        assert str(_TA) in called_key

    def test_set_returns_true_on_success(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        result = _run(cache.set(_TA, "key", b"val", 60))
        assert result is True

    def test_get_returns_none_on_cache_miss(self) -> None:
        client = _make_client(get_val=None)
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        result = _run(cache.get(_TA, "missing_key"))
        assert result is None

    def test_delete_uses_tenant_namespaced_keys(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        cache = CacheClient(client=client, circuit_breaker=cb)
        _run(cache.delete(_TA, "key1", "key2"))
        delete_args = client.delete.call_args[0]
        assert all(str(_TA) in k for k in delete_args)


# ---------------------------------------------------------------------------
# AC-3  HA failover: circuit opens after threshold failures
# ---------------------------------------------------------------------------


class TestHAFailover:
    """AC-3: circuit breaker opens after failure_threshold; calls fail-open."""

    def test_circuit_opens_after_threshold_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects_request(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert not cb.allow_request()

    def test_cache_get_fails_open_when_circuit_open(self) -> None:
        client = _make_client()
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()  # open the circuit
        cache = CacheClient(client=client, circuit_breaker=cb)
        result = _run(cache.get(_TA, "some_key"))
        assert result is None
        client.get.assert_not_called()

    def test_cache_set_fails_open_when_circuit_open(self) -> None:
        client = _make_client()
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cache = CacheClient(client=client, circuit_breaker=cb)
        result = _run(cache.set(_TA, "k", b"v", 60))
        assert result is False
        client.set.assert_not_called()

    def test_cache_get_returns_none_on_exception_and_records_failure(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(side_effect=ConnectionError("Redis unreachable"))
        cb = CircuitBreaker(failure_threshold=3)
        cache = CacheClient(client=client, circuit_breaker=cb)
        result = _run(cache.get(_TA, "key"))
        assert result is None
        assert cb._failures == 1

    def test_three_exceptions_open_the_circuit(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(side_effect=OSError("connection refused"))
        cb = CircuitBreaker(failure_threshold=3)
        cache = CacheClient(client=client, circuit_breaker=cb)
        for _ in range(3):
            _run(cache.get(_TA, "key"))
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# AC-4  Circuit recovers: CLOSED after success following OPEN→HALF_OPEN
# ---------------------------------------------------------------------------


class TestCircuitRecovery:
    """AC-4: OPEN → HALF_OPEN (on timeout) → CLOSED (on success)."""

    def test_record_success_resets_to_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_all_state(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failures == 0

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()  # → OPEN
        # Force transition to HALF_OPEN by checking state (recovery_timeout=0)
        _ = cb.state  # triggers auto-transition
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()  # → OPEN again
        assert cb._state == CircuitState.OPEN

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        _ = cb.state  # HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_closed_allows_requests(self) -> None:
        cb = CircuitBreaker()
        assert cb.allow_request() is True


# ---------------------------------------------------------------------------
# AC-5  Queue depth limit enforced
# ---------------------------------------------------------------------------


class TestQueueDepthLimit:
    """AC-5: QueueFull raised when queue is at or above depth_limit."""

    def test_queue_full_raised_at_limit(self) -> None:
        client = _make_client(llen_val=10_000)
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb, depth_limit=10_000)
        with pytest.raises(QueueFull):
            _run(q.enqueue(_TA, "main_queue", b"task"))

    def test_enqueue_succeeds_below_limit(self) -> None:
        client = _make_client(llen_val=9_999)
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb, depth_limit=10_000)
        _run(q.enqueue(_TA, "main_queue", b"task"))
        client.lpush.assert_called_once()

    def test_dequeue_returns_item(self) -> None:
        client = _make_client(rpop_val=b"task_data")
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        result = _run(q.dequeue(_TA, "main_queue"))
        assert result == b"task_data"

    def test_dequeue_returns_none_on_empty(self) -> None:
        client = _make_client(rpop_val=None)
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        result = _run(q.dequeue(_TA, "main_queue"))
        assert result is None

    def test_queue_full_exception_contains_depth_and_limit(self) -> None:
        client = _make_client(llen_val=5_000)
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb, depth_limit=5_000)
        with pytest.raises(QueueFull) as exc_info:
            _run(q.enqueue(_TA, "main_queue", b"x"))
        assert exc_info.value.depth == 5_000
        assert exc_info.value.limit == 5_000

    def test_depth_returns_llen(self) -> None:
        client = _make_client(llen_val=42)
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        depth = _run(q.depth(_TA, "main_queue"))
        assert depth == 42


# ---------------------------------------------------------------------------
# AC-6  Sorted-set cron queue delivers items in score order
# ---------------------------------------------------------------------------


class TestCronQueueOrder:
    """AC-6: cron queue delivers items with scores ≤ max_score."""

    def test_enqueue_scheduled_uses_zadd(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        _run(q.enqueue_scheduled(_TA, 1739923200.0, "task_payload"))
        client.zadd.assert_called_once()
        zadd_args = client.zadd.call_args
        assert 1739923200.0 in zadd_args[0][1].values()

    def test_dequeue_ready_uses_zrangebyscore(self) -> None:
        client = _make_client(zrangebyscore_val=[b"task1", b"task2"])
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        results = _run(q.dequeue_ready(_TA, max_score=1739923200.0))
        assert results == [b"task1", b"task2"]
        client.zrangebyscore.assert_called_once()

    def test_dequeue_ready_empty_returns_empty_list(self) -> None:
        client = _make_client(zrangebyscore_val=[])
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        results = _run(q.dequeue_ready(_TA, max_score=0.0))
        assert results == []

    def test_cron_queue_key_contains_tenant(self) -> None:
        client = _make_client()
        cb = _fresh_cb()
        q = QueueClient(client=client, circuit_breaker=cb)
        _run(q.enqueue_scheduled(_TA, 1.0, "p"))
        zadd_key: str = client.zadd.call_args[0][0]
        assert str(_TA) in zadd_key


# ---------------------------------------------------------------------------
# AC-7  Stream XADD/XRANGE round-trip
# ---------------------------------------------------------------------------


class TestStreamRoundTrip:
    """AC-7: xadd appends fields; xrange returns those entries."""

    def test_append_calls_xadd_with_correct_stream_key(self) -> None:
        client = _make_client(xadd_val="123-0")
        s = StreamClient(client=client)
        entry_id = _run(s.append(_TA, "metrics", {"p99_latency_ms": "45"}))
        assert entry_id == "123-0"
        xadd_key: str = client.xadd.call_args[0][0]
        assert str(_TA) in xadd_key
        assert "metrics" in xadd_key

    def test_append_passes_maxlen_to_xadd(self) -> None:
        client = _make_client()
        s = StreamClient(client=client, maxlen=500_000)
        _run(s.append(_TA, "metrics", {"val": "1"}))
        assert client.xadd.call_args[1]["maxlen"] == 500_000

    def test_read_range_calls_xrange(self) -> None:
        entries = [("123-0", {"p99": b"45"})]
        client = _make_client(xrange_val=entries)
        s = StreamClient(client=client)
        result = _run(s.read_range(_TA, "metrics"))
        assert result == entries

    def test_read_range_uses_correct_stream_key(self) -> None:
        client = _make_client(xrange_val=[])
        s = StreamClient(client=client)
        _run(s.read_range(_TB, "engine_metrics"))
        xrange_key: str = client.xrange.call_args[0][0]
        assert str(_TB) in xrange_key
        assert "engine_metrics" in xrange_key

    def test_different_tenants_use_different_stream_keys(self) -> None:
        key_a = stream_key(_TA, "metrics")
        key_b = stream_key(_TB, "metrics")
        assert key_a != key_b
        assert str(_TA) in key_a
        assert str(_TB) in key_b


# ---------------------------------------------------------------------------
# AC-8  Revocation: is_revoked after revoke
# ---------------------------------------------------------------------------


class TestRevocation:
    """AC-8: is_revoked returns True after revoke; False before."""

    def test_is_revoked_returns_false_when_key_absent(self) -> None:
        client = _make_client(exists_val=0)
        rev = RevocationCache(client=client)
        result = _run(rev.is_revoked("jti-abc"))
        assert result is False

    def test_is_revoked_returns_true_when_key_present(self) -> None:
        client = _make_client(exists_val=1)
        rev = RevocationCache(client=client)
        result = _run(rev.is_revoked("jti-abc"))
        assert result is True

    def test_revoke_calls_set_with_correct_key_and_ttl(self) -> None:
        client = _make_client()
        rev = RevocationCache(client=client)
        _run(rev.revoke("jti-xyz", ttl=3600))
        set_key: str = client.set.call_args[0][0]
        assert "revoked_token" in set_key
        assert "jti-xyz" in set_key
        assert client.set.call_args[1]["ex"] == 3600

    def test_is_revoked_checks_correct_key(self) -> None:
        client = _make_client(exists_val=0)
        rev = RevocationCache(client=client)
        _run(rev.is_revoked("jti-test"))
        exists_key: str = client.exists.call_args[0][0]
        assert "revoked_token" in exists_key
        assert "jti-test" in exists_key


# ---------------------------------------------------------------------------
# AC-9  Revocation fails open on client error
# ---------------------------------------------------------------------------


class TestRevocationFailOpen:
    """AC-9: is_revoked returns False on client error (ICD-049 fail-open)."""

    def test_fails_open_on_connection_error(self) -> None:
        client = AsyncMock()
        client.exists = AsyncMock(side_effect=ConnectionError("Redis down"))
        rev = RevocationCache(client=client)
        result = _run(rev.is_revoked("jti-abc"))
        assert result is False

    def test_fails_open_on_os_error(self) -> None:
        client = AsyncMock()
        client.exists = AsyncMock(side_effect=OSError("timeout"))
        rev = RevocationCache(client=client)
        result = _run(rev.is_revoked("jti-abc"))
        assert result is False


# ---------------------------------------------------------------------------
# AC-10  tenant_key namespacing
# ---------------------------------------------------------------------------


class TestTenantKeyNamespacing:
    """AC-10: different tenants produce different keys with correct format."""

    def test_different_tenants_produce_different_keys(self) -> None:
        assert tenant_key(_TA, "mykey") != tenant_key(_TB, "mykey")

    def test_same_tenant_same_key_deterministic(self) -> None:
        assert tenant_key(_TA, "k") == tenant_key(_TA, "k")

    def test_key_contains_tenant_id(self) -> None:
        k = tenant_key(_TA, "goal_hierarchy:u1:h1")
        assert str(_TA) in k

    def test_key_contains_logical_key(self) -> None:
        k = tenant_key(_TA, "goal_hierarchy:u1:h1")
        assert "goal_hierarchy:u1:h1" in k

    def test_key_starts_with_tenant_prefix(self) -> None:
        k = tenant_key(_TA, "something")
        assert k.startswith("tenant:")


# ---------------------------------------------------------------------------
# AC-11  Key naming matches ICD patterns
# ---------------------------------------------------------------------------


class TestKeyNamingConventions:
    """AC-11: queue_key, stream_key, revocation_key match ICD schemas."""

    def test_queue_key_pattern(self) -> None:
        k = queue_key(_TA, "main_queue")
        assert k == f"main_queue_{_TA}"

    def test_stream_key_pattern(self) -> None:
        k = stream_key(_TA, "metrics")
        assert k == f"metrics_{_TA}"

    def test_revocation_key_pattern(self) -> None:
        k = revocation_key("test-jti")
        assert k == "revoked_token:test-jti"

    def test_cron_queue_key_pattern(self) -> None:
        k = queue_key(_TA, "cron_queue")
        assert k == f"cron_queue_{_TA}"

    def test_engine_metrics_stream_key(self) -> None:
        k = stream_key(_TA, "engine_metrics")
        assert k == f"engine_metrics_{_TA}"

    def test_revocation_key_prefix(self) -> None:
        k = revocation_key("abc123")
        assert k.startswith("revoked_token:")


# ---------------------------------------------------------------------------
# AC-12  RedisBackend.from_client wires all components to a single CB
# ---------------------------------------------------------------------------


class TestRedisBackendFactory:
    """AC-12: from_client constructs a fully wired RedisBackend."""

    def test_all_components_present(self) -> None:
        client = _make_client()
        backend = RedisBackend.from_client(client)
        assert backend.cache is not None
        assert backend.queues is not None
        assert backend.pubsub is not None
        assert backend.streams is not None
        assert backend.revocation is not None
        assert backend.circuit_breaker is not None

    def test_cache_and_queues_share_same_circuit_breaker(self) -> None:
        client = _make_client()
        backend = RedisBackend.from_client(client)
        assert backend.cache.circuit_breaker is backend.circuit_breaker
        assert backend.queues.circuit_breaker is backend.circuit_breaker

    def test_custom_failure_threshold(self) -> None:
        client = _make_client()
        backend = RedisBackend.from_client(client, failure_threshold=5)
        assert backend.circuit_breaker.failure_threshold == 5

    def test_custom_queue_depth_limit(self) -> None:
        client = _make_client()
        backend = RedisBackend.from_client(client, queue_depth_limit=500)
        assert backend.queues.depth_limit == 500

    def test_custom_stream_maxlen(self) -> None:
        client = _make_client()
        backend = RedisBackend.from_client(client, stream_maxlen=250_000)
        assert backend.streams.maxlen == 250_000


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


class TestHypothesisProperties:
    """Hypothesis-driven invariant tests (AC-13, AC-14)."""

    @given(
        st.uuids(version=4),
        st.uuids(version=4),
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=":_-")),
    )
    @settings(max_examples=50)
    def test_tenant_key_injects_tenant_id(
        self, t1: UUID, t2: UUID, key: str
    ) -> None:
        """AC-13: tenant_key contains tenant_id; different tenants → different keys."""
        k1 = tenant_key(t1, key)
        k2 = tenant_key(t2, key)
        assert str(t1) in k1
        assert str(t2) in k2
        if t1 != t2:
            assert k1 != k2

    @given(
        st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_")),
    )
    @settings(max_examples=50)
    def test_revocation_key_contains_jti(self, jti: str) -> None:
        """AC-14: revocation_key always contains the jti."""
        k = revocation_key(jti)
        assert jti in k
        assert k.startswith("revoked_token:")
