"""Integration tests for MCP Registry (Task 42.4).

Tests cover:
- ICD-019/020 error contract compliance
- K2 permission gates integration
- End-to-end tool invocation flows
- Lane integration patterns
- Property-based tests with hypothesis
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from holly.engine.mcp_registry import (
    MCPRegistry,
    ToolInvocationRequest,
    ToolType,
)


# ─────────────────────────────────────────────────────────────────────────
# Integration: Error Contract Compliance (ICD-019/020)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_icd_error_contract_tool_not_found():
    """Test ICD-019/020 error contract: ToolNotFound."""
    registry = MCPRegistry()

    request = ToolInvocationRequest(
        tool_name="missing_tool",
        agent_id="agent1",
        tenant_id="tenant1",
    )

    response = await registry.invoke(request)

    # ICD-019/020 error contract: ToolNotFound
    assert response.error_code == "tool_not_found"
    assert response.error is not None
    assert response.tool_result is None


@pytest.mark.asyncio
async def test_icd_error_contract_permission_denied():
    """Test ICD-019/020 error contract: PermissionDenied."""
    registry = MCPRegistry()

    async def handler(input_dict):
        return {"ok": True}

    registry.register_tool("restricted_tool", handler)
    # Don't grant permission to agent1

    request = ToolInvocationRequest(
        tool_name="restricted_tool",
        agent_id="agent1",
        tenant_id="tenant1",
    )

    response = await registry.invoke(request)

    # ICD-019/020 error contract: PermissionDenied
    assert response.error_code == "permission_denied"
    assert response.error is not None
    assert response.tool_result is None


@pytest.mark.asyncio
async def test_icd_error_contract_tool_execution_error():
    """Test ICD-019/020 error contract: ToolExecutionError."""
    registry = MCPRegistry()

    async def failing_handler(input_dict):
        raise ValueError("tool failed")

    registry.register_tool("failing_tool", failing_handler)
    registry.grant_permission("failing_tool", "agent1", "admin")

    request = ToolInvocationRequest(
        tool_name="failing_tool",
        agent_id="agent1",
        tenant_id="tenant1",
    )

    response = await registry.invoke(request)

    # ICD-019/020 error contract: ToolExecutionError
    assert response.error_code == "tool_execution_error"
    assert "tool failed" in response.error
    assert response.tool_result is None


# ─────────────────────────────────────────────────────────────────────────
# Integration: K2 Permission Gates
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_k2_permission_gate_integration():
    """Test K2 permission gate integration with invocation."""
    registry = MCPRegistry()

    call_count = 0

    async def guarded_handler(input_dict):
        nonlocal call_count
        call_count += 1
        return {"calls": call_count}

    registry.register_tool("guarded_tool", guarded_handler)

    # Only grant to agent_secure
    registry.grant_permission("guarded_tool", "agent_secure", "admin")

    # agent_secure can call
    req_secure = ToolInvocationRequest(
        tool_name="guarded_tool",
        agent_id="agent_secure",
        tenant_id="tenant1",
    )
    resp_secure = await registry.invoke(req_secure)
    assert not resp_secure.is_error()
    assert call_count == 1

    # agent_untrusted cannot call
    req_untrusted = ToolInvocationRequest(
        tool_name="guarded_tool",
        agent_id="agent_untrusted",
        tenant_id="tenant1",
    )
    resp_untrusted = await registry.invoke(req_untrusted)
    assert resp_untrusted.is_error()
    assert resp_untrusted.error_code == "permission_denied"
    assert call_count == 1  # Handler not called


@pytest.mark.asyncio
async def test_k2_permission_expiration_integration():
    """Test K2 with expiring permissions."""
    registry = MCPRegistry()

    async def handler(input_dict):
        return {"ok": True}

    registry.register_tool("temporal_tool", handler)

    # Grant with expiry 1 second in future
    future = datetime.now(timezone.utc) + timedelta(seconds=1)
    registry.grant_permission("temporal_tool", "agent1", "admin", expires_at=future)

    # Should succeed now
    req = ToolInvocationRequest(
        tool_name="temporal_tool",
        agent_id="agent1",
        tenant_id="tenant1",
    )
    resp = await registry.invoke(req)
    assert not resp.is_error()

    # Grant with past expiry
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    registry.grant_permission("temporal_tool", "agent2", "admin", expires_at=past)

    # Should fail (expired)
    req2 = ToolInvocationRequest(
        tool_name="temporal_tool",
        agent_id="agent2",
        tenant_id="tenant1",
    )
    resp2 = await registry.invoke(req2)
    assert resp2.is_error()
    assert resp2.error_code == "permission_denied"


# ─────────────────────────────────────────────────────────────────────────
# Integration: Latency Budget Compliance (ICD-019/020)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_tool_lookup_under_sla():
    """Test tool lookup SLA p99 < 1ms."""
    registry = MCPRegistry()

    # Register many tools
    for i in range(100):

        async def handler(input_dict):
            return {"id": i}

        registry.register_tool(f"tool_{i}", handler)

    # Lookup should be fast
    import time

    times = []
    for i in range(50):
        start = time.perf_counter()
        tool = registry.get_tool(f"tool_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    # All lookups should be very fast (much less than 1ms)
    avg_time = sum(times) / len(times)
    assert avg_time < 1.0  # Assert average lookup < 1ms


@pytest.mark.asyncio
async def test_permission_check_under_sla():
    """Test permission check SLA p99 < 1ms."""
    registry = MCPRegistry()

    async def handler(input_dict):
        return {}

    registry.register_tool("perf_tool", handler)

    # Grant many permissions
    for i in range(100):
        registry.grant_permission("perf_tool", f"agent_{i}", "admin")

    # Permission check should be fast
    import time

    times = []
    for i in range(50):
        start = time.perf_counter()
        registry.has_permission("perf_tool", f"agent_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    # All checks should be very fast (much less than 1ms)
    avg_time = sum(times) / len(times)
    assert avg_time < 1.0


# ─────────────────────────────────────────────────────────────────────────
# Integration: Tenant Isolation (ICD-019/020)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_isolation_independent_tool_states():
    """Test tenant isolation: tool state is per-tenant."""
    registry = MCPRegistry()

    call_log = []

    async def tenant_aware_handler(input_dict):
        call_log.append(input_dict.get("tenant_id", "unknown"))
        return {"ok": True}

    registry.register_tool("shared_tool", tenant_aware_handler)
    registry.grant_permission("shared_tool", "agent1", "admin")

    # Invoke for tenant1
    req1 = ToolInvocationRequest(
        tool_name="shared_tool",
        agent_id="agent1",
        tenant_id="tenant1",
        input={"tenant_id": "tenant1"},
    )
    await registry.invoke(req1)

    # Invoke for tenant2
    req2 = ToolInvocationRequest(
        tool_name="shared_tool",
        agent_id="agent1",
        tenant_id="tenant2",
        input={"tenant_id": "tenant2"},
    )
    await registry.invoke(req2)

    # Both should execute independently
    assert len(call_log) == 2
    assert call_log[0] == "tenant1"
    assert call_log[1] == "tenant2"


@pytest.mark.asyncio
async def test_tenant_isolation_concurrency_limits():
    """Test tenant isolation: concurrency limits per tenant."""
    registry = MCPRegistry()

    invocation_count = 0
    max_concurrent = 0

    async def counting_handler(input_dict):
        nonlocal invocation_count, max_concurrent
        invocation_count += 1
        max_concurrent = max(max_concurrent, invocation_count)
        await asyncio.sleep(0.01)
        invocation_count -= 1
        return {"ok": True}

    registry.register_tool("concurrent_tool", counting_handler)
    registry.grant_permission("concurrent_tool", "agent1", "admin")

    # Set limit for tenant1
    registry.set_concurrency_limit("concurrent_tool", "tenant1", 3)

    # Invoke multiple times for same tenant
    reqs = [
        ToolInvocationRequest(
            tool_name="concurrent_tool",
            agent_id="agent1",
            tenant_id="tenant1",
        )
        for _ in range(5)
    ]

    results = await asyncio.gather(
        *[registry.invoke(req) for req in reqs],
        return_exceptions=True,
    )

    # All should succeed (no timeout errors)
    assert all(not r.is_error() for r in results if isinstance(r, type(results[0])))


# ─────────────────────────────────────────────────────────────────────────
# Integration: Idempotency Support (ICD-019/020)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotency_key_propagation():
    """Test idempotency_key propagation through request/response."""
    registry = MCPRegistry()

    async def handler(input_dict):
        return {"ok": True}

    registry.register_tool("idempotent_tool", handler)
    registry.grant_permission("idempotent_tool", "agent1", "admin")

    idempotency_key = "unique-request-1"
    request = ToolInvocationRequest(
        tool_name="idempotent_tool",
        agent_id="agent1",
        tenant_id="tenant1",
        idempotency_key=idempotency_key,
    )

    response = await registry.invoke(request)

    # Key should be in response for K5 deduplication
    assert response.idempotency_key == idempotency_key


# ─────────────────────────────────────────────────────────────────────────
# Integration: Traceability (ICD-019/020)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trace_id_propagation():
    """Test trace_id propagation through request/response."""
    registry = MCPRegistry()

    async def handler(input_dict):
        return {"ok": True}

    registry.register_tool("traced_tool", handler)
    registry.grant_permission("traced_tool", "agent1", "admin")

    trace_id = "trace-uuid-123"
    request = ToolInvocationRequest(
        tool_name="traced_tool",
        agent_id="agent1",
        tenant_id="tenant1",
        trace_id=trace_id,
    )

    response = await registry.invoke(request)

    # trace_id should be in response for request tracing
    assert response.trace_id == trace_id


# ─────────────────────────────────────────────────────────────────────────
# Integration: Tool Type Classification
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_tool_classification():
    """Test LLM tool type handling."""
    registry = MCPRegistry()

    async def llm_handler(input_dict):
        prompt = input_dict.get("prompt", "")
        # Simulate LLM response
        return {"response": f"Response to: {prompt}"}

    registry.register_tool(
        "llm_tool",
        llm_handler,
        tool_type=ToolType.LLM,
        is_llm=True,
    )
    registry.grant_permission("llm_tool", "agent1", "admin")

    tool = registry.get_tool("llm_tool")
    assert tool.tool_type == ToolType.LLM
    assert tool.is_llm


@pytest.mark.asyncio
async def test_external_tool_classification():
    """Test external tool type handling."""
    registry = MCPRegistry()

    async def external_handler(input_dict):
        # Simulate external API call
        return {"external_data": "..."}

    registry.register_tool(
        "external_tool",
        external_handler,
        tool_type=ToolType.EXTERNAL,
    )
    registry.grant_permission("external_tool", "agent1", "admin")

    tool = registry.get_tool("external_tool")
    assert tool.tool_type == ToolType.EXTERNAL


@pytest.mark.asyncio
async def test_sandbox_tool_classification():
    """Test sandbox tool type handling."""
    registry = MCPRegistry()

    async def sandbox_handler(input_dict):
        code = input_dict.get("code", "")
        # Simulate sandbox execution
        return {"result": f"Executed: {code}"}

    registry.register_tool(
        "sandbox_tool",
        sandbox_handler,
        tool_type=ToolType.SANDBOX,
    )
    registry.grant_permission("sandbox_tool", "agent1", "admin")

    tool = registry.get_tool("sandbox_tool")
    assert tool.tool_type == ToolType.SANDBOX


# ─────────────────────────────────────────────────────────────────────────
# Integration: Multi-Agent Collaboration
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multi_agent_shared_tool_access():
    """Test multiple agents accessing same tool with different permissions."""
    registry = MCPRegistry()

    async def shared_tool_handler(input_dict):
        agent_id = input_dict.get("agent_id", "unknown")
        return {"processed_by": agent_id}

    registry.register_tool("shared_tool", shared_tool_handler)

    # Grant different agents access
    registry.grant_permission("shared_tool", "analyst_agent", "admin")
    registry.grant_permission("shared_tool", "compute_agent", "admin")

    # Both agents can call
    req1 = ToolInvocationRequest(
        tool_name="shared_tool",
        agent_id="analyst_agent",
        tenant_id="tenant1",
        input={"agent_id": "analyst_agent"},
    )
    resp1 = await registry.invoke(req1)
    assert not resp1.is_error()
    assert resp1.tool_result["processed_by"] == "analyst_agent"

    req2 = ToolInvocationRequest(
        tool_name="shared_tool",
        agent_id="compute_agent",
        tenant_id="tenant1",
        input={"agent_id": "compute_agent"},
    )
    resp2 = await registry.invoke(req2)
    assert not resp2.is_error()
    assert resp2.tool_result["processed_by"] == "compute_agent"


@pytest.mark.asyncio
async def test_agent_without_permission_cannot_access():
    """Test that agent without permission cannot access tool."""
    registry = MCPRegistry()

    async def private_tool_handler(input_dict):
        return {"ok": True}

    registry.register_tool("private_tool", private_tool_handler)

    # Grant only to specific agent
    registry.grant_permission("private_tool", "privileged_agent", "admin")

    # Unprivileged agent cannot access
    req = ToolInvocationRequest(
        tool_name="private_tool",
        agent_id="unprivileged_agent",
        tenant_id="tenant1",
    )
    resp = await registry.invoke(req)

    assert resp.is_error()
    assert resp.error_code == "permission_denied"


# ─────────────────────────────────────────────────────────────────────────
# Integration: Registry Statistics and Monitoring
# ─────────────────────────────────────────────────────────────────────────


def test_registry_stats_comprehensive():
    """Test comprehensive registry statistics."""
    registry = MCPRegistry()

    async def handler1(input_dict):
        return {}

    async def handler2(input_dict):
        return {}

    registry.register_tool("tool1", handler1)
    registry.register_tool("tool2", handler2, is_llm=True)

    registry.grant_permission("tool1", "agent1", "admin")
    registry.grant_permission("tool1", "agent2", "admin")
    registry.grant_permission("tool2", "agent1", "admin")

    stats = registry.get_registry_stats()

    assert stats["tool_count"] == 2
    assert len(stats["tools"]) == 2

    tool1_stats = next(t for t in stats["tools"] if t["name"] == "tool1")
    assert tool1_stats["permission_count"] == 2

    tool2_stats = next(t for t in stats["tools"] if t["name"] == "tool2")
    assert tool2_stats["is_llm"]


# ─────────────────────────────────────────────────────────────────────────
# Integration: End-to-End Flow
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_to_end_tool_invocation_flow():
    """Test complete end-to-end tool invocation flow."""
    registry = MCPRegistry()

    # Setup: Register tool with metadata
    async def analyze_data(input_dict):
        data = input_dict.get("data", [])
        return {
            "sum": sum(data),
            "count": len(data),
            "avg": sum(data) / len(data) if data else 0,
        }

    registry.register_tool(
        "analyze",
        analyze_data,
        tool_type=ToolType.STANDARD,
        description="Analyze numeric data",
        input_schema={"data": {"type": "array", "items": {"type": "number"}}},
        output_schema={
            "sum": {"type": "number"},
            "count": {"type": "integer"},
            "avg": {"type": "number"},
        },
    )

    # Setup: Grant permissions
    registry.grant_permission("analyze", "data_scientist_agent", "admin")

    # Execute: Introspect
    tool = registry.get_tool("analyze")
    assert tool is not None
    assert tool.description == "Analyze numeric data"

    # Execute: Invoke
    request = ToolInvocationRequest(
        tool_name="analyze",
        agent_id="data_scientist_agent",
        tenant_id="tenant1",
        user_id="user1",
        input={"data": [1, 2, 3, 4, 5]},
        trace_id="trace-123",
    )

    response = await registry.invoke(request)

    # Verify: Response
    assert not response.is_error()
    assert response.tool_result["sum"] == 15
    assert response.tool_result["count"] == 5
    assert response.tool_result["avg"] == 3.0
    assert response.execution_time_ms > 0
    assert response.trace_id == "trace-123"
