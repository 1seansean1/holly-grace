"""Holly Grace's tools — functions she can call via the Anthropic function-calling API.

Each tool is a plain function with a docstring that serves as the tool description.
The agent module converts these to Anthropic tool schemas.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ticket tools
# ---------------------------------------------------------------------------

def approve_ticket(ticket_id: int, note: str = "") -> dict:
    """Approve a pending tower ticket and resume the associated workflow run.

    Args:
        ticket_id: The ID of the ticket to approve.
        note: Optional note explaining the approval decision.
    """
    from src.tower.store import decide_ticket, get_ticket

    ticket = get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"Ticket {ticket_id} not found"}
    if ticket["status"] != "pending":
        return {"error": f"Ticket {ticket_id} is already {ticket['status']}"}

    result = decide_ticket(
        ticket_id,
        "approve",
        decided_by="holly_grace",
        decision_payload={"note": note} if note else None,
        expected_checkpoint_id=ticket.get("checkpoint_id"),
    )

    # Re-queue the run for the worker to pick up
    from src.tower.store import update_run_status
    if ticket.get("run_id"):
        try:
            update_run_status(ticket["run_id"], "queued")
        except Exception:
            pass

    return {
        "status": "approved",
        "ticket_id": ticket_id,
        "run_id": ticket.get("run_id"),
    }


def reject_ticket(ticket_id: int, reason: str = "") -> dict:
    """Reject a pending tower ticket.

    Args:
        ticket_id: The ID of the ticket to reject.
        reason: Explanation for why the ticket was rejected.
    """
    from src.tower.store import decide_ticket, get_ticket

    ticket = get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"Ticket {ticket_id} not found"}
    if ticket["status"] != "pending":
        return {"error": f"Ticket {ticket_id} is already {ticket['status']}"}

    result = decide_ticket(
        ticket_id,
        "reject",
        decided_by="holly_grace",
        decision_payload={"reason": reason},
        expected_checkpoint_id=ticket.get("checkpoint_id"),
    )

    # Mark the run as failed if it was waiting
    from src.tower.store import update_run_status
    if ticket.get("run_id"):
        try:
            update_run_status(
                ticket["run_id"], "failed",
                last_error=f"Rejected by Holly Grace: {reason}",
            )
        except Exception:
            pass

    return {
        "status": "rejected",
        "ticket_id": ticket_id,
        "run_id": ticket.get("run_id"),
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Workflow tools
# ---------------------------------------------------------------------------

def start_workflow(
    task: str,
    workflow_id: str = "default",
    priority: int = 5,
    run_name: str | None = None,
) -> dict:
    """Start a new durable workflow run in the Control Tower.

    Args:
        task: Description of the task for the workflow to execute.
        workflow_id: Which workflow to run (default: 'default').
        priority: Priority level 1-10 (higher = processed first).
        run_name: Optional human-readable name for the run.
    """
    from src.tower.store import create_run

    input_state = {
        "messages": [{"type": "human", "content": task}],
        "trigger_source": "holly_grace",
        "trigger_payload": {"task": task},
        "retry_count": 0,
    }

    run_id = create_run(
        workflow_id=workflow_id,
        run_name=run_name or task[:80],
        input_state=input_state,
        metadata={"created_via": "holly_grace"},
        priority=priority,
        created_by="holly_grace",
    )

    return {"run_id": run_id, "status": "queued", "workflow_id": workflow_id}


# ---------------------------------------------------------------------------
# Query tools
# ---------------------------------------------------------------------------

def query_runs(status: str | None = None, limit: int = 20) -> dict:
    """List tower runs, optionally filtered by status.

    Args:
        status: Filter by status (queued, running, waiting_approval, completed, failed).
        limit: Maximum number of runs to return.
    """
    from src.tower.store import list_runs

    runs = list_runs(status=status, limit=limit)
    # Summarize for LLM context
    summary = []
    for r in runs:
        summary.append({
            "run_id": r["run_id"],
            "status": r["status"],
            "workflow_id": r.get("workflow_id", "default"),
            "run_name": r.get("run_name"),
            "created_at": str(r.get("created_at", "")),
            "last_error": r.get("last_error"),
        })
    return {"runs": summary, "count": len(summary)}


def query_tickets(status: str = "pending", risk_level: str | None = None, limit: int = 20) -> dict:
    """List tower tickets, optionally filtered by status and risk level.

    Args:
        status: Filter by status (pending, approved, rejected, expired).
        risk_level: Filter by risk level (low, medium, high).
        limit: Maximum number of tickets to return.
    """
    from src.tower.store import list_tickets

    tickets = list_tickets(status=status, risk_level=risk_level, limit=limit)
    summary = []
    for t in tickets:
        cp = t.get("context_pack", {})
        if isinstance(cp, str):
            try:
                cp = json.loads(cp)
            except Exception:
                cp = {}
        summary.append({
            "id": t["id"],
            "run_id": t["run_id"],
            "ticket_type": t["ticket_type"],
            "risk_level": t["risk_level"],
            "status": t["status"],
            "tldr": cp.get("tldr", ""),
            "why_stopped": cp.get("why_stopped", ""),
            "created_at": str(t.get("created_at", "")),
        })
    return {"tickets": summary, "count": len(summary)}


def query_run_detail(run_id: str) -> dict:
    """Get detailed information about a specific tower run including events.

    Args:
        run_id: The ID of the run to inspect.
    """
    from src.tower.store import get_events, get_run

    run = get_run(run_id)
    if run is None:
        return {"error": f"Run {run_id} not found"}

    events = get_events(run_id, limit=50)
    event_summary = [
        {
            "event_type": e["event_type"],
            "created_at": str(e.get("created_at", "")),
            "payload": e.get("payload", {}),
        }
        for e in events
    ]

    return {
        "run": {
            "run_id": run["run_id"],
            "status": run["status"],
            "workflow_id": run.get("workflow_id"),
            "run_name": run.get("run_name"),
            "created_at": str(run.get("created_at", "")),
            "started_at": str(run.get("started_at", "")),
            "finished_at": str(run.get("finished_at", "")),
            "last_error": run.get("last_error"),
        },
        "events": event_summary,
        "event_count": len(event_summary),
    }


def query_system_health() -> dict:
    """Check the health of all system services (Postgres, Redis, Ollama, ChromaDB)."""
    import os
    health = {}

    # Redis — use the same env var as the bus module
    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
        health["redis"] = "healthy"
    except Exception as e:
        health["redis"] = f"unhealthy: {e}"

    # Postgres — use the same env var as the session module
    try:
        import psycopg
        pg_dsn = os.environ.get(
            "DATABASE_URL",
            os.environ.get(
                "POSTGRES_DSN",
                "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
            ),
        )
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("SELECT 1")
        health["postgres"] = "healthy"
    except Exception as e:
        health["postgres"] = f"unhealthy: {e}"

    # Ollama
    try:
        import urllib.request
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11435")
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=3)
        health["ollama"] = "healthy"
    except Exception:
        health["ollama"] = "unreachable"

    # ChromaDB
    try:
        import urllib.request
        chroma_url = os.environ.get("CHROMA_URL", "http://localhost:8100")
        urllib.request.urlopen(f"{chroma_url}/api/v1/heartbeat", timeout=3)
        health["chromadb"] = "healthy"
    except Exception:
        health["chromadb"] = "unreachable"

    # Run counts
    from src.tower.store import list_runs, list_tickets
    try:
        running = list_runs(status="running", limit=100)
        queued = list_runs(status="queued", limit=100)
        waiting = list_runs(status="waiting_approval", limit=100)
        pending_tickets = list_tickets(status="pending", limit=100)
        health["active_runs"] = len(running)
        health["queued_runs"] = len(queued)
        health["waiting_approval"] = len(waiting)
        health["pending_tickets"] = len(pending_tickets)
    except Exception:
        pass

    overall = "healthy" if all(
        v == "healthy" for k, v in health.items()
        if k in ("redis", "postgres")
    ) else "degraded"
    health["overall"] = overall

    return health


def query_financial_health() -> dict:
    """Get current financial health: revenue phase, epsilon, and budget status."""
    try:
        from src.aps.financial_health import get_financial_health
        fh = get_financial_health()
        return {
            "phase": fh.phase.value if hasattr(fh.phase, "value") else str(fh.phase),
            "epsilon_r": fh.epsilon_r,
            "monthly_revenue": fh.monthly_revenue,
            "monthly_refunds": fh.monthly_refunds,
            "balance": fh.balance,
            "last_updated": str(fh.last_updated) if fh.last_updated else None,
        }
    except Exception as e:
        return {"error": f"Financial health unavailable: {e}"}


def send_notification(channel: str, message: str) -> dict:
    """Send a notification via a channel (slack or email).

    Args:
        channel: The channel to send through ('slack' or 'email').
        message: The message content to send.
    """
    try:
        from src.channels.bridge import get_channel_dock
        dock = get_channel_dock()
        dock.send(channel, message)
        return {"status": "sent", "channel": channel}
    except Exception as e:
        return {"error": f"Failed to send via {channel}: {e}"}


# ---------------------------------------------------------------------------
# Construction Crew dispatch tools
# ---------------------------------------------------------------------------

def dispatch_crew(agent_id: str, task: str, context: str = "") -> dict:
    """Dispatch a Construction Crew agent to perform a task.

    Creates a Tower run for the crew agent so the work is durable,
    interruptible, and auditable.

    Args:
        agent_id: The crew agent ID (e.g., 'crew_architect').
        task: Description of what the crew agent should do.
        context: Additional context or specifications for the task.
    """
    from src.holly.crew.registry import get_crew_agent
    from src.tower.store import create_run

    agent = get_crew_agent(agent_id)
    if agent is None:
        return {"error": f"Unknown crew agent: {agent_id}"}

    input_state = {
        "messages": [{"type": "human", "content": task}],
        "trigger_source": "holly_grace_crew",
        "trigger_payload": {
            "crew_agent": agent_id,
            "task": task,
            "context": context,
        },
        "retry_count": 0,
    }

    run_id = create_run(
        workflow_id=f"crew_solo_{agent_id}",
        run_name=f"[{agent.display_name}] {task[:60]}",
        input_state=input_state,
        metadata={
            "created_via": "holly_grace_crew",
            "crew_agent": agent_id,
            "crew_model": agent.model,
        },
        priority=7,
        created_by="holly_grace",
    )

    return {
        "run_id": run_id,
        "status": "queued",
        "crew_agent": agent_id,
        "display_name": agent.display_name,
    }


def list_crew_agents() -> dict:
    """List all available Construction Crew agents and their roles."""
    from src.holly.crew.registry import list_crew
    agents = list_crew()
    return {"agents": agents, "count": len(agents)}


# ---------------------------------------------------------------------------
# System introspection tools
# ---------------------------------------------------------------------------

def query_registered_tools(category: str | None = None) -> dict:
    """List all registered tools (Python + MCP), optionally filtered by category.

    Args:
        category: Filter by category (e.g., 'shopify', 'stripe', 'mcp', 'hierarchy').
    """
    from src.tool_registry import get_tool_registry

    registry = get_tool_registry()
    all_tools = registry.to_dicts()

    if category:
        all_tools = [t for t in all_tools if t.get("category") == category]

    summary = [
        {
            "tool_id": t["tool_id"],
            "display_name": t.get("display_name", t["tool_id"]),
            "description": t.get("description", ""),
            "category": t.get("category", ""),
            "provider": t.get("provider", ""),
        }
        for t in all_tools
    ]

    categories = sorted(set(t.get("category", "") for t in all_tools))
    return {"tools": summary, "count": len(summary), "categories": categories}


def query_mcp_servers() -> dict:
    """List all registered MCP servers with their health status and tool counts."""
    from src.mcp.store import list_servers, list_tools

    try:
        servers = list_servers()
        summary = []
        for s in servers:
            tools = list_tools(s["server_id"])
            summary.append({
                "server_id": s["server_id"],
                "display_name": s.get("display_name", s["server_id"]),
                "transport": s.get("transport", ""),
                "enabled": s.get("enabled", True),
                "health_status": s.get("last_health_status", "unknown"),
                "health_error": s.get("last_health_error", "") or "",
                "tool_count": len(tools),
                "enabled_tool_count": sum(1 for t in tools if t.get("enabled")),
            })
        return {"servers": summary, "count": len(summary)}
    except Exception as e:
        return {"error": f"MCP store unavailable: {e}"}


def query_agents(agent_id: str | None = None) -> dict:
    """List agent configurations, or get details for a specific agent.

    Args:
        agent_id: Optional specific agent ID to look up.
    """
    from src.agent_registry import get_registry

    registry = get_registry()

    if agent_id:
        configs = registry.get_all()
        match = [c for c in configs if c.agent_id == agent_id]
        if not match:
            return {"error": f"Agent '{agent_id}' not found"}
        c = match[0]
        return {
            "agent_id": c.agent_id,
            "display_name": c.display_name,
            "description": c.description,
            "model_id": c.model_id,
            "channel_id": c.channel_id,
            "tool_ids": c.tool_ids,
            "version": c.version,
            "is_builtin": c.is_builtin,
        }

    configs = registry.get_all()
    summary = [
        {
            "agent_id": c.agent_id,
            "display_name": c.display_name,
            "description": c.description,
            "model_id": c.model_id,
            "tool_count": len(c.tool_ids),
            "is_builtin": c.is_builtin,
        }
        for c in configs
    ]
    return {"agents": summary, "count": len(summary)}


def query_workflows(workflow_id: str | None = None) -> dict:
    """List workflow definitions, or get details for a specific workflow.

    Args:
        workflow_id: Optional specific workflow ID to look up.
    """
    from src.workflow_registry import get_workflow_registry

    registry = get_workflow_registry()

    if workflow_id:
        wf = registry.get(workflow_id)
        if not wf:
            return {"error": f"Workflow '{workflow_id}' not found"}
        defn = wf.get("definition", {})
        return {
            "workflow_id": wf["workflow_id"],
            "display_name": wf.get("display_name", ""),
            "description": wf.get("description", ""),
            "is_active": wf.get("is_active", False),
            "version": wf.get("version", 1),
            "node_count": len(defn.get("nodes", [])) if isinstance(defn, dict) else 0,
            "edge_count": len(defn.get("edges", [])) if isinstance(defn, dict) else 0,
        }

    workflows = registry.get_all()
    summary = [
        {
            "workflow_id": w["workflow_id"],
            "display_name": w.get("display_name", ""),
            "description": w.get("description", ""),
            "is_active": w.get("is_active", False),
            "version": w.get("version", 1),
        }
        for w in workflows
    ]
    return {"workflows": summary, "count": len(summary)}


def query_hierarchy_gate() -> dict:
    """Check the lexicographic gate status at all levels (L0-L6)."""
    from src.hierarchy.store import get_all_predicates, get_gate_status

    try:
        gates = get_gate_status()
        predicates = get_all_predicates()

        gate_summary = [
            {
                "level": g.level,
                "is_open": g.is_open,
                "failing_predicates": g.failing_predicates,
                "failing_count": len(g.failing_predicates),
            }
            for g in gates
        ]

        all_open = all(g.is_open for g in gates)
        total_failing = sum(len(g.failing_predicates) for g in gates)

        return {
            "overall": "open" if all_open else "blocked",
            "total_predicates": len(predicates),
            "total_failing": total_failing,
            "levels": gate_summary,
        }
    except Exception as e:
        return {"error": f"Hierarchy store unavailable: {e}"}


def query_scheduled_jobs() -> dict:
    """List all scheduled jobs with their next run times and triggers."""
    from src.scheduler.autonomous import get_global_scheduler

    try:
        sched = get_global_scheduler()
        if sched is None:
            return {"error": "Scheduler not initialized"}

        jobs = [
            {
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else "paused",
                "trigger": str(job.trigger),
            }
            for job in sched.jobs
        ]
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        return {"error": f"Scheduler unavailable: {e}"}


# ---------------------------------------------------------------------------
# MCP tool bridge — call any registered MCP tool
# ---------------------------------------------------------------------------

def store_memory_fact(category: str, content: str, source: str | None = None) -> dict:
    """Store a key fact in Holly's long-term memory.

    Facts persist across sessions and are retrieved in context assembly.
    Categories help organize knowledge (e.g. 'system', 'revenue', 'crew',
    'workflow', 'model', 'lesson_learned').
    """
    from src.holly.memory import store_fact

    try:
        fact_id = store_fact(category, content, source=source)
        return {"stored": True, "fact_id": fact_id, "category": category}
    except Exception as e:
        return {"error": f"Failed to store fact: {e}"}


def query_memory(category: str | None = None, limit: int = 20) -> dict:
    """Query Holly's long-term memory facts and recent episodes.

    Returns both facts (optionally filtered by category) and recent
    episode summaries from completed tasks.
    """
    from src.holly.memory import get_facts, get_recent_episodes

    try:
        facts = get_facts(category=category, limit=limit)
        episodes = get_recent_episodes(limit=10)
        return {
            "facts": facts,
            "fact_count": len(facts),
            "recent_episodes": episodes,
            "episode_count": len(episodes),
        }
    except Exception as e:
        return {"error": f"Memory query failed: {e}"}


def query_autonomy_status() -> dict:
    """Check the status of Holly's autonomous execution loop."""
    from src.holly.autonomy import get_autonomy_status, get_queue_depth

    try:
        status = get_autonomy_status()
        status["queue_depth"] = get_queue_depth()
        return status
    except Exception as e:
        return {"error": f"Autonomy status unavailable: {e}"}


def submit_autonomous_task(objective: str, priority: str = "normal") -> dict:
    """Submit a new task to Holly's autonomous execution queue.

    Tasks are processed in order (high-priority tasks jump the queue).
    """
    from src.holly.autonomy import submit_task

    try:
        task_id = submit_task(objective, priority=priority)
        return {"submitted": True, "task_id": task_id, "priority": priority}
    except Exception as e:
        return {"error": f"Failed to submit task: {e}"}


def tune_epsilon(
    goal_id: str | None = None,
    action: str = "status",
    new_epsilon: float | None = None,
) -> dict:
    """Inspect or adjust APS epsilon values for morphogenetic goals.

    Actions:
      - "status": Get current epsilon values for all goals (or one goal)
      - "adjust": Change epsilon_G for a goal (requires goal_id + new_epsilon)
      - "revenue_phase": Get current revenue phase and epsilon_R
      - "costs": Get model cost summary and per-workflow spending

    Args:
        goal_id: Specific goal to inspect/adjust (optional for status/revenue_phase).
        action: One of "status", "adjust", "revenue_phase", "costs".
        new_epsilon: New epsilon_G value (only for action="adjust", 0.0-1.0).
    """
    if action == "revenue_phase":
        try:
            from src.aps.revenue_epsilon import get_revenue_epsilon
            from src.aps.financial_health import get_latest_health

            epsilon_r = get_revenue_epsilon()
            health = get_latest_health()
            phase = "unknown"
            if health:
                from src.aps.revenue_epsilon import _classify_phase
                phase = _classify_phase(health)
            return {
                "epsilon_r": epsilon_r,
                "phase": phase,
                "monthly_revenue": health.monthly_revenue if health else 0,
                "balance": health.balance if health else 0,
            }
        except Exception as e:
            return {"error": f"Revenue phase unavailable: {e}"}

    if action == "costs":
        try:
            from src.llm.cost_config import get_cost_summary, get_total_cost_by_workflow
            return {
                "models": get_cost_summary(),
                "per_workflow": get_total_cost_by_workflow(),
            }
        except Exception as e:
            return {"error": f"Cost data unavailable: {e}"}

    if action == "status":
        try:
            from src.morphogenetic.goals import get_default_goal_specs
            goals = get_default_goal_specs()
            if goal_id:
                goals = [g for g in goals if g.goal_id == goal_id]
                if not goals:
                    return {"error": f"Goal '{goal_id}' not found"}
            return {
                "goals": [
                    {
                        "goal_id": g.goal_id,
                        "display_name": g.display_name,
                        "epsilon_g": g.epsilon_g,
                        "horizon_t": g.horizon_t,
                        "primary_tier": g.primary_tier,
                        "priority": g.priority,
                    }
                    for g in goals
                ],
                "count": len(goals),
            }
        except Exception as e:
            return {"error": f"Goal status unavailable: {e}"}

    if action == "adjust":
        if not goal_id:
            return {"error": "goal_id is required for action='adjust'"}
        if new_epsilon is None or not (0.0 <= new_epsilon <= 1.0):
            return {"error": "new_epsilon must be between 0.0 and 1.0"}
        try:
            from src.aps.store import get_goal, upsert_goal
            existing = get_goal(goal_id)
            if not existing:
                return {"error": f"Goal '{goal_id}' not found in DB"}
            old_epsilon = existing.get("epsilon_g", 0)
            existing["epsilon_g"] = new_epsilon
            upsert_goal(existing)
            logger.info("Epsilon adjusted for %s: %.4f → %.4f", goal_id, old_epsilon, new_epsilon)
            return {
                "adjusted": True,
                "goal_id": goal_id,
                "old_epsilon": old_epsilon,
                "new_epsilon": new_epsilon,
            }
        except Exception as e:
            return {"error": f"Failed to adjust epsilon: {e}"}

    return {"error": f"Unknown action: {action}. Use 'status', 'adjust', 'revenue_phase', or 'costs'."}


def run_workflow(workflow_name: str) -> dict:
    """Manually trigger a registered workflow (signal_generator or revenue_engine).

    Args:
        workflow_name: One of "signal_generator" or "revenue_engine".
    """
    if workflow_name == "signal_generator":
        try:
            from src.workflows.signal_generator import run_signal_generator
            result = run_signal_generator()
            return {"status": "completed", "workflow": workflow_name, "summary": result}
        except Exception as e:
            return {"error": f"Signal generator failed: {e}"}

    elif workflow_name == "revenue_engine":
        try:
            from src.workflows.revenue_engine import run_revenue_engine
            result = run_revenue_engine()
            return {"status": "completed", "workflow": workflow_name, "summary": result}
        except Exception as e:
            return {"error": f"Revenue engine failed: {e}"}

    return {"error": f"Unknown workflow: {workflow_name}. Options: signal_generator, revenue_engine"}


def query_crew_enneagram(agent_id: str | None = None) -> dict:
    """Query crew enneagram personality profiles and team balance.

    Args:
        agent_id: Optional specific crew agent to inspect.
    """
    from src.holly.crew.enneagram import get_crew_type, get_coupling_axes, get_team_balance_report

    if agent_id:
        etype = get_crew_type(agent_id)
        if not etype:
            return {"error": f"No enneagram type for '{agent_id}'"}
        axes = get_coupling_axes(agent_id)
        return {
            "agent_id": agent_id,
            "type": etype.number,
            "name": etype.name,
            "triad": etype.triad,
            "core_desire": etype.core_desire,
            "core_fear": etype.core_fear,
            "voice_traits": etype.voice_traits,
            "coupling_axes": axes,
        }

    return get_team_balance_report()


def call_mcp_tool(server_id: str, tool_name: str, arguments: dict | None = None) -> dict:
    """Call any tool on any registered MCP server.

    Use query_mcp_servers first to discover available servers and tools,
    then use this to invoke them.

    Args:
        server_id: The MCP server ID (e.g. "github-reader").
        tool_name: The tool name on that server (e.g. "read_file").
        arguments: Tool arguments as a dict (varies by tool).
    """
    from src.mcp.manager import get_mcp_manager

    try:
        result = get_mcp_manager().call_tool(server_id, tool_name, arguments or {})
        return {"server_id": server_id, "tool": tool_name, "result": result}
    except Exception as e:
        return {"error": str(e), "server_id": server_id, "tool": tool_name}


# ---------------------------------------------------------------------------
# Tool registry for the agent
# ---------------------------------------------------------------------------

HOLLY_TOOLS = {
    "approve_ticket": approve_ticket,
    "reject_ticket": reject_ticket,
    "start_workflow": start_workflow,
    "query_runs": query_runs,
    "query_tickets": query_tickets,
    "query_run_detail": query_run_detail,
    "query_system_health": query_system_health,
    "query_financial_health": query_financial_health,
    "send_notification": send_notification,
    "dispatch_crew": dispatch_crew,
    "list_crew_agents": list_crew_agents,
    "query_registered_tools": query_registered_tools,
    "query_mcp_servers": query_mcp_servers,
    "query_agents": query_agents,
    "query_workflows": query_workflows,
    "query_hierarchy_gate": query_hierarchy_gate,
    "query_scheduled_jobs": query_scheduled_jobs,
    "tune_epsilon": tune_epsilon,
    "run_workflow": run_workflow,
    "query_crew_enneagram": query_crew_enneagram,
    "call_mcp_tool": call_mcp_tool,
    "store_memory_fact": store_memory_fact,
    "query_memory": query_memory,
    "query_autonomy_status": query_autonomy_status,
    "submit_autonomous_task": submit_autonomous_task,
}

# Anthropic tool schemas for function calling
HOLLY_TOOL_SCHEMAS = [
    {
        "name": "approve_ticket",
        "description": "Approve a pending tower ticket and resume the associated workflow run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to approve"},
                "note": {"type": "string", "description": "Optional approval note"},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "reject_ticket",
        "description": "Reject a pending tower ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to reject"},
                "reason": {"type": "string", "description": "Reason for rejection"},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "start_workflow",
        "description": "Start a new durable workflow run in the Control Tower.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description for the workflow"},
                "workflow_id": {"type": "string", "description": "Which workflow to run"},
                "priority": {"type": "integer", "description": "Priority 1-10 (higher first)"},
                "run_name": {"type": "string", "description": "Human-readable run name"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "query_runs",
        "description": "List tower runs, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status"},
                "limit": {"type": "integer", "description": "Max results"},
            },
        },
    },
    {
        "name": "query_tickets",
        "description": "List tower tickets, optionally filtered by status and risk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (default: pending)"},
                "risk_level": {"type": "string", "description": "Filter by risk level"},
                "limit": {"type": "integer", "description": "Max results"},
            },
        },
    },
    {
        "name": "query_run_detail",
        "description": "Get detailed information about a specific run including events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "The run ID to inspect"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "query_system_health",
        "description": "Check health of all system services (Postgres, Redis, Ollama, ChromaDB) and run counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_financial_health",
        "description": "Get current financial health: revenue phase, epsilon, and budget status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_notification",
        "description": "Send a notification via Slack or email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["slack", "email"], "description": "Channel"},
                "message": {"type": "string", "description": "Message content"},
            },
            "required": ["channel", "message"],
        },
    },
    {
        "name": "dispatch_crew",
        "description": "Dispatch a Construction Crew agent to perform a task. Creates a durable Tower run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Crew agent ID (e.g. 'crew_architect')"},
                "task": {"type": "string", "description": "Task description for the crew agent"},
                "context": {"type": "string", "description": "Additional context or specifications"},
            },
            "required": ["agent_id", "task"],
        },
    },
    {
        "name": "list_crew_agents",
        "description": "List all available Construction Crew agents and their roles.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_registered_tools",
        "description": "List all registered tools (Python and MCP), optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category (shopify, stripe, mcp, hierarchy, etc.)"},
            },
        },
    },
    {
        "name": "query_mcp_servers",
        "description": "List all registered MCP servers with health status and tool counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_agents",
        "description": "List all agent configurations, or get details for a specific agent including model, tools, and description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Optional specific agent ID to look up"},
            },
        },
    },
    {
        "name": "query_workflows",
        "description": "List all workflow definitions, or get details for a specific workflow including node/edge counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Optional specific workflow ID to look up"},
            },
        },
    },
    {
        "name": "query_hierarchy_gate",
        "description": "Check the lexicographic gate status at all levels (L0-L6). Shows which levels are open/blocked and which predicates are failing.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_scheduled_jobs",
        "description": "List all scheduled jobs with their next run times and triggers.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tune_epsilon",
        "description": "Inspect or adjust APS epsilon values. Actions: 'status' (list goal epsilons), 'adjust' (change a goal's epsilon_G), 'revenue_phase' (current phase + epsilon_R), 'costs' (model pricing + per-workflow spend).",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "description": "Goal ID to inspect or adjust"},
                "action": {"type": "string", "enum": ["status", "adjust", "revenue_phase", "costs"], "description": "What to do"},
                "new_epsilon": {"type": "number", "description": "New epsilon value (0.0-1.0, only for adjust)"},
            },
        },
    },
    {
        "name": "run_workflow",
        "description": "Manually trigger a registered workflow. Options: 'signal_generator' (A/B test product descriptions) or 'revenue_engine' (SEO + content marketing).",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_name": {"type": "string", "enum": ["signal_generator", "revenue_engine"], "description": "Which workflow to run"},
            },
            "required": ["workflow_name"],
        },
    },
    {
        "name": "query_crew_enneagram",
        "description": "Query crew personality profiles (enneagram types, coupling axes, team balance). Pass agent_id for one agent, or omit for full team report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Optional crew agent ID to inspect"},
            },
        },
    },
    {
        "name": "call_mcp_tool",
        "description": "Call any tool on any registered MCP server. Use query_mcp_servers first to discover available servers and their tools, then invoke them here. For example: call_mcp_tool('github-reader', 'read_file', {'path': 'src/serve.py'}).",
        "input_schema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "The MCP server ID (e.g. 'github-reader')"},
                "tool_name": {"type": "string", "description": "The tool name on that server (e.g. 'read_file')"},
                "arguments": {"type": "object", "description": "Tool arguments as key-value pairs (varies by tool)"},
            },
            "required": ["server_id", "tool_name"],
        },
    },
    {
        "name": "store_memory_fact",
        "description": "Store a key fact in long-term memory. Facts persist across sessions. Use categories like 'system', 'revenue', 'crew', 'workflow', 'model', 'lesson_learned', 'config'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Fact category for organization"},
                "content": {"type": "string", "description": "The fact to store"},
                "source": {"type": "string", "description": "Where this fact came from (optional)"},
            },
            "required": ["category", "content"],
        },
    },
    {
        "name": "query_memory",
        "description": "Query long-term memory facts and recent task episodes. Use to recall past decisions, learned patterns, and system knowledge.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter facts by category (optional)"},
                "limit": {"type": "integer", "description": "Max facts to return (default 20)"},
            },
        },
    },
    {
        "name": "query_autonomy_status",
        "description": "Check the status of the autonomous execution loop: current task, queue depth, completed count.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "submit_autonomous_task",
        "description": "Submit a new task to the autonomous execution queue. High-priority tasks jump the queue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "What to accomplish"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"], "description": "Task priority"},
            },
            "required": ["objective"],
        },
    },
]
