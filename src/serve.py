"""LangServe FastAPI app: exposes the agent graph as REST endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from langserve import add_routes

from src.events import (
    HollyEventCallbackHandler,
    WebSocketLogHandler,
    broadcaster,
)
from src.graph import build_graph
from src.llm.config import LLMSettings
from src.llm.router import LLMRouter
from src.scheduler.autonomous import AutonomousScheduler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attach WebSocket log handler to root logger for Holly Grace streaming
_ws_log_handler = WebSocketLogHandler()
_ws_log_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(_ws_log_handler)

# Build the graph
settings = LLMSettings()
router = LLMRouter(settings)

# If Ollama is absent, remap TRIVIAL tasks to GPT-4o-mini
if not settings.ollama_base_url:
    from src.llm.config import COMPLEXITY_MODEL_MAP, ModelID, TaskComplexity

    COMPLEXITY_MODEL_MAP[TaskComplexity.TRIVIAL] = ModelID.GPT4O_MINI
    logger.info("Ollama absent — TRIVIAL tasks routed to GPT-4o-mini")

graph = build_graph(router)

# Create the callback handler for Holly Grace events
holly_callback = HollyEventCallbackHandler()

# Compile graph WITH Tower checkpointer for durable interrupt/resume
from src.tower.checkpointer import setup_checkpointer, get_checkpointer, shutdown_checkpointer

_tower_checkpointer = None
if os.environ.get("TESTING") != "1":
    try:
        setup_checkpointer()
        _tower_checkpointer = get_checkpointer()
        logger.info("Tower checkpointer initialized (PostgresSaver)")
    except Exception as e:
        logger.warning("Tower checkpointer unavailable, compiling without: %s", e)

compiled_graph = graph.compile(checkpointer=_tower_checkpointer)

# Create the scheduler
scheduler = AutonomousScheduler(compiled_graph.invoke)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on startup, stop on shutdown.

    When TESTING=1 env var is set, skip all startup side effects
    (DB connections, scheduler, seeding) but keep routes + middleware active.
    """
    if os.environ.get("TESTING") == "1":
        logger.info("TESTING=1: skipping lifespan startup (DB, scheduler, seeding)")
        yield
        return

    # Initialize APS tables + registries
    from src.aps import init_aps

    await init_aps()
    logger.info("APS system initialized (tables + partitions + thetas)")

    # Seed agent configs
    from src.agent_registry import get_registry

    get_registry().seed_defaults()
    logger.info("Agent config registry initialized")

    # Seed tool registry
    from src.tool_registry import get_tool_registry

    get_tool_registry().seed_to_db()
    logger.info("Tool registry initialized (23 tools)")

    # Seed default + App Factory workflows
    from src.workflow_registry import get_workflow_registry

    get_workflow_registry().seed_defaults()
    logger.info("Workflow registry initialized (default + app_factory workflows seeded)")

    # Initialize Tower tables (tower_runs, tower_tickets, tower_effects, tower_run_events)
    from src.tower.store import init_tower_tables
    init_tower_tables()
    logger.info("Tower tables initialized")

    # Start Tower worker (claims and executes durable runs)
    from src.tower.worker import TowerWorker
    tower_worker = TowerWorker(compiled_graph)
    tower_worker.start()
    logger.info("Tower worker started (poll interval: 2s)")

    scheduler.start()
    logger.info("Autonomous scheduler started — store is now running 24/7")
    yield
    scheduler.stop()
    logger.info("Autonomous scheduler stopped")
    tower_worker.stop()
    logger.info("Tower worker stopped")
    shutdown_checkpointer()
    logger.info("Tower checkpointer shutdown")


app = FastAPI(
    title="E-Commerce Agents",
    description="Autonomous print-on-demand e-commerce agent system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse({"service": "holly-grace", "version": "1.0.0"})


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    from src.resilience.health import run_health_checks

    health = run_health_checks()
    critical_checks = {k: v for k, v in health.items() if k != "ollama"}
    all_critical_healthy = all(critical_checks.values())
    status = (
        "healthy" if all(health.values())
        else "degraded" if all_critical_healthy
        else "unhealthy"
    )
    return JSONResponse(
        {"status": status, "service": "holly-grace", "checks": health},
        status_code=200 if all_critical_healthy else 503,
    )


@app.get("/scheduler/jobs")
async def scheduler_jobs():
    """List all scheduled jobs."""
    jobs = [
        {"id": job.id, "next_run": str(job.next_run_time), "trigger": str(job.trigger)}
        for job in scheduler.jobs
    ]
    return JSONResponse({"jobs": jobs, "count": len(jobs)})


@app.post("/scheduler/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job immediately."""
    for job in scheduler.jobs:
        if job.id == job_id:
            job.modify(next_run_time=datetime.now(timezone.utc))
            return JSONResponse({"status": "triggered", "job_id": job_id})
    return JSONResponse({"status": "not_found", "job_id": job_id}, status_code=404)


@app.get("/graph/definition")
async def graph_definition():
    """Introspect the compiled graph and return node/edge structure."""
    try:
        graph_data = compiled_graph.get_graph()
        nodes = []
        edges = []

        for node_id, node_data in graph_data.nodes.items():
            node_name = node_data.name if hasattr(node_data, "name") else str(node_id)
            nodes.append({"id": str(node_id), "name": node_name})

        for edge in graph_data.edges:
            edges.append({
                "source": str(edge.source),
                "target": str(edge.target),
                "conditional": edge.conditional if hasattr(edge, "conditional") else False,
            })

        return JSONResponse({"nodes": nodes, "edges": edges})
    except Exception as e:
        logger.error("Failed to introspect graph: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/graph/metadata")
async def graph_metadata():
    """Batch metadata for all graph nodes: channel, p_fail, latency, tools, version."""
    from src.agent_registry import get_registry
    from src.aps.store import get_latest_metrics

    registry = get_registry()
    agents = registry.get_all()
    metrics_rows = get_latest_metrics()
    metrics_by_channel = {r["channel_id"]: r for r in metrics_rows}

    # Map agent_id -> graph node_id for cases where they differ
    _GRAPH_ALIASES = {"revenue": "revenue_analytics"}

    nodes: dict[str, dict] = {}
    for agent in agents:
        channel = agent.channel_id
        m = metrics_by_channel.get(channel, {})
        last_latency = None
        if m.get("total_time_s") and m.get("n_observations"):
            last_latency = round(m["total_time_s"] / m["n_observations"] * 1000, 1)
        entry = {
            "channel_id": channel,
            "p_fail": m.get("p_fail"),
            "last_latency_ms": last_latency,
            "tool_count": len(agent.tool_ids) if hasattr(agent, "tool_ids") and agent.tool_ids else 0,
            "version": agent.version,
            "model_id": agent.model_id,
            "capacity": m.get("capacity"),
            "n_observations": m.get("n_observations", 0),
        }
        nodes[agent.agent_id] = entry
        # Also index by graph node alias if different
        if agent.agent_id in _GRAPH_ALIASES:
            nodes[_GRAPH_ALIASES[agent.agent_id]] = entry

    return JSONResponse({"nodes": nodes})


@app.get("/circuit-breakers")
async def circuit_breakers():
    """Get all circuit breaker states."""
    from src.resilience.circuit_breaker import get_all_states

    return JSONResponse(get_all_states())


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """WebSocket endpoint streaming real-time execution events.

    Auth: token passed as query parameter ?token=<jwt>
    Origin: validated against CORS_ALLOWED_ORIGINS
    """
    from src.security.auth import verify_token

    # Validate origin
    origin = websocket.headers.get("origin", "")
    allowed_origins = os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8050"
    ).split(",")
    if origin and origin not in allowed_origins:
        logger.warning("WebSocket rejected: disallowed origin %s", origin)
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # Validate token from query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        payload = verify_token(token)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    sub_id, queue = broadcaster.subscribe()
    try:
        while True:
            event = await queue.get()
            # Sanitize: strip any accidental secret leaks from events
            sanitized = {k: v for k, v in event.items() if k != "raw_env"}
            await websocket.send_text(json.dumps(sanitized, default=str))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Redact token from error messages
        error_msg = str(e).replace(token, "[REDACTED]") if token else str(e)
        logger.debug("WebSocket error: %s", error_msg)
    finally:
        broadcaster.unsubscribe(sub_id)


# ---------------------------------------------------------------------------
# APS (Adaptive Partition Selection) API endpoints
# ---------------------------------------------------------------------------


@app.get("/aps/metrics")
async def aps_metrics():
    """Get latest APS metrics for all channels."""
    from src.aps.store import get_latest_metrics

    rows = get_latest_metrics()
    results = {r["channel_id"]: r for r in rows}
    return JSONResponse({"metrics": results})


@app.get("/aps/metrics/{channel_id}")
async def aps_metrics_channel(channel_id: str):
    """Get metric history for a single channel."""
    from src.aps.store import get_metrics_history

    history = get_metrics_history(channel_id, limit=100)
    return JSONResponse({"channel_id": channel_id, "history": history})


@app.get("/aps/partitions")
async def aps_partitions():
    """Get current theta state (active partition + protocol) for all channels."""
    from src.aps.theta import get_all_theta_states

    return JSONResponse({"theta_states": get_all_theta_states()})


@app.post("/aps/switch/{channel_id}/{theta_id}")
async def aps_manual_switch(channel_id: str, theta_id: str):
    """Manually switch a channel's theta configuration."""
    from src.aps.store import store_theta_switch_event
    from src.aps.theta import set_active_theta

    try:
        from src.aps.theta import get_active_theta as _get_theta
        old_theta = _get_theta(channel_id)
        set_active_theta(channel_id, theta_id)
        store_theta_switch_event(
            channel_id=channel_id,
            from_theta=old_theta.theta_id,
            to_theta=theta_id,
            direction="manual",
            from_level=old_theta.level,
            to_level=0,  # will be correct after set_active_theta
            model_changed=False,
            protocol_changed=False,
            trigger_p_fail=0.0,
            trigger_epsilon=0.0,
            goal_id="manual_override",
        )
        return JSONResponse({"status": "switched", "channel_id": channel_id, "theta_id": theta_id})
    except KeyError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


@app.get("/aps/chain-capacity")
async def aps_chain_capacity():
    """Get realized bottleneck capacity and path analysis (Theorem 1)."""
    from src.aps.controller import aps_controller

    bottlenecks = aps_controller._compute_realized_bottlenecks()
    return JSONResponse({"bottlenecks": bottlenecks})


@app.post("/aps/evaluate")
async def aps_evaluate():
    """Trigger an immediate APS evaluation cycle."""
    from src.aps.controller import aps_controller

    aps_controller.evaluate_all()
    from src.aps.theta import get_all_theta_states

    return JSONResponse({"status": "evaluated", "theta_states": get_all_theta_states()})


@app.get("/aps/trace/{trace_id}")
async def aps_trace(trace_id: str):
    """Get all APS observations for a single workflow trace."""
    from src.aps.store import get_observations_by_trace

    observations = get_observations_by_trace(trace_id)
    return JSONResponse({"trace_id": trace_id, "observations": observations, "count": len(observations)})


@app.get("/aps/cache")
async def aps_cache():
    """Get current theta cache state (context fingerprints → cached thetas)."""
    from src.aps.store import get_all_theta_cache

    cache = get_all_theta_cache()
    return JSONResponse({"cache": cache})


# ---------------------------------------------------------------------------
# Agent efficacy endpoints
# ---------------------------------------------------------------------------


@app.get("/agents/{agent_id}/efficacy")
async def agent_efficacy(agent_id: str, days: int = 30):
    """Get efficacy history for an agent."""
    from src.aps.store import get_agent_efficacy

    history = get_agent_efficacy(agent_id, days=days)
    return JSONResponse({"agent_id": agent_id, "days": days, "history": history})


@app.post("/agents/efficacy/compute")
async def compute_efficacy(days: int = 30):
    """Trigger efficacy aggregation."""
    from src.aps.store import compute_agent_efficacy

    count = compute_agent_efficacy(days=days)
    return JSONResponse({"status": "computed", "rows_inserted": count})


# ---------------------------------------------------------------------------
# Agent config CRUD endpoints
# ---------------------------------------------------------------------------


def _agent_to_dict(c, *, include_prompt: bool = True) -> dict:
    """Serialize an AgentConfig to a JSON-safe dict.

    Args:
        include_prompt: If False, omits system_prompt (for non-admin responses).
    """
    d = {
        "agent_id": c.agent_id,
        "channel_id": c.channel_id,
        "display_name": c.display_name,
        "description": c.description,
        "model_id": c.model_id,
        "tool_ids": c.tool_ids if hasattr(c, "tool_ids") else [],
        "is_builtin": c.is_builtin if hasattr(c, "is_builtin") else False,
        "version": c.version,
    }
    if include_prompt:
        d["system_prompt"] = c.system_prompt
    return d


@app.get("/agents")
async def list_agents(request: Request):
    """List all agent configurations."""
    from src.agent_registry import get_registry

    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    configs = get_registry().get_all()
    return JSONResponse({"agents": [_agent_to_dict(c, include_prompt=is_admin) for c in configs]})


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    """Get a single agent configuration."""
    from src.agent_registry import get_registry

    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    try:
        config = get_registry().get(agent_id)
        return JSONResponse(_agent_to_dict(config, include_prompt=is_admin))
    except KeyError:
        return JSONResponse({"error": f"Agent '{agent_id}' not found"}, status_code=404)


@app.post("/agents")
async def create_agent(request: Request):
    """Create a new agent configuration."""
    from src.agent_registry import get_registry

    body = await request.json()
    required = ("agent_id", "channel_id", "display_name", "model_id")
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JSONResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"},
            status_code=400,
        )

    registry = get_registry()
    result = registry.create(
        agent_id=body["agent_id"],
        channel_id=body["channel_id"],
        display_name=body["display_name"],
        description=body.get("description", ""),
        model_id=body["model_id"],
        system_prompt=body.get("system_prompt", ""),
        tool_ids=body.get("tool_ids"),
    )
    if result is None:
        return JSONResponse(
            {"error": f"Agent '{body['agent_id']}' already exists or DB error"},
            status_code=409,
        )
    return JSONResponse(_agent_to_dict(result), status_code=201)


@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: Request):
    """Update an agent configuration with optimistic concurrency."""
    from src.agent_registry import get_registry

    body = await request.json()
    expected_version = body.get("expected_version")
    if expected_version is None:
        return JSONResponse(
            {"error": "expected_version is required"}, status_code=400
        )

    updates = {}
    for key in ("display_name", "description", "model_id", "system_prompt", "tool_ids"):
        if key in body:
            updates[key] = body[key]

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    registry = get_registry()
    result = registry.update(agent_id, updates, expected_version)
    if result is None:
        return JSONResponse(
            {"error": "Version conflict or agent not found"}, status_code=409
        )

    return JSONResponse(_agent_to_dict(result))


@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Soft-delete an agent (builtin agents cannot be deleted)."""
    from src.agent_registry import get_registry

    registry = get_registry()
    deleted = registry.delete(agent_id)
    if not deleted:
        return JSONResponse(
            {"error": f"Cannot delete '{agent_id}' (builtin or not found)"},
            status_code=400,
        )
    return JSONResponse({"status": "deleted", "agent_id": agent_id})


@app.get("/agents/{agent_id}/versions")
async def list_agent_versions(agent_id: str):
    """Get version history for an agent."""
    from src.agent_registry import get_registry

    history = get_registry().get_version_history(agent_id)
    return JSONResponse({"agent_id": agent_id, "versions": history})


@app.get("/agents/{agent_id}/versions/{version}")
async def get_agent_version(agent_id: str, version: int):
    """Get a specific version snapshot."""
    from src.agent_registry import get_registry

    snapshot = get_registry().get_version(agent_id, version)
    if snapshot is None:
        return JSONResponse({"error": "Version not found"}, status_code=404)
    return JSONResponse(snapshot)


@app.post("/agents/{agent_id}/rollback")
async def rollback_agent(agent_id: str, request: Request):
    """Rollback an agent to a previous version."""
    from src.agent_registry import get_registry

    body = await request.json()
    target_version = body.get("target_version")
    if target_version is None:
        return JSONResponse(
            {"error": "target_version is required"}, status_code=400
        )

    registry = get_registry()
    result = registry.rollback(agent_id, target_version)
    if result is None:
        return JSONResponse(
            {"error": "Rollback failed (version not found or conflict)"},
            status_code=409,
        )
    return JSONResponse(_agent_to_dict(result))


@app.get("/agents/{agent_id}/default")
async def get_agent_default(agent_id: str):
    """Get the hardcoded default config for an agent (for 'Reset to Default')."""
    from src.agent_registry import AgentConfigRegistry

    default = AgentConfigRegistry.get_hardcoded_default(agent_id)
    if default is None:
        return JSONResponse({"error": f"No default for '{agent_id}'"}, status_code=404)

    return JSONResponse(_agent_to_dict(default))


# ---------------------------------------------------------------------------
# Tool registry endpoints
# ---------------------------------------------------------------------------


@app.get("/tools")
async def list_tools():
    """List all available tools."""
    from src.tool_registry import get_tool_registry

    tools = get_tool_registry().to_dicts()
    return JSONResponse({"tools": tools, "count": len(tools)})


# ---------------------------------------------------------------------------
# Workflow CRUD endpoints
# ---------------------------------------------------------------------------


@app.get("/workflows")
async def list_workflows():
    """List all non-deleted workflows."""
    from src.workflow_registry import get_workflow_registry

    workflows = get_workflow_registry().get_all()
    return JSONResponse({"workflows": workflows, "count": len(workflows)})


@app.get("/workflows/{workflow_id}")
async def get_workflow_endpoint(workflow_id: str):
    """Get a single workflow."""
    from src.workflow_registry import get_workflow_registry

    wf = get_workflow_registry().get(workflow_id)
    if wf is None:
        return JSONResponse({"error": f"Workflow '{workflow_id}' not found"}, status_code=404)
    return JSONResponse(wf)


@app.post("/workflows")
async def create_workflow_endpoint(request: Request):
    """Create a new workflow."""
    from src.workflow_registry import get_workflow_registry

    body = await request.json()
    required = ("workflow_id", "display_name", "definition")
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JSONResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"},
            status_code=400,
        )

    # Validate definition (skip for empty/draft workflows with no nodes)
    defn_body = body["definition"]
    if defn_body.get("nodes"):
        from src.workflow_compiler import validate_workflow
        from src.workflow_registry import WorkflowDefinition

        try:
            defn = WorkflowDefinition.from_dict({
                "workflow_id": body["workflow_id"],
                "display_name": body["display_name"],
                "description": body.get("description", ""),
                **defn_body,
            })
            errors = validate_workflow(defn)
            if errors:
                return JSONResponse({"error": "Validation failed", "details": errors}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": f"Invalid definition: {e}"}, status_code=400)

    registry = get_workflow_registry()
    result = registry.create(
        workflow_id=body["workflow_id"],
        display_name=body["display_name"],
        description=body.get("description", ""),
        definition=body["definition"],
    )
    if result is None:
        return JSONResponse(
            {"error": f"Workflow '{body['workflow_id']}' already exists or DB error"},
            status_code=409,
        )
    return JSONResponse(result, status_code=201)


@app.put("/workflows/{workflow_id}")
async def update_workflow_endpoint(workflow_id: str, request: Request):
    """Update a workflow with optimistic concurrency."""
    from src.workflow_registry import get_workflow_registry

    body = await request.json()
    expected_version = body.get("expected_version")
    if expected_version is None:
        return JSONResponse({"error": "expected_version is required"}, status_code=400)

    updates = {}
    for key in ("display_name", "description", "definition"):
        if key in body:
            updates[key] = body[key]

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    # Validate definition if provided
    if "definition" in updates:
        from src.workflow_compiler import validate_workflow
        from src.workflow_registry import WorkflowDefinition

        try:
            existing = get_workflow_registry().get(workflow_id)
            defn = WorkflowDefinition.from_dict({
                "workflow_id": workflow_id,
                "display_name": updates.get("display_name", existing["display_name"] if existing else ""),
                **updates["definition"],
            })
            errors = validate_workflow(defn)
            if errors:
                return JSONResponse({"error": "Validation failed", "details": errors}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": f"Invalid definition: {e}"}, status_code=400)

    registry = get_workflow_registry()
    result = registry.update(workflow_id, updates, expected_version)
    if result is None:
        return JSONResponse(
            {"error": "Version conflict or workflow not found"}, status_code=409
        )

    # Invalidate compiled graph cache
    from src.workflow_compiler import invalidate_cache
    invalidate_cache(workflow_id)

    return JSONResponse(result)


@app.delete("/workflows/{workflow_id}")
async def delete_workflow_endpoint(workflow_id: str):
    """Soft-delete a workflow (builtin workflows cannot be deleted)."""
    from src.workflow_registry import get_workflow_registry

    registry = get_workflow_registry()
    deleted = registry.delete(workflow_id)
    if not deleted:
        return JSONResponse(
            {"error": f"Cannot delete '{workflow_id}' (builtin or not found)"},
            status_code=400,
        )
    return JSONResponse({"status": "deleted", "workflow_id": workflow_id})


@app.post("/workflows/{workflow_id}/activate")
async def activate_workflow_endpoint(workflow_id: str):
    """Activate a workflow (deactivates all others)."""
    from src.workflow_registry import get_workflow_registry

    registry = get_workflow_registry()
    activated = registry.activate(workflow_id)
    if not activated:
        return JSONResponse(
            {"error": f"Cannot activate '{workflow_id}' (not found or deleted)"},
            status_code=400,
        )
    return JSONResponse({"status": "activated", "workflow_id": workflow_id})


@app.post("/workflows/{workflow_id}/compile")
async def compile_workflow_endpoint(workflow_id: str):
    """Dry-run compile a workflow (validation without execution)."""
    from src.workflow_compiler import compile_workflow, validate_workflow
    from src.workflow_registry import WorkflowDefinition, get_workflow_registry

    registry = get_workflow_registry()
    wf = registry.get(workflow_id)
    if wf is None:
        return JSONResponse({"error": f"Workflow '{workflow_id}' not found"}, status_code=404)

    defn = WorkflowDefinition.from_dict({
        "workflow_id": wf["workflow_id"],
        "display_name": wf["display_name"],
        "description": wf["description"],
        **wf["definition"],
    })

    errors = validate_workflow(defn)
    if errors:
        return JSONResponse({"status": "invalid", "errors": errors}, status_code=400)

    try:
        compiled = compile_workflow(defn, router, version=wf["version"], use_cache=False)
        graph_data = compiled.compile().get_graph()
        node_count = len(graph_data.nodes)
        edge_count = len(graph_data.edges)
        return JSONResponse({
            "status": "valid",
            "workflow_id": workflow_id,
            "version": wf["version"],
            "nodes": node_count,
            "edges": edge_count,
        })
    except Exception as e:
        return JSONResponse({"status": "compile_error", "error": str(e)}, status_code=400)


@app.get("/workflows/{workflow_id}/versions")
async def list_workflow_versions(workflow_id: str):
    """Get version history for a workflow."""
    from src.workflow_registry import get_workflow_registry

    history = get_workflow_registry().get_version_history(workflow_id)
    return JSONResponse({"workflow_id": workflow_id, "versions": history})


@app.get("/workflows/{workflow_id}/versions/{version}")
async def get_workflow_version_endpoint(workflow_id: str, version: int):
    """Get a specific version snapshot."""
    from src.workflow_registry import get_workflow_registry

    snapshot = get_workflow_registry().get_version(workflow_id, version)
    if snapshot is None:
        return JSONResponse({"error": "Version not found"}, status_code=404)
    return JSONResponse(snapshot)


@app.post("/workflows/{workflow_id}/rollback")
async def rollback_workflow(workflow_id: str, request: Request):
    """Rollback a workflow to a previous version."""
    from src.workflow_registry import get_workflow_registry

    body = await request.json()
    target_version = body.get("target_version")
    if target_version is None:
        return JSONResponse({"error": "target_version is required"}, status_code=400)

    registry = get_workflow_registry()
    result = registry.rollback(workflow_id, target_version)
    if result is None:
        return JSONResponse(
            {"error": "Rollback failed (version not found or conflict)"},
            status_code=409,
        )

    # Invalidate compiled graph cache
    from src.workflow_compiler import invalidate_cache
    invalidate_cache(workflow_id)

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Dead Letter Queue endpoints
# ---------------------------------------------------------------------------


@app.get("/scheduler/dlq")
async def list_dlq():
    """List all dead letter queue entries."""
    from src.aps.store import dlq_list_all

    entries = dlq_list_all()
    return JSONResponse({"entries": entries, "count": len(entries)})


@app.post("/scheduler/dlq/{dlq_id}/retry")
async def retry_dlq(dlq_id: int):
    """Manually retry a DLQ entry."""
    from src.aps.store import dlq_get_pending, dlq_increment_attempt, dlq_resolve

    # Find the entry
    from src.aps.store import _get_conn
    import json as _json

    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT id, payload FROM dead_letter_queue WHERE id = %s AND resolved_at IS NULL",
                (dlq_id,),
            ).fetchone()
        if not row:
            return JSONResponse({"error": "DLQ entry not found or already resolved"}, status_code=404)

        payload = row[1] if isinstance(row[1], dict) else _json.loads(row[1])
        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content=payload.get("task_description", ""))],
            "trigger_source": f"dlq_manual:{payload.get('trigger_source', '')}",
            "retry_count": 0,
        }
        compiled_graph.invoke(state)
        dlq_resolve(dlq_id)
        return JSONResponse({"status": "resolved", "dlq_id": dlq_id})
    except Exception as e:
        return JSONResponse({"status": "failed", "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Approval queue endpoints
# ---------------------------------------------------------------------------


@app.get("/approvals")
async def list_approvals(status: str = "pending"):
    """List approval requests. Default: pending only."""
    from src.aps.store import approval_list_all, approval_list_pending

    if status == "pending":
        entries = approval_list_pending()
    else:
        entries = approval_list_all()
    return JSONResponse({"approvals": entries, "count": len(entries)})


@app.get("/approvals/stats")
async def approval_stats():
    """Get approval queue statistics."""
    from src.aps.store import approval_list_all

    all_approvals = approval_list_all(limit=1000)
    pending = sum(1 for a in all_approvals if a["status"] == "pending")
    approved = sum(1 for a in all_approvals if a["status"] == "approved")
    rejected = sum(1 for a in all_approvals if a["status"] == "rejected")
    expired = sum(1 for a in all_approvals if a["status"] == "expired")

    return JSONResponse({
        "total": len(all_approvals),
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "expired": expired,
    })


@app.get("/approvals/{approval_id}")
async def get_approval(approval_id: int):
    """Get a single approval request."""
    from src.aps.store import approval_get

    entry = approval_get(approval_id)
    if entry is None:
        return JSONResponse({"error": "Approval not found"}, status_code=404)
    return JSONResponse(entry)


@app.post("/approvals/{approval_id}/approve")
async def approve_request(approval_id: int, request: Request):
    """Approve a pending approval request."""
    from src.aps.store import approval_decide

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "")
    decided_by = body.get("decided_by", "console")

    success = approval_decide(approval_id, "approved", decided_by=decided_by, reason=reason)
    if not success:
        return JSONResponse({"error": "Approval not found or already decided"}, status_code=400)
    return JSONResponse({"status": "approved", "approval_id": approval_id})


@app.post("/approvals/{approval_id}/reject")
async def reject_request(approval_id: int, request: Request):
    """Reject a pending approval request."""
    from src.aps.store import approval_decide

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "")
    decided_by = body.get("decided_by", "console")

    success = approval_decide(approval_id, "rejected", decided_by=decided_by, reason=reason)
    if not success:
        return JSONResponse({"error": "Approval not found or already decided"}, status_code=400)
    return JSONResponse({"status": "rejected", "approval_id": approval_id})


# ---------------------------------------------------------------------------
# Evaluation suite endpoints
# ---------------------------------------------------------------------------


@app.post("/eval/run")
async def run_eval():
    """Trigger a golden evaluation suite run."""
    import os

    from src.evaluation.golden_suite import EvalRunner, load_golden_tasks

    tasks_path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "tasks.json")
    if not os.path.exists(tasks_path):
        return JSONResponse({"error": "Golden tasks file not found"}, status_code=404)

    runner = EvalRunner(compiled_graph.invoke)
    tasks = load_golden_tasks(tasks_path)
    report = runner.run_suite(tasks)
    return JSONResponse(report)


@app.get("/eval/results")
async def eval_results():
    """Get eval suite run history."""
    from src.aps.store import get_eval_history

    history = get_eval_history()
    return JSONResponse({"history": history})


@app.get("/eval/results/{suite_id}")
async def eval_result_detail(suite_id: str):
    """Get detailed results for a specific eval suite run."""
    from src.aps.store import get_eval_results

    results = get_eval_results(suite_id)
    if not results:
        return JSONResponse({"error": "Suite not found"}, status_code=404)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return JSONResponse({
        "suite_id": suite_id,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total > 0 else 0,
        "results": results,
    })


# ---------------------------------------------------------------------------
# Morphogenetic system endpoints
# ---------------------------------------------------------------------------


@app.get("/morphogenetic/snapshot")
async def morphogenetic_snapshot():
    """Compute a live developmental snapshot."""
    from src.morphogenetic.instruments import compute_developmental_snapshot

    snapshot = compute_developmental_snapshot()
    return JSONResponse(snapshot.to_dict())


@app.get("/morphogenetic/trajectory")
async def morphogenetic_trajectory(limit: int = 100):
    """Get the developmental trajectory (historical snapshots)."""
    from src.aps.store import get_developmental_trajectory

    trajectory = get_developmental_trajectory(limit=limit)
    return JSONResponse({"trajectory": trajectory, "count": len(trajectory)})


@app.get("/morphogenetic/goals")
async def morphogenetic_goals():
    """Get all morphogenetic goal specs with current status."""
    from src.aps.store import get_latest_metrics
    from src.morphogenetic.goals import get_default_goal_specs

    goals = get_default_goal_specs()
    metrics_rows = get_latest_metrics()
    metrics = {r["channel_id"]: r for r in metrics_rows}

    result = []
    for goal in goals:
        g = {
            "goal_id": goal.goal_id,
            "display_name": goal.display_name,
            "formalization_level": goal.formalization_level,
            "failure_predicate": goal.failure_predicate,
            "g0_description": goal.g0_description,
            "epsilon_g": goal.epsilon_g,
            "horizon_t": goal.horizon_t,
            "observation_map": goal.observation_map,
            "primary_tier": goal.primary_tier,
            "priority": goal.priority,
        }
        # Check satisfaction
        if goal.is_formalized():
            satisfied = True
            channel_status = {}
            for ch in goal.observation_map:
                ch_m = metrics.get(ch, {})
                p_fail = ch_m.get("p_fail", 1.0)
                channel_status[ch] = {
                    "p_fail": round(p_fail, 4),
                    "within_tolerance": p_fail <= goal.epsilon_g,
                }
                if p_fail > goal.epsilon_g:
                    satisfied = False
            g["satisfied"] = satisfied
            g["channel_status"] = channel_status
        else:
            g["satisfied"] = None
            g["channel_status"] = {}

        result.append(g)

    return JSONResponse({"goals": result, "count": len(result)})


@app.get("/morphogenetic/assembly")
async def morphogenetic_assembly():
    """Get all cached competencies from the assembly cache."""
    from src.morphogenetic.assembly import get_all_competencies, get_competency_distribution

    competencies = get_all_competencies()
    distribution = get_competency_distribution()
    return JSONResponse({
        "competencies": competencies,
        "distribution": distribution,
        "count": len(competencies),
    })


@app.get("/morphogenetic/cascade")
async def morphogenetic_cascade(limit: int = 50):
    """Get cascade event history."""
    from src.aps.store import get_cascade_history

    events = get_cascade_history(limit=limit)
    return JSONResponse({"events": events, "count": len(events)})


@app.post("/morphogenetic/evaluate")
async def morphogenetic_evaluate():
    """Trigger an immediate morphogenetic evaluation cycle."""
    from src.morphogenetic.scheduler_jobs import morphogenetic_evaluation_job

    morphogenetic_evaluation_job()

    from src.morphogenetic.instruments import compute_developmental_snapshot

    snapshot = compute_developmental_snapshot()
    return JSONResponse({
        "status": "evaluated",
        "snapshot": snapshot.to_dict(),
    })


# ---------------------------------------------------------------------------
# Goal CRUD endpoints
# ---------------------------------------------------------------------------


@app.post("/morphogenetic/goals")
async def create_goal(request: Request):
    """Create a new morphogenetic goal."""
    from src.aps.store import upsert_goal

    body = await request.json()
    required = ["goal_id", "display_name", "failure_predicate", "epsilon_g", "horizon_t", "observation_map"]
    missing = [f for f in required if f not in body]
    if missing:
        return JSONResponse({"error": f"Missing fields: {missing}"}, status_code=400)
    result = upsert_goal(body)
    if result is None:
        return JSONResponse({"error": "Failed to create goal"}, status_code=500)
    return JSONResponse(result, status_code=201)


@app.put("/morphogenetic/goals/{goal_id}")
async def update_goal(goal_id: str, request: Request):
    """Update an existing morphogenetic goal."""
    from src.aps.store import get_goal, upsert_goal

    existing = get_goal(goal_id)
    if existing is None:
        return JSONResponse({"error": "Goal not found"}, status_code=404)
    body = await request.json()
    # Merge: existing values + updates
    merged = {**existing, **body, "goal_id": goal_id}
    result = upsert_goal(merged)
    if result is None:
        return JSONResponse({"error": "Failed to update goal"}, status_code=500)
    return JSONResponse(result)


@app.delete("/morphogenetic/goals/{goal_id}")
async def delete_goal_endpoint(goal_id: str):
    """Delete a morphogenetic goal."""
    from src.aps.store import delete_goal

    deleted = delete_goal(goal_id)
    if not deleted:
        return JSONResponse({"error": "Goal not found or delete failed"}, status_code=404)
    return JSONResponse({"status": "deleted", "goal_id": goal_id})


@app.post("/morphogenetic/goals/reset")
async def reset_goals():
    """Reset goals to hardcoded defaults (deletes all, re-seeds)."""
    from src.aps.store import _get_conn, seed_default_goals
    from src.morphogenetic.goals import _goal_to_dict, _hardcoded_goal_specs

    try:
        with _get_conn() as conn:
            conn.execute("DELETE FROM morphogenetic_goals")
        defaults = _hardcoded_goal_specs()
        count = seed_default_goals([_goal_to_dict(g) for g in defaults])
        return JSONResponse({"status": "reset", "goals_seeded": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Cascade config endpoints
# ---------------------------------------------------------------------------


@app.get("/morphogenetic/cascade/config")
async def get_cascade_config_endpoint():
    """Get current cascade configuration."""
    from src.aps.store import get_cascade_config

    return JSONResponse(get_cascade_config())


@app.put("/morphogenetic/cascade/config")
async def update_cascade_config_endpoint(request: Request):
    """Update cascade configuration."""
    from src.aps.store import update_cascade_config

    body = await request.json()
    result = update_cascade_config(body)
    return JSONResponse(result)


@app.post("/morphogenetic/cascade/config/reset")
async def reset_cascade_config_endpoint():
    """Reset cascade configuration to defaults."""
    from src.aps.store import reset_cascade_config

    result = reset_cascade_config()
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# System image endpoints
# ---------------------------------------------------------------------------


@app.get("/system/export")
async def system_export():
    """Export the full system configuration as a portable image."""
    from src.aps.store import export_system_image, store_system_image

    image = export_system_image()
    # Store a copy in history
    store_system_image(image)
    return JSONResponse(image)


@app.post("/system/import")
async def system_import(request: Request):
    """Import a system image. Applies changes to current system."""
    from src.aps.store import export_system_image, import_system_image, store_system_image

    body = await request.json()

    # Create pre-import backup
    backup = export_system_image()
    backup["name"] = "pre-import-backup"
    store_system_image(backup)

    result = import_system_image(body)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


@app.post("/system/import/preview")
async def system_import_preview(request: Request):
    """Preview what an import would change (dry run)."""
    from src.aps.store import import_system_image

    body = await request.json()
    result = import_system_image(body, dry_run=True)
    return JSONResponse(result)


@app.get("/system/images")
async def list_system_images_endpoint():
    """List previously exported system images."""
    from src.aps.store import list_system_images

    images = list_system_images()
    return JSONResponse({"images": images, "count": len(images)})


@app.get("/system/images/{image_id}")
async def get_system_image_endpoint(image_id: int):
    """Get a full system image by ID."""
    from src.aps.store import get_system_image

    image = get_system_image(image_id)
    if image is None:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    return JSONResponse(image)


# ---------------------------------------------------------------------------
# Checkpoint endpoints
# ---------------------------------------------------------------------------


@app.get("/executions/{thread_id}/checkpoints")
async def list_checkpoints(thread_id: str):
    """List checkpoints for a thread."""
    from src.aps.store import get_checkpoints

    checkpoints = get_checkpoints(thread_id)
    return JSONResponse({"thread_id": thread_id, "checkpoints": checkpoints})


# Add LangServe routes with Holly Grace callback injection
def _per_req_config_modifier(config: dict, request) -> dict:
    """Inject HollyEventCallbackHandler + APS trace_id into every invocation."""
    callbacks = config.get("callbacks", []) or []
    callbacks.append(holly_callback)
    config["callbacks"] = callbacks
    # APS: inject trace_id for cross-node correlation
    metadata = config.get("metadata", {}) or {}
    metadata["aps_trace_id"] = str(uuid.uuid4())
    config["metadata"] = metadata
    return config


add_routes(
    app,
    compiled_graph,
    path="/agent",
    per_req_config_modifier=_per_req_config_modifier,
)


# ---------------------------------------------------------------------------
# App Factory project endpoints
# ---------------------------------------------------------------------------


@app.post("/app-factory/projects")
async def create_af_project(request: Request):
    """Create a new App Factory project."""
    from src.app_factory.models import AppProject, create_project

    body = await request.json()
    idea = body.get("idea", "")
    if not idea:
        return JSONResponse({"error": "idea is required"}, status_code=400)

    project = AppProject(
        project_id=AppProject.new_id(),
        idea=idea,
        status="pending",
        current_phase="ideation",
    )
    result = create_project(project)
    if result is None:
        return JSONResponse({"error": "Failed to create project"}, status_code=500)
    return JSONResponse(result, status_code=201)


@app.get("/app-factory/projects")
async def list_af_projects():
    """List all App Factory projects."""
    from src.app_factory.models import list_projects

    projects = list_projects()
    return JSONResponse({"projects": projects, "count": len(projects)})


@app.get("/app-factory/projects/{project_id}")
async def get_af_project(project_id: str):
    """Get full project detail."""
    from src.app_factory.models import get_project

    project = get_project(project_id)
    if project is None:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    return JSONResponse(project.to_dict())


@app.delete("/app-factory/projects/{project_id}")
async def delete_af_project(project_id: str):
    """Delete a project and clean up its Docker workspace."""
    from src.app_factory.models import delete_project

    deleted = delete_project(project_id)
    if not deleted:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    # Best-effort workspace cleanup
    try:
        import subprocess
        subprocess.run(
            ["docker", "exec", "ecom-android-builder", "rm", "-rf", f"/workspace/{project_id}"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass

    return JSONResponse({"status": "deleted", "project_id": project_id})


# ---------------------------------------------------------------------------
# Tower (Control Tower) API endpoints — durable runs, tickets, effects
# ---------------------------------------------------------------------------


@app.post("/tower/runs/start")
async def tower_start_run(request: Request):
    """Start a new Tower run. The worker will pick it up and execute it."""
    from src.tower.runner import start_run

    body = await request.json()
    input_state = body.get("input_state", {})
    if not input_state:
        return JSONResponse({"error": "input_state is required"}, status_code=400)

    run_id = start_run(
        compiled_graph,
        input_state=input_state,
        workflow_id=body.get("workflow_id", "default"),
        run_name=body.get("run_name"),
        metadata=body.get("metadata"),
        created_by=body.get("created_by", "api"),
    )
    return JSONResponse({"run_id": run_id, "status": "queued"}, status_code=201)


@app.get("/tower/runs")
async def tower_list_runs(
    status: str | None = None,
    workflow_id: str | None = None,
    limit: int = 50,
):
    """List Tower runs with optional status/workflow filters."""
    from src.tower.store import list_runs

    runs = list_runs(status=status, workflow_id=workflow_id, limit=limit)
    return JSONResponse({"runs": runs, "count": len(runs)})


@app.get("/tower/runs/{run_id}")
async def tower_get_run(run_id: str):
    """Get a Tower run by ID."""
    from src.tower.store import get_run

    run = get_run(run_id)
    if run is None:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return JSONResponse(run)


@app.get("/tower/runs/{run_id}/events")
async def tower_get_events(run_id: str):
    """Get event timeline for a Tower run."""
    from src.tower.store import get_events

    events = get_events(run_id)
    return JSONResponse({"run_id": run_id, "events": events, "count": len(events)})


@app.get("/tower/runs/{run_id}/snapshot")
async def tower_get_snapshot(run_id: str):
    """Get the current LangGraph state snapshot for a Tower run."""
    from src.tower.runner import get_run_snapshot

    snapshot = get_run_snapshot(compiled_graph, run_id)
    if snapshot is None:
        return JSONResponse({"error": "Snapshot not available"}, status_code=404)
    return JSONResponse(snapshot)


@app.post("/tower/runs/{run_id}/resume")
async def tower_resume_run(run_id: str, request: Request):
    """Resume a Tower run after a ticket decision.

    Body: { "ticket_id": int, "decision": "approve"|"reject",
            "decided_by": str, "decision_payload": dict,
            "expected_checkpoint_id": str }
    """
    from src.tower.runner import resume_run

    body = await request.json()
    ticket_id = body.get("ticket_id")
    decision = body.get("decision")

    if not ticket_id or not decision:
        return JSONResponse(
            {"error": "ticket_id and decision are required"}, status_code=400
        )
    if decision not in ("approve", "reject"):
        return JSONResponse(
            {"error": "decision must be 'approve' or 'reject'"}, status_code=400
        )

    try:
        status = resume_run(
            compiled_graph,
            run_id,
            ticket_id,
            decision,
            decided_by=body.get("decided_by", "console"),
            decision_payload=body.get("decision_payload"),
            expected_checkpoint_id=body.get("expected_checkpoint_id"),
        )
        return JSONResponse({"run_id": run_id, "status": status})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@app.get("/tower/inbox")
async def tower_inbox(
    status: str = "pending",
    risk_level: str | None = None,
    limit: int = 50,
):
    """Get Tower ticket inbox (pending tickets needing decisions)."""
    from src.tower.store import list_tickets

    tickets = list_tickets(status=status, risk_level=risk_level, limit=limit)
    return JSONResponse({"tickets": tickets, "count": len(tickets)})


@app.get("/tower/tickets/{ticket_id}")
async def tower_get_ticket(ticket_id: int):
    """Get a Tower ticket by ID."""
    from src.tower.store import get_ticket

    ticket = get_ticket(ticket_id)
    if ticket is None:
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    return JSONResponse(ticket)


@app.post("/tower/tickets/{ticket_id}/decide")
async def tower_decide_ticket(ticket_id: int, request: Request):
    """Decide a Tower ticket (approve/reject) and resume the run.

    Body: { "decision": "approve"|"reject", "decided_by": str,
            "decision_payload": dict, "expected_checkpoint_id": str }
    """
    from src.tower.store import decide_ticket, get_ticket

    body = await request.json()
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        return JSONResponse(
            {"error": "decision must be 'approve' or 'reject'"}, status_code=400
        )

    try:
        ticket = get_ticket(ticket_id)
        if ticket is None:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)

        result = decide_ticket(
            ticket_id,
            decision,
            decided_by=body.get("decided_by", "console"),
            decision_payload=body.get("decision_payload"),
            expected_checkpoint_id=body.get("expected_checkpoint_id"),
        )

        # Auto-resume the run if ticket has a run_id
        run_id = ticket.get("run_id")
        if run_id:
            from src.tower.store import update_run_status, log_event
            update_run_status(run_id, "queued")
            log_event(run_id, "run.resume_queued", {
                "ticket_id": ticket_id,
                "decision": decision,
            })

        return JSONResponse({"ticket_id": ticket_id, "status": result["status"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@app.get("/tower/effects/{effect_id}")
async def tower_get_effect(effect_id: str):
    """Get a Tower effect by ID."""
    from src.tower.store import get_effect

    effect = get_effect(effect_id)
    if effect is None:
        return JSONResponse({"error": "Effect not found"}, status_code=404)
    return JSONResponse(effect)


# Register webhook inbound routes (before security middleware)
from src.webhooks.handlers import register_webhook_routes

register_webhook_routes(app)

# Install security middleware AFTER all routes are registered
from src.security.middleware import install_security_middleware

install_security_middleware(app)


# JSON decode errors should return 400 (not 500)
@app.exception_handler(json.JSONDecodeError)
async def json_decode_error_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse({"error": "Invalid JSON in request body"}, status_code=400)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8050)
