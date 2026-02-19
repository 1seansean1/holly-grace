"""Redis client layer for Holly Grace storage.

Implements tenant-scoped Redis operations per ICDs:
  ICD-033: Core ↔ Redis (short-term memory, goal cache, idempotency)
  ICD-035: Engine ↔ Redis (task queues, pub/sub, cron queues)
  ICD-037: Observability ↔ Redis (real-time metrics streams)
  ICD-041: Memory System ↔ Redis (conversation context, agent memory)
  ICD-049: JWT Middleware ↔ Redis (token revocation cache)

All components are Protocol-based for mock-testability without a live Redis.
HA failover is handled by a CircuitBreaker (3-failure threshold, fail-open semantics).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL constants (seconds, per ICD-033 / ICD-041)
# ---------------------------------------------------------------------------

TTL_GOAL_HIERARCHY: int = 3_600        # 1 h   (ICD-033 / ICD-041)
TTL_TIER_CLASSIFICATION: int = 86_400  # 24 h  (ICD-033)
TTL_CONVERSATION_CONTEXT: int = 604_800  # 7 d  (ICD-033 / ICD-041)
TTL_AGENT_CHECKPOINT: int = 2_592_000  # 30 d  (ICD-033)
TTL_IDEMPOTENCY_CACHE: int = 86_400    # 24 h  (ICD-033)
TTL_AGENT_SHORT_TERM: int = 1_800      # 30 min (ICD-041)

# ---------------------------------------------------------------------------
# Queue/stream limits (per ICD-035 / ICD-037)
# ---------------------------------------------------------------------------

QUEUE_DEPTH_LIMIT: int = 10_000   # max items per tenant queue (ICD-035)
STREAM_MAXLEN: int = 1_000_000    # XADD MAXLEN ~ trim target (ICD-037)

# ---------------------------------------------------------------------------
# Key-building helpers (pure functions)
# ---------------------------------------------------------------------------


def tenant_key(tenant_id: UUID, key: str) -> str:
    """Build a tenant-namespaced cache key: ``tenant:{tenant_id}:{key}``.

    Per ICD-033: "Keys namespaced by tenant_id: `tenant:{tenant_id}:{key_name}`".
    """
    return f"tenant:{tenant_id}:{key}"


def queue_key(tenant_id: UUID, queue_name: str) -> str:
    """Build a tenant-scoped queue key: ``{queue_name}_{tenant_id}``.

    Per ICD-035: e.g. ``main_queue_{tenant_id}``, ``cron_queue_{tenant_id}``.
    """
    return f"{queue_name}_{tenant_id}"


def stream_key(tenant_id: UUID, stream_name: str) -> str:
    """Build a tenant-scoped stream key: ``{stream_name}_{tenant_id}``.

    Per ICD-037: e.g. ``metrics_{tenant_id}``.
    """
    return f"{stream_name}_{tenant_id}"


def revocation_key(jti: str) -> str:
    """Build a token revocation key: ``revoked_token:{jti}``.

    Per ICD-049: existence of this key indicates the token is revoked.
    """
    return f"revoked_token:{jti}"


# ---------------------------------------------------------------------------
# RedisClientProto — minimal async interface for testability
# ---------------------------------------------------------------------------


class RedisClientProto(Protocol):
    """Minimal async Redis client interface.

    All methods that can be called by this module.  Implementations may be
    real aioredis clients or mocks for unit testing.
    """

    async def get(self, key: str) -> bytes | None:
        """Return the value at *key*, or ``None`` if absent."""
        ...

    async def set(
        self,
        key: str,
        value: bytes | str,
        ex: int | None = None,
    ) -> None:
        """Set *key* to *value* with optional expiry *ex* (seconds)."""
        ...

    async def delete(self, *keys: str) -> int:
        """Delete *keys*; returns count of deleted keys."""
        ...

    async def lpush(self, key: str, *values: str | bytes) -> int:
        """Left-push *values* onto list *key*; returns new list length."""
        ...

    async def rpop(self, key: str) -> bytes | None:
        """Right-pop one item from list *key*; returns ``None`` if empty."""
        ...

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """Add score→member pairs to sorted set *key*; returns added count."""
        ...

    async def zrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
    ) -> list[bytes]:
        """Return members of sorted set *key* with scores in [*min_score*, *max_score*]."""
        ...

    async def publish(self, channel: str, message: str | bytes) -> int:
        """Publish *message* to *channel*; returns subscriber count."""
        ...

    async def subscribe(self, *channels: str) -> None:
        """Subscribe to *channels*."""
        ...

    async def get_message(self, timeout: float = 0.1) -> dict[str, object] | None:
        """Poll for a pub/sub message; returns ``None`` on timeout."""
        ...

    async def xadd(
        self,
        name: str,
        fields: dict[str, str | bytes],
        maxlen: int | None = None,
    ) -> str:
        """Append *fields* to stream *name*; returns the entry ID string."""
        ...

    async def xrange(
        self,
        name: str,
        min_id: str = "-",
        max_id: str = "+",
        count: int | None = None,
    ) -> list[tuple[str, dict[str, bytes]]]:
        """Return entries from stream *name* in [*min_id*, *max_id*]."""
        ...

    async def exists(self, *keys: str) -> int:
        """Return count of *keys* that exist."""
        ...

    async def llen(self, key: str) -> int:
        """Return length of list *key* (0 if absent)."""
        ...

    async def ping(self) -> bool:
        """Return ``True`` if the connection is alive."""
        ...


# ---------------------------------------------------------------------------
# CircuitBreaker — HA failover (ICD-033 / ICD-035 error contracts)
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    """Circuit breaker state per the standard three-state model."""

    CLOSED = "closed"      # Normal — requests pass through.
    OPEN = "open"          # Failing — requests rejected immediately (fail-open).
    HALF_OPEN = "half_open"  # Probing — one request allowed to test recovery.


@dataclass
class CircuitBreaker:
    """Three-state circuit breaker protecting Redis calls.

    Per ICD-033: "circuit breaker triggers after 3 failures; Core falls back to
    slower path (skip caching)".  ``allow_request()`` returns ``False`` when
    open, enabling callers to skip the Redis call and return a safe default.

    Attributes:
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout:  Seconds to wait in OPEN before probing (HALF_OPEN).
    """

    failure_threshold: int = 3
    recovery_timeout: float = 30.0

    _failures: int = field(default=0, init=False, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may auto-transition OPEN→HALF_OPEN on timeout)."""
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        """Return ``True`` if a request should be attempted.

        CLOSED and HALF_OPEN both allow requests (HALF_OPEN allows one probe).
        OPEN rejects all requests until *recovery_timeout* elapses.
        """
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        """Record a successful Redis call; resets the breaker to CLOSED."""
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        """Record a failed Redis call; may open the circuit."""
        if self._state is CircuitState.HALF_OPEN:
            # Probe failed — reopen.
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        """Force-reset to CLOSED (used in tests / recovery procedures)."""
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None


# ---------------------------------------------------------------------------
# QueueFull — raised when tenant queue exceeds depth limit
# ---------------------------------------------------------------------------


class QueueFull(Exception):
    """Queue depth limit reached for this tenant (ICD-035).

    Attributes:
        queue: The queue key that is full.
        depth: Current depth at the time of the check.
        limit: The configured depth limit.
    """

    def __init__(self, queue: str, depth: int, limit: int) -> None:
        super().__init__(
            f"Queue {queue!r} is full: depth={depth} >= limit={limit}"
        )
        self.queue = queue
        self.depth = depth
        self.limit = limit


# ---------------------------------------------------------------------------
# CacheClient — ICD-033 / ICD-041
# ---------------------------------------------------------------------------


@dataclass
class CacheClient:
    """Tenant-namespaced GET / SET / DEL cache operations.

    Used by Core (ICD-033) and Memory System (ICD-041).  All keys are wrapped
    via :func:`tenant_key`.  Calls fail open (return ``None`` / ``False``) when
    the circuit is open.

    Attributes:
        client:          Underlying Redis client.
        circuit_breaker: Shared circuit breaker for this Redis connection.
    """

    client: RedisClientProto
    circuit_breaker: CircuitBreaker

    async def get(self, tenant_id: UUID, key: str) -> bytes | None:
        """Return cached value for *key* under *tenant_id*, or ``None``.

        Fails open (returns ``None``) when circuit is open.
        """
        if not self.circuit_breaker.allow_request():
            log.debug("cache.get skipped: circuit open (tenant=%s key=%s)", tenant_id, key)
            return None
        try:
            value = await self.client.get(tenant_key(tenant_id, key))
            self.circuit_breaker.record_success()
            return value
        except Exception:
            self.circuit_breaker.record_failure()
            log.debug("cache.get failed (non-fatal, tenant=%s key=%s)", tenant_id, key)
            return None

    async def set(
        self,
        tenant_id: UUID,
        key: str,
        value: bytes | str,
        ttl: int,
    ) -> bool:
        """Store *value* under *key* for *tenant_id* with *ttl* seconds.

        Returns ``True`` on success, ``False`` when skipped (circuit open) or
        on error (fail-open).
        """
        if not self.circuit_breaker.allow_request():
            log.debug("cache.set skipped: circuit open (tenant=%s key=%s)", tenant_id, key)
            return False
        try:
            await self.client.set(tenant_key(tenant_id, key), value, ex=ttl)
            self.circuit_breaker.record_success()
            return True
        except Exception:
            self.circuit_breaker.record_failure()
            log.debug("cache.set failed (non-fatal, tenant=%s key=%s)", tenant_id, key)
            return False

    async def delete(self, tenant_id: UUID, *keys: str) -> int:
        """Delete *keys* under *tenant_id*; returns count deleted.

        Returns 0 and fails open when circuit is open or an error occurs.
        """
        if not self.circuit_breaker.allow_request():
            return 0
        try:
            namespaced = [tenant_key(tenant_id, k) for k in keys]
            count = await self.client.delete(*namespaced)
            self.circuit_breaker.record_success()
            return count
        except Exception:
            self.circuit_breaker.record_failure()
            return 0


# ---------------------------------------------------------------------------
# QueueClient — ICD-035
# ---------------------------------------------------------------------------


@dataclass
class QueueClient:
    """Tenant-isolated task queues (LPUSH/RPOP) and cron queues (sorted set).

    Queue keys follow the ICD-035 pattern ``{queue_name}_{tenant_id}``.
    Enforces *depth_limit* per tenant queue; raises :exc:`QueueFull` if
    ``LLEN >= depth_limit`` before enqueueing.

    Attributes:
        client:      Redis client.
        circuit_breaker: Shared circuit breaker.
        depth_limit: Maximum queue depth per tenant (ICD-035: 10 000).
    """

    client: RedisClientProto
    circuit_breaker: CircuitBreaker
    depth_limit: int = QUEUE_DEPTH_LIMIT

    async def enqueue(
        self,
        tenant_id: UUID,
        queue_name: str,
        payload: bytes | str,
    ) -> None:
        """Left-push *payload* onto *queue_name* for *tenant_id*.

        Raises:
            QueueFull: If the queue is at or above *depth_limit*.
        """
        key = queue_key(tenant_id, queue_name)
        current_depth = await self.client.llen(key)
        if current_depth >= self.depth_limit:
            raise QueueFull(key, current_depth, self.depth_limit)
        await self.client.lpush(key, payload)

    async def dequeue(
        self,
        tenant_id: UUID,
        queue_name: str,
    ) -> bytes | None:
        """Right-pop one item from *queue_name* for *tenant_id*.

        Returns ``None`` if the queue is empty.
        """
        return await self.client.rpop(queue_key(tenant_id, queue_name))

    async def enqueue_scheduled(
        self,
        tenant_id: UUID,
        score: float,
        payload: str,
    ) -> None:
        """Add *payload* to the cron sorted-set queue with *score* (Unix epoch).

        Per ICD-035 ``cron_queue_{tenant_id}``.
        """
        key = queue_key(tenant_id, "cron_queue")
        await self.client.zadd(key, {payload: score})

    async def dequeue_ready(
        self,
        tenant_id: UUID,
        max_score: float,
    ) -> list[bytes]:
        """Return all cron-queue items with score ≤ *max_score*.

        Used to dequeue tasks whose scheduled time has arrived.
        """
        key = queue_key(tenant_id, "cron_queue")
        return await self.client.zrangebyscore(key, 0.0, max_score)

    async def depth(self, tenant_id: UUID, queue_name: str) -> int:
        """Return current length of *queue_name* for *tenant_id*."""
        return await self.client.llen(queue_key(tenant_id, queue_name))


# ---------------------------------------------------------------------------
# PubSubClient — ICD-035
# ---------------------------------------------------------------------------


@dataclass
class PubSubClient:
    """PUBLISH / SUBSCRIBE for lane status notifications (ICD-035).

    Channel naming: ``lane_status_{execution_id}`` per ICD-035 pub-sub schema.
    """

    client: RedisClientProto

    async def publish(self, channel: str, message: str | bytes) -> int:
        """Publish *message* to *channel*; returns subscriber count."""
        return await self.client.publish(channel, message)

    async def subscribe(self, *channels: str) -> None:
        """Subscribe to one or more *channels*."""
        await self.client.subscribe(*channels)

    async def get_message(self, timeout: float = 0.1) -> dict[str, object] | None:
        """Poll for the next message from subscribed channels.

        Returns a message dict (keys: ``type``, ``channel``, ``data``) or
        ``None`` on timeout.
        """
        return await self.client.get_message(timeout)


# ---------------------------------------------------------------------------
# StreamClient — ICD-037
# ---------------------------------------------------------------------------


@dataclass
class StreamClient:
    """Redis Streams for real-time metrics (ICD-037).

    Stream keys follow the pattern ``{stream_name}_{tenant_id}``.  Appends
    trim at *maxlen* (approximate) to prevent unbounded growth; ICD-037
    specifies trimming at 1 000 000 events.

    Attributes:
        client: Redis client.
        maxlen: XADD MAXLEN ~ trim target (default: 1 000 000 per ICD-037).
    """

    client: RedisClientProto
    maxlen: int = STREAM_MAXLEN

    async def append(
        self,
        tenant_id: UUID,
        stream_name: str,
        fields: dict[str, str | bytes],
    ) -> str:
        """Append *fields* to *stream_name* for *tenant_id*.

        Returns:
            The Redis stream entry ID (e.g. ``"1739923200000-0"``).
        """
        key = stream_key(tenant_id, stream_name)
        return await self.client.xadd(key, fields, maxlen=self.maxlen)

    async def read_range(
        self,
        tenant_id: UUID,
        stream_name: str,
        min_id: str = "-",
        max_id: str = "+",
        count: int | None = None,
    ) -> list[tuple[str, dict[str, bytes]]]:
        """Return entries from *stream_name* for *tenant_id* in [*min_id*, *max_id*].

        Args:
            tenant_id:   Tenant scope.
            stream_name: Logical stream name (prefix before ``_{tenant_id}``).
            min_id:      Lower bound stream ID (default ``"-"`` = beginning).
            max_id:      Upper bound stream ID (default ``"+"`` = end).
            count:       Maximum entries to return (``None`` = all).
        """
        key = stream_key(tenant_id, stream_name)
        return await self.client.xrange(key, min_id, max_id, count)


# ---------------------------------------------------------------------------
# RevocationCache — ICD-049
# ---------------------------------------------------------------------------


@dataclass
class RevocationCache:
    """Token revocation lookup via ``EXISTS revoked_token:{jti}`` (ICD-049).

    Per ICD-049 error contract: "If Redis unavailable, fail open (allow token
    if signature valid)".  :meth:`is_revoked` returns ``False`` on any
    connection error.

    Attributes:
        client: Redis client.
    """

    client: RedisClientProto

    async def is_revoked(self, jti: str) -> bool:
        """Return ``True`` if *jti* is in the revocation list.

        Fails open (returns ``False``) on any exception, per ICD-049.
        """
        try:
            count = await self.client.exists(revocation_key(jti))
            return count > 0
        except Exception:
            log.debug("revocation_cache.is_revoked failed (fail-open, jti=%s)", jti)
            return False

    async def revoke(self, jti: str, ttl: int) -> None:
        """Mark *jti* as revoked with expiry *ttl* seconds.

        Per ICD-049: ``SET revoked_token:{jti} "" EX {ttl}``.
        """
        await self.client.set(revocation_key(jti), b"", ex=ttl)


# ---------------------------------------------------------------------------
# RedisBackend — top-level facade
# ---------------------------------------------------------------------------


@dataclass
class RedisBackend:
    """Facade combining all Redis client components.

    The shared :class:`CircuitBreaker` is used by ``cache`` and ``queues``;
    ``pubsub``, ``streams``, and ``revocation`` have their own error semantics.

    Attributes:
        cache:           Tenant-namespaced cache (ICD-033 / ICD-041).
        queues:          Tenant task queues + cron queues (ICD-035).
        pubsub:          Lane-status pub/sub (ICD-035).
        streams:         Real-time metrics streams (ICD-037).
        revocation:      Token revocation lookup (ICD-049).
        circuit_breaker: Shared breaker for cache + queues.
    """

    cache: CacheClient
    queues: QueueClient
    pubsub: PubSubClient
    streams: StreamClient
    revocation: RevocationCache
    circuit_breaker: CircuitBreaker

    @classmethod
    def from_client(
        cls,
        client: RedisClientProto,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        queue_depth_limit: int = QUEUE_DEPTH_LIMIT,
        stream_maxlen: int = STREAM_MAXLEN,
    ) -> RedisBackend:
        """Construct a :class:`RedisBackend` from a single Redis client.

        All components share the same *client* and a single
        :class:`CircuitBreaker` (for ``cache`` and ``queues``; ``pubsub``,
        ``streams``, and ``revocation`` wrap the client directly).

        Args:
            client:             The underlying Redis client.
            failure_threshold:  Failures before circuit opens (default 3).
            recovery_timeout:   Seconds before OPEN→HALF_OPEN (default 30).
            queue_depth_limit:  Per-tenant queue depth cap (default 10 000).
            stream_maxlen:      XADD trim target (default 1 000 000).
        """
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        return cls(
            cache=CacheClient(client=client, circuit_breaker=cb),
            queues=QueueClient(
                client=client,
                circuit_breaker=cb,
                depth_limit=queue_depth_limit,
            ),
            pubsub=PubSubClient(client=client),
            streams=StreamClient(client=client, maxlen=stream_maxlen),
            revocation=RevocationCache(client=client),
            circuit_breaker=cb,
        )
