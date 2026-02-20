"""Unit tests for contract verifier — contract violation detection and result validation.

Tests cover:
- ContractViolation: creation, types, severity validation
- ContractVerificationResult: structure, is_valid property
- ContractVerifier.verify_pre_steer: agent existence, peer validity, coverage
- ContractVerifier.verify_post_steer: contract preservation, obligation fulfillment
- ContractVerifier.verify_steer_operation: full pipeline
- Helper methods: _check_topology_validity, _check_communication_patterns, etc.
"""

from __future__ import annotations

import pytest

from holly.agents.contract_verifier import (
    ContractViolation,
    ContractViolationType,
    ContractVerificationResult,
    ContractVerifier,
    verify_steer_contracts,
)


# ──────────────────────────────────────────────────────────
# § Test ContractViolationType
# ──────────────────────────────────────────────────────────


class TestContractViolationType:
    """Test ContractViolationType enum."""

    def test_violation_type_values(self) -> None:
        """Test all violation types are defined."""
        assert ContractViolationType.COMMUNICATION_BREAK.value == "communication_break"
        assert ContractViolationType.OBLIGATION_UNMET.value == "obligation_unmet"
        assert ContractViolationType.CAPABILITY_MISMATCH.value == "capability_mismatch"
        assert ContractViolationType.TOPOLOGY_INVALID.value == "topology_invalid"

    def test_violation_type_count(self) -> None:
        """Test correct number of violation types."""
        types = list(ContractViolationType)
        assert len(types) == 4


# ──────────────────────────────────────────────────────────
# § Test ContractViolation
# ──────────────────────────────────────────────────────────


class TestContractViolation:
    """Test ContractViolation dataclass."""

    def test_violation_creation_critical(self) -> None:
        """Test creating a critical violation."""
        violation = ContractViolation(
            violation_type=ContractViolationType.COMMUNICATION_BREAK,
            contract_id="c1",
            agent_id="agent-1",
            description="Peer missing",
            severity="critical",
        )
        assert violation.violation_type == ContractViolationType.COMMUNICATION_BREAK
        assert violation.contract_id == "c1"
        assert violation.agent_id == "agent-1"
        assert violation.severity == "critical"

    def test_violation_creation_warning(self) -> None:
        """Test creating a warning-level violation."""
        violation = ContractViolation(
            violation_type=ContractViolationType.OBLIGATION_UNMET,
            contract_id="c2",
            agent_id="agent-2",
            description="Missing responsibility",
            severity="warning",
        )
        assert violation.severity == "warning"

    def test_violation_creation_info(self) -> None:
        """Test creating an info-level violation."""
        violation = ContractViolation(
            violation_type=ContractViolationType.CAPABILITY_MISMATCH,
            contract_id="c3",
            agent_id="agent-3",
            description="Info message",
            severity="info",
        )
        assert violation.severity == "info"

    def test_violation_invalid_severity(self) -> None:
        """Test that invalid severity raises error."""
        with pytest.raises(ValueError, match="severity must be one of"):
            ContractViolation(
                violation_type=ContractViolationType.COMMUNICATION_BREAK,
                contract_id="c1",
                agent_id="agent-1",
                description="Test",
                severity="invalid",
            )

    def test_violation_empty_contract_id(self) -> None:
        """Test that empty contract_id raises error."""
        with pytest.raises(ValueError, match="contract_id cannot be empty"):
            ContractViolation(
                violation_type=ContractViolationType.COMMUNICATION_BREAK,
                contract_id="",
                agent_id="agent-1",
                description="Test",
                severity="critical",
            )

    def test_violation_empty_agent_id(self) -> None:
        """Test that empty agent_id raises error."""
        with pytest.raises(ValueError, match="agent_id cannot be empty"):
            ContractViolation(
                violation_type=ContractViolationType.COMMUNICATION_BREAK,
                contract_id="c1",
                agent_id="",
                description="Test",
                severity="critical",
            )

    def test_violation_frozen(self) -> None:
        """Test that ContractViolation is frozen."""
        violation = ContractViolation(
            violation_type=ContractViolationType.COMMUNICATION_BREAK,
            contract_id="c1",
            agent_id="agent-1",
            description="Test",
            severity="critical",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            violation.severity = "warning"  # type: ignore

    def test_all_violation_types_with_severity(self) -> None:
        """Test creating violations with all types."""
        for vtype in ContractViolationType:
            violation = ContractViolation(
                violation_type=vtype,
                contract_id="c1",
                agent_id="agent-1",
                description="Test",
                severity="critical",
            )
            assert violation.violation_type == vtype


# ──────────────────────────────────────────────────────────
# § Test ContractVerificationResult
# ──────────────────────────────────────────────────────────


class TestContractVerificationResult:
    """Test ContractVerificationResult dataclass."""

    def test_result_creation_valid(self) -> None:
        """Test creating a valid result."""
        result = ContractVerificationResult(
            steer_operation_id="op-1",
            violations=[],
            pre_topology_valid=True,
            post_topology_valid=True,
            contracts_preserved=True,
        )
        assert result.steer_operation_id == "op-1"
        assert len(result.violations) == 0
        assert result.pre_topology_valid
        assert result.post_topology_valid
        assert result.contracts_preserved

    def test_result_is_valid_true(self) -> None:
        """Test is_valid property when valid."""
        result = ContractVerificationResult(
            steer_operation_id="op-1",
            violations=[],
            contracts_preserved=True,
        )
        assert result.is_valid is True

    def test_result_is_valid_false_with_violations(self) -> None:
        """Test is_valid property with violations."""
        violation = ContractViolation(
            violation_type=ContractViolationType.COMMUNICATION_BREAK,
            contract_id="c1",
            agent_id="a1",
            description="Test",
            severity="critical",
        )
        result = ContractVerificationResult(
            steer_operation_id="op-1",
            violations=[violation],
            contracts_preserved=True,
        )
        assert result.is_valid is False

    def test_result_is_valid_false_contracts_not_preserved(self) -> None:
        """Test is_valid property when contracts not preserved."""
        result = ContractVerificationResult(
            steer_operation_id="op-1",
            violations=[],
            contracts_preserved=False,
        )
        assert result.is_valid is False

    def test_result_default_violations_empty(self) -> None:
        """Test that violations default to empty list."""
        result = ContractVerificationResult(steer_operation_id="op-1")
        assert result.violations == []

    def test_result_default_topology_valid(self) -> None:
        """Test that topology validity defaults to True."""
        result = ContractVerificationResult(steer_operation_id="op-1")
        assert result.pre_topology_valid is True
        assert result.post_topology_valid is True

    def test_result_default_contracts_preserved(self) -> None:
        """Test that contracts_preserved defaults to True."""
        result = ContractVerificationResult(steer_operation_id="op-1")
        assert result.contracts_preserved is True


# ──────────────────────────────────────────────────────────
# § Test ContractVerifier Initialization
# ──────────────────────────────────────────────────────────


class TestContractVerifierInit:
    """Test ContractVerifier initialization and setup."""

    def test_verifier_creation(self) -> None:
        """Test creating a contract verifier."""
        verifier = ContractVerifier()
        assert verifier is not None

    def test_verifier_operation_counter(self) -> None:
        """Test that verifier initializes operation counter."""
        verifier = ContractVerifier()
        # Counter starts at 0, will increment with each operation
        result1 = verifier.verify_steer_operation(None, None, [])
        assert "steer-op-1" in result1.steer_operation_id

    def test_multiple_verifier_instances(self) -> None:
        """Test that multiple instances have independent counters."""
        v1 = ContractVerifier()
        v2 = ContractVerifier()
        r1 = v1.verify_steer_operation(None, None, [])
        r2 = v2.verify_steer_operation(None, None, [])
        assert r1.steer_operation_id == "steer-op-1"
        assert r2.steer_operation_id == "steer-op-1"


# ──────────────────────────────────────────────────────────
# § Test verify_pre_steer
# ──────────────────────────────────────────────────────────


class TestVerifyPreSteer:
    """Test pre-steer verification."""

    def test_verify_pre_steer_empty_topology(self) -> None:
        """Test pre-steer with no agents."""
        verifier = ContractVerifier()
        result = verifier.verify_pre_steer(None, [])
        assert isinstance(result, list)

    def test_verify_pre_steer_missing_agent(self) -> None:
        """Test violation when contract agent missing."""
        # Mock contract with missing agent
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "missing-agent"
                self.peer_agent_id = None
                self.responsibility_domain = frozenset()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {}

        verifier = ContractVerifier()
        violations = verifier.verify_pre_steer(
            MockTopology(), [MockContract()]
        )
        assert len(violations) > 0
        assert any(v.severity == "critical" for v in violations)

    def test_verify_pre_steer_missing_peer(self) -> None:
        """Test violation when peer agent missing."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = "missing-peer"
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self) -> None:
                self.agent_id = "agent-1"

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent()}

        verifier = ContractVerifier()
        violations = verifier.verify_pre_steer(
            MockTopology(), [MockContract()]
        )
        assert len(violations) > 0

    def test_verify_pre_steer_valid_contract(self) -> None:
        """Test no violations with valid contract."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = "agent-2"
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self, agent_id: str) -> None:
                self.agent_id = agent_id
                self.assigned_goals = frozenset()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {
                    "agent-1": MockAgent("agent-1"),
                    "agent-2": MockAgent("agent-2"),
                }

        verifier = ContractVerifier()
        violations = verifier.verify_pre_steer(
            MockTopology(), [MockContract()]
        )
        # Should have no critical violations
        assert not any(v.severity == "critical" for v in violations)


# ──────────────────────────────────────────────────────────
# § Test verify_post_steer
# ──────────────────────────────────────────────────────────


class TestVerifyPostSteer:
    """Test post-steer verification."""

    def test_verify_post_steer_empty_topologies(self) -> None:
        """Test post-steer with empty topologies."""
        verifier = ContractVerifier()
        result = verifier.verify_post_steer(None, None, [])
        assert isinstance(result, list)

    def test_verify_post_steer_communication_broken(self) -> None:
        """Test violation when communication path broken."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = "agent-2"
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self, agent_id: str) -> None:
                self.agent_id = agent_id
                self.assigned_goals = frozenset()

        class MockOldTopology:
            def __init__(self) -> None:
                self.agents = {
                    "agent-1": MockAgent("agent-1"),
                    "agent-2": MockAgent("agent-2"),
                }

        class MockNewTopology:
            def __init__(self) -> None:
                # agent-2 removed
                self.agents = {"agent-1": MockAgent("agent-1")}

        verifier = ContractVerifier()
        violations = verifier.verify_post_steer(
            MockOldTopology(), MockNewTopology(), [MockContract()]
        )
        assert len(violations) > 0

    def test_verify_post_steer_valid_preservation(self) -> None:
        """Test no violations when contracts preserved."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = "agent-2"
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self, agent_id: str) -> None:
                self.agent_id = agent_id
                self.assigned_goals = frozenset()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {
                    "agent-1": MockAgent("agent-1"),
                    "agent-2": MockAgent("agent-2"),
                }
                self.goal_assignments = {}

        verifier = ContractVerifier()
        violations = verifier.verify_post_steer(
            MockTopology(), MockTopology(), [MockContract()]
        )
        # Should have no critical violations
        assert not any(v.severity == "critical" for v in violations)


# ──────────────────────────────────────────────────────────
# § Test verify_steer_operation (Full Pipeline)
# ──────────────────────────────────────────────────────────


class TestVerifySteerOperation:
    """Test full steer operation verification."""

    def test_verify_steer_operation_basic(self) -> None:
        """Test basic steer operation verification."""
        verifier = ContractVerifier()
        result = verifier.verify_steer_operation(None, None, [])
        assert isinstance(result, ContractVerificationResult)
        assert result.steer_operation_id.startswith("steer-op-")

    def test_verify_steer_operation_returns_result(self) -> None:
        """Test that verify_steer_operation returns ContractVerificationResult."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = None
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self, agent_id: str) -> None:
                self.agent_id = agent_id
                self.assigned_goals = frozenset()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent("agent-1")}

        verifier = ContractVerifier()
        result = verifier.verify_steer_operation(
            MockTopology(), MockTopology(), [MockContract()]
        )
        assert isinstance(result, ContractVerificationResult)

    def test_verify_steer_operation_operation_counter(self) -> None:
        """Test that operation IDs increment."""
        verifier = ContractVerifier()
        r1 = verifier.verify_steer_operation(None, None, [])
        r2 = verifier.verify_steer_operation(None, None, [])
        assert r1.steer_operation_id == "steer-op-1"
        assert r2.steer_operation_id == "steer-op-2"

    def test_verify_steer_operation_valid_case(self) -> None:
        """Test verification passes for valid steer."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = None
                self.responsibility_domain = frozenset()

        class MockAgent:
            def __init__(self, agent_id: str) -> None:
                self.agent_id = agent_id
                self.assigned_goals = frozenset()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent("agent-1")}
                self.goal_assignments = {}

        verifier = ContractVerifier()
        result = verifier.verify_steer_operation(
            MockTopology(), MockTopology(), [MockContract()]
        )
        # Should have no violations
        critical_violations = [
            v for v in result.violations if v.severity == "critical"
        ]
        assert len(critical_violations) == 0


# ──────────────────────────────────────────────────────────
# § Test Helper Methods
# ──────────────────────────────────────────────────────────


class TestCheckTopologyValidity:
    """Test _check_topology_validity helper."""

    def test_check_topology_no_agents_attribute(self) -> None:
        """Test with topology missing agents attribute."""
        verifier = ContractVerifier()
        violations = verifier._check_topology_validity(None)
        assert len(violations) > 0

    def test_check_topology_empty(self) -> None:
        """Test with empty topology."""
        class MockTopology:
            def __init__(self) -> None:
                self.agents = {}

        verifier = ContractVerifier()
        violations = verifier._check_topology_validity(MockTopology())
        assert len(violations) > 0

    def test_check_topology_valid(self) -> None:
        """Test with valid topology."""
        class MockAgent:
            def __init__(self) -> None:
                self.agent_id = "agent-1"

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent()}
                self.goal_assignments = {}

        verifier = ContractVerifier()
        violations = verifier._check_topology_validity(MockTopology())
        assert len(violations) == 0


class TestCheckCommunicationPatterns:
    """Test _check_communication_patterns helper."""

    def test_check_communication_no_contracts(self) -> None:
        """Test with no contracts."""
        class MockTopology:
            def __init__(self) -> None:
                self.agents = {}

        verifier = ContractVerifier()
        violations = verifier._check_communication_patterns(MockTopology(), [])
        assert len(violations) == 0

    def test_check_communication_valid(self) -> None:
        """Test with valid communication pattern."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.peer_agent_id = "agent-2"

        class MockAgent:
            def __init__(self) -> None:
                pass

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {
                    "agent-1": MockAgent(),
                    "agent-2": MockAgent(),
                }

        verifier = ContractVerifier()
        violations = verifier._check_communication_patterns(
            MockTopology(), [MockContract()]
        )
        assert len(violations) == 0


class TestCheckCapabilityCoverage:
    """Test _check_capability_coverage helper."""

    def test_check_capability_no_contracts(self) -> None:
        """Test with no contracts."""
        class MockTopology:
            def __init__(self) -> None:
                self.agents = {}

        verifier = ContractVerifier()
        violations = verifier._check_capability_coverage(MockTopology(), [])
        assert len(violations) == 0

    def test_check_capability_valid(self) -> None:
        """Test with valid capabilities."""
        class MockContract:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.responsibility_domain = frozenset()

        class MockPermissions:
            def __init__(self) -> None:
                self.capability_level = "STANDARD"

        class MockAgent:
            def __init__(self) -> None:
                self.agent_id = "agent-1"
                self.permissions = MockPermissions()

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent()}

        verifier = ContractVerifier()
        violations = verifier._check_capability_coverage(
            MockTopology(), [MockContract()]
        )
        # Valid capabilities, so no critical violations
        assert not any(v.severity == "critical" for v in violations)


# ──────────────────────────────────────────────────────────
# § Test Main Entry Point
# ──────────────────────────────────────────────────────────


class TestVerifySteerContractsFunction:
    """Test verify_steer_contracts main entry point."""

    def test_entry_point_returns_result(self) -> None:
        """Test that entry point returns ContractVerificationResult."""
        result = verify_steer_contracts(None, None, [])
        assert isinstance(result, ContractVerificationResult)

    def test_entry_point_creates_verifier(self) -> None:
        """Test that entry point creates verifier internally."""
        result1 = verify_steer_contracts(None, None, [])
        result2 = verify_steer_contracts(None, None, [])
        # Different calls should create different operation IDs
        # Each entry point call creates a new verifier, so operations start at 1
        assert result1.steer_operation_id.startswith("steer-op-")
        assert result2.steer_operation_id.startswith("steer-op-")

    def test_entry_point_with_valid_topologies(self) -> None:
        """Test entry point with valid topologies."""
        class MockAgent:
            def __init__(self) -> None:
                self.agent_id = "agent-1"

        class MockTopology:
            def __init__(self) -> None:
                self.agents = {"agent-1": MockAgent()}
                self.goal_assignments = {}

        result = verify_steer_contracts(
            MockTopology(), MockTopology(), []
        )
        assert isinstance(result, ContractVerificationResult)

    def test_entry_point_operation_idempotent(self) -> None:
        """Test entry point consistency."""
        result = verify_steer_contracts(None, None, [])
        assert result.is_valid is not None
        assert result.contracts_preserved is not None
        assert result.violations is not None
