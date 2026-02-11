"""Tests for Phase 1: Give Holly Eyes — GitHub Reader MCP + Crew Routing.

Covers:
1. GitHub Reader MCP server protocol and tool dispatch
2. MCP server seed function (idempotent registration)
3. Crew agent tool bindings (5 agents have GitHub reader tools)
4. Crew workflow routing (dispatch_crew uses crew_solo_ prefix)
5. TowerWorker graph selection (crew_solo_ → dynamic graph)
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# 1. GitHub Reader MCP Server — protocol tests
# =========================================================================

def _send_mcp_messages(messages: list[dict], timeout: float = 10.0) -> list[dict]:
    """Start the GitHub reader MCP server and send JSON-RPC messages via stdin."""
    input_text = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, "-m", "src.mcp.servers.github_reader"],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    responses = []
    for line in proc.stdout.strip().split("\n"):
        line = line.strip()
        if line:
            responses.append(json.loads(line))
    return responses


class TestGitHubReaderMcpProtocol:
    """Tests for the MCP stdio server protocol."""

    def test_initialize_response(self):
        """Server responds to initialize with capabilities."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        ])
        assert len(responses) == 1
        result = responses[0]["result"]
        assert result["protocolVersion"] == "2025-11-25"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "github-reader"

    def test_tools_list_returns_5_tools(self):
        """Server lists exactly 5 tools."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ])
        tools_response = responses[1]
        tools = tools_response["result"]["tools"]
        assert len(tools) == 5
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"read_file", "list_directory", "search_code", "list_branches", "get_file_tree"}

    def test_tools_have_input_schemas(self):
        """Each tool has a valid inputSchema."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ])
        tools = responses[1]["result"]["tools"]
        for tool in tools:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]

    def test_ping_response(self):
        """Server responds to ping."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}},
        ])
        assert responses[1]["result"] == {}

    def test_unknown_tool_returns_error(self):
        """Calling an unknown tool returns an error."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nonexistent", "arguments": {}}},
        ])
        assert "error" in responses[1]

    def test_read_file_missing_path_returns_error(self):
        """read_file without path argument returns an error in content."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "read_file", "arguments": {}}},
        ])
        result = responses[1]["result"]
        content_text = result["content"][0]["text"]
        parsed = json.loads(content_text)
        assert "error" in parsed

    def test_search_code_missing_query_returns_error(self):
        """search_code without query argument returns an error in content."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "search_code", "arguments": {}}},
        ])
        result = responses[1]["result"]
        content_text = result["content"][0]["text"]
        parsed = json.loads(content_text)
        assert "error" in parsed

    def test_unknown_method_returns_error(self):
        """Unknown method returns JSON-RPC error."""
        responses = _send_mcp_messages([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "nonexistent/method", "params": {}},
        ])
        assert "error" in responses[1]


# =========================================================================
# 2. MCP server seed function
# =========================================================================

class TestSeedGitHubReader:
    """Tests for the seed_github_reader() function."""

    @patch("src.mcp.store.get_server")
    @patch("src.mcp.store.create_server")
    @patch("src.mcp.manager.get_mcp_manager")
    def test_seed_creates_server_if_not_exists(self, mock_mgr, mock_create, mock_get):
        """seed_github_reader creates the server when it doesn't exist."""
        mock_get.return_value = None  # server doesn't exist
        mock_mgr.return_value.sync_tools.return_value = {"tools_synced": 5}

        from src.mcp.servers import seed_github_reader
        seed_github_reader()

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["server_id"] == "github-reader"
        assert call_kwargs.kwargs["transport"] == "stdio"
        assert call_kwargs.kwargs["stdio_command"] == "python3"

    @patch("src.mcp.store.get_server")
    @patch("src.mcp.store.create_server")
    def test_seed_skips_if_already_exists(self, mock_create, mock_get):
        """seed_github_reader is idempotent — skips if server exists."""
        mock_get.return_value = {"server_id": "github-reader"}

        from src.mcp.servers import seed_github_reader
        seed_github_reader()

        mock_create.assert_not_called()

    @patch("src.mcp.store.get_server")
    @patch("src.mcp.store.create_server")
    @patch("src.mcp.manager.get_mcp_manager")
    def test_seed_syncs_tools_after_creation(self, mock_mgr, mock_create, mock_get):
        """After creating the server, sync_tools is called."""
        mock_get.return_value = None
        manager = MagicMock()
        mock_mgr.return_value = manager

        from src.mcp.servers import seed_github_reader
        seed_github_reader()

        manager.sync_tools.assert_called_once_with("github-reader")


# =========================================================================
# 3. Crew agent tool bindings
# =========================================================================

class TestCrewToolBindings:
    """Tests for GitHub reader tool_ids bound to crew agents."""

    def test_architect_has_github_tools(self):
        from src.holly.crew.registry import CREW_AGENTS
        agent = CREW_AGENTS["crew_architect"]
        assert "mcp_github_reader_read_file" in agent.tools
        assert "mcp_github_reader_list_directory" in agent.tools
        assert "mcp_github_reader_search_code" in agent.tools
        assert "mcp_github_reader_get_file_tree" in agent.tools

    def test_system_engineer_has_github_tools(self):
        from src.holly.crew.registry import CREW_AGENTS
        agent = CREW_AGENTS["crew_system_engineer"]
        assert "mcp_github_reader_read_file" in agent.tools
        assert len(agent.tools) == 4

    def test_critic_has_github_tools(self):
        from src.holly.crew.registry import CREW_AGENTS
        agent = CREW_AGENTS["crew_critic"]
        assert "mcp_github_reader_search_code" in agent.tools

    def test_tool_smith_has_github_tools(self):
        from src.holly.crew.registry import CREW_AGENTS
        agent = CREW_AGENTS["crew_tool_smith"]
        assert "mcp_github_reader_read_file" in agent.tools

    def test_mcp_creator_has_github_tools(self):
        from src.holly.crew.registry import CREW_AGENTS
        agent = CREW_AGENTS["crew_mcp_creator"]
        assert "mcp_github_reader_read_file" in agent.tools

    def test_agents_without_tools_still_empty(self):
        """Agents not assigned GitHub tools still have empty tools list."""
        from src.holly.crew.registry import CREW_AGENTS
        no_tool_agents = [
            "crew_test_engineer", "crew_wiring_tech", "crew_program_manager",
            "crew_finance_officer", "crew_lead_researcher", "crew_wise_old_man",
            "crew_epsilon_tuner", "crew_strategic_advisor", "crew_cyber_security",
            "crew_product_manager",
        ]
        for agent_id in no_tool_agents:
            agent = CREW_AGENTS[agent_id]
            assert agent.tools == [], f"{agent_id} should have no tools but has {agent.tools}"

    def test_tool_ids_flow_to_agent_config(self):
        """Crew tool_ids flow through _load_crew_defaults to AgentConfig."""
        from src.agent_registry import _HARDCODED_DEFAULTS
        config = _HARDCODED_DEFAULTS.get("crew_architect")
        assert config is not None
        assert "mcp_github_reader_read_file" in config.tool_ids


# =========================================================================
# 4. Crew workflow routing — dispatch_crew
# =========================================================================

class TestDispatchCrewRouting:
    """Tests for dispatch_crew workflow_id assignment."""

    @patch("src.tower.store.create_run", return_value="test-run-123")
    @patch("src.holly.crew.registry.get_crew_agent")
    def test_dispatch_crew_uses_crew_solo_prefix(self, mock_get, mock_create):
        """dispatch_crew creates run with crew_solo_{agent_id} workflow_id."""
        from src.holly.crew.registry import CrewAgent
        mock_get.return_value = CrewAgent(
            agent_id="crew_architect",
            display_name="Architect",
            role="Designs things",
            system_prompt="You are the architect.",
        )

        from src.holly.tools import dispatch_crew
        result = dispatch_crew("crew_architect", "Design a new workflow")

        assert result["run_id"] == "test-run-123"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["workflow_id"] == "crew_solo_crew_architect"

    @patch("src.tower.store.create_run")
    @patch("src.holly.crew.registry.get_crew_agent")
    def test_dispatch_unknown_agent_returns_error(self, mock_get, mock_create):
        """dispatch_crew returns error for unknown agent."""
        mock_get.return_value = None

        from src.holly.tools import dispatch_crew
        result = dispatch_crew("nonexistent_agent", "Do something")

        assert "error" in result
        mock_create.assert_not_called()


# =========================================================================
# 5. TowerWorker graph selection
# =========================================================================

class TestTowerWorkerGraphSelection:
    """Tests for TowerWorker._get_graph() routing logic."""

    def test_default_workflow_returns_default_graph(self):
        from src.tower.worker import TowerWorker
        mock_graph = MagicMock()
        worker = TowerWorker(mock_graph, router=MagicMock())
        run = {"run_id": "r1", "workflow_id": "default"}
        assert worker._get_graph(run) is mock_graph

    def test_crew_solo_without_router_falls_back_to_default(self):
        """If no router provided, crew_solo_ falls back to default graph."""
        from src.tower.worker import TowerWorker
        mock_graph = MagicMock()
        worker = TowerWorker(mock_graph, router=None)
        run = {"run_id": "r1", "workflow_id": "crew_solo_crew_architect"}
        assert worker._get_graph(run) is mock_graph

    @patch("src.tower.worker.TowerWorker._get_crew_graph")
    def test_crew_solo_with_router_compiles_crew_graph(self, mock_compile):
        """crew_solo_ with router calls _get_crew_graph."""
        from src.tower.worker import TowerWorker
        mock_graph = MagicMock()
        mock_crew_graph = MagicMock()
        mock_compile.return_value = mock_crew_graph

        worker = TowerWorker(mock_graph, router=MagicMock())
        run = {"run_id": "r1", "workflow_id": "crew_solo_crew_architect"}
        result = worker._get_graph(run)

        mock_compile.assert_called_once_with("crew_architect")
        assert result is mock_crew_graph

    def test_other_workflow_ids_return_default(self):
        """Non-crew, non-default workflow_ids still use default graph."""
        from src.tower.worker import TowerWorker
        mock_graph = MagicMock()
        worker = TowerWorker(mock_graph, router=MagicMock())

        for wf_id in ["solana_mining", "app_factory", "custom_wf"]:
            run = {"run_id": "r1", "workflow_id": wf_id}
            assert worker._get_graph(run) is mock_graph

    def test_crew_graph_cache_reuses_compiled_graph(self):
        """Compiled crew graphs are cached by agent_id."""
        from src.tower.worker import TowerWorker
        mock_graph = MagicMock()
        worker = TowerWorker(mock_graph, router=MagicMock())

        # Pre-populate cache
        cached_graph = MagicMock()
        worker._crew_graph_cache["crew_architect"] = cached_graph

        run = {"run_id": "r1", "workflow_id": "crew_solo_crew_architect"}
        result = worker._get_graph(run)
        assert result is cached_graph

    def test_execute_with_timeout_uses_selected_graph(self):
        """_execute_with_timeout passes the selected graph to execute_run."""
        from src.tower.worker import TowerWorker
        mock_default = MagicMock()
        mock_crew = MagicMock()

        worker = TowerWorker(mock_default, router=MagicMock())
        worker._crew_graph_cache["crew_architect"] = mock_crew

        with patch("src.tower.worker.execute_run") as mock_exec:
            run = {"run_id": "r1", "workflow_id": "crew_solo_crew_architect"}
            worker._execute_with_timeout(run)
            mock_exec.assert_called_once_with(mock_crew, run)


# =========================================================================
# 6. MCP naming integration
# =========================================================================

class TestMcpNaming:
    """Verify the naming module generates expected tool_ids."""

    def test_github_reader_tool_id_format(self):
        from src.mcp.naming import mcp_tool_id
        assert mcp_tool_id("github-reader", "read_file") == "mcp_github_reader_read_file"
        assert mcp_tool_id("github-reader", "list_directory") == "mcp_github_reader_list_directory"
        assert mcp_tool_id("github-reader", "search_code") == "mcp_github_reader_search_code"
        assert mcp_tool_id("github-reader", "get_file_tree") == "mcp_github_reader_get_file_tree"
        assert mcp_tool_id("github-reader", "list_branches") == "mcp_github_reader_list_branches"
