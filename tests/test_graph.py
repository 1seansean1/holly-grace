"""Tests for the master StateGraph construction and routing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from src.graph import build_graph, _route_from_orchestrator, _route_from_sales, _error_handler
from src.state import AgentState


def test_graph_compiles(router):
    """The master graph should compile without errors."""
    graph = build_graph(router)
    compiled = graph.compile()
    assert compiled is not None


def test_graph_has_all_nodes(router):
    """The graph should have all expected nodes."""
    graph = build_graph(router)
    node_names = set(graph.nodes.keys())
    assert "orchestrator" in node_names
    assert "sales_marketing" in node_names
    assert "operations" in node_names
    assert "revenue_analytics" in node_names
    assert "error_handler" in node_names
    assert "sub_agents" in node_names


def test_route_from_orchestrator_sales():
    """Should route to sales_marketing when route_to is sales_marketing."""
    state = {"route_to": "sales_marketing", "error": ""}
    assert _route_from_orchestrator(state) == "sales_marketing"


def test_route_from_orchestrator_operations():
    """Should route to operations."""
    state = {"route_to": "operations", "error": ""}
    assert _route_from_orchestrator(state) == "operations"


def test_route_from_orchestrator_revenue():
    """Should route to revenue_analytics."""
    state = {"route_to": "revenue_analytics", "error": ""}
    assert _route_from_orchestrator(state) == "revenue_analytics"


def test_route_from_orchestrator_error():
    """Should route to error_handler on error."""
    state = {"route_to": "sales_marketing", "error": "Something broke"}
    assert _route_from_orchestrator(state) == "error_handler"


def test_route_from_orchestrator_unknown():
    """Should route to error_handler on unknown route."""
    state = {"route_to": "invalid_route", "error": ""}
    assert _route_from_orchestrator(state) == "error_handler"


def test_route_from_sales_simple():
    """Sales should end for simple tasks (no sub-agents)."""
    state = {"should_spawn_sub_agents": False}
    assert _route_from_sales(state) == "__end__"


def test_route_from_sales_complex():
    """Sales should route to sub_agents for complex tasks."""
    state = {"should_spawn_sub_agents": True}
    assert _route_from_sales(state) == "sub_agents"


def test_error_handler_retries():
    """Error handler should increment retry count and clear error."""
    state = {"retry_count": 0, "error": "Timeout"}
    result = _error_handler(state)
    assert result["retry_count"] == 1
    assert result["error"] == ""


def test_error_handler_exhausted():
    """Error handler should give up after max retries."""
    state = {"retry_count": 3, "error": "Persistent failure"}
    result = _error_handler(state)
    assert result["current_agent"] == "error_handler"
    assert len(result["messages"]) > 0
