"""Workflow Registry: CRUD + versioning for workflow definitions.

A workflow definition is a JSON structure describing:
- Nodes (agent_id, position, entry point, error handler)
- Edges (source, target, type, conditions)
- Error config

The registry reads/writes to Postgres and manages version history + rollback.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.aps.store import (
    activate_workflow,
    create_workflow,
    get_active_workflow,
    get_all_workflows,
    get_workflow,
    get_workflow_version,
    get_workflow_version_history,
    seed_workflow,
    soft_delete_workflow,
    update_workflow,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class WorkflowNodeDef:
    """A node in a workflow definition."""

    node_id: str
    agent_id: str
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    is_entry_point: bool = False
    is_error_handler: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "position": self.position,
            "is_entry_point": self.is_entry_point,
            "is_error_handler": self.is_error_handler,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> WorkflowNodeDef:
        return WorkflowNodeDef(
            node_id=d["node_id"],
            agent_id=d["agent_id"],
            position=d.get("position", {"x": 0, "y": 0}),
            is_entry_point=d.get("is_entry_point", False),
            is_error_handler=d.get("is_error_handler", False),
        )


@dataclass
class WorkflowEdgeDef:
    """An edge in a workflow definition."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str = "direct"  # "direct" | "conditional"
    conditions: list[dict] | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type,
            "conditions": self.conditions,
            "label": self.label,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> WorkflowEdgeDef:
        return WorkflowEdgeDef(
            edge_id=d["edge_id"],
            source_node_id=d["source_node_id"],
            target_node_id=d["target_node_id"],
            edge_type=d.get("edge_type", "direct"),
            conditions=d.get("conditions"),
            label=d.get("label", ""),
        )


@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""

    workflow_id: str
    display_name: str
    description: str
    nodes: list[WorkflowNodeDef]
    edges: list[WorkflowEdgeDef]
    error_config: dict = field(default_factory=lambda: {"max_retries": 3})

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "display_name": self.display_name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "error_config": self.error_config,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> WorkflowDefinition:
        return WorkflowDefinition(
            workflow_id=d["workflow_id"],
            display_name=d.get("display_name", d["workflow_id"]),
            description=d.get("description", ""),
            nodes=[WorkflowNodeDef.from_dict(n) for n in d.get("nodes", [])],
            edges=[WorkflowEdgeDef.from_dict(e) for e in d.get("edges", [])],
            error_config=d.get("error_config", {"max_retries": 3}),
        )


# ---------------------------------------------------------------------------
# Default workflow definition (mirrors current graph.py hardcoded graph)
# ---------------------------------------------------------------------------


DEFAULT_WORKFLOW = WorkflowDefinition(
    workflow_id="default",
    display_name="Default Workflow",
    description="The original hardcoded agent graph: orchestrator routes to sales, ops, or revenue",
    nodes=[
        WorkflowNodeDef("orchestrator", "orchestrator", {"x": 400, "y": 50}, is_entry_point=True),
        WorkflowNodeDef("sales_marketing", "sales_marketing", {"x": 150, "y": 250}),
        WorkflowNodeDef("operations", "operations", {"x": 400, "y": 250}),
        WorkflowNodeDef("revenue_analytics", "revenue", {"x": 650, "y": 250}),
        WorkflowNodeDef("error_handler", "error_handler", {"x": 400, "y": 450}, is_error_handler=True),
        WorkflowNodeDef("sub_agents", "sub_agents", {"x": 150, "y": 450}),
    ],
    edges=[
        WorkflowEdgeDef(
            "e1", "orchestrator", "sales_marketing", "conditional",
            conditions=[
                {"target": "sales_marketing", "type": "field_equals", "field": "route_to", "value": "sales_marketing"},
                {"target": "operations", "type": "field_equals", "field": "route_to", "value": "operations"},
                {"target": "revenue_analytics", "type": "field_equals", "field": "route_to", "value": "revenue_analytics"},
                {"target": "error_handler", "type": "default"},
            ],
        ),
        WorkflowEdgeDef(
            "e2", "sales_marketing", "sub_agents", "conditional",
            conditions=[
                {"target": "sub_agents", "type": "field_equals", "field": "should_spawn_sub_agents", "value": "True"},
                {"target": "__end__", "type": "default"},
            ],
        ),
        WorkflowEdgeDef("e3", "sub_agents", "__end__", "direct"),
        WorkflowEdgeDef("e4", "operations", "__end__", "direct"),
        WorkflowEdgeDef("e5", "revenue_analytics", "__end__", "direct"),
        WorkflowEdgeDef(
            "e6", "error_handler", "orchestrator", "conditional",
            conditions=[
                {"target": "orchestrator", "type": "field_equals", "field": "error", "value": ""},
                {"target": "__end__", "type": "default"},
            ],
        ),
    ],
    error_config={"max_retries": 3},
)


# ---------------------------------------------------------------------------
# App Factory workflow definition (hub-and-spoke: orchestrator ↔ specialists)
# ---------------------------------------------------------------------------


APP_FACTORY_WORKFLOW = WorkflowDefinition(
    workflow_id="app_factory",
    display_name="App Factory",
    description="Autonomous Android app development — idea to Play Store",
    nodes=[
        WorkflowNodeDef("af_orchestrator", "af_orchestrator", {"x": 400, "y": 50}, is_entry_point=True),
        WorkflowNodeDef("af_architect", "af_architect", {"x": 100, "y": 250}),
        WorkflowNodeDef("af_coder", "af_coder", {"x": 300, "y": 250}),
        WorkflowNodeDef("af_tester", "af_tester", {"x": 500, "y": 250}),
        WorkflowNodeDef("af_security", "af_security", {"x": 700, "y": 250}),
        WorkflowNodeDef("af_builder", "af_builder", {"x": 300, "y": 450}),
        WorkflowNodeDef("af_deployer", "af_deployer", {"x": 500, "y": 450}),
    ],
    edges=[
        # Orchestrator routes to specialists (conditional)
        WorkflowEdgeDef(
            "af_e1", "af_orchestrator", "af_architect", "conditional",
            conditions=[
                {"target": "af_architect", "type": "field_equals", "field": "route_to", "value": "af_architect"},
                {"target": "af_coder", "type": "field_equals", "field": "route_to", "value": "af_coder"},
                {"target": "af_tester", "type": "field_equals", "field": "route_to", "value": "af_tester"},
                {"target": "af_security", "type": "field_equals", "field": "route_to", "value": "af_security"},
                {"target": "af_builder", "type": "field_equals", "field": "route_to", "value": "af_builder"},
                {"target": "af_deployer", "type": "field_equals", "field": "route_to", "value": "af_deployer"},
                {"target": "__end__", "type": "field_equals", "field": "route_to", "value": "__end__"},
                {"target": "__end__", "type": "default"},
            ],
        ),
        # All specialists route back to orchestrator
        WorkflowEdgeDef("af_e8", "af_architect", "af_orchestrator", "direct"),
        WorkflowEdgeDef("af_e9", "af_coder", "af_orchestrator", "direct"),
        WorkflowEdgeDef("af_e10", "af_tester", "af_orchestrator", "direct"),
        WorkflowEdgeDef("af_e11", "af_security", "af_orchestrator", "direct"),
        WorkflowEdgeDef("af_e12", "af_builder", "af_orchestrator", "direct"),
        WorkflowEdgeDef("af_e13", "af_deployer", "af_orchestrator", "direct"),
    ],
    error_config={"max_retries": 3},
)


# ---------------------------------------------------------------------------
# Solana Mining workflow definition
# ---------------------------------------------------------------------------


SOLANA_MINING_WORKFLOW = WorkflowDefinition(
    workflow_id="solana_mining",
    display_name="Solana Mining",
    description=(
        "Monitors Solana mining profitability, validator health, and hierarchy "
        "gate status. Runs every 6 hours, gated by L5 Celestial gate."
    ),
    nodes=[
        WorkflowNodeDef("orchestrator", "orchestrator", {"x": 400, "y": 50}, is_entry_point=True),
        WorkflowNodeDef("revenue_analytics", "revenue", {"x": 400, "y": 250}),
    ],
    edges=[
        WorkflowEdgeDef(
            "sm_e1", "orchestrator", "revenue_analytics", "conditional",
            conditions=[
                {"target": "revenue_analytics", "type": "field_equals", "field": "route_to", "value": "revenue_analytics"},
                {"target": "revenue_analytics", "type": "default"},
            ],
        ),
        WorkflowEdgeDef("sm_e2", "revenue_analytics", "__end__", "direct"),
    ],
    error_config={"max_retries": 2},
)


# ---------------------------------------------------------------------------
# Signal Generator workflow definition
# ---------------------------------------------------------------------------


SIGNAL_GENERATOR_WORKFLOW = WorkflowDefinition(
    workflow_id="signal_generator",
    display_name="Signal Generator",
    description=(
        "Fetches all Shopify products every 2 hours, scores their descriptions "
        "for readability and SEO quality, generates improved variants using "
        "GPT-4o-mini, and automatically updates any description that scores "
        "10 or more points higher than the original."
    ),
    nodes=[
        WorkflowNodeDef("orchestrator", "orchestrator", {"x": 400, "y": 50}, is_entry_point=True),
        WorkflowNodeDef("operations", "operations", {"x": 400, "y": 250}),
    ],
    edges=[
        WorkflowEdgeDef(
            "sg_e1", "orchestrator", "operations", "conditional",
            conditions=[
                {"target": "operations", "type": "field_equals", "field": "route_to", "value": "operations"},
                {"target": "operations", "type": "default"},
            ],
        ),
        WorkflowEdgeDef("sg_e2", "operations", "__end__", "direct"),
    ],
    error_config={"max_retries": 2},
)


# ---------------------------------------------------------------------------
# Revenue Engine workflow definition
# ---------------------------------------------------------------------------


REVENUE_ENGINE_WORKFLOW = WorkflowDefinition(
    workflow_id="revenue_engine",
    display_name="Revenue Engine",
    description=(
        "Runs daily to audit every Shopify product for SEO issues (thin descriptions, "
        "missing structure, weak titles), auto-fixes problems using GPT-4o-mini, "
        "generates social media posts and re-engagement email drafts, and tracks "
        "all improvements through evaluation metrics."
    ),
    nodes=[
        WorkflowNodeDef("orchestrator", "orchestrator", {"x": 400, "y": 50}, is_entry_point=True),
        WorkflowNodeDef("sales_marketing", "sales_marketing", {"x": 250, "y": 250}),
        WorkflowNodeDef("revenue_analytics", "revenue", {"x": 550, "y": 250}),
    ],
    edges=[
        WorkflowEdgeDef(
            "re_e1", "orchestrator", "sales_marketing", "conditional",
            conditions=[
                {"target": "sales_marketing", "type": "field_equals", "field": "route_to", "value": "sales_marketing"},
                {"target": "revenue_analytics", "type": "field_equals", "field": "route_to", "value": "revenue_analytics"},
                {"target": "sales_marketing", "type": "default"},
            ],
        ),
        WorkflowEdgeDef("re_e2", "sales_marketing", "__end__", "direct"),
        WorkflowEdgeDef("re_e3", "revenue_analytics", "__end__", "direct"),
    ],
    error_config={"max_retries": 2},
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class WorkflowRegistry:
    """CRUD + version control for workflow definitions."""

    def __init__(self, cache_ttl: float = 30.0):
        self._cache: dict[str, tuple[dict, float]] = {}
        self._cache_ttl = cache_ttl

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        """Get a workflow by id."""
        if workflow_id in self._cache:
            data, ts = self._cache[workflow_id]
            if time.time() - ts < self._cache_ttl:
                return data

        row = get_workflow(workflow_id)
        if row:
            self._cache[workflow_id] = (row, time.time())
        return row

    def get_all(self) -> list[dict[str, Any]]:
        """Get all non-deleted workflows."""
        rows = get_all_workflows()
        for row in rows:
            self._cache[row["workflow_id"]] = (row, time.time())
        return rows

    def create(
        self,
        *,
        workflow_id: str,
        display_name: str,
        description: str = "",
        definition: dict,
    ) -> dict[str, Any] | None:
        """Create a new workflow."""
        row = create_workflow(
            workflow_id=workflow_id,
            display_name=display_name,
            description=description,
            definition=definition,
            is_builtin=False,
            is_active=False,
        )
        if row:
            self._cache[workflow_id] = (row, time.time())
        return row

    def update(
        self,
        workflow_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> dict[str, Any] | None:
        """Update a workflow. Auto-snapshots before applying."""
        row = update_workflow(workflow_id, expected_version=expected_version, **updates)
        if row:
            self._cache[workflow_id] = (row, time.time())
        return row

    def delete(self, workflow_id: str) -> bool:
        """Soft-delete a workflow."""
        result = soft_delete_workflow(workflow_id)
        if result:
            self._cache.pop(workflow_id, None)
        return result

    def activate(self, workflow_id: str) -> bool:
        """Activate a workflow (deactivates others)."""
        result = activate_workflow(workflow_id)
        if result:
            # Invalidate all cache entries since is_active changed
            self._cache.clear()
        return result

    def get_active(self) -> dict[str, Any] | None:
        """Get the currently active workflow."""
        return get_active_workflow()

    def get_version_history(self, workflow_id: str, limit: int = 50) -> list[dict]:
        """Get version history for a workflow."""
        return get_workflow_version_history(workflow_id, limit=limit)

    def get_version(self, workflow_id: str, version: int) -> dict | None:
        """Get a specific version snapshot."""
        return get_workflow_version(workflow_id, version)

    def rollback(self, workflow_id: str, target_version: int) -> dict[str, Any] | None:
        """Rollback a workflow to a previous version."""
        snapshot = get_workflow_version(workflow_id, target_version)
        if not snapshot:
            return None

        current = get_workflow(workflow_id)
        if not current:
            return None

        return self.update(
            workflow_id,
            {"definition": snapshot["definition"]},
            expected_version=current["version"],
        )

    def seed_defaults(self) -> None:
        """Seed all built-in workflows into the DB."""
        for wf, active in [
            (DEFAULT_WORKFLOW, True),
            (APP_FACTORY_WORKFLOW, False),
            (SOLANA_MINING_WORKFLOW, False),
            (SIGNAL_GENERATOR_WORKFLOW, False),
            (REVENUE_ENGINE_WORKFLOW, False),
        ]:
            defn = wf.to_dict()
            seed_workflow(
                workflow_id=wf.workflow_id,
                display_name=wf.display_name,
                description=wf.description,
                definition=defn,
                is_builtin=True,
                is_active=active,
            )

    def invalidate(self, workflow_id: str) -> None:
        """Clear a cache entry."""
        self._cache.pop(workflow_id, None)


# Global singleton
_workflow_registry: WorkflowRegistry | None = None


def get_workflow_registry() -> WorkflowRegistry:
    """Get or create the global workflow registry."""
    global _workflow_registry
    if _workflow_registry is None:
        _workflow_registry = WorkflowRegistry()
    return _workflow_registry
