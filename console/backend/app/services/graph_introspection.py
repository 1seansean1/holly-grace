"""Graph introspection: returns the ecom-agents graph topology for React Flow."""

from __future__ import annotations

from app.models.graph import EdgeDefinition, GraphDefinition, NodeDefinition

# Hardcoded graph structure matching ecom-agents src/graph.py
# This will be replaced with dynamic introspection via /graph/definition in Phase 2

MASTER_GRAPH = GraphDefinition(
    nodes=[
        NodeDefinition(
            id="__start__", label="Start", node_type="terminal",
        ),
        NodeDefinition(
            id="orchestrator", label="Orchestrator",
            node_type="orchestrator", model_id="ollama_qwen", model_provider="ollama",
        ),
        NodeDefinition(
            id="sales_marketing", label="Sales & Marketing",
            node_type="agent", model_id="gpt4o", model_provider="openai",
        ),
        NodeDefinition(
            id="operations", label="Operations",
            node_type="agent", model_id="gpt4o_mini", model_provider="openai",
        ),
        NodeDefinition(
            id="revenue_analytics", label="Revenue & Analytics",
            node_type="agent", model_id="claude_opus", model_provider="anthropic",
        ),
        NodeDefinition(
            id="error_handler", label="Error Handler",
            node_type="error_handler",
        ),
        NodeDefinition(
            id="sub_agents", label="Campaign Sub-Agents",
            node_type="sub_agent",
        ),
        NodeDefinition(
            id="__end__", label="End", node_type="terminal",
        ),
    ],
    edges=[
        EdgeDefinition(id="e1", source="__start__", target="orchestrator"),
        EdgeDefinition(id="e2", source="orchestrator", target="sales_marketing", conditional=True, label="sales"),
        EdgeDefinition(id="e3", source="orchestrator", target="operations", conditional=True, label="ops"),
        EdgeDefinition(id="e4", source="orchestrator", target="revenue_analytics", conditional=True, label="revenue"),
        EdgeDefinition(id="e5", source="orchestrator", target="error_handler", conditional=True, label="error"),
        EdgeDefinition(id="e6", source="sales_marketing", target="sub_agents", conditional=True, label="campaign"),
        EdgeDefinition(id="e7", source="sales_marketing", target="__end__", conditional=True),
        EdgeDefinition(id="e8", source="operations", target="__end__"),
        EdgeDefinition(id="e9", source="revenue_analytics", target="__end__"),
        EdgeDefinition(id="e10", source="sub_agents", target="__end__"),
        EdgeDefinition(id="e11", source="error_handler", target="orchestrator", conditional=True, label="retry"),
        EdgeDefinition(id="e12", source="error_handler", target="__end__", conditional=True),
    ],
    subgraphs={
        "sub_agents": GraphDefinition(
            nodes=[
                NodeDefinition(
                    id="sub_start", label="Start", node_type="terminal",
                ),
                NodeDefinition(
                    id="content_writer", label="Content Writer",
                    node_type="sub_agent", model_id="gpt4o", model_provider="openai",
                ),
                NodeDefinition(
                    id="image_selector", label="Image Selector",
                    node_type="sub_agent", model_id="gpt4o_mini", model_provider="openai",
                ),
                NodeDefinition(
                    id="hashtag_optimizer", label="Hashtag Optimizer",
                    node_type="sub_agent", model_id="ollama_qwen", model_provider="ollama",
                ),
                NodeDefinition(
                    id="campaign_analyzer", label="Campaign Analyzer",
                    node_type="sub_agent", model_id="claude_opus", model_provider="anthropic",
                ),
                NodeDefinition(
                    id="sub_end", label="End", node_type="terminal",
                ),
            ],
            edges=[
                EdgeDefinition(id="se1", source="sub_start", target="content_writer"),
                EdgeDefinition(id="se2", source="sub_start", target="image_selector"),
                EdgeDefinition(id="se3", source="content_writer", target="hashtag_optimizer"),
                EdgeDefinition(id="se4", source="image_selector", target="hashtag_optimizer"),
                EdgeDefinition(id="se5", source="hashtag_optimizer", target="campaign_analyzer"),
                EdgeDefinition(id="se6", source="campaign_analyzer", target="sub_end"),
            ],
        ),
    },
)


def get_graph_definition() -> GraphDefinition:
    """Return the graph definition for rendering."""
    return MASTER_GRAPH
