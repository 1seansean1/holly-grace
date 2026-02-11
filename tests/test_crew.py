"""Tests for Holly Grace's Construction Crew — registry, dispatch, and tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.holly.crew.registry import (
    CREW_AGENTS,
    CrewAgent,
    get_crew_agent,
    list_crew,
)
from src.holly.tools import dispatch_crew, list_crew_agents


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestCrewRegistry:
    """Test the crew agent registry."""

    def test_all_15_agents_registered(self):
        assert len(CREW_AGENTS) == 15

    def test_all_ids_have_crew_prefix(self):
        for agent_id in CREW_AGENTS:
            assert agent_id.startswith("crew_"), f"{agent_id} missing crew_ prefix"

    def test_agent_ids_unique(self):
        ids = list(CREW_AGENTS.keys())
        assert len(ids) == len(set(ids))

    def test_all_agents_have_required_fields(self):
        for agent_id, agent in CREW_AGENTS.items():
            assert agent.display_name, f"{agent_id} missing display_name"
            assert agent.role, f"{agent_id} missing role"
            assert agent.system_prompt, f"{agent_id} missing system_prompt"
            assert agent.model, f"{agent_id} missing model"

    def test_expected_agents_present(self):
        expected = [
            "crew_architect",
            "crew_tool_smith",
            "crew_mcp_creator",
            "crew_test_engineer",
            "crew_wiring_tech",
            "crew_program_manager",
            "crew_finance_officer",
            "crew_lead_researcher",
            "crew_critic",
            "crew_wise_old_man",
            "crew_epsilon_tuner",
            "crew_strategic_advisor",
            "crew_system_engineer",
            "crew_cyber_security",
            "crew_product_manager",
        ]
        for agent_id in expected:
            assert agent_id in CREW_AGENTS, f"Missing: {agent_id}"

    def test_models_are_valid(self):
        valid_models = {"claude-opus-4-6", "gpt-4o", "gpt-4o-mini"}
        for agent_id, agent in CREW_AGENTS.items():
            assert agent.model in valid_models, f"{agent_id} has invalid model: {agent.model}"

    def test_architect_uses_opus(self):
        agent = CREW_AGENTS["crew_architect"]
        assert agent.model == "claude-opus-4-6"

    def test_wiring_tech_uses_mini(self):
        agent = CREW_AGENTS["crew_wiring_tech"]
        assert agent.model == "gpt-4o-mini"


class TestGetCrewAgent:
    """Test get_crew_agent lookup."""

    def test_returns_agent_for_valid_id(self):
        agent = get_crew_agent("crew_architect")
        assert agent is not None
        assert isinstance(agent, CrewAgent)
        assert agent.display_name == "Architect"

    def test_returns_none_for_unknown_id(self):
        assert get_crew_agent("crew_nonexistent") is None
        assert get_crew_agent("") is None

    def test_returns_none_for_non_crew_id(self):
        assert get_crew_agent("not_a_crew") is None


class TestListCrew:
    """Test list_crew function."""

    def test_returns_list_of_dicts(self):
        agents = list_crew()
        assert isinstance(agents, list)
        assert len(agents) == 15
        for a in agents:
            assert isinstance(a, dict)
            assert "agent_id" in a
            assert "display_name" in a
            assert "role" in a
            assert "model" in a

    def test_dict_keys_match_expected(self):
        agents = list_crew()
        expected_keys = {"agent_id", "display_name", "role", "model"}
        for a in agents:
            assert set(a.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Dispatch tool tests
# ---------------------------------------------------------------------------

class TestDispatchCrew:
    """Test the dispatch_crew tool function."""

    def test_unknown_agent_returns_error(self):
        result = dispatch_crew("crew_nonexistent", "do something")
        assert "error" in result
        assert "Unknown crew agent" in result["error"]

    @patch("src.tower.store.create_run")
    def test_dispatch_creates_tower_run(self, mock_create_run):
        mock_create_run.return_value = "run_abc123"

        result = dispatch_crew("crew_architect", "design a pricing workflow")

        assert result["run_id"] == "run_abc123"
        assert result["status"] == "queued"
        assert result["crew_agent"] == "crew_architect"
        assert result["display_name"] == "Architect"

        # Verify create_run was called with correct args
        call_args = mock_create_run.call_args
        assert call_args.kwargs["workflow_id"] == "crew_solo_crew_architect"
        assert "[Architect]" in call_args.kwargs["run_name"]
        assert call_args.kwargs["metadata"]["crew_agent"] == "crew_architect"
        assert call_args.kwargs["priority"] == 7
        assert call_args.kwargs["created_by"] == "holly_grace"

    @patch("src.tower.store.create_run")
    def test_dispatch_includes_context(self, mock_create_run):
        mock_create_run.return_value = "run_xyz"

        result = dispatch_crew(
            "crew_lead_researcher",
            "research competitor pricing",
            context="Focus on Shopify competitors in apparel",
        )

        call_args = mock_create_run.call_args
        input_state = call_args.kwargs["input_state"]
        assert input_state["trigger_payload"]["context"] == "Focus on Shopify competitors in apparel"

    @patch("src.tower.store.create_run")
    def test_dispatch_input_state_structure(self, mock_create_run):
        mock_create_run.return_value = "run_001"

        dispatch_crew("crew_tool_smith", "build a price checker tool")

        call_args = mock_create_run.call_args
        input_state = call_args.kwargs["input_state"]
        assert input_state["trigger_source"] == "holly_grace_crew"
        assert input_state["retry_count"] == 0
        assert len(input_state["messages"]) == 1
        assert input_state["messages"][0]["type"] == "human"
        assert "price checker" in input_state["messages"][0]["content"]


class TestListCrewAgentsTool:
    """Test the list_crew_agents tool function."""

    def test_returns_all_agents(self):
        result = list_crew_agents()
        assert result["count"] == 15
        assert len(result["agents"]) == 15

    def test_agent_dicts_have_required_keys(self):
        result = list_crew_agents()
        for a in result["agents"]:
            assert "agent_id" in a
            assert "display_name" in a
            assert "role" in a


# ---------------------------------------------------------------------------
# System prompt content tests
# ---------------------------------------------------------------------------

class TestSystemPromptContent:
    """Verify key content in crew system prompts."""

    def test_lead_researcher_has_deep_research_protocol(self):
        agent = CREW_AGENTS["crew_lead_researcher"]
        prompt = agent.system_prompt
        assert "Deep Research Protocol" in prompt
        assert "Phase 1" in prompt
        assert "Meta Prompt Evaluation" in prompt
        assert "Contradiction Detection" in prompt or "contradicting" in prompt
        assert "meta-research report" in prompt.lower() or "meta-research-report" in prompt.lower()

    def test_cyber_security_references_existing_security(self):
        agent = CREW_AGENTS["crew_cyber_security"]
        prompt = agent.system_prompt
        assert "OWASP" in prompt
        assert "JWT" in prompt
        assert "RBAC" in prompt

    def test_system_engineer_is_non_invasive(self):
        agent = CREW_AGENTS["crew_system_engineer"]
        prompt = agent.system_prompt
        assert "non-invasive" in prompt.lower() or "NEVER modify" in prompt

    def test_product_manager_manages_backlog(self):
        agent = CREW_AGENTS["crew_product_manager"]
        prompt = agent.system_prompt
        assert "backlog" in prompt.lower()

    def test_strategic_advisor_references_wise_old_man(self):
        agent = CREW_AGENTS["crew_strategic_advisor"]
        prompt = agent.system_prompt
        assert "Wise Old Man" in prompt

    def test_epsilon_tuner_understands_epsilon_chain(self):
        agent = CREW_AGENTS["crew_epsilon_tuner"]
        prompt = agent.system_prompt
        assert "revenue_epsilon" in prompt
        assert "goal_epsilon" in prompt
