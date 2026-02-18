"""Pydantic v2 schema for architecture.yaml.

This is the machine-readable representation of the Holly SAD.
Every field traces back to a specific mermaid source line.

The schema is designed for consumption by:
- Architecture registry (Task 2.x)
- Kernel boundary decorators (Task 3.x)
- Traceability matrix (Task 1.1)
- Drift detection tooling
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ── Enumerations ─────────────────────────────────────

class LayerID(StrEnum):
    """SAD layer identifiers."""
    L0_VPC = "L0"
    L1_KERNEL = "L1"
    L2_CORE = "L2"
    L3_ENGINE = "L3"
    L4_OBSERVABILITY = "L4"
    L5_CONSOLE = "L5"
    SANDBOX = "SANDBOX"
    DATA = "DATA"
    EXTERNAL = "EXTERNAL"
    INFRA = "INFRA"


class EdgeKind(StrEnum):
    """Semantic classification of cross-boundary edges."""
    REQUEST_FLOW = "request_flow"
    IN_PROCESS = "in_process"
    INTERNAL_FLOW = "internal_flow"
    DISPATCH = "dispatch"
    EMIT_EVENTS = "emit_events"
    DATA_ACCESS = "data_access"
    CREDENTIAL = "credential"
    GRPC = "grpc"
    GOVERNS = "governs"
    STREAM = "stream"
    EXTERNAL_CALL = "external_call"


class ConnectionStyle(StrEnum):
    """Visual style of the connection in the SAD."""
    SOLID = "solid"
    DOTTED = "dotted"
    THICK = "thick"


# ── Source traceability ──────────────────────────────

class SourceRef(BaseModel):
    """Trace back to a specific line in the SAD mermaid file."""
    file: str = Field(description="Relative path to the SAD file")
    line: int = Field(ge=1, description="1-indexed line number")
    raw: str = Field(default="", description="Raw mermaid text at that line")


# ── Component model ──────────────────────────────────

class Component(BaseModel):
    """A single architectural component (node in the SAD)."""
    id: str = Field(description="Mermaid node ID (e.g., 'K1', 'CONV', 'PG')")
    name: str = Field(description="Human-readable component name")
    description: str = Field(default="", description="Multi-line description from label")
    layer: LayerID = Field(description="Which SAD layer this component belongs to")
    subgraph_id: str = Field(description="Mermaid subgraph ID containing this node")
    style_class: str = Field(default="", description="CSS class name from classDef")
    source: SourceRef = Field(description="Where this component is defined in the SAD")

    @property
    def is_kernel(self) -> bool:
        return self.layer == LayerID.L1_KERNEL

    @property
    def is_boundary_crossing(self) -> bool:
        """True if this component sits at a layer boundary (e.g., JWTMW, EGRESS)."""
        return self.layer == LayerID.INFRA


class SubgraphEntry(BaseModel):
    """A subgraph (layer/region) in the SAD."""
    id: str = Field(description="Mermaid subgraph ID")
    title: str = Field(description="Display title")
    layer: LayerID = Field(description="SAD layer this subgraph represents")
    direction: str = Field(default="TB", description="Layout direction (TB, LR)")
    parent_id: str | None = Field(default=None, description="Parent subgraph ID if nested")
    children: list[str] = Field(default_factory=list, description="Child component/subgraph IDs")
    source: SourceRef = Field(description="Where this subgraph is defined in the SAD")


# ── Connection model ─────────────────────────────────

class Connection(BaseModel):
    """A directed edge between two components."""
    source_id: str = Field(description="Source component ID")
    target_id: str = Field(description="Target component ID")
    label: str = Field(default="", description="Edge annotation text")
    kind: EdgeKind = Field(description="Semantic classification")
    style: ConnectionStyle = Field(default=ConnectionStyle.SOLID)
    crosses_boundary: bool = Field(
        default=False,
        description="True if this edge crosses a layer boundary",
    )
    source_layer: LayerID = Field(description="Layer of source component")
    target_layer: LayerID = Field(description="Layer of target component")
    source_ref: SourceRef = Field(description="SAD source line")


# ── Invariant model (K1-K8) ─────────────────────────

class KernelInvariant(BaseModel):
    """A kernel invariant gate (K1 through K8)."""
    id: str = Field(description="Gate ID, e.g. 'K1'")
    name: str = Field(description="Short name, e.g. 'Schema Validation'")
    description: str = Field(default="")
    component_id: str = Field(description="Corresponding SAD component ID")
    source: SourceRef = Field(description="SAD source line")


# ── Top-level document ───────────────────────────────

class SADMetadata(BaseModel):
    """Metadata about the SAD version and parsing."""
    sad_version: str = Field(description="e.g., '0.1.0.5'")
    sad_file: str = Field(description="Relative path to source SAD file")
    chart_type: str = Field(default="flowchart")
    chart_direction: str = Field(default="TB")
    generated_by: str = Field(default="holly.arch.extract")
    schema_version: str = Field(default="1.0.0")


class ArchitectureDocument(BaseModel):
    """Root schema for architecture.yaml.

    This is the single source of truth for machine-readable
    architecture data, derived from the SAD mermaid file.
    """
    metadata: SADMetadata
    layers: dict[str, SubgraphEntry] = Field(
        default_factory=dict,
        description="All subgraphs keyed by ID",
    )
    components: dict[str, Component] = Field(
        default_factory=dict,
        description="All components keyed by mermaid node ID",
    )
    connections: list[Connection] = Field(
        default_factory=list,
        description="All directed edges",
    )
    kernel_invariants: list[KernelInvariant] = Field(
        default_factory=list,
        description="K1-K8 invariant gates",
    )

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def connection_count(self) -> int:
        return len(self.connections)

    @property
    def boundary_crossing_count(self) -> int:
        return sum(1 for c in self.connections if c.crosses_boundary)

    def components_in_layer(self, layer: LayerID) -> list[Component]:
        """Return all components belonging to a specific layer."""
        return [c for c in self.components.values() if c.layer == layer]

    model_config = {"populate_by_name": True}
