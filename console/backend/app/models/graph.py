"""Graph definition models for React Flow rendering."""

from __future__ import annotations

from pydantic import BaseModel


class NodeDefinition(BaseModel):
    id: str
    label: str
    node_type: str  # "orchestrator", "agent", "sub_agent", "error_handler", "terminal"
    model_id: str | None = None
    model_provider: str | None = None
    position: dict[str, float] | None = None


class EdgeDefinition(BaseModel):
    id: str
    source: str
    target: str
    conditional: bool = False
    label: str | None = None


class GraphDefinition(BaseModel):
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    subgraphs: dict[str, "GraphDefinition"] = {}
