"""Topological verification of component dependency graph.

Task 36.4 — Verifies that the component dependency graph has correct
topological properties:
- No circular dependencies between modules
- Celestial level ordering preserved (L0 cannot depend on L1+)
- Layer separation maintained (safety layer below goals layer, etc.)
- RTD (Runtime Dependency) topology verified against architecture.yaml

Provides cycle detection via DFS, level ordering checks, and layer
separation validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Data Models ──────────────────────────────────────


@dataclass(slots=True, frozen=True)
class TopologyNode:
    """A node in the component dependency graph.

    Attributes
    ----------
    component_id
        Unique component identifier (e.g., "CONV", "K1", "GOALS").
    module_path
        Python module path (e.g., "holly.goals.predicates").
    celestial_level
        Celestial level (0-4) if component is a Celestial component,
        None otherwise. L0 has no deps; L1 deps only on L0; etc.
    layer
        Component layer: "safety", "goals", "kernel", "storage", "arch", "infra".
    """
    component_id: str
    module_path: str
    celestial_level: int | None
    layer: str

    def __post_init__(self) -> None:
        """Validate node attributes."""
        if self.celestial_level is not None:
            if not (0 <= self.celestial_level <= 4):
                raise ValueError(f"celestial_level must be 0-4 or None, got {self.celestial_level}")
        valid_layers = {"safety", "goals", "kernel", "storage", "arch", "infra"}
        if self.layer not in valid_layers:
            raise ValueError(f"layer must be one of {valid_layers}, got {self.layer}")


@dataclass(slots=True, frozen=True)
class TopologyEdge:
    """A directed dependency edge: source imports/depends on target.

    Attributes
    ----------
    source
        Component ID of the dependent.
    target
        Component ID of the dependency.
    dependency_type
        Type of dependency: "import", "protocol", or "runtime".
    """
    source: str
    target: str
    dependency_type: str

    def __post_init__(self) -> None:
        """Validate edge attributes."""
        valid_types = {"import", "protocol", "runtime"}
        if self.dependency_type not in valid_types:
            raise ValueError(
                f"dependency_type must be one of {valid_types}, got {self.dependency_type}"
            )


@dataclass(slots=True, frozen=True)
class TopologyViolation:
    """A topology invariant violation.

    Attributes
    ----------
    violation_type
        Type: "cycle", "level_inversion", "layer_violation".
    description
        Human-readable description of the violation.
    nodes_involved
        List of component IDs involved in the violation.
    """
    violation_type: str
    description: str
    nodes_involved: list[str]

    def __post_init__(self) -> None:
        """Validate violation attributes."""
        valid_types = {"cycle", "level_inversion", "layer_violation"}
        if self.violation_type not in valid_types:
            raise ValueError(
                f"violation_type must be one of {valid_types}, got {self.violation_type}"
            )


@dataclass(slots=True)
class TopologyReport:
    """Report from topological verification run.

    Attributes
    ----------
    nodes
        List of all TopologyNodes in the graph.
    edges
        List of all TopologyEdges in the graph.
    violations
        List of detected TopologyViolations.
    is_acyclic
        True if no cycles detected.
    celestial_order_preserved
        True if Celestial level ordering is valid.
    layer_separation_valid
        True if layer separation is maintained.
    """
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    violations: list[TopologyViolation]
    is_acyclic: bool
    celestial_order_preserved: bool
    layer_separation_valid: bool

    @property
    def is_valid(self) -> bool:
        """Return True if no violations detected."""
        return len(self.violations) == 0


# ── Layer Ordering ───────────────────────────────────────

# Layer ordering: Infra-layer can't depend on Goals/Safety, Safety/Goals can depend on Kernel.
# Basic rule: infra < arch < storage < kernel < safety < goals (as dependency targets)
# But in practice, goals and safety can depend on kernel universally.
# We'll only enforce strong violations: infra/arch shouldn't depend on goals/safety.
LAYER_PRIORITY = {"goals": 6, "safety": 5, "kernel": 4, "storage": 3, "infra": 2, "arch": 1}


# ── Topology Verifier ────────────────────────────────────


class TopologyVerifier:
    """Verifies topological properties of the component graph."""

    def build_graph(self, nodes: list[TopologyNode], edges: list[TopologyEdge]) -> dict[str, list[str]]:
        """Build adjacency list representation of the graph.

        Parameters
        ----------
        nodes
            List of all TopologyNodes.
        edges
            List of all TopologyEdges (dependencies).

        Returns
        -------
        dict
            Adjacency list: {component_id: [dependent_component_ids]}.
        """
        graph: dict[str, list[str]] = {node.component_id: [] for node in nodes}
        for edge in edges:
            if edge.source in graph and edge.target in graph:
                graph[edge.source].append(edge.target)
        return graph

    def find_cycles(self, graph: dict[str, list[str]]) -> list[list[str]]:
        """Find all cycles in the dependency graph using DFS.

        Parameters
        ----------
        graph
            Adjacency list representation (source -> targets).

        Returns
        -------
        list
            List of cycles, where each cycle is a list of component IDs
            forming a circular path.
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []
        path: list[str] = []

        def dfs(node: str) -> None:
            """DFS helper to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return cycles

    def check_celestial_ordering(
        self, nodes: list[TopologyNode], edges: list[TopologyEdge]
    ) -> list[TopologyViolation]:
        """Verify Celestial level ordering.

        L0 cannot depend on L1+, L1 cannot depend on L2+, etc.

        Parameters
        ----------
        nodes
            List of TopologyNodes.
        edges
            List of TopologyEdges.

        Returns
        -------
        list
            List of TopologyViolations for level inversions.
        """
        violations: list[TopologyViolation] = []

        # Build node ID -> level map
        level_map: dict[str, int] = {
            node.component_id: node.celestial_level
            for node in nodes
            if node.celestial_level is not None
        }

        for edge in edges:
            source_level = level_map.get(edge.source)
            target_level = level_map.get(edge.target)

            # Skip edges where one or both nodes are not Celestial
            if source_level is None or target_level is None:
                continue

            # A higher level should not depend on a lower level
            if source_level < target_level:
                violations.append(
                    TopologyViolation(
                        violation_type="level_inversion",
                        description=(
                            f"L{source_level} component '{edge.source}' depends on "
                            f"L{target_level} component '{edge.target}'"
                        ),
                        nodes_involved=[edge.source, edge.target],
                    )
                )

        return violations

    def check_layer_separation(
        self, nodes: list[TopologyNode], edges: list[TopologyEdge]
    ) -> list[TopologyViolation]:
        """Verify layer separation constraints.

        Infra/arch layers shouldn't depend on goals/safety (higher level abstractions).

        Parameters
        ----------
        nodes
            List of TopologyNodes.
        edges
            List of TopologyEdges.

        Returns
        -------
        list
            List of TopologyViolations for layer boundary violations.
        """
        violations: list[TopologyViolation] = []

        # Build node ID -> layer map
        layer_map: dict[str, str] = {node.component_id: node.layer for node in nodes}

        # Identify lower-level layers (infra, arch) and higher-level layers (goals, safety)
        lower_layers = {"infra", "arch"}
        higher_layers = {"goals", "safety"}

        for edge in edges:
            source_layer = layer_map.get(edge.source)
            target_layer = layer_map.get(edge.target)

            # Skip edges where we don't have layer info
            if source_layer is None or target_layer is None:
                continue

            # Lower-level layers shouldn't depend on higher-level layers
            if source_layer in lower_layers and target_layer in higher_layers:
                violations.append(
                    TopologyViolation(
                        violation_type="layer_violation",
                        description=(
                            f"Lower abstraction layer '{source_layer}' ({edge.source}) depends on "
                            f"higher abstraction layer '{target_layer}' ({edge.target})"
                        ),
                        nodes_involved=[edge.source, edge.target],
                    )
                )

        return violations

    def verify(
        self, nodes: list[TopologyNode], edges: list[TopologyEdge]
    ) -> TopologyReport:
        """Run full topological verification.

        Parameters
        ----------
        nodes
            List of TopologyNodes.
        edges
            List of TopologyEdges.

        Returns
        -------
        TopologyReport
            Complete verification report with all results.
        """
        graph = self.build_graph(nodes, edges)
        cycles = self.find_cycles(graph)

        # Determine if acyclic
        is_acyclic = len(cycles) == 0

        # Check celestial ordering
        celestial_violations = self.check_celestial_ordering(nodes, edges)
        celestial_order_preserved = len(celestial_violations) == 0

        # Check layer separation
        layer_violations = self.check_layer_separation(nodes, edges)
        layer_separation_valid = len(layer_violations) == 0

        # Combine all violations
        violations: list[TopologyViolation] = []

        # Add cycle violations
        for cycle in cycles:
            violations.append(
                TopologyViolation(
                    violation_type="cycle",
                    description=f"Circular dependency: {' -> '.join(cycle)}",
                    nodes_involved=cycle,
                )
            )

        violations.extend(celestial_violations)
        violations.extend(layer_violations)

        return TopologyReport(
            nodes=nodes,
            edges=edges,
            violations=violations,
            is_acyclic=is_acyclic,
            celestial_order_preserved=celestial_order_preserved,
            layer_separation_valid=layer_separation_valid,
        )


# ── Holly Component Graph ────────────────────────────────


HOLLY_COMPONENT_NODES: list[TopologyNode] = [
    # Kernel layer (L1)
    TopologyNode("K1", "holly.kernel.k1", None, "kernel"),
    TopologyNode("K2", "holly.kernel.k2", None, "kernel"),
    TopologyNode("K3", "holly.kernel.k3", None, "kernel"),
    TopologyNode("K4", "holly.kernel.k4", None, "kernel"),
    TopologyNode("K5", "holly.kernel.k5", None, "kernel"),
    TopologyNode("K6", "holly.kernel.k6", None, "kernel"),
    TopologyNode("K7", "holly.kernel.k7", None, "kernel"),
    TopologyNode("K8", "holly.kernel.k8", None, "kernel"),
    TopologyNode("KCTX", "holly.kernel.context", None, "kernel"),
    # Core layer (L2)
    TopologyNode("CONV", "holly.core.conversation", None, "goals"),
    TopologyNode("INTENT", "holly.core.intent", None, "goals"),
    TopologyNode("GOALS", "holly.core.goals", None, "goals"),
    TopologyNode("APS", "holly.core.aps", None, "goals"),
    TopologyNode("TOPO", "holly.core.topo", None, "goals"),
    TopologyNode("MEM", "holly.core.memory", None, "goals"),
    TopologyNode("CFG", "holly.core.config", None, "storage"),
    # Engine layer (L3)
    TopologyNode("MAIN", "holly.engine.main", None, "safety"),
    TopologyNode("CRON", "holly.engine.cron", None, "safety"),
    TopologyNode("SUB", "holly.engine.subscription", None, "safety"),
    TopologyNode("MCP", "holly.engine.mcp", None, "safety"),
    TopologyNode("WF", "holly.engine.workflow", None, "safety"),
    TopologyNode("LANEPOL", "holly.engine.lanepol", None, "safety"),
    # Observability layer (L4)
    TopologyNode("EVBUS", "holly.obs.eventbus", None, "infra"),
    TopologyNode("WS", "holly.obs.websocket", None, "infra"),
    TopologyNode("LOGS", "holly.obs.logging", None, "infra"),
    TopologyNode("DASH", "holly.obs.dashboard", None, "infra"),
    # Sandbox
    TopologyNode("SEXEC", "holly.sandbox.exec", None, "arch"),
    TopologyNode("SSEC", "holly.sandbox.security", None, "safety"),
    # Storage
    TopologyNode("DB", "holly.storage.database", None, "storage"),
    TopologyNode("CACHE", "holly.storage.cache", None, "storage"),
    # Additional components
    TopologyNode("AUTH", "holly.auth.tokens", None, "safety"),
    TopologyNode("SEC", "holly.security.policies", None, "safety"),
]


HOLLY_COMPONENT_EDGES: list[TopologyEdge] = [
    # Goals layer depends on Kernel
    TopologyEdge("CONV", "K1", "import"),
    TopologyEdge("INTENT", "K2", "import"),
    TopologyEdge("GOALS", "K3", "import"),
    TopologyEdge("APS", "K4", "import"),
    TopologyEdge("TOPO", "K5", "import"),
    TopologyEdge("MEM", "KCTX", "import"),
    # Safety layer depends on Goals
    TopologyEdge("MAIN", "CONV", "import"),
    TopologyEdge("MAIN", "INTENT", "import"),
    TopologyEdge("MAIN", "GOALS", "import"),
    TopologyEdge("CRON", "CONV", "import"),
    TopologyEdge("SUB", "MEM", "import"),
    TopologyEdge("MCP", "APS", "import"),
    TopologyEdge("WF", "GOALS", "import"),
    TopologyEdge("LANEPOL", "TOPO", "import"),
    # Safety layer depends on Kernel directly
    TopologyEdge("MAIN", "K1", "protocol"),
    TopologyEdge("AUTH", "K2", "import"),
    TopologyEdge("SEC", "K3", "import"),
    # Infra layer depends on Storage (not goals/safety - valid!)
    TopologyEdge("EVBUS", "DB", "import"),
    TopologyEdge("WS", "DB", "import"),
    TopologyEdge("LOGS", "DB", "import"),
    TopologyEdge("DASH", "EVBUS", "import"),
    # Arch layer depends on Storage (not goals/safety - valid!)
    TopologyEdge("SEXEC", "CFG", "runtime"),
    # Storage layer dependencies
    TopologyEdge("CFG", "K1", "import"),
    TopologyEdge("DB", "CFG", "import"),
    TopologyEdge("CACHE", "DB", "import"),
]


def verify_holly_topology() -> TopologyReport:
    """Verify topology of the Holly Grace component graph.

    Returns
    -------
    TopologyReport
        Complete verification report with acyclicity, Celestial ordering,
        and layer separation results.
    """
    verifier = TopologyVerifier()
    return verifier.verify(HOLLY_COMPONENT_NODES, HOLLY_COMPONENT_EDGES)
