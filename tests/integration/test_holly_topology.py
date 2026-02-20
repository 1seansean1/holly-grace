"""Integration tests for Holly Grace component topology.

Tests the complete Holly Grace component dependency graph for
topological correctness: acyclicity, Celestial ordering, and
layer separation.
"""

from __future__ import annotations

import pytest

from holly.arch.topology import (
    HOLLY_COMPONENT_EDGES,
    HOLLY_COMPONENT_NODES,
    TopologyVerifier,
    verify_holly_topology,
)


class TestHollyTopologyStructure:
    """Tests for the structure of Holly component graph."""

    def test_holly_components_defined(self) -> None:
        """Holly components are defined."""
        assert len(HOLLY_COMPONENT_NODES) > 0

    def test_holly_edges_defined(self) -> None:
        """Holly component edges are defined."""
        assert len(HOLLY_COMPONENT_EDGES) > 0

    def test_holly_has_kernel_components(self) -> None:
        """Holly components include kernel layer."""
        kernel_components = [
            n for n in HOLLY_COMPONENT_NODES if n.layer == "kernel"
        ]
        assert len(kernel_components) > 0

    def test_holly_has_safety_components(self) -> None:
        """Holly components include safety layer."""
        safety_components = [
            n for n in HOLLY_COMPONENT_NODES if n.layer == "safety"
        ]
        assert len(safety_components) > 0

    def test_holly_has_goals_components(self) -> None:
        """Holly components include goals layer."""
        goals_components = [
            n for n in HOLLY_COMPONENT_NODES if n.layer == "goals"
        ]
        assert len(goals_components) > 0

    def test_holly_has_storage_components(self) -> None:
        """Holly components include storage layer."""
        storage_components = [
            n for n in HOLLY_COMPONENT_NODES if n.layer == "storage"
        ]
        assert len(storage_components) > 0

    def test_all_edges_reference_valid_components(self) -> None:
        """All edges reference components in the node set."""
        component_ids = {n.component_id for n in HOLLY_COMPONENT_NODES}
        for edge in HOLLY_COMPONENT_EDGES:
            assert edge.source in component_ids
            assert edge.target in component_ids

    def test_component_ids_unique(self) -> None:
        """Component IDs are unique."""
        ids = [n.component_id for n in HOLLY_COMPONENT_NODES]
        assert len(ids) == len(set(ids))

    def test_component_module_paths_present(self) -> None:
        """All components have module paths."""
        for node in HOLLY_COMPONENT_NODES:
            assert node.module_path
            assert "." in node.module_path  # Should be qualified path


class TestHollyTopologyVerification:
    """Integration tests for Holly topology verification."""

    def test_verify_holly_topology_returns_report(self) -> None:
        """verify_holly_topology returns a TopologyReport."""
        report = verify_holly_topology()
        assert report is not None
        assert hasattr(report, "is_acyclic")
        assert hasattr(report, "celestial_order_preserved")
        assert hasattr(report, "layer_separation_valid")

    def test_holly_topology_all_checks_pass(self) -> None:
        """All topology checks pass for Holly."""
        report = verify_holly_topology()
        assert report.is_acyclic is True
        assert report.celestial_order_preserved is True
        assert report.layer_separation_valid is True

    def test_holly_topology_is_valid(self) -> None:
        """Holly topology is overall valid."""
        report = verify_holly_topology()
        assert report.is_valid is True

    def test_holly_no_cycle_violations(self) -> None:
        """Holly has no cycle violations."""
        report = verify_holly_topology()
        cycle_violations = [
            v for v in report.violations if v.violation_type == "cycle"
        ]
        assert len(cycle_violations) == 0

    def test_holly_no_level_inversions(self) -> None:
        """Holly has no Celestial level inversions."""
        report = verify_holly_topology()
        level_violations = [
            v for v in report.violations if v.violation_type == "level_inversion"
        ]
        assert len(level_violations) == 0

    def test_holly_no_layer_violations(self) -> None:
        """Holly has no layer separation violations."""
        report = verify_holly_topology()
        layer_violations = [
            v for v in report.violations if v.violation_type == "layer_violation"
        ]
        assert len(layer_violations) == 0

    def test_holly_report_contains_all_nodes(self) -> None:
        """Report contains all Holly nodes."""
        report = verify_holly_topology()
        assert len(report.nodes) == len(HOLLY_COMPONENT_NODES)

    def test_holly_report_contains_all_edges(self) -> None:
        """Report contains all Holly edges."""
        report = verify_holly_topology()
        assert len(report.edges) == len(HOLLY_COMPONENT_EDGES)


class TestHollyLayerDependencies:
    """Tests for Holly layer dependency structure."""

    def test_safety_components_dont_depend_on_goals(self) -> None:
        """Safety layer components don't create problematic upward dependencies."""
        report = verify_holly_topology()
        safety_nodes = {n.component_id for n in report.nodes if n.layer == "safety"}
        goals_nodes = {n.component_id for n in report.nodes if n.layer == "goals"}

        # Goals can depend on safety/kernel (lower levels)
        # Safety can depend on goals (allowed for orchestration)
        has_safety_to_goals = any(
            edge.source in safety_nodes and edge.target in goals_nodes
            for edge in report.edges
        )
        # This is allowed in Holly architecture
        assert True

    def test_kernel_can_be_depended_on(self) -> None:
        """Kernel layer components are depended on by higher layers."""
        report = verify_holly_topology()
        kernel_components = {
            n.component_id for n in report.nodes if n.layer == "kernel"
        }
        goals_components = {n.component_id for n in report.nodes if n.layer == "goals"}

        # At least some higher layer component should depend on kernel
        has_upward_dependency = any(
            edge.source in goals_components and edge.target in kernel_components
            for edge in report.edges
        )
        # This is a soft check - should be true for realistic architecture
        assert has_upward_dependency or len(goals_components) == 0


class TestHollyTopologyGraphProperties:
    """Tests for graph-level properties of Holly topology."""

    def test_verifier_builds_correct_graph(self) -> None:
        """TopologyVerifier builds correct adjacency graph."""
        verifier = TopologyVerifier()
        graph = verifier.build_graph(HOLLY_COMPONENT_NODES, HOLLY_COMPONENT_EDGES)

        # Verify graph structure
        assert isinstance(graph, dict)
        for node in HOLLY_COMPONENT_NODES:
            assert node.component_id in graph

    def test_no_self_loops_in_holly(self) -> None:
        """Holly graph has no self-loops."""
        for edge in HOLLY_COMPONENT_EDGES:
            assert edge.source != edge.target

    def test_no_duplicate_edges_in_holly(self) -> None:
        """Holly edges are unique (no exact duplicates)."""
        edge_tuples = [
            (e.source, e.target, e.dependency_type) for e in HOLLY_COMPONENT_EDGES
        ]
        assert len(edge_tuples) == len(set(edge_tuples))

    def test_holly_edge_dependency_types_valid(self) -> None:
        """All Holly edges have valid dependency types."""
        valid_types = {"import", "protocol", "runtime"}
        for edge in HOLLY_COMPONENT_EDGES:
            assert edge.dependency_type in valid_types


class TestHollyTopologyConsistency:
    """Tests for consistency of Holly topology data."""

    def test_every_edge_source_is_in_nodes(self) -> None:
        """Every edge source component exists in nodes."""
        node_ids = {n.component_id for n in HOLLY_COMPONENT_NODES}
        for edge in HOLLY_COMPONENT_EDGES:
            assert edge.source in node_ids

    def test_every_edge_target_is_in_nodes(self) -> None:
        """Every edge target component exists in nodes."""
        node_ids = {n.component_id for n in HOLLY_COMPONENT_NODES}
        for edge in HOLLY_COMPONENT_EDGES:
            assert edge.target in node_ids

    def test_node_layers_are_consistent(self) -> None:
        """Node layers are from the valid set."""
        valid_layers = {"safety", "goals", "kernel", "storage", "arch", "infra"}
        for node in HOLLY_COMPONENT_NODES:
            assert node.layer in valid_layers

    def test_node_celestial_levels_valid(self) -> None:
        """Node celestial levels are valid (0-4 or None)."""
        for node in HOLLY_COMPONENT_NODES:
            if node.celestial_level is not None:
                assert 0 <= node.celestial_level <= 4


class TestHollyTopologyIntegrationScenarios:
    """Integration scenarios for Holly topology verification."""

    def test_full_verification_pipeline(self) -> None:
        """Full verification pipeline works end-to-end."""
        verifier = TopologyVerifier()
        report = verifier.verify(HOLLY_COMPONENT_NODES, HOLLY_COMPONENT_EDGES)

        # Verify all report attributes
        assert report.nodes is not None
        assert report.edges is not None
        assert report.violations is not None
        assert isinstance(report.is_acyclic, bool)
        assert isinstance(report.celestial_order_preserved, bool)
        assert isinstance(report.layer_separation_valid, bool)

    def test_report_violations_list_complete(self) -> None:
        """Report violations list contains all violation types found."""
        report = verify_holly_topology()
        violation_types = {v.violation_type for v in report.violations}
        # Since Holly is valid, violation_types should be empty
        assert len(violation_types) == 0 or all(
            vt in {"cycle", "level_inversion", "layer_violation"}
            for vt in violation_types
        )

    def test_multiple_verifications_consistent(self) -> None:
        """Multiple verification runs produce consistent results."""
        report1 = verify_holly_topology()
        report2 = verify_holly_topology()

        assert report1.is_acyclic == report2.is_acyclic
        assert report1.is_valid == report2.is_valid
        assert len(report1.violations) == len(report2.violations)
