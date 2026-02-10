"""Tower runner: start, execute, interrupt, and resume durable workflow runs.

This module contains the pure functions that drive run lifecycle.
The worker calls these; the API endpoints call these.

LangGraph 0.6.x behavior with checkpointer:
- interrupt() does NOT raise GraphInterrupt
- invoke() returns partial state
- get_state() shows next nodes and interrupt info
- Command(resume=...) continues from the interrupt point
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from src.tower.checkpointer import get_checkpointer
from src.tower.store import (
    create_run,
    create_ticket,
    get_run,
    get_ticket,
    log_event,
    update_run_status,
)

logger = logging.getLogger(__name__)


def start_run(
    compiled_graph: CompiledStateGraph,
    *,
    input_state: dict,
    run_id: str | None = None,
    workflow_id: str = "default",
    run_name: str | None = None,
    metadata: dict | None = None,
    created_by: str | None = None,
) -> str:
    """Create a run record and queue it for execution. Returns run_id."""
    run_id = create_run(
        run_id=run_id,
        workflow_id=workflow_id,
        run_name=run_name,
        input_state=input_state,
        metadata=metadata,
        created_by=created_by,
    )
    logger.info("Tower run created: %s (workflow=%s)", run_id, workflow_id)
    return run_id


def execute_run(
    compiled_graph: CompiledStateGraph,
    run: dict,
) -> dict:
    """Execute a run until completion or interrupt.

    This is called by the worker after claiming a run.
    Returns the final run state dict.

    In LangGraph 0.6.x with a checkpointer, interrupt() does NOT raise
    GraphInterrupt. Instead invoke() returns partial state and get_state()
    reveals the interrupt via snapshot.next and snapshot.tasks[].interrupts.
    """
    run_id = run["run_id"]
    config = {"configurable": {"thread_id": run_id}}

    # Determine if this is a fresh start or a resume
    is_resume = run.get("last_checkpoint_id") is not None

    try:
        if is_resume:
            # Resume from last checkpoint — state is already in checkpointer
            ticket_id = run.get("last_ticket_id")
            resume_value = None
            if ticket_id:
                ticket = get_ticket(ticket_id)
                if ticket and ticket["status"] == "approved":
                    resume_value = ticket.get("decision_payload") or {"approved": True}
                elif ticket and ticket["status"] == "rejected":
                    resume_value = {"rejected": True, "reason": (ticket.get("decision_payload") or {}).get("reason", "")}

            if resume_value is not None:
                log_event(run_id, "run.resumed", {"ticket_id": ticket_id})
                result = compiled_graph.invoke(
                    Command(resume=resume_value),
                    config=config,
                )
            else:
                logger.warning("Run %s has checkpoint but no decided ticket", run_id)
                result = compiled_graph.invoke(None, config=config)
        else:
            # Fresh start
            input_state = run.get("input_state", {})
            result = compiled_graph.invoke(input_state, config=config)

        # Check if the graph is paused at an interrupt (0.6.x pattern)
        snapshot = compiled_graph.get_state(config)
        if snapshot and snapshot.next:
            # Graph is paused — extract interrupt info from snapshot
            return _handle_interrupt_from_snapshot(run_id, snapshot, compiled_graph)

        # Run completed successfully (no next nodes)
        update_run_status(run_id, "completed")
        log_event(run_id, "run.completed")
        logger.info("Tower run completed: %s", run_id)
        return result

    except Exception as exc:
        update_run_status(run_id, "failed", last_error=str(exc)[:2000])
        log_event(run_id, "run.failed", {"error": str(exc)[:500]})
        logger.exception("Tower run failed: %s", run_id)
        raise


def resume_run(
    compiled_graph: CompiledStateGraph,
    run_id: str,
    ticket_id: int,
    decision: str,
    *,
    decided_by: str = "console",
    decision_payload: dict | None = None,
    expected_checkpoint_id: str | None = None,
) -> str:
    """Resume a run after a ticket decision.

    Validates the ticket, applies the decision, and re-queues the run.
    Returns the run status after re-queuing.
    """
    from src.tower.store import decide_ticket

    run = get_run(run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run["status"] != "waiting_approval":
        raise ValueError(f"Run {run_id} is {run['status']}, not waiting_approval")

    # Decide the ticket (validates optimistic concurrency)
    decide_ticket(
        ticket_id,
        decision,
        decided_by=decided_by,
        decision_payload=decision_payload,
        expected_checkpoint_id=expected_checkpoint_id,
    )

    # Re-queue the run so the worker picks it up
    update_run_status(run_id, "queued")
    log_event(run_id, "run.resume_queued", {
        "ticket_id": ticket_id,
        "decision": decision,
    })

    logger.info(
        "Tower run %s re-queued after ticket %d decision: %s",
        run_id, ticket_id, decision,
    )
    return "queued"


def get_run_snapshot(
    compiled_graph: CompiledStateGraph,
    run_id: str,
) -> dict | None:
    """Get the current LangGraph state snapshot for a run."""
    config = {"configurable": {"thread_id": run_id}}
    try:
        snapshot = compiled_graph.get_state(config)
        if snapshot is None:
            return None
        return {
            "values": snapshot.values,
            "next": list(snapshot.next) if snapshot.next else [],
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "interrupts": [
                        {"id": i.id, "value": i.value}
                        for i in (t.interrupts or [])
                    ] if hasattr(t, "interrupts") and t.interrupts else [],
                }
                for t in (snapshot.tasks or [])
            ],
        }
    except Exception as exc:
        logger.warning("Failed to get snapshot for run %s: %s", run_id, exc)
        return None


def _handle_interrupt_from_snapshot(
    run_id: str,
    snapshot: Any,
    compiled_graph: CompiledStateGraph,
) -> dict:
    """Handle an interrupt detected via snapshot (LangGraph 0.6.x pattern).

    In 0.6.x with checkpointer, interrupt() does NOT raise GraphInterrupt.
    Instead, invoke() returns and get_state() reveals the pause point via
    snapshot.next and snapshot.tasks[].interrupts.
    """
    # Extract checkpoint_id from snapshot config
    checkpoint_id = None
    if snapshot.config:
        cp_config = snapshot.config.get("configurable", {})
        checkpoint_id = cp_config.get("checkpoint_id")

    # Extract interrupt info from snapshot tasks
    interrupt_id = None
    interrupt_value = None
    for task in (snapshot.tasks or []):
        if hasattr(task, "interrupts") and task.interrupts:
            interrupt_obj = task.interrupts[0]
            interrupt_id = interrupt_obj.id
            interrupt_value = interrupt_obj.value
            break

    if interrupt_value is None:
        logger.warning("Run %s paused at %s but no interrupt payload found", run_id, snapshot.next)
        update_run_status(run_id, "failed", last_error="Paused without interrupt payload")
        return {}

    # Build context pack from interrupt payload
    context_pack = _build_context_pack(interrupt_value)

    # Determine ticket type and risk from interrupt payload
    ticket_type = "tool_call"
    risk_level = "medium"
    proposed_action = {}
    if isinstance(interrupt_value, dict):
        ticket_type = interrupt_value.get("ticket_type", "tool_call")
        risk_level = interrupt_value.get("risk_level", "medium")
        proposed_action = interrupt_value.get("proposed_action", interrupt_value)

    # Create the ticket
    ticket_id = create_ticket(
        run_id=run_id,
        ticket_type=ticket_type,
        risk_level=risk_level,
        proposed_action=proposed_action,
        context_pack=context_pack,
        checkpoint_id=checkpoint_id,
        interrupt_id=str(interrupt_id) if interrupt_id else None,
    )

    # Park the run
    update_run_status(
        run_id,
        "waiting_approval",
        last_checkpoint_id=checkpoint_id,
        last_ticket_id=ticket_id,
    )
    log_event(run_id, "run.waiting_approval", {
        "ticket_id": ticket_id,
        "checkpoint_id": checkpoint_id,
        "interrupt_id": str(interrupt_id) if interrupt_id else None,
    })

    # Publish to message bus (fire-and-forget)
    from src.bus import STREAM_TOWER_EVENTS, publish
    publish(STREAM_TOWER_EVENTS, "run.waiting_approval", {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "ticket_type": ticket_type,
        "risk_level": risk_level,
        "checkpoint_id": checkpoint_id,
    }, source="tower.runner")

    logger.info(
        "Tower run %s interrupted — ticket %d created (type=%s, risk=%s)",
        run_id, ticket_id, ticket_type, risk_level,
    )
    return {"interrupted": True, "ticket_id": ticket_id}


def _build_context_pack(interrupt_value: Any) -> dict:
    """Build a structured context pack from an interrupt payload."""
    if isinstance(interrupt_value, dict):
        return {
            "tldr": interrupt_value.get("tldr", "Approval required"),
            "why_stopped": interrupt_value.get("why_stopped", "Action requires human approval"),
            "proposed_action_preview": interrupt_value.get("proposed_action_preview", ""),
            "impact": interrupt_value.get("impact", ""),
            "risk_flags": interrupt_value.get("risk_flags", []),
            "options": {
                "approve": True,
                "approve_with_edits": bool(interrupt_value.get("allowed_edits")),
                "reject": True,
            },
        }
    return {
        "tldr": "Approval required",
        "why_stopped": str(interrupt_value)[:200] if interrupt_value else "Unknown",
        "options": {"approve": True, "reject": True},
    }
