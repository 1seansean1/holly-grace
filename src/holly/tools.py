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
    health = {}

    # Redis
    try:
        import redis
        r = redis.from_url("redis://localhost:6381/0", decode_responses=True)
        r.ping()
        health["redis"] = "healthy"
    except Exception as e:
        health["redis"] = f"unhealthy: {e}"

    # Postgres
    try:
        import psycopg
        with psycopg.connect(
            "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
            autocommit=True,
        ) as conn:
            conn.execute("SELECT 1")
        health["postgres"] = "healthy"
    except Exception as e:
        health["postgres"] = f"unhealthy: {e}"

    # Ollama
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11435/api/tags", timeout=3)
        health["ollama"] = "healthy"
    except Exception:
        health["ollama"] = "unreachable"

    # ChromaDB
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:8100/api/v1/heartbeat", timeout=3)
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
]
