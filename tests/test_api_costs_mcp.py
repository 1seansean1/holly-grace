"""Tests for the API Costs MCP server (src/mcp/servers/api_costs.py).

Covers:
- _anthropic_usage: happy path, empty, cost_config unavailable
- _openai_usage: happy path, workflow_id filter, cost_config unavailable
- _combined_cost_summary: happy path, per-workflow breakdown, pricing ref
- Aggregation: multi-entry same model, 6-decimal rounding
- MCP protocol: initialize, tools/list, tools/call dispatch, unknown tool, ping
"""

from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Shared mock factory
# ---------------------------------------------------------------------------

def _make_model_cost(model_id: str, display_name: str, is_local: bool = False):
    """Return a lightweight mock that quacks like cost_config.ModelCost."""
    mc = SimpleNamespace(
        model_id=model_id,
        display_name=display_name,
        is_local=is_local,
        input_per_1m=0.0 if is_local else 2.50,
        output_per_1m=0.0 if is_local else 10.00,
    )
    return mc


def _mock_cost_config(
    *,
    workflow_costs: list[dict] | None = None,
    workflow_totals: dict | None = None,
    cost_summary: dict | None = None,
):
    """Build a mock cost_config module with sensible defaults."""
    cc = MagicMock()

    cc.MODEL_COSTS = {
        "claude-opus-4-6": _make_model_cost("claude-opus-4-6", "Claude Opus 4.6"),
        "claude-sonnet-4-5": _make_model_cost("claude-sonnet-4-5", "Claude Sonnet 4.5"),
        "gpt-4o": _make_model_cost("gpt-4o", "GPT-4o"),
        "gpt-4o-mini": _make_model_cost("gpt-4o-mini", "GPT-4o Mini"),
        "qwen2.5:3b": _make_model_cost("qwen2.5:3b", "Qwen 2.5 3B", is_local=True),
    }

    if workflow_costs is None:
        workflow_costs = []
    cc.get_workflow_costs = MagicMock(return_value=workflow_costs)
    cc.get_total_cost_by_workflow = MagicMock(return_value=workflow_totals or {})
    cc.get_cost_summary = MagicMock(return_value=cost_summary or {})
    return cc


# Canonical sample entries used across multiple tests
_SAMPLE_ENTRIES = [
    {"model_id": "claude-opus-4-6", "input_tokens": 1000, "output_tokens": 500, "cost_usd": 0.0525, "calls": 1},
    {"model_id": "claude-sonnet-4-5", "input_tokens": 2000, "output_tokens": 800, "cost_usd": 0.018, "calls": 2},
    {"model_id": "gpt-4o", "input_tokens": 3000, "output_tokens": 1200, "cost_usd": 0.0195, "calls": 3},
    {"model_id": "gpt-4o-mini", "input_tokens": 5000, "output_tokens": 2000, "cost_usd": 0.00195, "calls": 5},
    {"model_id": "qwen2.5:3b", "input_tokens": 10000, "output_tokens": 4000, "cost_usd": 0.0, "calls": 10},
]


# ---------------------------------------------------------------------------
# Test: _anthropic_usage
# ---------------------------------------------------------------------------

class TestAnthropicUsage(unittest.TestCase):
    """Tests for the anthropic_usage tool handler."""

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_happy_path_filters_claude_only(self, mock_load):
        """Should return only claude models from mixed entries."""
        from src.mcp.servers.api_costs import _anthropic_usage

        mock_load.return_value = _mock_cost_config(workflow_costs=list(_SAMPLE_ENTRIES))
        raw = _anthropic_usage({})
        result = json.loads(raw)

        self.assertEqual(result["provider"], "anthropic")
        # Only 2 entries are anthropic (claude-opus-4-6 + claude-sonnet-4-5)
        self.assertEqual(result["entries_scanned"], 2)
        model_ids = {m["model_id"] for m in result["models"]}
        self.assertEqual(model_ids, {"claude-opus-4-6", "claude-sonnet-4-5"})
        # Grand total = 0.0525 + 0.018
        self.assertAlmostEqual(result["grand_total_usd"], 0.0705, places=6)
        # Models sorted by cost descending
        self.assertEqual(result["models"][0]["model_id"], "claude-opus-4-6")
        self.assertIsNone(result["filter_workflow"])

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_empty_results(self, mock_load):
        """No cost entries at all should return empty models list and zero total."""
        from src.mcp.servers.api_costs import _anthropic_usage

        mock_load.return_value = _mock_cost_config(workflow_costs=[])
        raw = _anthropic_usage({})
        result = json.loads(raw)

        self.assertEqual(result["provider"], "anthropic")
        self.assertEqual(result["models"], [])
        self.assertEqual(result["grand_total_usd"], 0.0)
        self.assertEqual(result["entries_scanned"], 0)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_cost_config_unavailable(self, mock_load):
        """When cost_config cannot be imported, should return error with hint."""
        from src.mcp.servers.api_costs import _anthropic_usage

        mock_load.return_value = None
        raw = _anthropic_usage({})
        result = json.loads(raw)

        self.assertIn("error", result)
        self.assertIn("Cost tracking unavailable", result["error"])
        self.assertIn("hint", result)


# ---------------------------------------------------------------------------
# Test: _openai_usage
# ---------------------------------------------------------------------------

class TestOpenAIUsage(unittest.TestCase):
    """Tests for the openai_usage tool handler."""

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_happy_path_filters_gpt_only(self, mock_load):
        """Should return only GPT models from mixed entries."""
        from src.mcp.servers.api_costs import _openai_usage

        mock_load.return_value = _mock_cost_config(workflow_costs=list(_SAMPLE_ENTRIES))
        raw = _openai_usage({})
        result = json.loads(raw)

        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["entries_scanned"], 2)
        model_ids = {m["model_id"] for m in result["models"]}
        self.assertEqual(model_ids, {"gpt-4o", "gpt-4o-mini"})
        # Grand total = 0.0195 + 0.00195
        self.assertAlmostEqual(result["grand_total_usd"], 0.02145, places=6)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_workflow_id_filter_passed_through(self, mock_load):
        """The workflow_id arg should be forwarded to get_workflow_costs."""
        from src.mcp.servers.api_costs import _openai_usage

        cc = _mock_cost_config(workflow_costs=[
            {"model_id": "gpt-4o", "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.00075, "calls": 1},
        ])
        mock_load.return_value = cc
        raw = _openai_usage({"workflow_id": "signal_generator"})
        result = json.loads(raw)

        cc.get_workflow_costs.assert_called_once_with(workflow_id="signal_generator", limit=100)
        self.assertEqual(result["filter_workflow"], "signal_generator")
        self.assertEqual(result["entries_scanned"], 1)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_cost_config_unavailable(self, mock_load):
        """Should return an error dict when cost_config is None."""
        from src.mcp.servers.api_costs import _openai_usage

        mock_load.return_value = None
        raw = _openai_usage({})
        result = json.loads(raw)

        self.assertIn("error", result)
        self.assertIn("Cost tracking unavailable", result["error"])


# ---------------------------------------------------------------------------
# Test: _combined_cost_summary
# ---------------------------------------------------------------------------

class TestCombinedCostSummary(unittest.TestCase):
    """Tests for the combined_cost_summary tool handler."""

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_happy_path_all_providers(self, mock_load):
        """Should aggregate across anthropic, openai, and local providers."""
        from src.mcp.servers.api_costs import _combined_cost_summary

        mock_load.return_value = _mock_cost_config(
            workflow_costs=list(_SAMPLE_ENTRIES),
            workflow_totals={"signal_generator": 0.05, "revenue_engine": 0.02},
            cost_summary={"models": 5, "tracked": True},
        )
        raw = _combined_cost_summary({})
        result = json.loads(raw)

        # Grand total covers all entries
        expected_total = round(0.0525 + 0.018 + 0.0195 + 0.00195 + 0.0, 6)
        self.assertAlmostEqual(result["grand_total_usd"], expected_total, places=6)
        self.assertEqual(result["entries_scanned"], 5)
        self.assertIsNone(result["filter_workflow"])

        # 3 providers: anthropic, openai, local
        provider_names = {p["provider"] for p in result["by_provider"]}
        self.assertEqual(provider_names, {"anthropic", "openai", "local"})

        # 5 model entries
        self.assertEqual(len(result["by_model"]), 5)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_per_workflow_breakdown_included(self, mock_load):
        """by_workflow key should contain the data from get_total_cost_by_workflow."""
        from src.mcp.servers.api_costs import _combined_cost_summary

        wf_totals = {"signal_generator": 0.042, "revenue_engine": 0.013}
        mock_load.return_value = _mock_cost_config(
            workflow_costs=[],
            workflow_totals=wf_totals,
        )
        raw = _combined_cost_summary({})
        result = json.loads(raw)

        self.assertEqual(result["by_workflow"], wf_totals)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_pricing_reference_included(self, mock_load):
        """pricing_reference key should contain the data from get_cost_summary."""
        from src.mcp.servers.api_costs import _combined_cost_summary

        summary = {"models": 8, "total_input_spend": 1.23}
        mock_load.return_value = _mock_cost_config(
            workflow_costs=[],
            cost_summary=summary,
        )
        raw = _combined_cost_summary({})
        result = json.loads(raw)

        self.assertEqual(result["pricing_reference"], summary)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_local_model_classified_correctly(self, mock_load):
        """qwen2.5:3b (is_local=True) should appear under the 'local' provider."""
        from src.mcp.servers.api_costs import _combined_cost_summary

        mock_load.return_value = _mock_cost_config(workflow_costs=[
            {"model_id": "qwen2.5:3b", "input_tokens": 5000, "output_tokens": 2000, "cost_usd": 0.0, "calls": 3},
        ])
        raw = _combined_cost_summary({})
        result = json.loads(raw)

        providers = {p["provider"] for p in result["by_provider"]}
        self.assertIn("local", providers)
        local_entry = [p for p in result["by_provider"] if p["provider"] == "local"][0]
        self.assertEqual(local_entry["total_calls"], 3)


# ---------------------------------------------------------------------------
# Test: Aggregation logic
# ---------------------------------------------------------------------------

class TestAggregation(unittest.TestCase):
    """Tests for multi-entry aggregation and rounding."""

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_multiple_entries_same_model_summed(self, mock_load):
        """Two entries for the same model should be aggregated into one total."""
        from src.mcp.servers.api_costs import _anthropic_usage

        entries = [
            {"model_id": "claude-opus-4-6", "input_tokens": 1000, "output_tokens": 500, "cost_usd": 0.0525, "calls": 1},
            {"model_id": "claude-opus-4-6", "input_tokens": 2000, "output_tokens": 800, "cost_usd": 0.075, "calls": 2},
        ]
        mock_load.return_value = _mock_cost_config(workflow_costs=entries)
        raw = _anthropic_usage({})
        result = json.loads(raw)

        # Should be one aggregated model entry
        self.assertEqual(len(result["models"]), 1)
        model = result["models"][0]
        self.assertEqual(model["model_id"], "claude-opus-4-6")
        self.assertEqual(model["total_input_tokens"], 3000)
        self.assertEqual(model["total_output_tokens"], 1300)
        self.assertEqual(model["total_calls"], 3)
        self.assertAlmostEqual(model["total_cost_usd"], 0.1275, places=6)

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_costs_rounded_to_6_decimals(self, mock_load):
        """Cost values with more than 6 decimal places should be rounded."""
        from src.mcp.servers.api_costs import _openai_usage

        # 0.0000001 + 0.0000002 = 0.0000003 — should round to 6 decimals
        entries = [
            {"model_id": "gpt-4o", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.00000017, "calls": 1},
            {"model_id": "gpt-4o", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.00000023, "calls": 1},
        ]
        mock_load.return_value = _mock_cost_config(workflow_costs=entries)
        raw = _openai_usage({})
        result = json.loads(raw)

        model = result["models"][0]
        # 0.00000017 + 0.00000023 = 0.0000004 → rounded to 6 decimals = 0.0
        self.assertEqual(model["total_cost_usd"], round(0.0000004, 6))
        self.assertEqual(result["grand_total_usd"], round(0.0000004, 6))


# ---------------------------------------------------------------------------
# Test: MCP stdio protocol
# ---------------------------------------------------------------------------

class TestMCPProtocol(unittest.TestCase):
    """Tests for the JSON-RPC stdio main() loop."""

    def _run_main(self, messages: list[dict]) -> list[dict]:
        """Feed JSON-RPC messages into main() and capture responses."""
        from src.mcp.servers.api_costs import main

        stdin_data = "\n".join(json.dumps(m) for m in messages) + "\n"
        captured = StringIO()

        with patch("sys.stdin", StringIO(stdin_data)), patch("sys.stdout", captured):
            main()

        captured.seek(0)
        responses = []
        for line in captured:
            line = line.strip()
            if line:
                responses.append(json.loads(line))
        return responses

    def test_initialize_response(self):
        """Initialize should echo protocolVersion and report server info."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        ])

        self.assertEqual(len(responses), 1)
        r = responses[0]
        self.assertEqual(r["id"], 1)
        self.assertEqual(r["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(r["result"]["serverInfo"]["name"], "api-costs")
        self.assertEqual(r["result"]["serverInfo"]["version"], "1.0.0")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_tools_list_returns_three_tools(self):
        """tools/list should return exactly 3 tool definitions."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        ])

        self.assertEqual(len(responses), 1)
        tools = responses[0]["result"]["tools"]
        self.assertEqual(len(tools), 3)
        names = {t["name"] for t in tools}
        self.assertEqual(names, {"anthropic_usage", "openai_usage", "combined_cost_summary"})

    @patch("src.mcp.servers.api_costs._load_cost_config")
    def test_tools_call_dispatches_correctly(self, mock_load):
        """tools/call with a known tool name should dispatch and return content."""
        mock_load.return_value = _mock_cost_config(workflow_costs=[])

        responses = self._run_main([
            {
                "jsonrpc": "2.0", "id": 42,
                "method": "tools/call",
                "params": {"name": "anthropic_usage", "arguments": {}},
            },
        ])

        self.assertEqual(len(responses), 1)
        r = responses[0]
        self.assertEqual(r["id"], 42)
        content = r["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        # Should be valid JSON inside
        parsed = json.loads(content[0]["text"])
        self.assertEqual(parsed["provider"], "anthropic")

    def test_unknown_tool_returns_error(self):
        """tools/call with an unknown tool name should return a JSON-RPC error."""
        responses = self._run_main([
            {
                "jsonrpc": "2.0", "id": 99,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
        ])

        self.assertEqual(len(responses), 1)
        r = responses[0]
        self.assertEqual(r["id"], 99)
        self.assertIn("error", r)
        self.assertEqual(r["error"]["code"], -32601)
        self.assertIn("nonexistent_tool", r["error"]["message"])

    def test_ping_returns_empty_result(self):
        """ping method should return an empty result object."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 7, "method": "ping"},
        ])

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 7)
        self.assertEqual(responses[0]["result"], {})

    def test_notifications_ignored(self):
        """Messages without an id (notifications) should be silently ignored."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        ])

        # Only the ping (which has an id) should produce a response
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 1)

    def test_unknown_method_returns_error(self):
        """An unrecognized method should return -32601 error."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 5, "method": "completions/complete"},
        ])

        self.assertEqual(len(responses), 1)
        r = responses[0]
        self.assertEqual(r["error"]["code"], -32601)
        self.assertIn("completions/complete", r["error"]["message"])


if __name__ == "__main__":
    unittest.main()
