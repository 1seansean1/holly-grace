"""Tests for holly.arch.sad_parser — mermaid flowchart → AST."""

from __future__ import annotations

from typing import TYPE_CHECKING

from holly.arch.sad_parser import (
    EdgeDirection,
    EdgeStyle,
    parse_sad,
    parse_sad_file,
)

if TYPE_CHECKING:
    from pathlib import Path

# ── Minimal synthetic SAD ────────────────────────────

MINIMAL_SAD = """\
%%{init: {"theme": "dark"}}%%
flowchart TB
    %% Test SAD
    subgraph KERNEL["Layer 1: Kernel"]
        direction LR
        K1["Schema\\nValidation"]
        K2["Permission\\nGates"]
    end

    subgraph CORE["Layer 2: Core"]
        CONV["Conversation"]
        INTENT["Intent Classifier"]
    end

    CONV --> INTENT
    CORE -.->|"KernelContext\\nin-process"| KERNEL
    K1 --- K2

    classDef kernel fill:#6b0000,stroke:#ff4444,color:#ffffff
    classDef core fill:#1b4332,stroke:#40916c,color:#ffffff
    class K1,K2 kernel
    class CONV,INTENT core
"""


class TestParseMinimal:
    """Test parsing of a minimal synthetic SAD."""

    def test_chart_type(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert ast.chart_type == "flowchart"
        assert ast.chart_direction == "TB"

    def test_init_directive(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert len(ast.init_directives) == 1
        assert '"theme"' in ast.init_directives[0].raw

    def test_comments_extracted(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        texts = [c.text for c in ast.comments]
        assert any("Test SAD" in t for t in texts)

    def test_subgraphs(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert "KERNEL" in ast.subgraphs
        assert "CORE" in ast.subgraphs
        assert ast.subgraphs["KERNEL"].title == "Layer 1: Kernel"
        assert ast.subgraphs["KERNEL"].direction == "LR"

    def test_nodes(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert "K1" in ast.nodes
        assert "K2" in ast.nodes
        assert "CONV" in ast.nodes
        assert "INTENT" in ast.nodes
        assert ast.nodes["K1"].label_lines[0] == "Schema"

    def test_node_parent_subgraph(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert ast.nodes["K1"].parent_subgraph == "KERNEL"
        assert ast.nodes["CONV"].parent_subgraph == "CORE"

    def test_edges(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert ast.edge_count >= 2

        # CONV --> INTENT (solid forward)
        forward_edges = [
            e for e in ast.edges
            if e.source == "CONV" and e.target == "INTENT"
        ]
        assert len(forward_edges) == 1
        assert forward_edges[0].style == EdgeStyle.SOLID
        assert forward_edges[0].direction == EdgeDirection.FORWARD

    def test_dotted_edge_with_label(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        dotted = [e for e in ast.edges if e.style == EdgeStyle.DOTTED]
        assert len(dotted) >= 1
        assert any("KernelContext" in e.label for e in dotted)

    def test_undirected_edge(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        none_dir = [e for e in ast.edges if e.direction == EdgeDirection.NONE]
        assert len(none_dir) >= 1
        assert any(e.source == "K1" and e.target == "K2" for e in none_dir)

    def test_style_defs(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert "kernel" in ast.style_defs
        assert "core" in ast.style_defs
        assert "fill:#6b0000" in ast.style_defs["kernel"].properties

    def test_style_assignments(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        assert len(ast.style_assignments) >= 2
        # K1 should have kernel class
        classes = ast.style_classes_for_node("K1")
        assert "kernel" in classes

    def test_nodes_in_subgraph(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        kernel_nodes = ast.nodes_in_subgraph("KERNEL")
        ids = {n.node_id for n in kernel_nodes}
        assert "K1" in ids
        assert "K2" in ids


class TestParseRealSAD:
    """Test parsing the actual SAD file if available."""

    def test_parse_real_sad(self, sad_path: Path) -> None:
        if not sad_path.exists():
            return  # skip if file not available

        ast = parse_sad_file(sad_path)

        # SAD v0.1.0.5 has 48 components
        assert ast.node_count >= 40, f"Expected >=40 nodes, got {ast.node_count}"

        # Should have multiple subgraphs
        assert ast.subgraph_count >= 8, f"Expected >=8 subgraphs, got {ast.subgraph_count}"

        # Should have K1-K8
        for k in range(1, 9):
            assert f"K{k}" in ast.nodes, f"Missing kernel gate K{k}"

        # Should have many edges
        assert ast.edge_count >= 30, f"Expected >=30 edges, got {ast.edge_count}"

        # Kernel subgraph should exist and contain K1-K8
        assert "KERNEL" in ast.subgraphs
        kernel_nodes = ast.nodes_in_subgraph("KERNEL")
        kernel_ids = {n.node_id for n in kernel_nodes}
        assert "K1" in kernel_ids
        assert "KCTX" in kernel_ids
