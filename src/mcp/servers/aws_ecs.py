"""AWS ECS Observability MCP server — read-only ECS/CloudWatch access.

Stdio MCP server that exposes 5 tools:
- describe_service: Service status, running count, deployments, events
- list_tasks: Task ARNs, health, started time, stopped reason
- get_task_logs: CloudWatch log tail (last N lines)
- describe_task_definition: Container defs and resources (env secrets REDACTED)
- get_service_events: Recent ECS service events

Uses boto3 — imported lazily inside functions.
Runs as: python -m src.mcp.servers.aws_ecs
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Defaults — configurable via env vars
_CLUSTER = os.environ.get("ECS_CLUSTER", "holly-grace-cluster")
_SERVICE = os.environ.get("ECS_SERVICE", "holly-grace")
_REGION = os.environ.get("AWS_REGION", "us-east-2")
_LOG_GROUP = os.environ.get("ECS_LOG_GROUP", "/ecs/holly-grace-holly-grace")

# Env var name fragments that should be redacted in task definitions
_REDACT_KEYWORDS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def _get_ecs_client():
    """Lazily import boto3 and return an ECS client."""
    import boto3
    return boto3.client("ecs", region_name=_REGION)


def _get_logs_client():
    """Lazily import boto3 and return a CloudWatch Logs client."""
    import boto3
    return boto3.client("logs", region_name=_REGION)


def _redact_env(env_list: list[dict]) -> list[dict]:
    """Redact env var values containing sensitive keywords."""
    redacted = []
    for entry in env_list:
        name = entry.get("name", "")
        value = entry.get("value", "")
        upper_name = name.upper()
        if any(kw in upper_name for kw in _REDACT_KEYWORDS):
            redacted.append({"name": name, "value": "***REDACTED***"})
        else:
            redacted.append({"name": name, "value": value})
    return redacted


def _serialize(obj: Any) -> Any:
    """Convert datetime objects for JSON serialization."""
    import datetime
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _describe_service(args: dict) -> str:
    """Describe the ECS service: running count, desired count, deployments, events."""
    try:
        ecs = _get_ecs_client()
        cluster = args.get("cluster", _CLUSTER)
        service = args.get("service", _SERVICE)

        resp = ecs.describe_services(cluster=cluster, services=[service])
        services = resp.get("services", [])
        if not services:
            return json.dumps({"error": f"Service '{service}' not found in cluster '{cluster}'"})

        svc = services[0]
        deployments = []
        for d in svc.get("deployments", []):
            deployments.append({
                "id": d.get("id", ""),
                "status": d.get("status", ""),
                "taskDefinition": d.get("taskDefinition", ""),
                "runningCount": d.get("runningCount", 0),
                "desiredCount": d.get("desiredCount", 0),
                "pendingCount": d.get("pendingCount", 0),
                "rolloutState": d.get("rolloutState", ""),
                "createdAt": d.get("createdAt"),
            })

        events = []
        for e in svc.get("events", [])[:10]:
            events.append({
                "createdAt": e.get("createdAt"),
                "message": e.get("message", ""),
            })

        result = {
            "serviceName": svc.get("serviceName", ""),
            "status": svc.get("status", ""),
            "runningCount": svc.get("runningCount", 0),
            "desiredCount": svc.get("desiredCount", 0),
            "pendingCount": svc.get("pendingCount", 0),
            "launchType": svc.get("launchType", ""),
            "deployments": deployments,
            "recentEvents": events,
        }
        return json.dumps(_serialize(result))

    except ImportError:
        return json.dumps({"error": "boto3 is not installed — cannot access AWS APIs"})
    except Exception as e:
        return json.dumps({"error": f"describe_service failed: {str(e)}"})


def _list_tasks(args: dict) -> str:
    """List ECS tasks with their health status and timing."""
    try:
        ecs = _get_ecs_client()
        cluster = args.get("cluster", _CLUSTER)
        service = args.get("service", _SERVICE)
        status_filter = args.get("status", "RUNNING")

        list_resp = ecs.list_tasks(
            cluster=cluster,
            serviceName=service,
            desiredStatus=status_filter,
        )
        task_arns = list_resp.get("taskArns", [])
        if not task_arns:
            return json.dumps({
                "cluster": cluster,
                "service": service,
                "status_filter": status_filter,
                "tasks": [],
                "count": 0,
            })

        desc_resp = ecs.describe_tasks(cluster=cluster, tasks=task_arns)
        tasks = []
        for t in desc_resp.get("tasks", []):
            containers = []
            for c in t.get("containers", []):
                containers.append({
                    "name": c.get("name", ""),
                    "lastStatus": c.get("lastStatus", ""),
                    "healthStatus": c.get("healthStatus", "UNKNOWN"),
                    "exitCode": c.get("exitCode"),
                })
            tasks.append({
                "taskArn": t.get("taskArn", ""),
                "lastStatus": t.get("lastStatus", ""),
                "healthStatus": t.get("healthStatus", "UNKNOWN"),
                "desiredStatus": t.get("desiredStatus", ""),
                "startedAt": t.get("startedAt"),
                "stoppedAt": t.get("stoppedAt"),
                "stoppedReason": t.get("stoppedReason", ""),
                "containers": containers,
                "cpu": t.get("cpu", ""),
                "memory": t.get("memory", ""),
            })

        result = {
            "cluster": cluster,
            "service": service,
            "status_filter": status_filter,
            "tasks": tasks,
            "count": len(tasks),
        }
        return json.dumps(_serialize(result))

    except ImportError:
        return json.dumps({"error": "boto3 is not installed — cannot access AWS APIs"})
    except Exception as e:
        return json.dumps({"error": f"list_tasks failed: {str(e)}"})


def _get_task_logs(args: dict) -> str:
    """Retrieve recent CloudWatch log lines for the ECS task."""
    try:
        logs = _get_logs_client()
        log_group = args.get("log_group", _LOG_GROUP)
        lines = int(args.get("lines", 50))
        log_stream = args.get("log_stream", "")

        # If no specific stream, find the most recent one
        if not log_stream:
            streams_resp = logs.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=1,
            )
            streams = streams_resp.get("logStreams", [])
            if not streams:
                return json.dumps({"error": f"No log streams found in {log_group}"})
            log_stream = streams[0]["logStreamName"]

        events_resp = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            limit=lines,
            startFromHead=False,
        )

        log_events = []
        for ev in events_resp.get("events", []):
            log_events.append({
                "timestamp": ev.get("timestamp"),
                "message": ev.get("message", "").rstrip(),
            })

        result = {
            "logGroup": log_group,
            "logStream": log_stream,
            "lines_requested": lines,
            "lines_returned": len(log_events),
            "events": log_events,
        }
        return json.dumps(_serialize(result))

    except ImportError:
        return json.dumps({"error": "boto3 is not installed — cannot access AWS APIs"})
    except Exception as e:
        return json.dumps({"error": f"get_task_logs failed: {str(e)}"})


def _describe_task_definition(args: dict) -> str:
    """Describe the active task definition with env secrets redacted."""
    try:
        ecs = _get_ecs_client()
        cluster = args.get("cluster", _CLUSTER)
        service = args.get("service", _SERVICE)
        task_def_arn = args.get("task_definition", "")

        # If no explicit ARN, look up the service's active task definition
        if not task_def_arn:
            svc_resp = ecs.describe_services(cluster=cluster, services=[service])
            services = svc_resp.get("services", [])
            if not services:
                return json.dumps({"error": f"Service '{service}' not found"})
            task_def_arn = services[0].get("taskDefinition", "")

        if not task_def_arn:
            return json.dumps({"error": "Could not determine task definition ARN"})

        td_resp = ecs.describe_task_definition(taskDefinition=task_def_arn)
        td = td_resp.get("taskDefinition", {})

        container_defs = []
        for cd in td.get("containerDefinitions", []):
            env_vars = _redact_env(cd.get("environment", []))
            # Also redact secrets from secretValueFrom
            secrets = []
            for s in cd.get("secrets", []):
                secrets.append({
                    "name": s.get("name", ""),
                    "valueFrom": "***REDACTED***",
                })

            container_defs.append({
                "name": cd.get("name", ""),
                "image": cd.get("image", ""),
                "cpu": cd.get("cpu", 0),
                "memory": cd.get("memory"),
                "memoryReservation": cd.get("memoryReservation"),
                "essential": cd.get("essential", True),
                "portMappings": cd.get("portMappings", []),
                "environment": env_vars,
                "secrets": secrets,
                "logConfiguration": cd.get("logConfiguration"),
                "healthCheck": cd.get("healthCheck"),
                "command": cd.get("command"),
                "entryPoint": cd.get("entryPoint"),
            })

        result = {
            "taskDefinitionArn": td.get("taskDefinitionArn", ""),
            "family": td.get("family", ""),
            "revision": td.get("revision", 0),
            "status": td.get("status", ""),
            "cpu": td.get("cpu", ""),
            "memory": td.get("memory", ""),
            "networkMode": td.get("networkMode", ""),
            "requiresCompatibilities": td.get("requiresCompatibilities", []),
            "executionRoleArn": td.get("executionRoleArn", ""),
            "taskRoleArn": td.get("taskRoleArn", ""),
            "containerDefinitions": container_defs,
        }
        return json.dumps(_serialize(result))

    except ImportError:
        return json.dumps({"error": "boto3 is not installed — cannot access AWS APIs"})
    except Exception as e:
        return json.dumps({"error": f"describe_task_definition failed: {str(e)}"})


def _get_service_events(args: dict) -> str:
    """Get recent ECS service events (deployment changes, scaling, errors)."""
    try:
        ecs = _get_ecs_client()
        cluster = args.get("cluster", _CLUSTER)
        service = args.get("service", _SERVICE)
        count = int(args.get("count", 10))

        resp = ecs.describe_services(cluster=cluster, services=[service])
        services = resp.get("services", [])
        if not services:
            return json.dumps({"error": f"Service '{service}' not found in cluster '{cluster}'"})

        svc = services[0]
        events = []
        for e in svc.get("events", [])[:count]:
            events.append({
                "id": e.get("id", ""),
                "createdAt": e.get("createdAt"),
                "message": e.get("message", ""),
            })

        result = {
            "serviceName": svc.get("serviceName", ""),
            "events_requested": count,
            "events_returned": len(events),
            "events": events,
        }
        return json.dumps(_serialize(result))

    except ImportError:
        return json.dumps({"error": "boto3 is not installed — cannot access AWS APIs"})
    except Exception as e:
        return json.dumps({"error": f"get_service_events failed: {str(e)}"})


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "describe_service",
        "description": "Describe the ECS service: running count, desired count, deployments, and recent events.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster": {"type": "string", "description": "ECS cluster name (default: holly-grace-cluster)"},
                "service": {"type": "string", "description": "ECS service name (default: holly-grace)"},
            },
        },
    },
    {
        "name": "list_tasks",
        "description": "List ECS tasks with health status, started time, and stopped reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster": {"type": "string", "description": "ECS cluster name (default: holly-grace-cluster)"},
                "service": {"type": "string", "description": "ECS service name (default: holly-grace)"},
                "status": {"type": "string", "description": "Task status filter: RUNNING or STOPPED (default: RUNNING)"},
            },
        },
    },
    {
        "name": "get_task_logs",
        "description": "Get recent CloudWatch log lines from the ECS task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_group": {"type": "string", "description": "CloudWatch log group (default: /ecs/holly-grace-holly-grace)"},
                "log_stream": {"type": "string", "description": "Specific log stream name (default: most recent stream)"},
                "lines": {"type": "integer", "description": "Number of log lines to return (default: 50)"},
            },
        },
    },
    {
        "name": "describe_task_definition",
        "description": "Describe the active ECS task definition with container configs and resources. Env secrets are REDACTED.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster": {"type": "string", "description": "ECS cluster name (default: holly-grace-cluster)"},
                "service": {"type": "string", "description": "ECS service name (default: holly-grace)"},
                "task_definition": {"type": "string", "description": "Task definition ARN (default: auto-detect from service)"},
            },
        },
    },
    {
        "name": "get_service_events",
        "description": "Get recent ECS service events (deployment changes, scaling activity, errors).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster": {"type": "string", "description": "ECS cluster name (default: holly-grace-cluster)"},
                "service": {"type": "string", "description": "ECS service name (default: holly-grace)"},
                "count": {"type": "integer", "description": "Number of events to return (default: 10)"},
            },
        },
    },
]

_TOOL_DISPATCH = {
    "describe_service": _describe_service,
    "list_tasks": _list_tasks,
    "get_task_logs": _get_task_logs,
    "describe_task_definition": _describe_task_definition,
    "get_service_events": _get_service_events,
}


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications (no id) — ignore
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(req_id, {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aws-ecs", "version": "1.0.0"},
            })
            continue

        if method == "ping":
            _result(req_id, {})
            continue

        if method == "tools/list":
            _result(req_id, {"tools": _TOOLS})
            continue

        if method == "tools/call":
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments") or {}
            handler = _TOOL_DISPATCH.get(name)
            if not handler:
                _error(req_id, -32601, f"Unknown tool: {name}")
                continue
            try:
                text = handler(arguments if isinstance(arguments, dict) else {})
            except Exception as e:
                text = json.dumps({"error": str(e)})
            _result(req_id, {"content": [{"type": "text", "text": text}]})
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
