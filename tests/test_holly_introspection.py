"""Tests for Holly Grace system introspection tools.

Verifies the 6 new tools that give Holly visibility into her own system:
- query_registered_tools
- query_mcp_servers
- query_agents
- query_workflows
- query_hierarchy_gate
- query_scheduled_jobs
"""

import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field


# =========================================================================
# 1. query_registered_tools
# =========================================================================

class TestQueryRegisteredTools(unittest.TestCase):

    @patch("src.tool_registry.get_tool_registry")
    def test_returns_all_tools(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.to_dicts.return_value = [
            {"tool_id": "t1", "display_name": "T1", "description": "d1", "category": "shopify", "provider": "python"},
            {"tool_id": "t2", "display_name": "T2", "description": "d2", "category": "stripe", "provider": "python"},
            {"tool_id": "t3", "display_name": "T3", "description": "d3", "category": "mcp", "provider": "mcp"},
        ]
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_registered_tools
        result = query_registered_tools()

        self.assertEqual(result["count"], 3)
        self.assertIn("shopify", result["categories"])
        self.assertIn("stripe", result["categories"])
        self.assertIn("mcp", result["categories"])

    @patch("src.tool_registry.get_tool_registry")
    def test_filters_by_category(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.to_dicts.return_value = [
            {"tool_id": "t1", "display_name": "T1", "description": "d1", "category": "shopify", "provider": "python"},
            {"tool_id": "t2", "display_name": "T2", "description": "d2", "category": "stripe", "provider": "python"},
        ]
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_registered_tools
        result = query_registered_tools(category="shopify")

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tools"][0]["tool_id"], "t1")

    @patch("src.tool_registry.get_tool_registry")
    def test_empty_result(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.to_dicts.return_value = []
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_registered_tools
        result = query_registered_tools()

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["tools"], [])


# =========================================================================
# 2. query_mcp_servers
# =========================================================================

class TestQueryMcpServers(unittest.TestCase):

    @patch("src.mcp.store.list_tools")
    @patch("src.mcp.store.list_servers")
    def test_returns_servers_with_tool_counts(self, mock_list_svr, mock_list_tools):
        mock_list_svr.return_value = [
            {
                "server_id": "github-reader",
                "display_name": "GitHub Reader",
                "transport": "stdio",
                "enabled": True,
                "last_health_status": "healthy",
                "last_health_error": None,
            },
        ]
        mock_list_tools.return_value = [
            {"tool_id": "t1", "enabled": True},
            {"tool_id": "t2", "enabled": True},
            {"tool_id": "t3", "enabled": False},
        ]

        from src.holly.tools import query_mcp_servers
        result = query_mcp_servers()

        self.assertEqual(result["count"], 1)
        server = result["servers"][0]
        self.assertEqual(server["server_id"], "github-reader")
        self.assertEqual(server["tool_count"], 3)
        self.assertEqual(server["enabled_tool_count"], 2)
        self.assertEqual(server["health_status"], "healthy")

    @patch("src.mcp.store.list_servers")
    def test_empty_servers(self, mock_list_svr):
        mock_list_svr.return_value = []

        from src.holly.tools import query_mcp_servers
        result = query_mcp_servers()

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["servers"], [])

    @patch("src.mcp.store.list_servers", side_effect=Exception("DB down"))
    def test_error_handling(self, mock_list_svr):
        from src.holly.tools import query_mcp_servers
        result = query_mcp_servers()

        self.assertIn("error", result)
        self.assertIn("DB down", result["error"])


# =========================================================================
# 3. query_agents
# =========================================================================

@dataclass
class FakeAgentConfig:
    agent_id: str
    display_name: str
    description: str
    model_id: str
    channel_id: str = ""
    tool_ids: list = field(default_factory=list)
    version: int = 1
    is_builtin: bool = True


class TestQueryAgents(unittest.TestCase):

    @patch("src.agent_registry.get_registry")
    def test_returns_all_agents(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get_all.return_value = [
            FakeAgentConfig("orchestrator", "Orchestrator", "Routes tasks", "ollama/qwen2.5:3b"),
            FakeAgentConfig("sales", "Sales", "Sales agent", "gpt-4o", tool_ids=["shopify_list", "stripe_charge"]),
        ]
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_agents
        result = query_agents()

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["agents"][0]["agent_id"], "orchestrator")
        self.assertEqual(result["agents"][1]["tool_count"], 2)

    @patch("src.agent_registry.get_registry")
    def test_returns_specific_agent(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get_all.return_value = [
            FakeAgentConfig("orchestrator", "Orchestrator", "Routes tasks", "ollama/qwen2.5:3b",
                            tool_ids=["t1", "t2"]),
        ]
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_agents
        result = query_agents(agent_id="orchestrator")

        self.assertEqual(result["agent_id"], "orchestrator")
        self.assertEqual(result["tool_ids"], ["t1", "t2"])
        self.assertNotIn("agents", result)  # single agent, not a list

    @patch("src.agent_registry.get_registry")
    def test_unknown_agent(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get_all.return_value = []
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_agents
        result = query_agents(agent_id="nonexistent")

        self.assertIn("error", result)
        self.assertIn("nonexistent", result["error"])


# =========================================================================
# 4. query_workflows
# =========================================================================

class TestQueryWorkflows(unittest.TestCase):

    @patch("src.workflow_registry.get_workflow_registry")
    def test_returns_all_workflows(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get_all.return_value = [
            {"workflow_id": "default", "display_name": "Default", "description": "Main", "is_active": True, "version": 1},
            {"workflow_id": "solana_mining", "display_name": "Solana Mining", "description": "Mining", "is_active": True, "version": 2},
        ]
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_workflows
        result = query_workflows()

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["workflows"][1]["workflow_id"], "solana_mining")

    @patch("src.workflow_registry.get_workflow_registry")
    def test_returns_specific_workflow(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get.return_value = {
            "workflow_id": "default",
            "display_name": "Default",
            "description": "Main workflow",
            "is_active": True,
            "version": 3,
            "definition": {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"id": "e1"}]},
        }
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_workflows
        result = query_workflows(workflow_id="default")

        self.assertEqual(result["workflow_id"], "default")
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["edge_count"], 1)

    @patch("src.workflow_registry.get_workflow_registry")
    def test_unknown_workflow(self, mock_get_reg):
        mock_reg = MagicMock()
        mock_reg.get.return_value = None
        mock_get_reg.return_value = mock_reg

        from src.holly.tools import query_workflows
        result = query_workflows(workflow_id="nonexistent")

        self.assertIn("error", result)


# =========================================================================
# 5. query_hierarchy_gate
# =========================================================================

@dataclass
class FakeGateStatus:
    level: int
    is_open: bool = True
    failing_predicates: list = field(default_factory=list)
    timestamp: object = None


@dataclass
class FakePredicate:
    index: int
    name: str
    level: int


class TestQueryHierarchyGate(unittest.TestCase):

    @patch("src.hierarchy.store.get_all_predicates")
    @patch("src.hierarchy.store.get_gate_status")
    def test_all_gates_open(self, mock_gate, mock_preds):
        mock_gate.return_value = [
            FakeGateStatus(level=i) for i in range(7)
        ]
        mock_preds.return_value = [FakePredicate(i, f"f{i}", 0) for i in range(37)]

        from src.holly.tools import query_hierarchy_gate
        result = query_hierarchy_gate()

        self.assertEqual(result["overall"], "open")
        self.assertEqual(result["total_predicates"], 37)
        self.assertEqual(result["total_failing"], 0)
        self.assertEqual(len(result["levels"]), 7)

    @patch("src.hierarchy.store.get_all_predicates")
    @patch("src.hierarchy.store.get_gate_status")
    def test_some_gates_blocked(self, mock_gate, mock_preds):
        mock_gate.return_value = [
            FakeGateStatus(level=0),
            FakeGateStatus(level=1),
            FakeGateStatus(level=2, is_open=False, failing_predicates=[5, 6]),
            FakeGateStatus(level=3),
            FakeGateStatus(level=4),
            FakeGateStatus(level=5, is_open=False, failing_predicates=[30]),
            FakeGateStatus(level=6),
        ]
        mock_preds.return_value = [FakePredicate(i, f"f{i}", 0) for i in range(37)]

        from src.holly.tools import query_hierarchy_gate
        result = query_hierarchy_gate()

        self.assertEqual(result["overall"], "blocked")
        self.assertEqual(result["total_failing"], 3)
        # Level 2 has 2 failing
        self.assertEqual(result["levels"][2]["failing_count"], 2)
        self.assertFalse(result["levels"][2]["is_open"])

    @patch("src.hierarchy.store.get_gate_status", side_effect=Exception("DB down"))
    def test_error_handling(self, mock_gate):
        from src.holly.tools import query_hierarchy_gate
        result = query_hierarchy_gate()

        self.assertIn("error", result)


# =========================================================================
# 6. query_scheduled_jobs
# =========================================================================

class TestQueryScheduledJobs(unittest.TestCase):

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_returns_jobs(self, mock_get_sched):
        mock_sched = MagicMock()
        mock_job1 = MagicMock()
        mock_job1.id = "order_check"
        mock_job1.next_run_time = "2026-02-10 12:00:00"
        mock_job1.trigger = "interval[0:30:00]"
        mock_job2 = MagicMock()
        mock_job2.id = "health_check"
        mock_job2.next_run_time = "2026-02-10 12:15:00"
        mock_job2.trigger = "interval[0:15:00]"
        mock_sched.jobs = [mock_job1, mock_job2]
        mock_get_sched.return_value = mock_sched

        from src.holly.tools import query_scheduled_jobs
        result = query_scheduled_jobs()

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["jobs"][0]["id"], "order_check")
        self.assertEqual(result["jobs"][1]["id"], "health_check")

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_scheduler_not_initialized(self, mock_get_sched):
        mock_get_sched.return_value = None

        from src.holly.tools import query_scheduled_jobs
        result = query_scheduled_jobs()

        self.assertIn("error", result)
        self.assertIn("not initialized", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler", side_effect=Exception("crash"))
    def test_scheduler_error(self, mock_get_sched):
        from src.holly.tools import query_scheduled_jobs
        result = query_scheduled_jobs()

        self.assertIn("error", result)


# =========================================================================
# 7. Tool registration verification
# =========================================================================

class TestToolRegistration(unittest.TestCase):

    def test_all_introspection_tools_in_registry(self):
        from src.holly.tools import HOLLY_TOOLS
        expected = [
            "query_registered_tools",
            "query_mcp_servers",
            "query_agents",
            "query_workflows",
            "query_hierarchy_gate",
            "query_scheduled_jobs",
        ]
        for name in expected:
            self.assertIn(name, HOLLY_TOOLS, f"{name} missing from HOLLY_TOOLS")

    def test_all_introspection_tools_have_schemas(self):
        from src.holly.tools import HOLLY_TOOL_SCHEMAS
        schema_names = {s["name"] for s in HOLLY_TOOL_SCHEMAS}
        expected = [
            "query_registered_tools",
            "query_mcp_servers",
            "query_agents",
            "query_workflows",
            "query_hierarchy_gate",
            "query_scheduled_jobs",
        ]
        for name in expected:
            self.assertIn(name, schema_names, f"{name} missing from HOLLY_TOOL_SCHEMAS")

    def test_holly_now_has_17_tools(self):
        from src.holly.tools import HOLLY_TOOLS
        self.assertEqual(len(HOLLY_TOOLS), 17)


if __name__ == "__main__":
    unittest.main()
