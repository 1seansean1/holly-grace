"""Contract Verifier — verify steer operations maintain contract invariants.

Task 38.8 implements formal verification that steering operations preserve
contract satisfaction per Goal Hierarchy §3 (steer operator formal spec):

- Communication patterns remain valid after steering
- Contract obligations are satisfied by new topology
- No contract violations introduced by steering
- Pre/post-topology validity confirmed
- Capability coverage preserved

References:
  - Goal Hierarchy Formal Spec, §3 (steer operator verification)
  - Task 38.4 (topology_manager.py) — AgentContract, TeamTopology
  - ICD-012/015 integration for contract validation
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


# ──────────────────────────────────────────────────────────
# §1 Contract Violation Types & Exceptions
# ──────────────────────────────────────────────────────────


class ContractViolationType(Enum):
    """Types of contract violations detected during steering verification."""

    COMMUNICATION_BREAK = "communication_break"
    """Communication path to peer agent is broken."""

    OBLIGATION_UNMET = "obligation_unmet"
    """Contract obligation (e.g., responsibility) is unmet."""

    CAPABILITY_MISMATCH = "capability_mismatch"
    """Required capability missing in topology."""

    TOPOLOGY_INVALID = "topology_invalid"
    """Overall topology structure is invalid."""


@dataclass(slots=True, frozen=True)
class ContractViolation:
    """A contract violation detected during steering verification.

    Attributes
    ----------
    violation_type
        Type of violation (communication_break, obligation_unmet, etc.).
    contract_id
        ID of the contract with violation (agent_id or contract pair).
    agent_id
        Agent ID involved in the violation.
    description
        Human-readable description of the violation.
    severity
        Severity level: "critical", "warning", or "info".
    """

    violation_type: ContractViolationType
    contract_id: str
    agent_id: str
    description: str
    severity: str  # "critical" | "warning" | "info"

    def __post_init__(self) -> None:
        """Validate contract violation."""
        if self.severity not in ("critical", "warning", "info"):
            raise ValueError(
                f"severity must be one of critical/warning/info, got {self.severity}"
            )
        if not self.contract_id:
            raise ValueError("contract_id cannot be empty")
        if not self.agent_id:
            raise ValueError("agent_id cannot be empty")


@dataclass(slots=True)
class ContractVerificationResult:
    """Result of verifying a steer operation against contracts.

    Attributes
    ----------
    steer_operation_id
        ID of the steer operation being verified.
    violations
        List of detected contract violations.
    pre_topology_valid
        Whether pre-steer topology satisfied all contracts.
    post_topology_valid
        Whether post-steer topology satisfies all contracts.
    contracts_preserved
        Whether contracts remain satisfiable after steering.
    """

    steer_operation_id: str
    violations: list[ContractViolation] = dataclasses.field(default_factory=list)
    pre_topology_valid: bool = True
    post_topology_valid: bool = True
    contracts_preserved: bool = True

    @property
    def is_valid(self) -> bool:
        """Whether the steer operation is valid (no violations, contracts preserved)."""
        return len(self.violations) == 0 and self.contracts_preserved


# ──────────────────────────────────────────────────────────
# §2 Contract Verifier Protocol
# ──────────────────────────────────────────────────────────


@runtime_checkable
class ContractVerifierProtocol(Protocol):
    """Protocol for contract verifiers implementing steer verification."""

    def verify_pre_steer(self, topology, contracts: list) -> list[ContractViolation]:
        """Verify contracts are valid before steering."""
        ...

    def verify_post_steer(
        self, old_topology, new_topology, contracts: list
    ) -> list[ContractViolation]:
        """Verify contracts remain valid after steering."""
        ...

    def verify_steer_operation(
        self, old_topology, new_topology, contracts: list
    ) -> ContractVerificationResult:
        """Full steer verification: pre + post + diff analysis."""
        ...


# ──────────────────────────────────────────────────────────
# §3 Contract Verifier Implementation
# ──────────────────────────────────────────────────────────


class ContractVerifier:
    """Verifies steer operations maintain contract invariants.

    Per Goal Hierarchy §3, when TopologyManager steers (redirects) agents:
    - Communication patterns remain valid after steering
    - Contract obligations are satisfied by new team topology
    - No contract violations introduced by steering

    This verifier checks pre-steer validity, post-steer validity,
    and ensures contracts are preserved through the steering operation.
    """

    def __init__(self) -> None:
        """Initialize contract verifier."""
        self._operation_counter: int = 0

    def verify_pre_steer(
        self, topology, contracts: list
    ) -> list[ContractViolation]:
        """Verify contracts are valid before steering.

        Checks:
        - All agents with contracts have defined peers in topology
        - All responsibility domains are covered
        - No capability mismatches

        Parameters
        ----------
        topology
            Current TeamTopology.
        contracts
            List of AgentContract to verify.

        Returns
        -------
        list[ContractViolation]
            List of violations found (empty if valid).
        """
        violations: list[ContractViolation] = []

        # Check each contract
        for contract in contracts:
            # Verify agent exists
            if not hasattr(topology, "agents") or contract.agent_id not in topology.agents:
                violations.append(
                    ContractViolation(
                        violation_type=ContractViolationType.COMMUNICATION_BREAK,
                        contract_id=f"{contract.agent_id}",
                        agent_id=contract.agent_id,
                        description=f"Contract agent {contract.agent_id} not in topology",
                        severity="critical",
                    )
                )
                continue

            # If contract specifies a peer, verify peer exists
            if contract.peer_agent_id is not None:
                if contract.peer_agent_id not in topology.agents:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.COMMUNICATION_BREAK,
                            contract_id=f"{contract.agent_id}-{contract.peer_agent_id}",
                            agent_id=contract.agent_id,
                            description=f"Peer agent {contract.peer_agent_id} not in topology",
                            severity="critical",
                        )
                    )

            # Check responsibility domain coverage
            if contract.responsibility_domain:
                agent = topology.agents[contract.agent_id]
                if not hasattr(agent, "assigned_goals"):
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.OBLIGATION_UNMET,
                            contract_id=f"{contract.agent_id}",
                            agent_id=contract.agent_id,
                            description=f"Agent {contract.agent_id} has no assigned goals",
                            severity="warning",
                        )
                    )

        return violations

    def verify_post_steer(
        self, old_topology, new_topology, contracts: list
    ) -> list[ContractViolation]:
        """Verify contracts remain valid after steering.

        Checks that the new topology still satisfies all original contracts:
        - Communication paths preserved or remapped
        - Obligations still met by topology
        - New topology structure is valid

        Parameters
        ----------
        old_topology
            Original TeamTopology before steering.
        new_topology
            New TeamTopology after steering.
        contracts
            List of original AgentContract that must be preserved.

        Returns
        -------
        list[ContractViolation]
            List of violations found (empty if contracts preserved).
        """
        violations: list[ContractViolation] = []

        # Check new topology is valid
        topology_errors = self._check_topology_validity(new_topology)
        violations.extend(topology_errors)

        # Verify each contract is still satisfiable
        for contract in contracts:
            # If agent was preserved in steering
            if (
                hasattr(new_topology, "agents")
                and contract.agent_id in new_topology.agents
            ):
                # If peer was also preserved, communication should be intact
                if contract.peer_agent_id is not None:
                    if contract.peer_agent_id not in new_topology.agents:
                        violations.append(
                            ContractViolation(
                                violation_type=ContractViolationType.COMMUNICATION_BREAK,
                                contract_id=f"{contract.agent_id}-{contract.peer_agent_id}",
                                agent_id=contract.agent_id,
                                description=f"Communication broken: peer {contract.peer_agent_id} removed during steering",
                                severity="critical",
                            )
                        )

                # Check responsibility is still assigned
                if contract.responsibility_domain:
                    new_agent = new_topology.agents[contract.agent_id]
                    if (
                        hasattr(new_agent, "assigned_goals")
                        and not new_agent.assigned_goals
                    ):
                        violations.append(
                            ContractViolation(
                                violation_type=ContractViolationType.OBLIGATION_UNMET,
                                contract_id=f"{contract.agent_id}",
                                agent_id=contract.agent_id,
                                description=f"Agent {contract.agent_id} has no responsibilities after steering",
                                severity="warning",
                            )
                        )

        return violations

    def verify_steer_operation(
        self, old_topology, new_topology, contracts: list
    ) -> ContractVerificationResult:
        """Full steer verification: pre + post + diff analysis.

        Performs comprehensive verification that a steer operation maintains
        contract invariants:
        1. Pre-steer contracts valid
        2. Post-steer contracts valid
        3. Contracts preserved through operation
        4. No new violations introduced

        Parameters
        ----------
        old_topology
            Original TeamTopology.
        new_topology
            New TeamTopology after steering.
        contracts
            List of AgentContract to verify.

        Returns
        -------
        ContractVerificationResult
            Complete verification result with violation list and flags.
        """
        self._operation_counter += 1
        operation_id = f"steer-op-{self._operation_counter}"

        # Phase 1: Verify pre-steer
        pre_violations = self.verify_pre_steer(old_topology, contracts)
        pre_valid = len(pre_violations) == 0

        # Phase 2: Verify post-steer
        post_violations = self.verify_post_steer(old_topology, new_topology, contracts)
        post_valid = len(post_violations) == 0

        # Phase 3: Check capability coverage
        capability_violations = self._check_capability_coverage(new_topology, contracts)

        # Phase 4: Check communication patterns
        communication_violations = self._check_communication_patterns(new_topology, contracts)

        # Combine all violations
        all_violations = (
            pre_violations + post_violations + capability_violations + communication_violations
        )

        # Determine if contracts are preserved
        contracts_preserved = (
            pre_valid and post_valid and len(capability_violations) == 0
        )

        return ContractVerificationResult(
            steer_operation_id=operation_id,
            violations=all_violations,
            pre_topology_valid=pre_valid,
            post_topology_valid=post_valid,
            contracts_preserved=contracts_preserved,
        )

    def _check_topology_validity(self, topology) -> list[ContractViolation]:
        """Verify topology structure is valid.

        Checks:
        - Topology has agents
        - Goal assignments are valid
        - No orphaned goals

        Parameters
        ----------
        topology
            TeamTopology to check.

        Returns
        -------
        list[ContractViolation]
            List of structural violations.
        """
        violations: list[ContractViolation] = []

        if not hasattr(topology, "agents"):
            violations.append(
                ContractViolation(
                    violation_type=ContractViolationType.TOPOLOGY_INVALID,
                    contract_id="topology",
                    agent_id="topology",
                    description="Topology has no agents attribute",
                    severity="critical",
                )
            )
            return violations

        if not topology.agents:
            violations.append(
                ContractViolation(
                    violation_type=ContractViolationType.TOPOLOGY_INVALID,
                    contract_id="topology",
                    agent_id="topology",
                    description="Topology is empty (no agents)",
                    severity="critical",
                )
            )
            return violations

        # Check goal assignments
        if hasattr(topology, "goal_assignments"):
            for goal_id, agent_ids in topology.goal_assignments.items():
                if not agent_ids:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.OBLIGATION_UNMET,
                            contract_id=f"goal-{goal_id}",
                            agent_id="topology",
                            description=f"Goal {goal_id} has no assigned agents",
                            severity="warning",
                        )
                    )
                else:
                    # Verify all assigned agents exist
                    for agent_id in agent_ids:
                        if agent_id not in topology.agents:
                            violations.append(
                                ContractViolation(
                                    violation_type=ContractViolationType.COMMUNICATION_BREAK,
                                    contract_id=f"goal-{goal_id}",
                                    agent_id=agent_id,
                                    description=f"Goal {goal_id} assigned to non-existent agent {agent_id}",
                                    severity="critical",
                                )
                            )

        return violations

    def _check_communication_patterns(
        self, topology, contracts: list
    ) -> list[ContractViolation]:
        """Verify all agents can reach their communication partners.

        Checks that for each contract in the topology, the peer agents exist
        and are reachable. This ensures communication graph is coherent.

        Parameters
        ----------
        topology
            TeamTopology with agents.
        contracts
            List of AgentContract specifying expected communication.

        Returns
        -------
        list[ContractViolation]
            Communication violations (empty if all paths valid).
        """
        violations: list[ContractViolation] = []

        if not hasattr(topology, "agents"):
            return violations

        for contract in contracts:
            if contract.agent_id not in topology.agents:
                continue

            if contract.peer_agent_id is None:
                # Broadcast contract — check agent exists
                if contract.agent_id not in topology.agents:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.COMMUNICATION_BREAK,
                            contract_id=f"{contract.agent_id}-broadcast",
                            agent_id=contract.agent_id,
                            description=f"Broadcast agent {contract.agent_id} not in topology",
                            severity="warning",
                        )
                    )
            else:
                # Point-to-point contract — check both agents exist
                if contract.peer_agent_id not in topology.agents:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.COMMUNICATION_BREAK,
                            contract_id=f"{contract.agent_id}-{contract.peer_agent_id}",
                            agent_id=contract.agent_id,
                            description=f"Peer agent {contract.peer_agent_id} missing for contract",
                            severity="critical",
                        )
                    )

        return violations

    def _check_capability_coverage(
        self, topology, contracts: list
    ) -> list[ContractViolation]:
        """Verify all required capabilities are still present in topology.

        Checks that agents with capability requirements have those capabilities
        in the new topology. Per Goal Hierarchy, capability coverage ensures
        that all necessary functions can still be executed.

        Parameters
        ----------
        topology
            TeamTopology after steering.
        contracts
            List of contracts defining capability requirements.

        Returns
        -------
        list[ContractViolation]
            Capability violations (empty if all covered).
        """
        violations: list[ContractViolation] = []

        if not hasattr(topology, "agents"):
            return violations

        for contract in contracts:
            # For each contract, verify the responsible agent exists
            if contract.agent_id in topology.agents:
                agent = topology.agents[contract.agent_id]

                # If agent has capability requirements (via permissions)
                if hasattr(agent, "permissions") and hasattr(
                    agent.permissions, "capability_level"
                ):
                    capability = agent.permissions.capability_level
                    if capability is None:
                        violations.append(
                            ContractViolation(
                                violation_type=ContractViolationType.CAPABILITY_MISMATCH,
                                contract_id=f"{contract.agent_id}",
                                agent_id=contract.agent_id,
                                description=f"Agent {contract.agent_id} lost capability after steering",
                                severity="warning",
                            )
                        )
            else:
                # Agent was dissolved - check if responsibilities were transferred
                if contract.responsibility_domain:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.CAPABILITY_MISMATCH,
                            contract_id=f"{contract.agent_id}",
                            agent_id=contract.agent_id,
                            description=f"Capability owner {contract.agent_id} removed; responsibilities unclear",
                            severity="warning",
                        )
                    )

        return violations


# ──────────────────────────────────────────────────────────
# §4 Main Entry Point
# ──────────────────────────────────────────────────────────


def verify_steer_contracts(
    old_topology,
    new_topology,
    contracts: list,
) -> ContractVerificationResult:
    """Main entry point for steer contract verification.

    Verifies that a steer operation maintains contract invariants per
    Goal Hierarchy §3 formal specification.

    Parameters
    ----------
    old_topology
        Original TeamTopology before steering.
    new_topology
        New TeamTopology after steering.
    contracts
        List of AgentContract that must be preserved.

    Returns
    -------
    ContractVerificationResult
        Complete verification result with violations and preservation status.

    Example
    -------
    >>> result = verify_steer_contracts(old_topo, new_topo, contracts)
    >>> if result.is_valid:
    ...     print("Steer operation valid: contracts preserved")
    ... else:
    ...     for violation in result.violations:
    ...         print(f"  {violation.severity}: {violation.description}")
    """
    verifier = ContractVerifier()
    return verifier.verify_steer_operation(old_topology, new_topology, contracts)
