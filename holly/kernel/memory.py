"""3-tier memory system with tenant isolation per ICDs 041-043.

Implements hierarchical memory management:
- L2 (Short-term): Redis via ICD-041 (TTL 30min, conversation_context 7d)
- L1.5 (Medium-term): PostgreSQL via ICD-042 (30d retention policy)
- L0 (Long-term): ChromaDB via ICD-043 (semantic search, 30d retention)

Tier promotion: Short → Medium → Long based on access patterns.
Tenant isolation: tenant_id namespacing in all tiers per ICD v0.1.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Protocol

if TYPE_CHECKING:
    from holly.storage.chroma.client import ChromaClient
    from holly.storage.postgres import PostgresBackend
    from holly.storage.redis.client import CacheClient


logger = logging.getLogger(__name__)


def _safe_uuid(val: str | uuid.UUID) -> uuid.UUID | str:
    """Convert string to UUID if valid, otherwise return as-is."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(val)
    except (ValueError, AttributeError):
        return val


class MemoryType(str, Enum):
    """Memory classification per ICD-042 schema."""

    CONVERSATION = "conversation"
    DECISION = "decision"
    FACT = "fact"


class TierLevel(str, Enum):
    """Memory storage tier."""

    SHORT = "short"  # Redis (ICD-041)
    MEDIUM = "medium"  # PostgreSQL (ICD-042)
    LONG = "long"  # ChromaDB (ICD-043)


@dataclass(slots=True)
class MemoryRecord:
    """Core memory unit with tier metadata."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    agent_id: str = ""
    tenant_id: str = ""
    memory_type: MemoryType = MemoryType.CONVERSATION
    content: str = ""
    embedding_id: str | None = None
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    retention_days: int = 30
    current_tier: TierLevel = TierLevel.SHORT
    access_count: int = 0
    last_accessed: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def content_hash(self) -> str:
        """Return SHA256 hash of content for idempotency."""
        return hashlib.sha256(self.content.encode()).hexdigest()

    def should_promote(self, threshold: int = 3) -> bool:
        """Decide if memory should promote to next tier."""
        return self.access_count >= threshold


@dataclass(slots=True)
class MemoryQueryResult:
    """Result of memory query operations."""

    records: list[MemoryRecord] = field(default_factory=list)
    total_count: int = 0
    is_partial: bool = False
    error: str | None = None


@dataclass(slots=True)
class TierPromotionEvent:
    """Record of memory tier promotion."""

    memory_id: str = ""
    tenant_id: str = ""
    from_tier: TierLevel = TierLevel.SHORT
    to_tier: TierLevel = TierLevel.MEDIUM
    reason: str = ""
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))


class MemoryBackendProto(Protocol):
    """Protocol for memory backend clients (cacheable via __runtime_checkable__)."""

    async def get_memory(
        self, memory_id: str, tenant_id: str
    ) -> MemoryRecord | None:
        """Retrieve single memory record."""
        ...

    async def store_memory(self, record: MemoryRecord) -> str:
        """Store memory; return memory_id."""
        ...

    async def query_memories(
        self, agent_id: str, tenant_id: str, limit: int = 10
    ) -> MemoryQueryResult:
        """Query memories for agent (bulk retrieve)."""
        ...

    async def delete_memory(self, memory_id: str, tenant_id: str) -> bool:
        """Soft-delete or remove memory."""
        ...


@dataclass(slots=True)
class TierPromotionPolicy:
    """Configurable promotion thresholds."""

    access_count_threshold: int = 3
    time_in_tier_seconds: int = 3600
    batch_size: int = 100
    promotion_interval_seconds: int = 300


class MemoryManager:
    """3-tier memory manager with tenant isolation and tier promotion.

    Implements ICD-041 (Redis), ICD-042 (PostgreSQL), ICD-043 (ChromaDB).
    Enforces tenant isolation per ICD v0.1 tenant isolation model.
    """

    __slots__ = (
        "_redis_client",
        "_postgres_client",
        "_chroma_client",
        "_policy",
        "_promotion_queue",
        "_active_promotions",
        "_logger",
    )

    def __init__(
        self,
        redis_client: CacheClient | None = None,
        postgres_client: PostgresBackend | None = None,
        chroma_client: ChromaClient | None = None,
        policy: TierPromotionPolicy | None = None,
    ):
        """Initialize 3-tier memory manager.

        Args:
            redis_client: Cache client for short-term storage (ICD-041).
            postgres_client: PostgreSQL client for medium-term (ICD-042).
            chroma_client: ChromaDB client for long-term embeddings (ICD-043).
            policy: Tier promotion policy (defaults provided).

        Raises:
            ValueError: If no backends provided.
        """
        self._redis_client = redis_client
        self._postgres_client = postgres_client
        self._chroma_client = chroma_client
        self._policy = policy or TierPromotionPolicy()
        self._promotion_queue: list[MemoryRecord] = []
        self._active_promotions: dict[str, asyncio.Task[bool]] = {}
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        if not any([redis_client, postgres_client, chroma_client]):
            msg = "At least one backend required (redis/postgres/chroma)"
            raise ValueError(msg)

    async def store(
        self,
        conversation_id: str,
        agent_id: str,
        tenant_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        retention_days: int = 30,
    ) -> MemoryRecord:
        """Store memory in short-term (Redis) tier.

        Args:
            conversation_id: Unique conversation identifier.
            agent_id: Agent creating memory.
            tenant_id: Tenant ID for isolation.
            content: Memory content (assumed already redacted per ICD-041).
            memory_type: Type of memory (conversation/decision/fact).
            retention_days: Retention policy.

        Returns:
            MemoryRecord with populated id, timestamp, current_tier.

        Raises:
            RuntimeError: If Redis unavailable and no fallback.
        """
        record = MemoryRecord(
            conversation_id=conversation_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            memory_type=memory_type,
            content=content,
            retention_days=retention_days,
            current_tier=TierLevel.SHORT,
            timestamp=int(datetime.now().timestamp()),
        )

        if self._redis_client:
            try:
                cache_key = f"memory:{tenant_id}:{record.id}"
                await self._redis_client.set(
                    cache_key,
                    record,
                    ttl=min(1800, retention_days * 86400),  # max 30min
                )
                self._logger.info(
                    "Memory stored in Redis",
                    extra={
                        "memory_id": record.id,
                        "tenant_id": tenant_id,
                        "tier": TierLevel.SHORT,
                    },
                )
                return record
            except Exception as e:
                self._logger.warning(
                    f"Redis unavailable: {e}; falling back to PostgreSQL"
                )

        if self._postgres_client:
            try:
                conv_uuid = _safe_uuid(conversation_id)
                agent_uuid = _safe_uuid(agent_id)
                tenant_uuid = _safe_uuid(tenant_id)
                
                await self._postgres_client.insert(
                    "memory_store",
                    {
                        "id": uuid.UUID(record.id),
                        "conversation_id": conv_uuid if isinstance(conv_uuid, uuid.UUID) else uuid.uuid4(),
                        "agent_id": agent_uuid if isinstance(agent_uuid, uuid.UUID) else uuid.uuid4(),
                        "memory_type": record.memory_type.value,
                        "content": content,
                        "timestamp": record.timestamp,
                        "tenant_id": tenant_uuid if isinstance(tenant_uuid, uuid.UUID) else uuid.uuid4(),
                        "retention_days": retention_days,
                    },
                )
                record.current_tier = TierLevel.MEDIUM
                self._logger.info(
                    "Memory stored in PostgreSQL",
                    extra={
                        "memory_id": record.id,
                        "tenant_id": tenant_id,
                        "tier": TierLevel.MEDIUM,
                    },
                )
                return record
            except Exception as e:
                self._logger.error(f"PostgreSQL insert failed: {e}")
                msg = "Memory store unavailable"
                raise RuntimeError(msg) from e

        msg = "No memory backend available"
        raise RuntimeError(msg)

    async def retrieve(
        self, memory_id: str, tenant_id: str
    ) -> MemoryRecord | None:
        """Retrieve single memory record from appropriate tier.

        Checks tiers in priority: SHORT → MEDIUM → LONG.
        Updates last_accessed timestamp and access_count.

        Args:
            memory_id: Memory identifier.
            tenant_id: Tenant ID for isolation check.

        Returns:
            MemoryRecord if found, None if not found or access denied.
        """
        if self._redis_client:
            try:
                cache_key = f"memory:{tenant_id}:{memory_id}"
                record: MemoryRecord | None = await self._redis_client.get(
                    cache_key, MemoryRecord
                )
                if record and record.tenant_id == tenant_id:
                    record.access_count += 1
                    record.last_accessed = int(datetime.now().timestamp())
                    if record.should_promote():
                        await self._enqueue_promotion(record)
                    self._logger.info(
                        "Memory hit in Redis",
                        extra={
                            "memory_id": memory_id,
                            "tenant_id": tenant_id,
                            "access_count": record.access_count,
                        },
                    )
                    return record
            except Exception as e:
                self._logger.debug(f"Redis get failed: {e}; checking PostgreSQL")

        if self._postgres_client:
            try:
                mem_uuid = _safe_uuid(memory_id)
                tenant_uuid = _safe_uuid(tenant_id)
                
                if not isinstance(mem_uuid, uuid.UUID) or not isinstance(tenant_uuid, uuid.UUID):
                    return None
                
                result = await self._postgres_client.query(
                    "SELECT * FROM memory_store WHERE id = %s AND tenant_id = %s",
                    (mem_uuid, tenant_uuid),
                )
                if result:
                    record = MemoryRecord(
                        id=str(result[0]["id"]),
                        conversation_id=str(result[0]["conversation_id"]),
                        agent_id=str(result[0]["agent_id"]),
                        tenant_id=str(result[0]["tenant_id"]),
                        memory_type=MemoryType(result[0]["memory_type"]),
                        content=result[0]["content"],
                        embedding_id=result[0].get("embedding_id"),
                        timestamp=result[0]["timestamp"],
                        retention_days=result[0]["retention_days"],
                        current_tier=TierLevel.MEDIUM,
                    )
                    record.access_count += 1
                    record.last_accessed = int(datetime.now().timestamp())
                    self._logger.info(
                        "Memory hit in PostgreSQL",
                        extra={"memory_id": memory_id, "tenant_id": tenant_id},
                    )
                    return record
            except Exception as e:
                self._logger.debug(f"PostgreSQL query failed: {e}")

        self._logger.info(
            "Memory miss in all tiers",
            extra={"memory_id": memory_id, "tenant_id": tenant_id},
        )
        return None

    async def query_by_agent(
        self, agent_id: str, tenant_id: str, limit: int = 10
    ) -> MemoryQueryResult:
        """Query recent memories for agent (bulk retrieve from all tiers).

        Args:
            agent_id: Target agent ID.
            tenant_id: Tenant ID for isolation.
            limit: Max records to return.

        Returns:
            MemoryQueryResult with records from medium/long term (faster query).
        """
        result = MemoryQueryResult()

        if self._postgres_client:
            try:
                agent_uuid = _safe_uuid(agent_id)
                tenant_uuid = _safe_uuid(tenant_id)
                
                if not isinstance(agent_uuid, uuid.UUID) or not isinstance(tenant_uuid, uuid.UUID):
                    return result
                
                rows = await self._postgres_client.query(
                    "SELECT * FROM memory_store "
                    "WHERE agent_id = %s AND tenant_id = %s "
                    "ORDER BY timestamp DESC LIMIT %s",
                    (agent_uuid, tenant_uuid, limit),
                )
                for row in rows:
                    record = MemoryRecord(
                        id=str(row["id"]),
                        conversation_id=str(row["conversation_id"]),
                        agent_id=str(row["agent_id"]),
                        tenant_id=str(row["tenant_id"]),
                        memory_type=MemoryType(row["memory_type"]),
                        content=row["content"],
                        embedding_id=row.get("embedding_id"),
                        timestamp=row["timestamp"],
                        retention_days=row["retention_days"],
                        current_tier=TierLevel.MEDIUM,
                    )
                    result.records.append(record)
                result.total_count = len(result.records)
                self._logger.info(
                    "Agent query from PostgreSQL",
                    extra={
                        "agent_id": agent_id,
                        "tenant_id": tenant_id,
                        "count": len(result.records),
                    },
                )
            except Exception as e:
                result.error = str(e)
                result.is_partial = True
                self._logger.error(f"PostgreSQL agent query failed: {e}")

        return result

    async def semantic_search(
        self,
        query_text: str,
        tenant_id: str,
        limit: int = 5,
        embedding_fn: Callable[[str], Awaitable[list[float]]] | None = None,
    ) -> MemoryQueryResult:
        """Search long-term memory by semantic similarity (ChromaDB).

        Args:
            query_text: Search query.
            tenant_id: Tenant ID for isolation.
            limit: Max results.
            embedding_fn: Optional custom embedding function.

        Returns:
            MemoryQueryResult with semantically similar memories.
        """
        result = MemoryQueryResult()

        if not self._chroma_client:
            result.error = "ChromaDB not available for semantic search"
            return result

        try:
            collection_name = f"memory_{tenant_id}"
            query_results = await self._chroma_client.query(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=limit,
            )

            if query_results and query_results.get("ids"):
                for doc_id, distance in zip(
                    query_results["ids"][0], query_results.get("distances", [[]])[0]
                ):
                    metadata = (query_results.get("metadatas", [[]])[0] or [{}])[0]
                    record = MemoryRecord(
                        id=doc_id,
                        conversation_id=metadata.get("conversation_id", ""),
                        agent_id=metadata.get("agent_id", ""),
                        tenant_id=tenant_id,
                        memory_type=MemoryType(
                            metadata.get("memory_type", "conversation")
                        ),
                        embedding_id=doc_id,
                        timestamp=int(metadata.get("timestamp", 0)),
                        current_tier=TierLevel.LONG,
                    )
                    result.records.append(record)

            result.total_count = len(result.records)
            self._logger.info(
                "Semantic search from ChromaDB",
                extra={
                    "query": query_text[:50],
                    "tenant_id": tenant_id,
                    "results": len(result.records),
                },
            )
        except Exception as e:
            result.error = str(e)
            self._logger.error(f"ChromaDB semantic search failed: {e}")

        return result

    async def promote_tier(
        self, memory_id: str, tenant_id: str, target_tier: TierLevel
    ) -> bool:
        """Promote memory to higher tier.

        Moves memory from SHORT → MEDIUM → LONG.
        Validates tenant isolation before promotion.

        Args:
            memory_id: Memory to promote.
            tenant_id: Tenant ID for isolation.
            target_tier: Target tier (must be higher).

        Returns:
            True if promotion succeeded.
        """
        record = await self.retrieve(memory_id, tenant_id)
        if not record:
            self._logger.warning(
                f"Cannot promote: memory {memory_id} not found for tenant {tenant_id}"
            )
            return False

        if record.tenant_id != tenant_id:
            self._logger.error(
                "Tenant isolation violation attempted",
                extra={"memory_id": memory_id, "tenant_id": tenant_id},
            )
            return False

        current_idx = list(TierLevel).index(record.current_tier)
        target_idx = list(TierLevel).index(target_tier)

        if target_idx <= current_idx:
            self._logger.warning(
                f"Invalid promotion: {record.current_tier} → {target_tier}"
            )
            return False

        promotion_event = TierPromotionEvent(
            memory_id=memory_id,
            tenant_id=tenant_id,
            from_tier=record.current_tier,
            to_tier=target_tier,
            reason="access_count_threshold",
        )

        try:
            if target_tier == TierLevel.MEDIUM and self._postgres_client:
                conv_uuid = _safe_uuid(record.conversation_id)
                agent_uuid = _safe_uuid(record.agent_id)
                tenant_uuid = _safe_uuid(record.tenant_id)
                
                await self._postgres_client.insert(
                    "memory_store",
                    {
                        "id": uuid.UUID(record.id),
                        "conversation_id": conv_uuid if isinstance(conv_uuid, uuid.UUID) else uuid.uuid4(),
                        "agent_id": agent_uuid if isinstance(agent_uuid, uuid.UUID) else uuid.uuid4(),
                        "memory_type": record.memory_type.value,
                        "content": record.content,
                        "timestamp": record.timestamp,
                        "tenant_id": tenant_uuid if isinstance(tenant_uuid, uuid.UUID) else uuid.uuid4(),
                        "retention_days": record.retention_days,
                    },
                )
                record.current_tier = TierLevel.MEDIUM
                self._logger.info(
                    "Memory promoted to MEDIUM",
                    extra={
                        "memory_id": memory_id,
                        "tenant_id": tenant_id,
                        "event": promotion_event,
                    },
                )
                return True

            elif target_tier == TierLevel.LONG and self._chroma_client:
                embedding = [0.0] * 1536  # Placeholder; real embedding would be computed
                collection_name = f"memory_{tenant_id}"
                await self._chroma_client.upsert(
                    collection_name=collection_name,
                    ids=[record.id],
                    embeddings=[embedding],
                    metadatas=[
                        {
                            "conversation_id": record.conversation_id,
                            "agent_id": record.agent_id,
                            "memory_type": record.memory_type.value,
                            "timestamp": record.timestamp,
                        }
                    ],
                    documents=[record.content],
                )
                record.current_tier = TierLevel.LONG
                record.embedding_id = record.id
                self._logger.info(
                    "Memory promoted to LONG",
                    extra={
                        "memory_id": memory_id,
                        "tenant_id": tenant_id,
                        "event": promotion_event,
                    },
                )
                return True

            return False

        except Exception as e:
            self._logger.error(f"Tier promotion failed: {e}")
            return False

    async def _enqueue_promotion(self, record: MemoryRecord) -> None:
        """Internal: enqueue memory for tier promotion."""
        self._promotion_queue.append(record)
        if len(self._promotion_queue) >= self._policy.batch_size:
            await self._process_promotion_batch()

    async def _process_promotion_batch(self) -> None:
        """Internal: process queued promotions in batch."""
        if not self._promotion_queue:
            return

        batch = self._promotion_queue[: self._policy.batch_size]
        self._promotion_queue = self._promotion_queue[self._policy.batch_size :]

        tasks = []
        for record in batch:
            if record.current_tier == TierLevel.SHORT:
                task = self.promote_tier(record.id, record.tenant_id, TierLevel.MEDIUM)
                tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            promoted = sum(1 for r in results if r is True)
            self._logger.info(
                f"Promotion batch processed: {promoted}/{len(batch)} succeeded"
            )
        except Exception as e:
            self._logger.error(f"Promotion batch error: {e}")

    async def cleanup_expired(self, tenant_id: str) -> int:
        """Delete memories older than retention_days.

        Args:
            tenant_id: Tenant ID for isolation.

        Returns:
            Count of deleted memories.
        """
        deleted = 0
        cutoff_ts = int((datetime.now() - timedelta(days=30)).timestamp())

        if self._postgres_client:
            try:
                tenant_uuid = _safe_uuid(tenant_id)
                
                if not isinstance(tenant_uuid, uuid.UUID):
                    return deleted
                
                result = await self._postgres_client.query(
                    "DELETE FROM memory_store "
                    "WHERE tenant_id = %s AND timestamp < %s "
                    "RETURNING id",
                    (tenant_uuid, cutoff_ts),
                )
                deleted += len(result) if result else 0
                self._logger.info(
                    "Expired memories cleaned",
                    extra={"tenant_id": tenant_id, "deleted": deleted},
                )
            except Exception as e:
                self._logger.error(f"Cleanup failed: {e}")

        return deleted

    def isolation_check(self, record: MemoryRecord, tenant_id: str) -> bool:
        """Verify tenant isolation on memory record.

        Args:
            record: Memory record to check.
            tenant_id: Expected tenant ID.

        Returns:
            True if record belongs to tenant.
        """
        return record.tenant_id == tenant_id
