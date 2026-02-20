"""Integration tests for steer verification — end-to-end steering with contract validation.

Tests cover:
- Full steer operation with valid topologies and contracts
- Contract preservation through steering operations
- Capability and obligation verification
- Real topology structures (from topology_manager)
- Multiple steer operations with contract chains
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
# § Integration Test Fixtures
# ──────────────────────────────────────────────────────────


class MockAgent:
    """Mock Agent for integration testing."""

    def __init__(
        self,
        agent_id: str,
        assigned_goals: frozenset[str] | None = None,
        parent_agent_id: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.assigned_goals = assigned_goals or frozenset()
        self.parent_agent_id = parent_agent_id
        self.contracts = frozenset()


class MockPermissions:
    """Mock Permissions for integration testing."""

    def __init__(
        self,
        agent_id: str,
        capability_level: str = "STANDARD",
    ) -> None:
        self.agent_id = agent_id
        self.capability_level = capability_level
        self.can_spawn = True
        self.can_steer = True
        self.can_dissolve = False
        self.max_concurrent_tasks = 5
        self.allowed_domains = frozenset(["goal", "coordination"])


class MockContract:
    """Mock Contract for integration testing."""

    def __init__(
        self,
        agent_id: str,
        peer_agent_id: str | None = None,
        expected_message_rate: float = 1.0,
        responsibility_domain: frozenset[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.peer_agent_id = peer_agent_id
        self.expected_message_rate = expected_message_rate
        self.responsibility_domain = responsibility_domain or frozenset()
        self.max_response_time_sec = 5.0
        self.escalation_threshold = 3


class MockTopology:
    """Mock TeamTopology for integration testing."""

    def __init__(self, topology_id: str) -> None:
        self.topology_id = topology_id
        self.agents: dict[str, MockAgent] = {}
        self.goal_assignments: dict[str, set[str]] = {}
        self.communication_matrix = None
        self.is_active = True

    def add_agent(self, agent: MockAgent) -> None:
        """Add an agent to topology."""
        self.agents[agent.agent_id] = agent

    def assign_goal(self, goal_id: str, agent_id: str) -> None:
        """Assign a goal to an agent."""
        if goal_id not in self.goal_assignments:
            self.goal_assignments[goal_id] = set()
        self.goal_assignments[goal_id].add(agent_id)


# ──────────────────────────────────────────────────────────
# § Test Simple Steer Operation
# ──────────────────────────────────────────────────────────


class TestSimpleSteering:
    """Test simple steering scenarios."""

    def test_steer_valid_single_agent(self) -> None:
        """Test steering with single agent topology."""
        # Create old topology
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        old_topo.add_agent(agent1)
        old_topo.assign_goal("goal-1", "agent-1")

        # Create new topology (same structure)
        new_topo = MockTopology("topo-2")
        agent2 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        new_topo.add_agent(agent2)
        new_topo.assign_goal("goal-1", "agent-1")

        # Contract with self-communication
        contract = MockContract("agent-1", peer_agent_id="agent-1")

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert result.is_valid
        assert len(result.violations) == 0
        assert result.contracts_preserved

    def test_steer_two_agent_topology(self) -> None:
        """Test steering with two-agent topology."""
        # Create old topology
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2 = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        old_topo.add_agent(agent1)
        old_topo.add_agent(agent2)
        old_topo.assign_goal("goal-1", "agent-1")
        old_topo.assign_goal("goal-2", "agent-2")

        # Create new topology (same structure)
        new_topo = MockTopology("topo-2")
        agent3 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent4 = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        new_topo.add_agent(agent3)
        new_topo.add_agent(agent4)
        new_topo.assign_goal("goal-1", "agent-1")
        new_topo.assign_goal("goal-2", "agent-2")

        # Contracts
        contracts = [
            MockContract("agent-1", peer_agent_id="agent-2"),
            MockContract("agent-2", peer_agent_id="agent-1"),
        ]

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, contracts)
        assert len(result.violations) == 0


# ──────────────────────────────────────────────────────────
# § Test Steer with Contract Violation
# ──────────────────────────────────────────────────────────


class TestSteeringViolations:
    """Test steering scenarios with contract violations."""

    def test_steer_peer_removed(self) -> None:
        """Test violation when peer agent is removed."""
        # Create old topology with two agents
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2 = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        old_topo.add_agent(agent1)
        old_topo.add_agent(agent2)

        # Create new topology with only agent-1
        new_topo = MockTopology("topo-2")
        agent3 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        new_topo.add_agent(agent3)

        # Contract requires peer that no longer exists
        contract = MockContract("agent-1", peer_agent_id="agent-2")

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert not result.is_valid
        assert len(result.violations) > 0
        assert any(v.severity == "critical" for v in result.violations)

    def test_steer_goal_unassigned(self) -> None:
        """Test violation when goal becomes unassigned."""
        # Create old topology
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        old_topo.add_agent(agent1)
        old_topo.assign_goal("goal-1", "agent-1")

        # Create new topology with agent but no goal assignment
        new_topo = MockTopology("topo-2")
        agent2 = MockAgent("agent-1", assigned_goals=frozenset())
        new_topo.add_agent(agent2)

        # Contract with responsibility domain
        contract = MockContract(
            "agent-1",
            peer_agent_id=None,
            responsibility_domain=frozenset(["goal-1"]),
        )

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, [contract])
        # Should detect obligation unmet
        assert any(
            v.violation_type == ContractViolationType.OBLIGATION_UNMET
            for v in result.violations
        )


# ──────────────────────────────────────────────────────────
# § Test Multi-Agent Steering
# ──────────────────────────────────────────────────────────


class TestMultiAgentSteering:
    """Test steering with multiple agents."""

    def test_steer_three_agent_chain(self) -> None:
        """Test steering with three-agent communication chain."""
        # Old topology: agent-1 -> agent-2 -> agent-3
        old_topo = MockTopology("topo-1")
        for i in range(1, 4):
            agent = MockAgent(f"agent-{i}", assigned_goals=frozenset([f"goal-{i}"]))
            old_topo.add_agent(agent)
            old_topo.assign_goal(f"goal-{i}", f"agent-{i}")

        # New topology: same structure
        new_topo = MockTopology("topo-2")
        for i in range(1, 4):
            agent = MockAgent(f"agent-{i}", assigned_goals=frozenset([f"goal-{i}"]))
            new_topo.add_agent(agent)
            new_topo.assign_goal(f"goal-{i}", f"agent-{i}")

        # Communication chain contracts
        contracts = [
            MockContract("agent-1", peer_agent_id="agent-2"),
            MockContract("agent-2", peer_agent_id="agent-3"),
        ]

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, contracts)
        assert result.is_valid
        assert len(result.violations) == 0

    def test_steer_mesh_topology(self) -> None:
        """Test steering with fully connected mesh of agents."""
        agent_count = 3

        # Create old topology
        old_topo = MockTopology("topo-1")
        for i in range(1, agent_count + 1):
            agent = MockAgent(f"agent-{i}", assigned_goals=frozenset([f"goal-{i}"]))
            old_topo.add_agent(agent)

        # Create new topology
        new_topo = MockTopology("topo-2")
        for i in range(1, agent_count + 1):
            agent = MockAgent(f"agent-{i}", assigned_goals=frozenset([f"goal-{i}"]))
            new_topo.add_agent(agent)

        # Full mesh contracts
        contracts = []
        for i in range(1, agent_count + 1):
            for j in range(1, agent_count + 1):
                if i != j:
                    contracts.append(
                        MockContract(f"agent-{i}", peer_agent_id=f"agent-{j}")
                    )

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, contracts)
        assert len(result.violations) == 0


# ──────────────────────────────────────────────────────────
# § Test Steer with Goal Reassignment
# ──────────────────────────────────────────────────────────


class TestGoalReassignment:
    """Test steering with goal reassignment between agents."""

    def test_steer_reassign_single_goal(self) -> None:
        """Test reassigning a single goal to different agent."""
        # Old topology: agent-1 has goal-1, agent-2 has goal-2
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2 = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        old_topo.add_agent(agent1)
        old_topo.add_agent(agent2)
        old_topo.assign_goal("goal-1", "agent-1")
        old_topo.assign_goal("goal-2", "agent-2")

        # New topology: agent-2 takes goal-1
        new_topo = MockTopology("topo-2")
        agent3 = MockAgent("agent-1", assigned_goals=frozenset())
        agent4 = MockAgent("agent-2", assigned_goals=frozenset(["goal-1", "goal-2"]))
        new_topo.add_agent(agent3)
        new_topo.add_agent(agent4)
        new_topo.assign_goal("goal-1", "agent-2")
        new_topo.assign_goal("goal-2", "agent-2")

        # Contracts
        contracts = [
            MockContract(
                "agent-1",
                responsibility_domain=frozenset(["goal-1"]),
            ),
            MockContract(
                "agent-2",
                responsibility_domain=frozenset(["goal-2"]),
            ),
        ]

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, contracts)
        # May have warnings about agent-1 losing responsibility
        assert result.steer_operation_id is not None

    def test_steer_redistribute_goals(self) -> None:
        """Test redistributing goals across agents."""
        # Old topology: agent-1 has [goal-1, goal-2, goal-3]
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent(
            "agent-1", assigned_goals=frozenset(["goal-1", "goal-2", "goal-3"])
        )
        old_topo.add_agent(agent1)
        for goal_id in ["goal-1", "goal-2", "goal-3"]:
            old_topo.assign_goal(goal_id, "agent-1")

        # New topology: goals split between agent-1, agent-2, agent-3
        new_topo = MockTopology("topo-2")
        agent2 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent3 = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        agent4 = MockAgent("agent-3", assigned_goals=frozenset(["goal-3"]))
        new_topo.add_agent(agent2)
        new_topo.add_agent(agent3)
        new_topo.add_agent(agent4)
        new_topo.assign_goal("goal-1", "agent-1")
        new_topo.assign_goal("goal-2", "agent-2")
        new_topo.assign_goal("goal-3", "agent-3")

        # Contract for original agent
        contract = MockContract(
            "agent-1",
            responsibility_domain=frozenset(["goal-1", "goal-2", "goal-3"]),
        )

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert result.steer_operation_id is not None


# ──────────────────────────────────────────────────────────
# § Test Sequential Steer Operations
# ──────────────────────────────────────────────────────────


class TestSequentialSteering:
    """Test multiple steer operations in sequence."""

    def test_two_step_steer(self) -> None:
        """Test verifying two sequential steer operations."""
        # Initial topology
        topo1 = MockTopology("topo-1")
        agent1a = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2a = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        topo1.add_agent(agent1a)
        topo1.add_agent(agent2a)
        topo1.assign_goal("goal-1", "agent-1")
        topo1.assign_goal("goal-2", "agent-2")

        # First steer: consolidate to single agent
        topo2 = MockTopology("topo-2")
        agent1b = MockAgent("agent-1", assigned_goals=frozenset(["goal-1", "goal-2"]))
        topo2.add_agent(agent1b)
        topo2.assign_goal("goal-1", "agent-1")
        topo2.assign_goal("goal-2", "agent-1")

        # Second steer: expand back out
        topo3 = MockTopology("topo-3")
        agent1c = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2c = MockAgent("agent-2", assigned_goals=frozenset(["goal-2"]))
        topo3.add_agent(agent1c)
        topo3.add_agent(agent2c)
        topo3.assign_goal("goal-1", "agent-1")
        topo3.assign_goal("goal-2", "agent-2")

        contracts = [
            MockContract("agent-1", peer_agent_id="agent-2"),
            MockContract("agent-2", peer_agent_id="agent-1"),
        ]

        # Verify first steer
        result1 = verify_steer_contracts(topo1, topo2, contracts)
        assert result1.steer_operation_id.startswith("steer-op-")

        # Verify second steer
        result2 = verify_steer_contracts(topo2, topo3, contracts)
        assert result2.steer_operation_id.startswith("steer-op-")

        # Both results should be valid for the steer operations
        assert result1.steer_operation_id is not None
        assert result2.steer_operation_id is not None


# ──────────────────────────────────────────────────────────
# § Test Capability Preservation
# ──────────────────────────────────────────────────────────


class TestCapabilityPreservation:
    """Test that steering preserves agent capabilities."""

    def test_steer_preserves_capability(self) -> None:
        """Test that agent capability levels are preserved."""
        # Create topologies with agent permissions
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent1.permissions = MockPermissions("agent-1", capability_level="LEAD")
        old_topo.add_agent(agent1)
        old_topo.assign_goal("goal-1", "agent-1")

        new_topo = MockTopology("topo-2")
        agent2 = MockAgent("agent-1", assigned_goals=frozenset(["goal-1"]))
        agent2.permissions = MockPermissions("agent-1", capability_level="LEAD")
        new_topo.add_agent(agent2)
        new_topo.assign_goal("goal-1", "agent-1")

        contract = MockContract("agent-1")

        # Verify
        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert len(result.violations) == 0


# ──────────────────────────────────────────────────────────
# § Test Broadcast Contracts
# ──────────────────────────────────────────────────────────


class TestBroadcastContracts:
    """Test steering with broadcast contracts."""

    def test_broadcast_contract_valid(self) -> None:
        """Test broadcast contract (peer_agent_id=None) is valid."""
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1")
        old_topo.add_agent(agent1)

        new_topo = MockTopology("topo-2")
        agent2 = MockAgent("agent-1")
        new_topo.add_agent(agent2)

        # Broadcast contract
        contract = MockContract("agent-1", peer_agent_id=None)

        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert len(result.violations) == 0

    def test_broadcast_contract_agent_removed(self) -> None:
        """Test violation when broadcast agent is removed."""
        old_topo = MockTopology("topo-1")
        agent1 = MockAgent("agent-1")
        old_topo.add_agent(agent1)

        new_topo = MockTopology("topo-2")  # Empty

        # Broadcast contract
        contract = MockContract("agent-1", peer_agent_id=None)

        result = verify_steer_contracts(old_topo, new_topo, [contract])
        assert len(result.violations) > 0
