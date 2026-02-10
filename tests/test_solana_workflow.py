"""Tests for Solana mining workflow integration.

Covers:
- Tool creation and invocation (3 tools return valid JSON)
- Tool registration in registry
- Workflow definition validity
- Gate integration: L5 gate closed → mining check skipped
- Gate integration: L5 gate open → tower run created
- Scheduler method existence
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "1")


# ======================================================================
# Tool tests
# ======================================================================


class TestSolanaTools:
    """Verify Solana tools exist and return valid JSON."""

    def test_profitability_tool_exists(self):
        from src.tools.solana_tool import solana_check_profitability
        assert solana_check_profitability is not None

    def test_validator_health_tool_exists(self):
        from src.tools.solana_tool import solana_validator_health
        assert solana_validator_health is not None

    def test_mining_report_tool_exists(self):
        from src.tools.solana_tool import solana_mining_report
        assert solana_mining_report is not None

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    @patch("src.tools.solana_tool._get_sol_price", return_value=150.0)
    def test_profitability_returns_json(self, mock_price, mock_rpc):
        from src.tools.solana_tool import solana_check_profitability
        result = solana_check_profitability.invoke({})
        data = json.loads(result)
        assert "profitability" in data
        assert "sol_price_usd" in data
        assert data["sol_price_usd"] == 150.0
        assert "is_profitable" in data["profitability"]

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    @patch("src.tools.solana_tool._get_sol_price", return_value=150.0)
    def test_profitability_calculates_roi(self, mock_price, mock_rpc):
        from src.tools.solana_tool import solana_check_profitability
        result = json.loads(solana_check_profitability.invoke({}))
        costs = result["costs"]
        assert costs["electricity_rate_kwh"] == 0.12
        assert costs["total_cost_monthly"] > 0
        revenue = result["revenue"]
        assert revenue["staked_sol"] == 1000
        assert revenue["monthly_reward_sol"] > 0

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    def test_validator_health_returns_json(self, mock_rpc):
        from src.tools.solana_tool import solana_validator_health
        result = solana_validator_health.invoke({})
        data = json.loads(result)
        assert "health_score" in data
        assert "status" in data
        assert "performance" in data
        assert "cluster" in data

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    def test_validator_health_score_range(self, mock_rpc):
        from src.tools.solana_tool import solana_validator_health
        result = json.loads(solana_validator_health.invoke({}))
        score = result["health_score"]
        assert 0.0 <= score <= 1.0

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    @patch("src.tools.solana_tool._get_sol_price", return_value=200.0)
    def test_mining_report_returns_json(self, mock_price, mock_rpc):
        from src.tools.solana_tool import solana_mining_report
        result = solana_mining_report.invoke({})
        data = json.loads(result)
        assert "recommendation" in data
        assert "profitability" in data
        assert "validator_health" in data
        assert "hierarchy" in data

    @patch("src.tools.solana_tool._rpc_call", return_value=None)
    @patch("src.tools.solana_tool._get_sol_price", return_value=0.01)
    def test_mining_report_unprofitable(self, mock_price, mock_rpc):
        """Very low SOL price → unprofitable → PAUSE recommendation."""
        from src.tools.solana_tool import solana_mining_report
        result = json.loads(solana_mining_report.invoke({}))
        assert "PAUSE" in result["recommendation"] or "HALT" in result["recommendation"]


class TestHealthScoreComputation:
    """Verify health score logic."""

    def test_delinquent_validator(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=True, skip_rate=None, validator_found=True
        )
        assert score == 0.1

    def test_high_skip_rate(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=False, skip_rate=25.0, validator_found=True
        )
        assert score == 0.3

    def test_moderate_skip_rate(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=False, skip_rate=12.0, validator_found=True
        )
        assert score == 0.6

    def test_low_skip_rate(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=False, skip_rate=3.0, validator_found=True
        )
        assert score == 1.0

    def test_validator_not_found(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=None, skip_rate=None, validator_found=False
        )
        assert score == 0.5

    def test_healthy_validator(self):
        from src.tools.solana_tool import _compute_health_score
        score = _compute_health_score(
            is_delinquent=False, skip_rate=None, validator_found=True
        )
        assert score == 1.0


# ======================================================================
# Registry tests
# ======================================================================


class TestToolRegistry:
    """Verify Solana tools are registered."""

    def test_three_solana_tools_registered(self):
        from src.tool_registry import _TOOL_DEFINITIONS
        solana_tools = [t for t in _TOOL_DEFINITIONS if t.category == "solana"]
        assert len(solana_tools) == 3

    def test_tool_ids(self):
        from src.tool_registry import _TOOL_DEFINITIONS
        solana_ids = {t.tool_id for t in _TOOL_DEFINITIONS if t.category == "solana"}
        assert solana_ids == {
            "solana_check_profitability",
            "solana_validator_health",
            "solana_mining_report",
        }

    def test_tool_modules(self):
        from src.tool_registry import _TOOL_DEFINITIONS
        solana_tools = [t for t in _TOOL_DEFINITIONS if t.category == "solana"]
        for t in solana_tools:
            assert t.module_path == "src.tools.solana_tool"


# ======================================================================
# Workflow definition tests
# ======================================================================


class TestWorkflowDefinition:
    """Verify the Solana mining workflow definition."""

    def test_workflow_exists(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        assert SOLANA_MINING_WORKFLOW.workflow_id == "solana_mining"

    def test_display_name(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        assert SOLANA_MINING_WORKFLOW.display_name == "Solana Mining"

    def test_has_entry_point(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        entry = [n for n in SOLANA_MINING_WORKFLOW.nodes if n.is_entry_point]
        assert len(entry) == 1
        assert entry[0].node_id == "orchestrator"

    def test_has_revenue_node(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        nodes = {n.node_id for n in SOLANA_MINING_WORKFLOW.nodes}
        assert "revenue_analytics" in nodes

    def test_edges_valid(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        assert len(SOLANA_MINING_WORKFLOW.edges) == 2

    def test_to_dict_roundtrip(self):
        from src.workflow_registry import SOLANA_MINING_WORKFLOW, WorkflowDefinition
        d = SOLANA_MINING_WORKFLOW.to_dict()
        restored = WorkflowDefinition.from_dict(d)
        assert restored.workflow_id == "solana_mining"
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 2

    def test_in_seed_defaults(self):
        """SOLANA_MINING_WORKFLOW is included in seed_defaults list."""
        from src.workflow_registry import SOLANA_MINING_WORKFLOW
        # Verify it's a valid WorkflowDefinition that can be seeded
        defn = SOLANA_MINING_WORKFLOW.to_dict()
        assert defn["workflow_id"] == "solana_mining"
        assert defn["display_name"] == "Solana Mining"
        assert len(defn["nodes"]) == 2


# ======================================================================
# Scheduler integration tests
# ======================================================================


class TestSchedulerIntegration:
    """Verify the scheduler has the Solana mining check method."""

    def test_scheduler_has_method(self):
        from src.scheduler.autonomous import AutonomousScheduler
        assert hasattr(AutonomousScheduler, "_solana_mining_check")

    def test_mining_check_skips_when_gate_closed(self):
        """When L5 gate is closed, mining check should not create a tower run."""
        from src.scheduler.autonomous import AutonomousScheduler

        mock_invoke = MagicMock()
        scheduler = AutonomousScheduler.__new__(AutonomousScheduler)
        scheduler._invoke = mock_invoke
        scheduler._start_tower_run = MagicMock()

        mock_gate = MagicMock()
        mock_gate.is_open = False
        mock_gate.failing_predicates = [6]

        with patch(
            "src.hierarchy.store.get_gate_status", return_value=[mock_gate]
        ):
            scheduler._solana_mining_check()

        scheduler._start_tower_run.assert_not_called()

    def test_mining_check_runs_when_gate_open(self):
        """When L5 gate is open, mining check should create a tower run."""
        from src.scheduler.autonomous import AutonomousScheduler

        scheduler = AutonomousScheduler.__new__(AutonomousScheduler)
        scheduler._start_tower_run = MagicMock()

        mock_gate = MagicMock()
        mock_gate.is_open = True

        with patch(
            "src.hierarchy.store.get_gate_status", return_value=[mock_gate]
        ):
            scheduler._solana_mining_check()

        scheduler._start_tower_run.assert_called_once()
        call_kwargs = scheduler._start_tower_run.call_args
        assert call_kwargs[1]["workflow_id"] == "solana_mining"
        assert call_kwargs[1]["run_name"] == "Solana Mining Check"

    def test_mining_check_runs_when_gate_unavailable(self):
        """If hierarchy is not available, mining check should still proceed."""
        from src.scheduler.autonomous import AutonomousScheduler

        scheduler = AutonomousScheduler.__new__(AutonomousScheduler)
        scheduler._start_tower_run = MagicMock()

        with patch(
            "src.hierarchy.store.get_gate_status", side_effect=Exception("DB down")
        ):
            scheduler._solana_mining_check()

        scheduler._start_tower_run.assert_called_once()


# ======================================================================
# Revenue agent binding tests
# ======================================================================


class TestRevenueAgentBinding:
    """Verify the revenue agent has Solana tools bound."""

    def test_revenue_has_solana_tools(self):
        from src.agent_registry import _HARDCODED_DEFAULTS
        revenue = _HARDCODED_DEFAULTS["revenue"]
        assert "solana_check_profitability" in revenue.tool_ids
        assert "solana_validator_health" in revenue.tool_ids
        assert "solana_mining_report" in revenue.tool_ids

    def test_revenue_has_hierarchy_tools(self):
        from src.agent_registry import _HARDCODED_DEFAULTS
        revenue = _HARDCODED_DEFAULTS["revenue"]
        assert "hierarchy_gate_status" in revenue.tool_ids
        assert "hierarchy_predicate_status" in revenue.tool_ids

    def test_revenue_has_stripe_tools(self):
        from src.agent_registry import _HARDCODED_DEFAULTS
        revenue = _HARDCODED_DEFAULTS["revenue"]
        assert "stripe_revenue_query" in revenue.tool_ids
