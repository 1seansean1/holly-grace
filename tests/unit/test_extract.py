"""Tests for holly.arch.extract — SAD AST → ArchitectureDocument pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from holly.arch.extract import extract, extract_from_file, to_yaml
from holly.arch.sad_parser import parse_sad
from holly.arch.schema import EdgeKind, LayerID

if TYPE_CHECKING:
    from pathlib import Path

MINIMAL_SAD = """\
%%{init: {"theme": "dark"}}%%
flowchart TB
    %% HOLLY 3.0 - SYSTEM ARCHITECTURE DOCUMENT v0.1.0.5

    subgraph KERNEL["Layer 1: Kernel"]
        direction LR
        KCTX["KernelContext\\nasync context manager"]
        K1["Schema\\nValidation"]
        K2["Permission\\nGates"]
    end

    subgraph CORE["Layer 2: Core"]
        CONV["Conversation\\nInterface"]
        INTENT["Intent Classifier"]
    end

    CONV --> INTENT
    CONV -.->|"KernelContext\\nin-process"| KCTX

    classDef kernelNode fill:#8b0000
    classDef coreNode fill:#245c3a
    class KCTX,K1,K2 kernelNode
    class CONV,INTENT coreNode
"""


class TestExtractMinimal:
    """Test extraction from minimal synthetic SAD."""

    def test_metadata(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        assert doc.metadata.sad_version == "0.1.0.5"
        assert doc.metadata.chart_type == "flowchart"

    def test_components(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        assert "K1" in doc.components
        assert "CONV" in doc.components
        assert doc.components["K1"].layer == LayerID.L1_KERNEL
        assert doc.components["CONV"].layer == LayerID.L2_CORE

    def test_component_names(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        assert doc.components["K1"].name == "Schema"
        assert doc.components["CONV"].name == "Conversation"

    def test_kernel_invariants(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        inv_ids = {inv.id for inv in doc.kernel_invariants}
        assert "K1" in inv_ids
        assert "K2" in inv_ids

    def test_connections(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        assert doc.connection_count >= 1

    def test_boundary_crossing(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        crossing = [c for c in doc.connections if c.crosses_boundary]
        # CORE -.-> KERNEL should cross
        assert len(crossing) >= 1

    def test_edge_classification(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        in_process = [c for c in doc.connections if c.kind == EdgeKind.IN_PROCESS]
        assert len(in_process) >= 1

    def test_layers(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        assert "KERNEL" in doc.layers
        assert "CORE" in doc.layers
        assert doc.layers["KERNEL"].layer == LayerID.L1_KERNEL

    def test_source_refs(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        for comp in doc.components.values():
            assert comp.source.line > 0
            assert comp.source.file

    def test_yaml_serialization(self) -> None:
        ast = parse_sad(MINIMAL_SAD)
        doc = extract(ast)
        yaml_str = to_yaml(doc)
        # Should be valid YAML
        data = yaml.safe_load(yaml_str)
        assert data["metadata"]["sad_version"] == "0.1.0.5"
        assert "components" in data
        assert "connections" in data


class TestExtractRealSAD:
    """Test extraction against the real SAD file."""

    def test_full_extraction(self, sad_path: Path) -> None:
        if not sad_path.exists():
            return

        doc = extract_from_file(sad_path)

        # 48 components in SAD v0.1.0.5
        assert doc.component_count >= 40, f"Got {doc.component_count}"

        # K1-K8 should all be present
        inv_ids = {inv.id for inv in doc.kernel_invariants}
        for k in range(1, 9):
            assert f"K{k}" in inv_ids, f"Missing K{k}"

        # Should have boundary-crossing connections
        assert doc.boundary_crossing_count > 0

        # Every component should have a source ref
        for comp in doc.components.values():
            assert comp.source.line > 0

        # YAML output should be valid
        yaml_str = to_yaml(doc)
        data = yaml.safe_load(yaml_str)
        assert isinstance(data, dict)

    def test_layer_distribution(self, sad_path: Path) -> None:
        if not sad_path.exists():
            return

        doc = extract_from_file(sad_path)

        # Each major layer should have components
        for layer in [LayerID.L1_KERNEL, LayerID.L2_CORE, LayerID.L3_ENGINE]:
            comps = doc.components_in_layer(layer)
            assert len(comps) > 0, f"No components in {layer}"
