"""Unit tests for topology verification module.

Tests TopologyNode, TopologyEdge, TopologyViolation, TopologyReport,
and TopologyVerifier classes.
"""

from __future__ import annotations

import pytest

from holly.arch.topology import (
    TopologyEdge,
    TopologyNode,
    TopologyReport,
    TopologyViolation,
    TopologyVerifier,
    verify_holly_topology,
)


# ── TestTopologyNode ──────────────────────────────────────


class TestTopologyNode:
    """Tests for TopologyNode creation and validation."""

    def test_create_valid_node(self) -> None:
        """Create a valid TopologyNode."""
        node = TopologyNode("K1", "holly.kernel.k1", None, "kernel")
        assert node.component_id == "K1"
        assert node.module_path == "holly.kernel.k1"
        assert node.celestial_level is None
        assert node.layer == "kernel"

    def test_create_node_with_celestial_level(self) -> None:
        """Create a TopologyNode with celestial_level."""
        node = TopologyNode("CONV", "holly.core.conv", 0, "goals")
        assert node.celestial_level == 0

    def test_celestial_levels_valid(self) -> None:
        """Celestial levels 0-4 are valid."""
        for level in range(5):
            node = TopologyNode("C", "path", level, "goals")
            assert node.celestial_level == level

    def test_celestial_level_invalid_negative(self) -> None:
        """Negative celestial_level raises ValueError."""
        with pytest.raises(ValueError, match="celestial_level must be 0-4"):
            TopologyNode("C", "path", -1, "goals")

    def test_celestial_level_invalid_too_high(self) -> None:
        """Celestial_level > 4 raises ValueError."""
        with pytest.raises(ValueError, match="celestial_level must be 0-4"):
            TopologyNode("C", "path", 5, "goals")

    def test_layer_valid_all_types(self) -> None:
        """All valid layer types are accepted."""
        valid_layers = ["safety", "goals", "kernel", "storage", "arch", "infra"]
        for layer in valid_layers:
            node = TopologyNode("C", "path", None, layer)
            assert node.layer == layer

    def test_layer_invalid(self) -> None:
        """Invalid layer type raises ValueError."""
        with pytest.raises(ValueError, match="layer must be one of"):
            TopologyNode("C", "path", None, "invalid_layer")

    def test_node_frozen(self) -> None:
        """TopologyNode is frozen (immutable)."""
        node = TopologyNode("K1", "path", None, "kernel")
        with pytest.raises(AttributeError):
            node.component_id = "K2"  # type: ignore


# ── TestTopologyEdge ──────────────────────────────────────


class TestTopologyEdge:
    """Tests for TopologyEdge creation and validation."""

    def test_create_valid_edge(self) -> None:
        """Create a valid TopologyEdge."""
        edge = TopologyEdge("K1", "K2", "import")
        assert edge.source == "K1"
        assert edge.target == "K2"
        assert edge.dependency_type == "import"

    def test_dependency_type_import(self) -> None:
        """Import dependency type is valid."""
        edge = TopologyEdge("A", "B", "import")
        assert edge.dependency_type == "import"

    def test_dependency_type_protocol(self) -> None:
        """Protocol dependency type is valid."""
        edge = TopologyEdge("A", "B", "protocol")
        assert edge.dependency_type == "protocol"

    def test_dependency_type_runtime(self) -> None:
        """Runtime dependency type is valid."""
        edge = TopologyEdge("A", "B", "runtime")
        assert edge.dependency_type == "runtime"

    def test_dependency_type_invalid(self) -> None:
        """Invalid dependency_type raises ValueError."""
        with pytest.raises(ValueError, match="dependency_type must be one of"):
            TopologyEdge("A", "B", "invalid")  # type: ignore

    def test_edge_frozen(self) -> None:
        """TopologyEdge is frozen (immutable)."""
        edge = TopologyEdge("K1", "K2", "import")
        with pytest.raises(AttributeError):
            edge.source = "K3"  # type: ignore


# ── TestTopologyViolation ────────────────────────────────


class TestTopologyViolation:
    """Tests for TopologyViolation creation and validation."""

    def test_create_cycle_violation(self) -> None:
        """Create a cycle violation."""
        v = TopologyViolation("cycle", "A -> B -> A", ["A", "B"])
        assert v.violation_type == "cycle"
        assert v.description == "A -> B -> A"
        assert v.nodes_involved == ["A", "B"]

    def test_create_level_inversion_violation(self) -> None:
        """Create a level_inversion violation."""
        v = TopologyViolation("level_inversion", "L0 depends on L1", ["A", "B"])
        assert v.violation_type == "level_inversion"

    def test_create_layer_violation(self) -> None:
        """Create a layer_violation."""
        v = TopologyViolation("layer_violation", "Infra depends on goals", ["X", "Y"])
        assert v.violation_type == "layer_violation"

    def test_violation_type_invalid(self) -> None:
        """Invalid violation_type raises ValueError."""
        with pytest.raises(ValueError, match="violation_type must be one of"):
            TopologyViolation("invalid", "desc", [])  # type: ignore

    def test_violation_frozen(self) -> None:
        """TopologyViolation is frozen."""
        v = TopologyViolation("cycle", "desc", ["A"])
        with pytest.raises(AttributeError):
            v.violation_type = "layer_violation"  # type: ignore


# ── TestTopologyReport ────────────────────────────────────


class TestTopologyReport:
    """Tests for TopologyReport structure and properties."""

    def test_report_with_no_violations(self) -> None:
        """Report is valid when no violations."""
        report = TopologyReport(
            nodes=[],
            edges=[],
            violations=[],
            is_acyclic=True,
            celestial_order_preserved=True,
            layer_separation_valid=True,
        )
        assert report.is_valid is True

    def test_report_with_violations(self) -> None:
        """Report is invalid when violations present."""
        v = TopologyViolation("cycle", "A -> B -> A", ["A", "B"])
        report = TopologyReport(
            nodes=[],
            edges=[],
            violations=[v],
            is_acyclic=False,
            celestial_order_preserved=True,
            layer_separation_valid=True,
        )
        assert report.is_valid is False

    def test_report_not_acyclic(self) -> None:
        """Report tracks acyclicity status."""
        v = TopologyViolation("cycle", "A -> B -> A", ["A", "B"])
        report = TopologyReport(
            nodes=[],
            edges=[],
            violations=[v],
            is_acyclic=False,
            celestial_order_preserved=True,
            layer_separation_valid=True,
        )
        assert report.is_acyclic is False

    def test_report_celestial_order_not_preserved(self) -> None:
        """Report tracks Celestial ordering status."""
        v = TopologyViolation("level_inversion", "L0 depends on L1", ["A", "B"])
        report = TopologyReport(
            nodes=[],
            edges=[],
            violations=[v],
            is_acyclic=True,
            celestial_order_preserved=False,
            layer_separation_valid=True,
        )
        assert report.celestial_order_preserved is False

    def test_report_layer_separation_invalid(self) -> None:
        """Report tracks layer separation status."""
        v = TopologyViolation("layer_violation", "Infra depends on goals", ["X", "Y"])
        report = TopologyReport(
            nodes=[],
            edges=[],
            violations=[v],
            is_acyclic=True,
            celestial_order_preserved=True,
            layer_separation_valid=False,
        )
        assert report.layer_separation_valid is False


# ── TestTopologyVerifier_CycleDetection ───────────────────


class TestTopologyVerifier_CycleDetection:
    """Tests for cycle detection in TopologyVerifier."""

    def test_acyclic_graph_no_cycles(self) -> None:
        """Acyclic graph has no cycles."""
        nodes = [
            TopologyNode("A", "path_a", None, "kernel"),
            TopologyNode("B", "path_b", None, "kernel"),
            TopologyNode("C", "path_c", None, "kernel"),
        ]
        edges = [
            TopologyEdge("A", "B", "import"),
            TopologyEdge("B", "C", "import"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is True
        assert len(report.violations) == 0

    def test_single_self_loop_cycle(self) -> None:
        """Single node self-loop is detected."""
        nodes = [TopologyNode("A", "path", None, "kernel")]
        edges = [TopologyEdge("A", "A", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is False
        cycle_violations = [v for v in report.violations if v.violation_type == "cycle"]
        assert len(cycle_violations) > 0

    def test_two_node_cycle(self) -> None:
        """Two-node cycle is detected."""
        nodes = [
            TopologyNode("A", "path_a", None, "kernel"),
            TopologyNode("B", "path_b", None, "kernel"),
        ]
        edges = [
            TopologyEdge("A", "B", "import"),
            TopologyEdge("B", "A", "import"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is False
        cycle_violations = [v for v in report.violations if v.violation_type == "cycle"]
        assert len(cycle_violations) > 0

    def test_three_node_cycle(self) -> None:
        """Three-node cycle is detected."""
        nodes = [
            TopologyNode("A", "path_a", None, "kernel"),
            TopologyNode("B", "path_b", None, "kernel"),
            TopologyNode("C", "path_c", None, "kernel"),
        ]
        edges = [
            TopologyEdge("A", "B", "import"),
            TopologyEdge("B", "C", "import"),
            TopologyEdge("C", "A", "import"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is False

    def test_multiple_independent_cycles(self) -> None:
        """Multiple independent cycles are detected."""
        nodes = [
            TopologyNode("A", "pa", None, "kernel"),
            TopologyNode("B", "pb", None, "kernel"),
            TopologyNode("C", "pc", None, "kernel"),
            TopologyNode("D", "pd", None, "kernel"),
        ]
        edges = [
            # Cycle 1: A -> B -> A
            TopologyEdge("A", "B", "import"),
            TopologyEdge("B", "A", "import"),
            # Cycle 2: C -> D -> C
            TopologyEdge("C", "D", "import"),
            TopologyEdge("D", "C", "import"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is False


# ── TestTopologyVerifier_CelestialOrdering ────────────────


class TestTopologyVerifier_CelestialOrdering:
    """Tests for Celestial level ordering verification."""

    def test_l0_no_dependencies_valid(self) -> None:
        """L0 component with no dependencies is valid."""
        nodes = [TopologyNode("L0_A", "path", 0, "kernel")]
        edges: list[TopologyEdge] = []
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) == 0

    def test_l1_depends_on_l0_valid(self) -> None:
        """L1 component depending on L0 is valid."""
        nodes = [
            TopologyNode("L0", "path0", 0, "kernel"),
            TopologyNode("L1", "path1", 1, "kernel"),
        ]
        edges = [TopologyEdge("L1", "L0", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) == 0

    def test_l0_depends_on_l1_invalid(self) -> None:
        """L0 depending on L1 is invalid."""
        nodes = [
            TopologyNode("L0", "path0", 0, "kernel"),
            TopologyNode("L1", "path1", 1, "kernel"),
        ]
        edges = [TopologyEdge("L0", "L1", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) > 0

    def test_l1_depends_on_l2_invalid(self) -> None:
        """L1 depending on L2 is invalid."""
        nodes = [
            TopologyNode("L1", "path1", 1, "kernel"),
            TopologyNode("L2", "path2", 2, "kernel"),
        ]
        edges = [TopologyEdge("L1", "L2", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) > 0

    def test_l2_depends_on_l0_valid(self) -> None:
        """L2 depending on L0 is valid."""
        nodes = [
            TopologyNode("L0", "path0", 0, "kernel"),
            TopologyNode("L2", "path2", 2, "kernel"),
        ]
        edges = [TopologyEdge("L2", "L0", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) == 0

    def test_l4_depends_on_l3_valid(self) -> None:
        """L4 depending on L3 is valid."""
        nodes = [
            TopologyNode("L3", "path3", 3, "kernel"),
            TopologyNode("L4", "path4", 4, "kernel"),
        ]
        edges = [TopologyEdge("L4", "L3", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) == 0

    def test_non_celestial_components_skipped(self) -> None:
        """Non-Celestial components (level=None) are skipped."""
        nodes = [
            TopologyNode("A", "path_a", None, "kernel"),
            TopologyNode("B", "path_b", None, "kernel"),
        ]
        edges = [TopologyEdge("A", "B", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        level_violations = [v for v in report.violations if v.violation_type == "level_inversion"]
        assert len(level_violations) == 0


# ── TestTopologyVerifier_LayerSeparation ──────────────────


class TestTopologyVerifier_LayerSeparation:
    """Tests for layer separation verification.
    
    Lower abstraction layers (infra, arch) shouldn't depend on higher
    abstraction layers (goals, safety).
    """

    def test_same_layer_dependencies_valid(self) -> None:
        """Dependencies within the same layer are valid."""
        nodes = [
            TopologyNode("K1", "path1", None, "kernel"),
            TopologyNode("K2", "path2", None, "kernel"),
        ]
        edges = [TopologyEdge("K1", "K2", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        layer_violations = [v for v in report.violations if v.violation_type == "layer_violation"]
        assert len(layer_violations) == 0

    def test_lower_layer_depends_on_storage_valid(self) -> None:
        """Lower abstraction layer depending on storage is valid."""
        nodes = [
            TopologyNode("ST1", "path1", None, "storage"),
            TopologyNode("I1", "path2", None, "infra"),
        ]
        edges = [TopologyEdge("I1", "ST1", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        layer_violations = [v for v in report.violations if v.violation_type == "layer_violation"]
        assert len(layer_violations) == 0

    def test_infra_depends_on_goals_invalid(self) -> None:
        """Infra depending on goals is invalid."""
        nodes = [
            TopologyNode("G1", "path1", None, "goals"),
            TopologyNode("I1", "path2", None, "infra"),
        ]
        edges = [TopologyEdge("I1", "G1", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        layer_violations = [v for v in report.violations if v.violation_type == "layer_violation"]
        assert len(layer_violations) > 0

    def test_arch_depends_on_storage_valid(self) -> None:
        """Arch depending on storage is valid."""
        nodes = [
            TopologyNode("ST1", "path1", None, "storage"),
            TopologyNode("A1", "path2", None, "arch"),
        ]
        edges = [TopologyEdge("A1", "ST1", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        layer_violations = [v for v in report.violations if v.violation_type == "layer_violation"]
        assert len(layer_violations) == 0

    def test_arch_depends_on_safety_invalid(self) -> None:
        """Arch depending on safety is invalid."""
        nodes = [
            TopologyNode("S1", "path1", None, "safety"),
            TopologyNode("A1", "path2", None, "arch"),
        ]
        edges = [TopologyEdge("A1", "S1", "import")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        layer_violations = [v for v in report.violations if v.violation_type == "layer_violation"]
        assert len(layer_violations) > 0


# ── TestVerifyHollyTopology ───────────────────────────────


class TestVerifyHollyTopology:
    """Tests for verification of the Holly Grace component graph."""

    def test_holly_topology_is_valid(self) -> None:
        """Holly Grace component graph is valid."""
        report = verify_holly_topology()
        assert report.is_valid is True

    def test_holly_topology_is_acyclic(self) -> None:
        """Holly Grace component graph is acyclic."""
        report = verify_holly_topology()
        assert report.is_acyclic is True

    def test_holly_topology_celestial_preserved(self) -> None:
        """Holly Grace preserves Celestial level ordering."""
        report = verify_holly_topology()
        assert report.celestial_order_preserved is True

    def test_holly_topology_layer_separation_valid(self) -> None:
        """Holly Grace maintains layer separation."""
        report = verify_holly_topology()
        assert report.layer_separation_valid is True

    def test_holly_no_violations(self) -> None:
        """Holly Grace has no topology violations."""
        report = verify_holly_topology()
        assert len(report.violations) == 0

    def test_holly_has_nodes(self) -> None:
        """Holly Grace graph has nodes."""
        report = verify_holly_topology()
        assert len(report.nodes) > 0

    def test_holly_has_edges(self) -> None:
        """Holly Grace graph has edges."""
        report = verify_holly_topology()
        assert len(report.edges) > 0

    def test_holly_node_count(self) -> None:
        """Holly Grace has expected number of nodes."""
        report = verify_holly_topology()
        # Should have at least kernel, goals, safety, storage, arch, infra components
        assert len(report.nodes) >= 10


# ── Additional Edge Cases ────────────────────────────────


class TestTopologyVerifierEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_graph(self) -> None:
        """Empty graph (no nodes/edges) is valid."""
        verifier = TopologyVerifier()
        report = verifier.verify([], [])
        assert report.is_valid is True

    def test_single_node_no_edges(self) -> None:
        """Single node with no edges is valid."""
        nodes = [TopologyNode("A", "path", None, "kernel")]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, [])
        assert report.is_valid is True

    def test_disconnected_components(self) -> None:
        """Disconnected graph components are valid if acyclic."""
        nodes = [
            TopologyNode("A", "pa", None, "kernel"),
            TopologyNode("B", "pb", None, "kernel"),
            TopologyNode("C", "pc", None, "kernel"),
            TopologyNode("D", "pd", None, "kernel"),
        ]
        edges = [
            TopologyEdge("A", "B", "import"),
            TopologyEdge("C", "D", "import"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        assert report.is_acyclic is True

    def test_build_graph_returns_dict(self) -> None:
        """build_graph returns proper adjacency list."""
        nodes = [
            TopologyNode("A", "pa", None, "kernel"),
            TopologyNode("B", "pb", None, "kernel"),
        ]
        edges = [TopologyEdge("A", "B", "import")]
        verifier = TopologyVerifier()
        graph = verifier.build_graph(nodes, edges)
        assert isinstance(graph, dict)
        assert "A" in graph
        assert "B" in graph
        assert "B" in graph["A"]

    def test_find_cycles_empty_graph(self) -> None:
        """find_cycles on empty graph returns empty list."""
        verifier = TopologyVerifier()
        cycles = verifier.find_cycles({})
        assert cycles == []

    def test_mixed_dependency_types(self) -> None:
        """Graph with mixed dependency types works correctly."""
        nodes = [
            TopologyNode("A", "pa", None, "kernel"),
            TopologyNode("B", "pb", None, "kernel"),
            TopologyNode("C", "pc", None, "kernel"),
        ]
        edges = [
            TopologyEdge("A", "B", "import"),
            TopologyEdge("B", "C", "protocol"),
            TopologyEdge("C", "A", "runtime"),
        ]
        verifier = TopologyVerifier()
        report = verifier.verify(nodes, edges)
        # A -> B -> C -> A forms a cycle
        assert report.is_acyclic is False
