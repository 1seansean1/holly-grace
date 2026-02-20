"""Unit and integration tests for 3-tier memory system (Task 39.4).

Tests cover:
- MemoryRecord creation and hashing
- MemoryManager initialization
- Tier storage: Redis (SHORT), PostgreSQL (MEDIUM), ChromaDB (LONG)
- Tenant isolation enforcement
- Tier promotion logic and thresholds
- Query operations (single, bulk, semantic)
- Cleanup and expiration
"""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from holly.kernel.memory import (
    MemoryManager,
    MemoryRecord,
    MemoryType,
    MemoryQueryResult,
    TierLevel,
    TierPromotionEvent,
    TierPromotionPolicy,
)


# ============================================================================
# UNIT TESTS: MemoryRecord
# ============================================================================


class TestMemoryRecord:
    """Tests for MemoryRecord dataclass."""

    def test_memory_record_creation(self):
        """Test basic MemoryRecord creation with defaults."""
        record = MemoryRecord(
            conversation_id="conv-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            content="Hello world",
        )
        assert record.conversation_id == "conv-1"
        assert record.agent_id == "agent-1"
        assert record.tenant_id == "tenant-1"
        assert record.content == "Hello world"
        assert record.memory_type == MemoryType.CONVERSATION
        assert record.current_tier == TierLevel.SHORT
        assert record.access_count == 0
        assert record.id is not None  # UUID generated

    def test_memory_record_content_hash(self):
        """Test content_hash method for idempotency."""
        record1 = MemoryRecord(content="test content")
        record2 = MemoryRecord(content="test content")
        record3 = MemoryRecord(content="different")

        assert record1.content_hash() == record2.content_hash()
        assert record1.content_hash() != record3.content_hash()

    def test_memory_record_hash_deterministic(self):
        """Test that content_hash is deterministic."""
        record = MemoryRecord(content="fixed content")
        hash1 = record.content_hash()
        hash2 = record.content_hash()
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_memory_record_should_promote_threshold(self):
        """Test promotion decision based on access_count."""
        record = MemoryRecord()
        assert not record.should_promote(threshold=3)

        record.access_count = 2
        assert not record.should_promote(threshold=3)

        record.access_count = 3
        assert record.should_promote(threshold=3)

        record.access_count = 10
        assert record.should_promote(threshold=3)

    def test_memory_record_memory_types(self):
        """Test all memory types."""
        for mtype in [MemoryType.CONVERSATION, MemoryType.DECISION, MemoryType.FACT]:
            record = MemoryRecord(memory_type=mtype)
            assert record.memory_type == mtype

    def test_memory_record_tier_levels(self):
        """Test all tier levels."""
        for tier in [TierLevel.SHORT, TierLevel.MEDIUM, TierLevel.LONG]:
            record = MemoryRecord(current_tier=tier)
            assert record.current_tier == tier

    def test_memory_record_slots(self):
        """Test that __slots__ is enforced."""
        record = MemoryRecord()
        with pytest.raises(AttributeError):
            record.new_attribute = "should fail"


# ============================================================================
# UNIT TESTS: TierPromotionPolicy & TierPromotionEvent
# ============================================================================


class TestTierPromotionPolicy:
    """Tests for TierPromotionPolicy configuration."""

    def test_default_policy(self):
        """Test default policy values."""
        policy = TierPromotionPolicy()
        assert policy.access_count_threshold == 3
        assert policy.time_in_tier_seconds == 3600
        assert policy.batch_size == 100

    def test_custom_policy(self):
        """Test custom policy values."""
        policy = TierPromotionPolicy(
            access_count_threshold=5,
            time_in_tier_seconds=7200,
            batch_size=50,
        )
        assert policy.access_count_threshold == 5
        assert policy.time_in_tier_seconds == 7200
        assert policy.batch_size == 50


class TestTierPromotionEvent:
    """Tests for TierPromotionEvent."""

    def test_promotion_event_creation(self):
        """Test promotion event creation."""
        event = TierPromotionEvent(
            memory_id="mem-1",
            tenant_id="tenant-1",
            from_tier=TierLevel.SHORT,
            to_tier=TierLevel.MEDIUM,
            reason="access_count_threshold",
        )
        assert event.memory_id == "mem-1"
        assert event.tenant_id == "tenant-1"
        assert event.from_tier == TierLevel.SHORT
        assert event.to_tier == TierLevel.MEDIUM
        assert event.reason == "access_count_threshold"
        assert event.timestamp > 0


# ============================================================================
# UNIT TESTS: MemoryQueryResult
# ============================================================================


class TestMemoryQueryResult:
    """Tests for MemoryQueryResult."""

    def test_query_result_empty(self):
        """Test empty query result."""
        result = MemoryQueryResult()
        assert result.records == []
        assert result.total_count == 0
        assert not result.is_partial
        assert result.error is None

    def test_query_result_with_records(self):
        """Test query result with records."""
        records = [
            MemoryRecord(content="mem1"),
            MemoryRecord(content="mem2"),
        ]
        result = MemoryQueryResult(records=records, total_count=2)
        assert len(result.records) == 2
        assert result.total_count == 2

    def test_query_result_partial(self):
        """Test partial query result."""
        result = MemoryQueryResult(
            records=[MemoryRecord()],
            total_count=100,
            is_partial=True,
            error="timeout",
        )
        assert result.is_partial
        assert result.error == "timeout"
        assert result.total_count == 100


# ============================================================================
# INTEGRATION TESTS: MemoryManager
# ============================================================================


class TestMemoryManagerInit:
    """Tests for MemoryManager initialization."""

    def test_manager_init_no_backends_raises(self):
        """Test that initialization without backends raises ValueError."""
        with pytest.raises(ValueError, match="At least one backend required"):
            MemoryManager()

    def test_manager_init_redis_only(self):
        """Test manager init with Redis only."""
        redis_mock = AsyncMock()
        manager = MemoryManager(redis_client=redis_mock)
        assert manager._redis_client == redis_mock
        assert manager._postgres_client is None
        assert manager._chroma_client is None

    def test_manager_init_postgres_only(self):
        """Test manager init with PostgreSQL only."""
        postgres_mock = AsyncMock()
        manager = MemoryManager(postgres_client=postgres_mock)
        assert manager._postgres_client == postgres_mock
        assert manager._redis_client is None

    def test_manager_init_chroma_only(self):
        """Test manager init with ChromaDB only."""
        chroma_mock = AsyncMock()
        manager = MemoryManager(chroma_client=chroma_mock)
        assert manager._chroma_client == chroma_mock

    def test_manager_init_custom_policy(self):
        """Test manager init with custom policy."""
        policy = TierPromotionPolicy(access_count_threshold=5)
        manager = MemoryManager(
            postgres_client=AsyncMock(),
            policy=policy,
        )
        assert manager._policy.access_count_threshold == 5


class TestMemoryManagerStore:
    """Tests for MemoryManager.store() method."""

    @pytest.mark.asyncio
    async def test_store_to_redis_success(self):
        """Test successful store to Redis."""
        redis_mock = AsyncMock()
        manager = MemoryManager(redis_client=redis_mock)

        record = await manager.store(
            conversation_id="conv-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            content="test memory",
            memory_type=MemoryType.CONVERSATION,
        )

        assert record.conversation_id == "conv-1"
        assert record.agent_id == "agent-1"
        assert record.tenant_id == "tenant-1"
        assert record.content == "test memory"
        assert record.current_tier == TierLevel.SHORT
        redis_mock.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_redis_fallback_to_postgres(self):
        """Test fallback from Redis to PostgreSQL on error."""
        redis_mock = AsyncMock()
        redis_mock.set.side_effect = ConnectionError("Redis unavailable")
        postgres_mock = AsyncMock()

        manager = MemoryManager(redis_client=redis_mock, postgres_client=postgres_mock)

        record = await manager.store(
            conversation_id=str(uuid4()),
            agent_id=str(uuid4()),
            tenant_id=str(uuid4()),
            content="fallback test",
        )

        assert record.current_tier == TierLevel.MEDIUM
        postgres_mock.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_no_backend_raises(self):
        """Test store raises when all backends fail."""
        redis_mock = AsyncMock()
        redis_mock.set.side_effect = ConnectionError()

        manager = MemoryManager(redis_client=redis_mock)

        with pytest.raises(RuntimeError, match="No memory backend available"):
            await manager.store(
                conversation_id="conv-1",
                agent_id="agent-1",
                tenant_id="tenant-1",
                content="test",
            )


class TestMemoryManagerRetrieve:
    """Tests for MemoryManager.retrieve() method."""

    @pytest.mark.asyncio
    async def test_retrieve_from_redis_hit(self):
        """Test retrieval from Redis (cache hit)."""
        redis_mock = AsyncMock()
        record = MemoryRecord(
            id="mem-1",
            tenant_id="tenant-1",
            content="cached",
        )
        redis_mock.get.return_value = record

        manager = MemoryManager(redis_client=redis_mock)
        result = await manager.retrieve("mem-1", "tenant-1")

        assert result is not None
        assert result.access_count == 1  # Incremented on access
        redis_mock.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_tenant_isolation(self):
        """Test tenant isolation check on retrieval."""
        redis_mock = AsyncMock()
        record = MemoryRecord(
            id="mem-1",
            tenant_id="tenant-1",
            content="should not access",
        )
        redis_mock.get.return_value = record

        manager = MemoryManager(redis_client=redis_mock)
        result = await manager.retrieve("mem-1", "tenant-2")

        # Redis hit but tenant mismatch → should be None
        assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self):
        """Test retrieve when memory not found."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        manager = MemoryManager(redis_client=redis_mock)
        result = await manager.retrieve("mem-notfound", "tenant-1")

        assert result is None


class TestMemoryManagerQueryByAgent:
    """Tests for MemoryManager.query_by_agent() method."""

    @pytest.mark.asyncio
    async def test_query_by_agent_success(self):
        """Test successful agent query."""
        postgres_mock = AsyncMock()
        mem_id = str(uuid4())
        conv_id = str(uuid4())
        agent_id = str(uuid4())
        tenant_id = str(uuid4())
        
        postgres_mock.query.return_value = [
            {
                "id": mem_id,
                "conversation_id": conv_id,
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "memory_type": "conversation",
                "content": "mem content",
                "timestamp": 1234567890,
                "retention_days": 30,
            },
        ]

        manager = MemoryManager(postgres_client=postgres_mock)
        result = await manager.query_by_agent(agent_id, tenant_id)

        assert result.total_count == 1
        assert len(result.records) == 1
        assert result.records[0].agent_id == agent_id
        assert not result.is_partial

    @pytest.mark.asyncio
    async def test_query_by_agent_empty(self):
        """Test agent query with no results."""
        postgres_mock = AsyncMock()
        postgres_mock.query.return_value = []

        manager = MemoryManager(postgres_client=postgres_mock)
        result = await manager.query_by_agent(str(uuid4()), str(uuid4()))

        assert result.total_count == 0
        assert result.records == []

    @pytest.mark.asyncio
    async def test_query_by_agent_error(self):
        """Test agent query with error."""
        postgres_mock = AsyncMock()
        postgres_mock.query.side_effect = Exception("DB error")

        manager = MemoryManager(postgres_client=postgres_mock)
        result = await manager.query_by_agent(str(uuid4()), str(uuid4()))

        assert result.is_partial
        assert result.error is not None


class TestMemoryManagerSemanticSearch:
    """Tests for MemoryManager.semantic_search() method."""

    @pytest.mark.asyncio
    async def test_semantic_search_success(self):
        """Test successful semantic search."""
        chroma_mock = AsyncMock()
        chroma_mock.query.return_value = {
            "ids": [["mem-1", "mem-2"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [
                [
                    {"conversation_id": "conv-1", "agent_id": "agent-1", "memory_type": "fact", "timestamp": 123456},
                    {"conversation_id": "conv-2", "agent_id": "agent-1", "memory_type": "fact", "timestamp": 123457},
                ]
            ],
        }

        manager = MemoryManager(chroma_client=chroma_mock)
        result = await manager.semantic_search("what is X?", "tenant-1")

        assert result.total_count == 2
        assert len(result.records) == 2
        assert result.records[0].current_tier == TierLevel.LONG

    @pytest.mark.asyncio
    async def test_semantic_search_no_chroma(self):
        """Test semantic search without ChromaDB."""
        postgres_mock = AsyncMock()
        manager = MemoryManager(postgres_client=postgres_mock)

        result = await manager.semantic_search("query", "tenant-1")

        assert result.error is not None
        assert "not available" in result.error


class TestMemoryManagerPromoteTier:
    """Tests for MemoryManager.promote_tier() method."""

    @pytest.mark.asyncio
    async def test_promote_short_to_medium(self):
        """Test tier promotion SHORT → MEDIUM."""
        postgres_mock = AsyncMock()
        redis_mock = AsyncMock()

        # Create a properly formed memory record
        mem_id = str(uuid4())
        record = MemoryRecord(
            id=mem_id,
            tenant_id="tenant-1",
            current_tier=TierLevel.SHORT,
            content="test",
            conversation_id=str(uuid4()),
            agent_id=str(uuid4()),
        )
        
        # Mock Redis get to return the record
        redis_mock.get.return_value = record

        manager = MemoryManager(
            redis_client=redis_mock,
            postgres_client=postgres_mock,
        )

        result = await manager.promote_tier(mem_id, "tenant-1", TierLevel.MEDIUM)

        assert result is True
        postgres_mock.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_promote_tenant_isolation_violation(self):
        """Test promotion fails on tenant isolation violation."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = MemoryRecord(
            id="mem-1",
            tenant_id="tenant-1",
            current_tier=TierLevel.SHORT,
        )

        manager = MemoryManager(redis_client=redis_mock)

        # Attempt to promote with mismatched tenant
        result = await manager.promote_tier("mem-1", "tenant-2", TierLevel.MEDIUM)

        assert result is False

    @pytest.mark.asyncio
    async def test_promote_not_found(self):
        """Test promotion fails if memory not found."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        manager = MemoryManager(redis_client=redis_mock)
        result = await manager.promote_tier("mem-notfound", "tenant-1", TierLevel.MEDIUM)

        assert result is False


class TestMemoryManagerCleanup:
    """Tests for MemoryManager.cleanup_expired() method."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_memories(self):
        """Test cleanup of expired memories."""
        postgres_mock = AsyncMock()
        postgres_mock.query.return_value = [
            {"id": "mem-1"},
            {"id": "mem-2"},
        ]

        manager = MemoryManager(postgres_client=postgres_mock)
        deleted = await manager.cleanup_expired(str(uuid4()))

        assert deleted == 2
        postgres_mock.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_expired(self):
        """Test cleanup with no expired memories."""
        postgres_mock = AsyncMock()
        postgres_mock.query.return_value = []

        manager = MemoryManager(postgres_client=postgres_mock)
        deleted = await manager.cleanup_expired(str(uuid4()))

        assert deleted == 0


class TestMemoryManagerIsolationCheck:
    """Tests for MemoryManager.isolation_check() method."""

    def test_isolation_check_pass(self):
        """Test isolation check passes for matching tenant."""
        record = MemoryRecord(tenant_id="tenant-1")
        manager = MemoryManager(postgres_client=AsyncMock())

        assert manager.isolation_check(record, "tenant-1") is True

    def test_isolation_check_fail(self):
        """Test isolation check fails for mismatched tenant."""
        record = MemoryRecord(tenant_id="tenant-1")
        manager = MemoryManager(postgres_client=AsyncMock())

        assert manager.isolation_check(record, "tenant-2") is False


# ============================================================================
# INTEGRATION TESTS: Multi-tier workflow
# ============================================================================


class TestMemoryTierWorkflow:
    """Integration tests for complete memory tier workflow."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle(self):
        """Test complete memory lifecycle: create → access → promote → query."""
        redis_mock = AsyncMock()
        postgres_mock = AsyncMock()
        chroma_mock = AsyncMock()

        manager = MemoryManager(
            redis_client=redis_mock,
            postgres_client=postgres_mock,
            chroma_client=chroma_mock,
        )

        # 1. Store in SHORT tier
        record = await manager.store(
            conversation_id="conv-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            content="lifecycle test",
            memory_type=MemoryType.DECISION,
        )
        assert record.current_tier == TierLevel.SHORT

        # 2. Retrieve (from cache)
        redis_mock.get.return_value = record
        retrieved = await manager.retrieve(record.id, "tenant-1")
        assert retrieved is not None
        assert retrieved.access_count == 1

        # 3. Promote to MEDIUM
        redis_mock.get.return_value = record
        promoted = await manager.promote_tier(record.id, "tenant-1", TierLevel.MEDIUM)
        assert promoted is True
        postgres_mock.insert.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_isolation_across_operations(self):
        """Test tenant isolation is enforced across all operations."""
        redis_mock = AsyncMock()
        postgres_mock = AsyncMock()

        manager = MemoryManager(
            redis_client=redis_mock,
            postgres_client=postgres_mock,
        )

        # Store for tenant-1
        record1 = await manager.store(
            conversation_id="conv-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            content="tenant-1 data",
        )

        # Attempt to retrieve with tenant-2
        redis_mock.get.return_value = record1
        retrieved = await manager.retrieve(record1.id, "tenant-2")

        # Should be None due to tenant isolation
        assert retrieved is None

        # Attempt to promote with wrong tenant
        redis_mock.get.return_value = record1
        promoted = await manager.promote_tier(record1.id, "tenant-2", TierLevel.MEDIUM)
        assert promoted is False


class TestMemoryEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_stores(self):
        """Test concurrent store operations."""
        import asyncio
        
        redis_mock = AsyncMock()
        manager = MemoryManager(redis_client=redis_mock)
        
        # Create 10 concurrent stores
        tasks = [
            manager.store(
                conversation_id=f"conv-{i}",
                agent_id=f"agent-{i}",
                tenant_id=f"tenant-{i % 3}",
                content=f"memory-{i}",
            )
            for i in range(10)
        ]
        
        records = await asyncio.gather(*tasks)
        assert len(records) == 10
        assert redis_mock.set.call_count == 10

    def test_memory_record_timestamp_reasonable(self):
        """Test that timestamps are reasonable."""
        now = int(datetime.now().timestamp())
        record = MemoryRecord()
        
        # Timestamp should be within 1 second of now
        assert abs(record.timestamp - now) < 2

    @pytest.mark.asyncio
    async def test_enqueue_and_process_promotion_batch(self):
        """Test that promotion batch processing works."""
        postgres_mock = AsyncMock()
        policy = TierPromotionPolicy(batch_size=5)
        
        manager = MemoryManager(
            postgres_client=postgres_mock,
            policy=policy,
        )
        
        # Create memory records and process batch directly
        records = [
            MemoryRecord(
                id=str(i),
                tenant_id="tenant-1",
                current_tier=TierLevel.SHORT,
                conversation_id=str(uuid4()),
                agent_id=str(uuid4()),
                access_count=5,
            )
            for i in range(3)
        ]
        
        # Add to promotion queue directly
        manager._promotion_queue.extend(records)
        
        # Process should clear the queue after processing
        await manager._process_promotion_batch()
        
        # Queue should be emptied
        assert len(manager._promotion_queue) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
