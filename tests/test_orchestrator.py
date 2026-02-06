"""Tests for the Orchestrator agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from src.agents.orchestrator import (
    VALID_COMPLEXITIES,
    VALID_ROUTES,
    VALID_TASK_TYPES,
    build_orchestrator_node,
)


def test_orchestrator_routes_order_check(router, sample_state, mock_llm_response):
    """Orchestrator should route order_check to operations."""
    mock_model = MagicMock()
    mock_model.invoke.return_value = mock_llm_response(
        json.dumps({
            "task_type": "order_check",
            "task_complexity": "simple",
            "route_to": "operations",
        })
    )

    with patch("src.agents.orchestrator.get_model_with_fallbacks", return_value=mock_model):
        node = build_orchestrator_node(router)
        result = node(sample_state)
        assert result["task_type"] == "order_check"
        assert result["route_to"] == "operations"
        assert result["should_spawn_sub_agents"] is False


def test_orchestrator_handles_malformed_json(router, sample_state, mock_llm_response):
    """Orchestrator should handle malformed LLM responses gracefully."""
    from src.agents.orchestrator import build_orchestrator_node
    from src.llm.config import ModelID
    from src.llm.fallback import get_model_with_fallbacks

    # Mock the model
    mock_model = MagicMock()
    mock_model.invoke.return_value = mock_llm_response("This is not JSON at all")

    with patch("src.agents.orchestrator.get_model_with_fallbacks", return_value=mock_model):
        node = build_orchestrator_node(router)
        result = node(sample_state)

        # Should fall back to defaults
        assert result["task_type"] == "content_post"
        assert result["route_to"] == "sales_marketing"
        assert result["error"] == ""


def test_orchestrator_spawns_sub_agents_for_campaign(router, mock_llm_response):
    """Orchestrator should set should_spawn_sub_agents for full_campaign."""
    mock_model = MagicMock()
    mock_model.invoke.return_value = mock_llm_response(
        json.dumps({
            "task_type": "full_campaign",
            "task_complexity": "complex",
            "route_to": "sales_marketing",
        })
    )

    with patch("src.agents.orchestrator.get_model_with_fallbacks", return_value=mock_model):
        node = build_orchestrator_node(router)
        state = {
            "messages": [HumanMessage(content="Launch a new campaign this week")],
            "trigger_payload": {},
        }
        result = node(state)

        assert result["task_type"] == "full_campaign"
        assert result["should_spawn_sub_agents"] is True
        assert result["route_to"] == "sales_marketing"


def test_orchestrator_no_spawn_for_simple_post(router, mock_llm_response):
    """Orchestrator should NOT spawn sub-agents for content_post."""
    mock_model = MagicMock()
    mock_model.invoke.return_value = mock_llm_response(
        json.dumps({
            "task_type": "content_post",
            "task_complexity": "moderate",
            "route_to": "sales_marketing",
        })
    )

    with patch("src.agents.orchestrator.get_model_with_fallbacks", return_value=mock_model):
        node = build_orchestrator_node(router)
        state = {
            "messages": [HumanMessage(content="Post something on Instagram")],
            "trigger_payload": {},
        }
        result = node(state)

        assert result["task_type"] == "content_post"
        assert result["should_spawn_sub_agents"] is False


def test_orchestrator_no_task_description(router, mock_llm_response):
    """Orchestrator should return error when no task description is provided."""
    mock_model = MagicMock()

    with patch("src.agents.orchestrator.get_model_with_fallbacks", return_value=mock_model):
        node = build_orchestrator_node(router)
        state = {"messages": [], "trigger_payload": {}}
        result = node(state)

        assert result.get("error") == "No task description provided"


def test_valid_task_types():
    """All expected task types should be defined."""
    assert "content_post" in VALID_TASK_TYPES
    assert "full_campaign" in VALID_TASK_TYPES
    assert "order_check" in VALID_TASK_TYPES
    assert "revenue_report" in VALID_TASK_TYPES
    assert len(VALID_TASK_TYPES) == 7


def test_valid_routes():
    """All expected routes should be defined."""
    assert "sales_marketing" in VALID_ROUTES
    assert "operations" in VALID_ROUTES
    assert "revenue_analytics" in VALID_ROUTES
