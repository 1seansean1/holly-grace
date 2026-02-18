"""Extraction pipeline: SAD mermaid AST → architecture.yaml (ArchitectureDocument).

Maps the raw parsed mermaid AST into semantically typed architecture data.
The key intelligence here is:
1. Subgraph → LayerID mapping (which subgraph is which SAD layer)
2. Edge → EdgeKind classification (what kind of connection)
3. Boundary crossing detection (does an edge cross layers)
4. K1-K8 invariant extraction
5. Source line linking (Task 1.8)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

from holly.arch.sad_parser import (
    EdgeDirection,
    EdgeStyle,
    MermaidAST,
    MermaidEdge,
    MermaidNode,
    parse_sad_file,
)
from holly.arch.schema import (
    ArchitectureDocument,
    Component,
    Connection,
    ConnectionDirection,
    ConnectionStyle,
    EdgeKind,
    KernelInvariant,
    LayerID,
    SADMetadata,
    SourceRef,
    SubgraphEntry,
)

if TYPE_CHECKING:
    from pathlib import Path

# ── Subgraph → Layer mapping ─────────────────────────

# This maps mermaid subgraph IDs to their semantic LayerID.
# Derived from the SAD structure — if the SAD changes subgraph IDs,
# this mapping must be updated.
_SUBGRAPH_LAYER_MAP: dict[str, LayerID] = {
    "VPC": LayerID.L0_VPC,
    "PUB": LayerID.L0_VPC,
    "PRIV": LayerID.L0_VPC,
    "KERNEL": LayerID.L1_KERNEL,
    "CORE": LayerID.L2_CORE,
    "ENGINE": LayerID.L3_ENGINE,
    "OBS": LayerID.L4_OBSERVABILITY,
    "UI": LayerID.L5_CONSOLE,
    "SANDBOX": LayerID.SANDBOX,
    "DATA": LayerID.DATA,
}

# Nodes that don't live in a subgraph but have known layers
_STANDALONE_NODE_LAYERS: dict[str, LayerID] = {
    "LLM": LayerID.EXTERNAL,
    "JWTMW": LayerID.INFRA,
    "AUTH": LayerID.INFRA,
    "EGRESS": LayerID.INFRA,
    "KMS": LayerID.INFRA,
}


def _resolve_layer(node: MermaidNode, ast: MermaidAST) -> LayerID:
    """Determine which LayerID a node belongs to.

    Walk up the subgraph nesting until we find a mapped layer.
    """
    # Check standalone overrides first
    if node.node_id in _STANDALONE_NODE_LAYERS:
        return _STANDALONE_NODE_LAYERS[node.node_id]

    # Walk up subgraph hierarchy
    sg_id = node.parent_subgraph
    while sg_id:
        if sg_id in _SUBGRAPH_LAYER_MAP:
            return _SUBGRAPH_LAYER_MAP[sg_id]
        sg = ast.subgraphs.get(sg_id)
        if sg:
            sg_id = sg.parent_subgraph
        else:
            break

    # Check style classes for hints
    for sc in node.style_classes:
        if "kernel" in sc.lower():
            return LayerID.L1_KERNEL
        if "core" in sc.lower():
            return LayerID.L2_CORE
        if "engine" in sc.lower():
            return LayerID.L3_ENGINE
        if "obs" in sc.lower():
            return LayerID.L4_OBSERVABILITY
        if "ui" in sc.lower() or "console" in sc.lower():
            return LayerID.L5_CONSOLE
        if "data" in sc.lower() or "stor" in sc.lower():
            return LayerID.DATA
        if "sandbox" in sc.lower():
            return LayerID.SANDBOX
        if "infra" in sc.lower() or "secrets" in sc.lower():
            return LayerID.INFRA

    return LayerID.L0_VPC  # fallback


# ── Edge → EdgeKind classification ───────────────────

_EDGE_LABEL_KIND_MAP: list[tuple[str, EdgeKind]] = [
    ("gRPC", EdgeKind.GRPC),
    ("HTTPS", EdgeKind.REQUEST_FLOW),
    ("WSS", EdgeKind.REQUEST_FLOW),
    ("Forward", EdgeKind.REQUEST_FLOW),
    ("Validated Claims", EdgeKind.REQUEST_FLOW),
    ("OIDC", EdgeKind.REQUEST_FLOW),
    ("/auth", EdgeKind.REQUEST_FLOW),
    ("KernelContext", EdgeKind.IN_PROCESS),
    ("in-process", EdgeKind.IN_PROCESS),
    ("Dispatch", EdgeKind.DISPATCH),
    ("Schedule", EdgeKind.DISPATCH),
    ("Spawn", EdgeKind.DISPATCH),
    ("Emit Events", EdgeKind.EMIT_EVENTS),
    ("Filtered Stream", EdgeKind.STREAM),
    ("Stream", EdgeKind.STREAM),
    ("LLM Calls", EdgeKind.EXTERNAL_CALL),
    ("Agent LLM Calls", EdgeKind.EXTERNAL_CALL),
    ("Allowlisted", EdgeKind.EXTERNAL_CALL),
    ("Local Inference", EdgeKind.EXTERNAL_CALL),
    ("State", EdgeKind.DATA_ACCESS),
    ("History", EdgeKind.DATA_ACCESS),
    ("Memory", EdgeKind.DATA_ACCESS),
    ("Queue", EdgeKind.DATA_ACCESS),
    ("Pub-Sub", EdgeKind.DATA_ACCESS),
    ("Logs", EdgeKind.DATA_ACCESS),
    ("Metrics", EdgeKind.DATA_ACCESS),
    ("WAL", EdgeKind.DATA_ACCESS),
    ("Checkpoints", EdgeKind.DATA_ACCESS),
    ("Task State", EdgeKind.DATA_ACCESS),
    ("Short-Term", EdgeKind.DATA_ACCESS),
    ("Medium-Term", EdgeKind.DATA_ACCESS),
    ("Long-Term", EdgeKind.DATA_ACCESS),
    ("API Keys", EdgeKind.CREDENTIAL),
    ("DB Creds", EdgeKind.CREDENTIAL),
    ("Tool Creds", EdgeKind.CREDENTIAL),
    ("JWKS", EdgeKind.CREDENTIAL),
    ("Client Secret", EdgeKind.CREDENTIAL),
    ("Revocation", EdgeKind.CREDENTIAL),
    ("Governs", EdgeKind.GOVERNS),
]


def _classify_edge(edge: MermaidEdge, source_layer: LayerID, target_layer: LayerID) -> EdgeKind:
    """Classify an edge by its label and context."""
    label = edge.label
    for pattern, kind in _EDGE_LABEL_KIND_MAP:
        if pattern.lower() in label.lower():
            return kind

    # Fall back to style-based heuristics
    if edge.style == EdgeStyle.DOTTED:
        if source_layer == LayerID.INFRA or target_layer == LayerID.INFRA:
            return EdgeKind.CREDENTIAL
        return EdgeKind.IN_PROCESS

    if source_layer != target_layer:
        return EdgeKind.DISPATCH

    return EdgeKind.INTERNAL_FLOW


def _edge_style_to_connection(style: EdgeStyle) -> ConnectionStyle:
    match style:
        case EdgeStyle.SOLID:
            return ConnectionStyle.SOLID
        case EdgeStyle.DOTTED:
            return ConnectionStyle.DOTTED
        case EdgeStyle.THICK:
            return ConnectionStyle.THICK


# ── Name extraction ──────────────────────────────────

def _extract_component_name(node: MermaidNode) -> str:
    """Extract a clean component name from a node label.

    The first line of the label is typically the component name.
    """
    lines = node.label_lines
    if not lines:
        return node.node_id
    # First line is the name; strip any trailing qualifiers
    name = lines[0].strip()
    # Remove trailing annotations like "- Out of Band"
    name = re.sub(r"\s*[-\u2013\u2014]\s*Out of Band.*", "", name)
    return name


def _extract_description(node: MermaidNode) -> str:
    """Extract description from label lines (everything after the first line)."""
    lines = node.label_lines
    if len(lines) <= 1:
        return ""
    return "\n".join(lines[1:])


# ── K1-K8 extraction ────────────────────────────────

_KERNEL_INVARIANTS: dict[str, str] = {
    "K1": "Schema Validation",
    "K2": "Permission Gates",
    "K3": "Bounds Checking",
    "K4": "Trace Injection",
    "K5": "Idempotency Key Generation",
    "K6": "Durability WAL",
    "K7": "HITL Gates",
    "K8": "Eval Gates",
}


def _extract_kernel_invariants(
    ast: MermaidAST, sad_file: str,
) -> list[KernelInvariant]:
    """Extract K1-K8 kernel invariant definitions from the AST."""
    invariants: list[KernelInvariant] = []
    for kid, name in _KERNEL_INVARIANTS.items():
        node = ast.nodes.get(kid)
        if node:
            invariants.append(KernelInvariant(
                id=kid,
                name=name,
                description=_extract_description(node),
                component_id=kid,
                source=SourceRef(
                    file=sad_file,
                    line=node.line_no,
                    raw=node.label,
                ),
            ))
    return invariants


# ── Main extraction ──────────────────────────────────

def extract(ast: MermaidAST, *, sad_file: str = "docs/architecture/SAD_0.1.0.5.mermaid") -> ArchitectureDocument:
    """Transform a parsed MermaidAST into an ArchitectureDocument.

    This is the core of Task 1.7 — the extraction pipeline.
    """
    # Extract SAD version from comments
    sad_version = "unknown"
    for comment in ast.comments:
        if "v0." in comment.text or "v1." in comment.text:
            m = re.search(r"v(\d+\.\d+\.\d+(?:\.\d+)?)", comment.text)
            if m:
                sad_version = m.group(1)
                break

    metadata = SADMetadata(
        sad_version=sad_version,
        sad_file=sad_file,
        chart_type=ast.chart_type,
        chart_direction=ast.chart_direction,
    )

    # Extract subgraphs → layers
    layers: dict[str, SubgraphEntry] = {}
    for sg_id, sg in ast.subgraphs.items():
        layer_id = _SUBGRAPH_LAYER_MAP.get(sg_id, LayerID.L0_VPC)
        layers[sg_id] = SubgraphEntry(
            id=sg_id,
            title=sg.title,
            layer=layer_id,
            direction=sg.direction,
            parent_id=sg.parent_subgraph,
            children=sg.children_ids,
            source=SourceRef(file=sad_file, line=sg.line_no, raw=sg.title),
        )

    # Extract nodes → components
    components: dict[str, Component] = {}
    for node_id, node in ast.nodes.items():
        layer = _resolve_layer(node, ast)
        name = _extract_component_name(node)
        desc = _extract_description(node)
        style_class = node.style_classes[0] if node.style_classes else ""
        components[node_id] = Component(
            id=node_id,
            name=name,
            description=desc,
            layer=layer,
            subgraph_id=node.parent_subgraph or "",
            style_class=style_class,
            source=SourceRef(file=sad_file, line=node.line_no, raw=node.label),
        )

    # Map parser EdgeDirection → schema ConnectionDirection
    _dir_map = {
        EdgeDirection.FORWARD: ConnectionDirection.FORWARD,
        EdgeDirection.BACKWARD: ConnectionDirection.BACKWARD,
        EdgeDirection.BOTH: ConnectionDirection.BOTH,
        EdgeDirection.NONE: ConnectionDirection.NONE,
    }

    # Extract edges → connections
    connections: list[Connection] = []
    for edge in ast.edges:
        # Normalise direction: for BACKWARD edges, swap source/target so
        # Connection.source_id always represents the semantic origin.
        if edge.direction == EdgeDirection.BACKWARD:
            src_id, tgt_id = edge.target, edge.source
        else:
            src_id, tgt_id = edge.source, edge.target

        source_comp = components.get(src_id)
        target_comp = components.get(tgt_id)
        if not source_comp or not target_comp:
            continue  # skip edges to/from unknown nodes

        source_layer = source_comp.layer
        target_layer = target_comp.layer
        kind = _classify_edge(edge, source_layer, target_layer)
        crosses = source_layer != target_layer

        connections.append(Connection(
            source_id=src_id,
            target_id=tgt_id,
            label=edge.label,
            kind=kind,
            style=_edge_style_to_connection(edge.style),
            direction=_dir_map.get(edge.direction, ConnectionDirection.FORWARD),
            crosses_boundary=crosses,
            source_layer=source_layer,
            target_layer=target_layer,
            source_ref=SourceRef(file=sad_file, line=edge.line_no, raw=edge.label),
        ))

    # Extract kernel invariants
    kernel_invariants = _extract_kernel_invariants(ast, sad_file)

    return ArchitectureDocument(
        metadata=metadata,
        layers=layers,
        components=components,
        connections=connections,
        kernel_invariants=kernel_invariants,
    )


def extract_from_file(sad_path: Path) -> ArchitectureDocument:
    """Full pipeline: file → parse → extract → ArchitectureDocument."""
    ast = parse_sad_file(sad_path)
    relative = str(sad_path.name)
    # Try to compute relative path from repo root
    for parent in sad_path.parents:
        if (parent / "pyproject.toml").exists():
            relative = str(sad_path.relative_to(parent))
            break
    return extract(ast, sad_file=relative)


def to_yaml(doc: ArchitectureDocument) -> str:
    """Serialize an ArchitectureDocument to YAML string."""
    data = doc.model_dump(mode="json", exclude_none=True)
    return yaml.dump(data, default_flow_style=False, sort_keys=False, width=120)


def write_architecture_yaml(doc: ArchitectureDocument, output_path: Path) -> None:
    """Write architecture.yaml to disk."""
    output_path.write_text(to_yaml(doc), encoding="utf-8")
