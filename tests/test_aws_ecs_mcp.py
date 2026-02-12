"""Tests for the AWS ECS MCP server (src/mcp/servers/aws_ecs.py).

Covers all 5 tool handlers, utility functions (_redact_env, _serialize),
and the MCP stdio JSON-RPC protocol (initialize, ping, tools/list, tools/call).

~30 tests using unittest.TestCase with mock.patch for boto3 client isolation.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, date
from io import StringIO
from unittest.mock import MagicMock, patch

from src.mcp.servers.aws_ecs import (
    _describe_service,
    _describe_task_definition,
    _get_service_events,
    _get_task_logs,
    _list_tasks,
    _redact_env,
    _serialize,
    _TOOLS,
    _TOOL_DISPATCH,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(raw: str) -> dict:
    """Parse a JSON string returned by a handler."""
    return json.loads(raw)


def _run_mcp(lines: list[str]) -> list[dict]:
    """Feed JSON-RPC messages through main() and return parsed responses."""
    stdin_text = "\n".join(json.dumps(m) for m in lines) + "\n"
    with patch("sys.stdin", StringIO(stdin_text)), \
         patch("sys.stdout", new_callable=StringIO) as mock_out:
        main()
        raw_lines = mock_out.getvalue().strip().split("\n")
        return [json.loads(r) for r in raw_lines if r.strip()]


# ===========================================================================
# 1. _redact_env
# ===========================================================================

class TestRedactEnv(unittest.TestCase):

    def test_redacts_key(self):
        env = [{"name": "API_KEY", "value": "abc123"}]
        result = _redact_env(env)
        self.assertEqual(result[0]["value"], "***REDACTED***")

    def test_redacts_secret(self):
        env = [{"name": "CLIENT_SECRET", "value": "s3cret"}]
        result = _redact_env(env)
        self.assertEqual(result[0]["value"], "***REDACTED***")

    def test_redacts_token(self):
        env = [{"name": "AUTH_TOKEN", "value": "tok"}]
        result = _redact_env(env)
        self.assertEqual(result[0]["value"], "***REDACTED***")

    def test_redacts_password(self):
        env = [{"name": "DB_PASSWORD", "value": "p@ss"}]
        result = _redact_env(env)
        self.assertEqual(result[0]["value"], "***REDACTED***")

    def test_passes_safe_names(self):
        env = [
            {"name": "APP_NAME", "value": "holly"},
            {"name": "LOG_LEVEL", "value": "INFO"},
            {"name": "AWS_REGION", "value": "us-east-2"},
        ]
        result = _redact_env(env)
        self.assertEqual(result[0]["value"], "holly")
        self.assertEqual(result[1]["value"], "INFO")
        self.assertEqual(result[2]["value"], "us-east-2")

    def test_case_insensitive_name_match(self):
        env = [{"name": "secret_key", "value": "val"}]
        result = _redact_env(env)
        # The code upper-cases the name, so "secret_key" -> "SECRET_KEY" hits both SECRET and KEY
        self.assertEqual(result[0]["value"], "***REDACTED***")

    def test_empty_list(self):
        self.assertEqual(_redact_env([]), [])


# ===========================================================================
# 2. _serialize
# ===========================================================================

class TestSerialize(unittest.TestCase):

    def test_datetime_converted(self):
        dt = datetime(2026, 2, 10, 14, 30, 0)
        self.assertEqual(_serialize(dt), "2026-02-10T14:30:00")

    def test_date_converted(self):
        d = date(2026, 2, 10)
        self.assertEqual(_serialize(d), "2026-02-10")

    def test_nested_dict(self):
        obj = {"a": {"ts": datetime(2026, 1, 1)}}
        result = _serialize(obj)
        self.assertEqual(result, {"a": {"ts": "2026-01-01T00:00:00"}})

    def test_list(self):
        obj = [datetime(2026, 1, 1), "plain"]
        result = _serialize(obj)
        self.assertEqual(result, ["2026-01-01T00:00:00", "plain"])

    def test_tuple_becomes_list(self):
        obj = (datetime(2026, 1, 1),)
        result = _serialize(obj)
        self.assertEqual(result, ["2026-01-01T00:00:00"])

    def test_passthrough(self):
        self.assertEqual(_serialize(42), 42)
        self.assertEqual(_serialize("hello"), "hello")
        self.assertIsNone(_serialize(None))


# ===========================================================================
# 3. _describe_service
# ===========================================================================

class TestDescribeService(unittest.TestCase):

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_happy_path(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [{
                "serviceName": "holly-grace",
                "status": "ACTIVE",
                "runningCount": 1,
                "desiredCount": 1,
                "pendingCount": 0,
                "launchType": "FARGATE",
                "deployments": [{
                    "id": "ecs-svc/123",
                    "status": "PRIMARY",
                    "taskDefinition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4",
                    "runningCount": 1,
                    "desiredCount": 1,
                    "pendingCount": 0,
                    "rolloutState": "COMPLETED",
                    "createdAt": datetime(2026, 2, 10, 12, 0, 0),
                }],
                "events": [{
                    "createdAt": datetime(2026, 2, 10, 12, 5, 0),
                    "message": "service has reached a steady state.",
                }],
            }]
        }

        result = _parse(_describe_service({}))
        self.assertEqual(result["serviceName"], "holly-grace")
        self.assertEqual(result["runningCount"], 1)
        self.assertEqual(len(result["deployments"]), 1)
        self.assertEqual(result["deployments"][0]["status"], "PRIMARY")
        self.assertEqual(len(result["recentEvents"]), 1)
        # datetime should be serialized
        self.assertIsInstance(result["deployments"][0]["createdAt"], str)

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_service_not_found(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {"services": []}

        result = _parse(_describe_service({"service": "ghost"}))
        self.assertIn("error", result)
        self.assertIn("ghost", result["error"])

    @patch("src.mcp.servers.aws_ecs._get_ecs_client", side_effect=ImportError)
    def test_boto3_not_installed(self, _):
        result = _parse(_describe_service({}))
        self.assertIn("error", result)
        self.assertIn("boto3", result["error"])

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_general_exception(self, mock_client_fn):
        mock_client_fn.side_effect = RuntimeError("connection timeout")
        result = _parse(_describe_service({}))
        self.assertIn("error", result)
        self.assertIn("connection timeout", result["error"])


# ===========================================================================
# 4. _list_tasks
# ===========================================================================

class TestListTasks(unittest.TestCase):

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_happy_path(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs

        task_arn = "arn:aws:ecs:us-east-2:327416545926:task/holly-grace-cluster/abc123"
        mock_ecs.list_tasks.return_value = {"taskArns": [task_arn]}
        mock_ecs.describe_tasks.return_value = {
            "tasks": [{
                "taskArn": task_arn,
                "lastStatus": "RUNNING",
                "healthStatus": "HEALTHY",
                "desiredStatus": "RUNNING",
                "startedAt": datetime(2026, 2, 10, 10, 0, 0),
                "stoppedAt": None,
                "stoppedReason": "",
                "containers": [{
                    "name": "holly-grace",
                    "lastStatus": "RUNNING",
                    "healthStatus": "HEALTHY",
                    "exitCode": None,
                }],
                "cpu": "256",
                "memory": "512",
            }]
        }

        result = _parse(_list_tasks({}))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tasks"][0]["healthStatus"], "HEALTHY")
        self.assertEqual(result["tasks"][0]["containers"][0]["name"], "holly-grace")

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_empty_tasks(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.list_tasks.return_value = {"taskArns": []}

        result = _parse(_list_tasks({}))
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["tasks"], [])

    @patch("src.mcp.servers.aws_ecs._get_ecs_client", side_effect=ImportError)
    def test_boto3_not_installed(self, _):
        result = _parse(_list_tasks({}))
        self.assertIn("boto3", result["error"])


# ===========================================================================
# 5. _get_task_logs
# ===========================================================================

class TestGetTaskLogs(unittest.TestCase):

    @patch("src.mcp.servers.aws_ecs._get_logs_client")
    def test_happy_path_with_stream(self, mock_logs_fn):
        mock_logs = MagicMock()
        mock_logs_fn.return_value = mock_logs
        mock_logs.get_log_events.return_value = {
            "events": [
                {"timestamp": 1707580000000, "message": "INFO: started\n"},
                {"timestamp": 1707580001000, "message": "INFO: healthy\n"},
            ]
        }

        result = _parse(_get_task_logs({"log_stream": "ecs/holly/abc123", "lines": "5"}))
        self.assertEqual(result["logStream"], "ecs/holly/abc123")
        self.assertEqual(result["lines_returned"], 2)
        # Messages should be rstripped
        self.assertEqual(result["events"][0]["message"], "INFO: started")

    @patch("src.mcp.servers.aws_ecs._get_logs_client")
    def test_auto_discovers_latest_stream(self, mock_logs_fn):
        mock_logs = MagicMock()
        mock_logs_fn.return_value = mock_logs
        mock_logs.describe_log_streams.return_value = {
            "logStreams": [{"logStreamName": "ecs/holly/latest-stream"}]
        }
        mock_logs.get_log_events.return_value = {"events": []}

        result = _parse(_get_task_logs({}))  # no log_stream in args
        self.assertEqual(result["logStream"], "ecs/holly/latest-stream")
        mock_logs.describe_log_streams.assert_called_once()

    @patch("src.mcp.servers.aws_ecs._get_logs_client")
    def test_no_streams_found(self, mock_logs_fn):
        mock_logs = MagicMock()
        mock_logs_fn.return_value = mock_logs
        mock_logs.describe_log_streams.return_value = {"logStreams": []}

        result = _parse(_get_task_logs({}))
        self.assertIn("error", result)
        self.assertIn("No log streams found", result["error"])

    @patch("src.mcp.servers.aws_ecs._get_logs_client", side_effect=ImportError)
    def test_boto3_not_installed(self, _):
        result = _parse(_get_task_logs({}))
        self.assertIn("boto3", result["error"])


# ===========================================================================
# 6. _describe_task_definition
# ===========================================================================

class TestDescribeTaskDefinition(unittest.TestCase):

    def _make_task_def_response(self):
        return {
            "taskDefinition": {
                "taskDefinitionArn": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4",
                "family": "holly-grace-holly-grace",
                "revision": 4,
                "status": "ACTIVE",
                "cpu": "256",
                "memory": "512",
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
                "executionRoleArn": "arn:aws:iam::role/ecsTaskExecutionRole",
                "taskRoleArn": "arn:aws:iam::role/ecsTaskRole",
                "containerDefinitions": [{
                    "name": "holly-grace",
                    "image": "327416545926.dkr.ecr.us-east-2.amazonaws.com/holly-grace/holly-grace:v11",
                    "cpu": 256,
                    "memory": 512,
                    "essential": True,
                    "portMappings": [{"containerPort": 8050}],
                    "environment": [
                        {"name": "APP_NAME", "value": "holly-grace"},
                        {"name": "ANTHROPIC_API_KEY", "value": "sk-ant-LIVE"},
                        {"name": "STRIPE_SECRET_KEY", "value": "sk_live_xxx"},
                        {"name": "DB_PASSWORD", "value": "hunter2"},
                        {"name": "AUTH_TOKEN", "value": "tok123"},
                        {"name": "LOG_LEVEL", "value": "INFO"},
                    ],
                    "secrets": [
                        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:ssm:param/openai"},
                    ],
                    "logConfiguration": {"logDriver": "awslogs"},
                    "healthCheck": {"command": ["CMD-SHELL", "curl -f http://localhost:8050/health"]},
                    "command": None,
                    "entryPoint": None,
                }],
            }
        }

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_auto_detect_from_service(self, mock_client_fn):
        """When no explicit task_definition ARN is given, look it up from the service."""
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs

        mock_ecs.describe_services.return_value = {
            "services": [{
                "taskDefinition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4"
            }]
        }
        mock_ecs.describe_task_definition.return_value = self._make_task_def_response()

        result = _parse(_describe_task_definition({}))
        self.assertEqual(result["family"], "holly-grace-holly-grace")
        self.assertEqual(result["revision"], 4)
        # Verify the describe_services was called for auto-detection
        mock_ecs.describe_services.assert_called_once()

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_explicit_arn(self, mock_client_fn):
        """When an explicit task_definition ARN is provided, skip the service lookup."""
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_task_definition.return_value = self._make_task_def_response()

        result = _parse(_describe_task_definition({
            "task_definition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4"
        }))
        self.assertEqual(result["family"], "holly-grace-holly-grace")
        # describe_services should NOT be called when explicit ARN given
        mock_ecs.describe_services.assert_not_called()

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_env_redaction(self, mock_client_fn):
        """Environment variables with KEY/SECRET/TOKEN/PASSWORD should be redacted."""
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_task_definition.return_value = self._make_task_def_response()

        result = _parse(_describe_task_definition({
            "task_definition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4"
        }))

        env_vars = result["containerDefinitions"][0]["environment"]
        env_map = {e["name"]: e["value"] for e in env_vars}

        # Safe env vars pass through
        self.assertEqual(env_map["APP_NAME"], "holly-grace")
        self.assertEqual(env_map["LOG_LEVEL"], "INFO")

        # Sensitive env vars are redacted
        self.assertEqual(env_map["ANTHROPIC_API_KEY"], "***REDACTED***")
        self.assertEqual(env_map["STRIPE_SECRET_KEY"], "***REDACTED***")
        self.assertEqual(env_map["DB_PASSWORD"], "***REDACTED***")
        self.assertEqual(env_map["AUTH_TOKEN"], "***REDACTED***")

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_secrets_redacted(self, mock_client_fn):
        """Secrets (valueFrom SSM/Secrets Manager) should always be redacted."""
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_task_definition.return_value = self._make_task_def_response()

        result = _parse(_describe_task_definition({
            "task_definition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace:4"
        }))

        secrets = result["containerDefinitions"][0]["secrets"]
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["name"], "OPENAI_API_KEY")
        self.assertEqual(secrets[0]["valueFrom"], "***REDACTED***")

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_service_not_found_during_auto_detect(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {"services": []}

        result = _parse(_describe_task_definition({}))
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    @patch("src.mcp.servers.aws_ecs._get_ecs_client", side_effect=ImportError)
    def test_boto3_not_installed(self, _):
        result = _parse(_describe_task_definition({}))
        self.assertIn("boto3", result["error"])


# ===========================================================================
# 7. _get_service_events
# ===========================================================================

class TestGetServiceEvents(unittest.TestCase):

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_happy_path(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [{
                "serviceName": "holly-grace",
                "events": [
                    {"id": "evt-1", "createdAt": datetime(2026, 2, 10, 12, 0), "message": "steady state."},
                    {"id": "evt-2", "createdAt": datetime(2026, 2, 10, 11, 0), "message": "started 1 tasks."},
                ],
            }]
        }

        result = _parse(_get_service_events({"count": "5"}))
        self.assertEqual(result["serviceName"], "holly-grace")
        self.assertEqual(result["events_requested"], 5)
        self.assertEqual(result["events_returned"], 2)
        self.assertEqual(result["events"][0]["id"], "evt-1")

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_service_not_found(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {"services": []}

        result = _parse(_get_service_events({"service": "ghost"}))
        self.assertIn("error", result)
        self.assertIn("ghost", result["error"])


# ===========================================================================
# 8. MCP Protocol (main stdio loop)
# ===========================================================================

class TestMCPProtocol(unittest.TestCase):

    def test_initialize_response(self):
        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        ])
        self.assertEqual(len(responses), 1)
        r = responses[0]["result"]
        self.assertEqual(r["protocolVersion"], "2025-11-25")
        self.assertEqual(r["serverInfo"]["name"], "aws-ecs")
        self.assertIn("tools", r["capabilities"])

    def test_tools_list_returns_five_tools(self):
        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        ])
        tools = responses[0]["result"]["tools"]
        self.assertEqual(len(tools), 5)
        tool_names = {t["name"] for t in tools}
        self.assertEqual(tool_names, {"describe_service", "list_tasks", "get_task_logs",
                                       "describe_task_definition", "get_service_events"})

    @patch("src.mcp.servers.aws_ecs._get_ecs_client")
    def test_tools_call_dispatches_correctly(self, mock_client_fn):
        mock_ecs = MagicMock()
        mock_client_fn.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [{
                "serviceName": "holly-grace",
                "status": "ACTIVE",
                "runningCount": 1,
                "desiredCount": 1,
                "pendingCount": 0,
                "launchType": "FARGATE",
                "deployments": [],
                "events": [],
            }]
        }

        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "describe_service", "arguments": {}}},
        ])
        content = responses[0]["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        payload = json.loads(content[0]["text"])
        self.assertEqual(payload["serviceName"], "holly-grace")

    def test_unknown_tool_error(self):
        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "nonexistent_tool", "arguments": {}}},
        ])
        self.assertIn("error", responses[0])
        self.assertIn("Unknown tool", responses[0]["error"]["message"])

    def test_ping_response(self):
        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 99, "method": "ping"},
        ])
        self.assertEqual(responses[0]["id"], 99)
        self.assertEqual(responses[0]["result"], {})

    def test_unknown_method(self):
        responses = _run_mcp([
            {"jsonrpc": "2.0", "id": 1, "method": "foo/bar"},
        ])
        self.assertIn("error", responses[0])
        self.assertIn("Unknown method", responses[0]["error"]["message"])

    def test_notifications_ignored(self):
        """Messages without an id (notifications) should produce no response."""
        responses = _run_mcp([
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ])
        self.assertEqual(len(responses), 0)

    def test_tool_dispatch_map_matches_tools_list(self):
        """Every tool name in _TOOLS must have a corresponding handler in _TOOL_DISPATCH."""
        tool_names = {t["name"] for t in _TOOLS}
        dispatch_names = set(_TOOL_DISPATCH.keys())
        self.assertEqual(tool_names, dispatch_names)


if __name__ == "__main__":
    unittest.main()
