"""Test Tower interrupt/resume with a real LangGraph + PostgresSaver.

This is the Phase 0 vertical slice: proves the full pattern works end-to-end.
In LangGraph 0.6.x with a checkpointer:
- interrupt() does NOT raise GraphInterrupt
- invoke() returns partial state
- get_state() shows next nodes and interrupt info
- Command(resume=...) continues from the interrupt point
"""
import os
os.environ.setdefault("TESTING", "1")

from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command

from src.tower.checkpointer import setup_checkpointer, get_checkpointer, shutdown_checkpointer
from src.tower.store import (
    init_tower_tables,
    create_run,
    get_run,
    create_ticket,
    get_ticket,
    decide_ticket,
    update_run_status,
    log_event,
    get_events,
)
from src.tower.runner import get_run_snapshot


class TowerState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    approved_action: str


def build_test_graph():
    """Build a simple graph that interrupts for approval, then completes."""

    def think_node(state: TowerState) -> dict:
        return {
            "messages": [AIMessage(content="I want to create a Stripe product for $500.")],
        }

    def approval_gate(state: TowerState) -> dict:
        """Interrupt for human approval before executing the risky action."""
        decision = interrupt({
            "ticket_type": "tool_call",
            "risk_level": "high",
            "tldr": "Create Stripe product ($500)",
            "why_stopped": "High-value product creation requires approval",
            "proposed_action": {
                "tool": "stripe_create_product",
                "params": {"name": "Premium Widget", "price": "500.00"},
            },
            "impact": "Will create a real product on Stripe",
            "risk_flags": ["spend > $100", "external API"],
        })

        # This code only runs AFTER resume
        if isinstance(decision, dict) and decision.get("rejected"):
            return {
                "messages": [AIMessage(content="Action was rejected by operator.")],
                "approved_action": "rejected",
            }
        return {
            "messages": [AIMessage(content="Action approved! Proceeding.")],
            "approved_action": "approved",
        }

    def execute_node(state: TowerState) -> dict:
        if state.get("approved_action") == "rejected":
            return {
                "messages": [AIMessage(content="Skipped execution due to rejection.")],
            }
        return {
            "messages": [AIMessage(content="Product created successfully: prod_xyz123")],
        }

    graph = StateGraph(TowerState)
    graph.add_node("think", think_node)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("execute", execute_node)

    graph.set_entry_point("think")
    graph.add_edge("think", "approval_gate")
    graph.add_edge("approval_gate", "execute")
    graph.add_edge("execute", END)

    return graph


def test_full_interrupt_resume():
    """Test the complete interrupt/resume lifecycle with Postgres checkpointing."""
    print("=" * 60)
    print("TOWER VERTICAL SLICE: Full Interrupt/Resume Test")
    print("=" * 60)

    # Setup
    init_tower_tables()
    setup_checkpointer()
    checkpointer = get_checkpointer()

    # Build and compile graph WITH checkpointer
    graph = build_test_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    # 1. Create a Tower run
    run_id = create_run(
        workflow_id="test_approval",
        run_name="Test interrupt/resume",
        input_state={"messages": [{"type": "human", "content": "Create a premium widget"}]},
    )
    update_run_status(run_id, "running")
    print(f"\n1. Created run: {run_id}")

    # 2. Execute the run — it should return partial state (interrupted at approval_gate)
    config = {"configurable": {"thread_id": run_id}}
    input_state = {"messages": [HumanMessage(content="Create a premium widget")]}

    result = compiled.invoke(input_state, config=config)
    print(f"   Invoke returned (partial state)")
    print(f"   Messages: {len(result.get('messages', []))}")

    # 3. Check that the graph is paused at approval_gate
    snapshot = compiled.get_state(config)
    assert snapshot.next, "Expected graph to be paused but next is empty"
    assert "approval_gate" in snapshot.next, f"Expected paused at approval_gate, got {snapshot.next}"
    print(f"\n2. Graph paused at: {snapshot.next}")

    # Extract interrupt info
    assert snapshot.tasks, "Expected tasks with interrupts"
    task = snapshot.tasks[0]
    assert task.interrupts, f"Expected interrupts on task {task.name}"
    interrupt_obj = task.interrupts[0]
    print(f"   Interrupt ID: {interrupt_obj.id}")
    print(f"   Interrupt value: {interrupt_obj.value.get('tldr', 'N/A')}")

    # Get checkpoint ID
    cp_config = snapshot.config.get("configurable", {})
    checkpoint_id = cp_config.get("checkpoint_id")
    print(f"   Checkpoint ID: {checkpoint_id}")

    # 4. Create a ticket in the Tower store
    ticket_id = create_ticket(
        run_id=run_id,
        ticket_type=interrupt_obj.value.get("ticket_type", "tool_call"),
        risk_level=interrupt_obj.value.get("risk_level", "medium"),
        proposed_action=interrupt_obj.value.get("proposed_action", {}),
        context_pack={
            "tldr": interrupt_obj.value.get("tldr", ""),
            "why_stopped": interrupt_obj.value.get("why_stopped", ""),
            "impact": interrupt_obj.value.get("impact", ""),
            "risk_flags": interrupt_obj.value.get("risk_flags", []),
        },
        checkpoint_id=checkpoint_id,
        interrupt_id=str(interrupt_obj.id),
    )
    update_run_status(
        run_id, "waiting_approval",
        last_checkpoint_id=checkpoint_id,
        last_ticket_id=ticket_id,
    )
    print(f"\n3. Created ticket: {ticket_id}")

    # 5. Verify run state
    run_after = get_run(run_id)
    assert run_after["status"] == "waiting_approval"
    print(f"   Run status: {run_after['status']}")

    # 6. Verify snapshot via runner helper
    tower_snapshot = get_run_snapshot(compiled, run_id)
    assert tower_snapshot is not None
    assert "approval_gate" in tower_snapshot["next"]
    print(f"   Tower snapshot next: {tower_snapshot['next']}")

    # 7. Decide the ticket (approve)
    decided = decide_ticket(
        ticket_id, "approve",
        decided_by="test_operator",
        decision_payload={"approved": True, "note": "Looks good"},
        expected_checkpoint_id=checkpoint_id,
    )
    print(f"\n4. Ticket decided: {decided['status']}")

    # 8. Resume the run
    update_run_status(run_id, "running")
    log_event(run_id, "run.resumed", {"ticket_id": ticket_id})

    result = compiled.invoke(
        Command(resume={"approved": True}),
        config=config,
    )
    update_run_status(run_id, "completed")
    print(f"\n5. Run resumed and completed!")

    # 9. Verify final state
    assert result.get("approved_action") == "approved"
    print(f"   approved_action: {result['approved_action']}")

    final_messages = result.get("messages", [])
    print(f"   Final messages: {len(final_messages)}")
    for msg in final_messages[-3:]:
        if hasattr(msg, "content"):
            print(f"   - [{msg.type}] {msg.content[:80]}")

    # 10. Verify graph is now complete (no next)
    final_snapshot = compiled.get_state(config)
    assert not final_snapshot.next, f"Expected complete, but next={final_snapshot.next}"
    print(f"\n6. Graph completed (next=empty)")

    # 11. Verify events timeline
    events = get_events(run_id)
    print(f"\n7. Event timeline ({len(events)} events):")
    for evt in events:
        print(f"   - {evt['event_type']}")

    # 12. Final run state
    final_run = get_run(run_id)
    assert final_run["status"] == "completed"
    assert final_run["finished_at"] is not None
    print(f"\n8. Final run status: {final_run['status']}")

    print("\n" + "=" * 60)
    print("VERTICAL SLICE TEST PASSED")
    print("=" * 60)


def test_reject_flow():
    """Test the reject path."""
    print("\n" + "=" * 60)
    print("TOWER: Reject Flow Test")
    print("=" * 60)

    checkpointer = get_checkpointer()
    graph = build_test_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    run_id = create_run(workflow_id="test_reject", run_name="Test reject flow")
    config = {"configurable": {"thread_id": run_id}}

    # Execute until interrupt
    compiled.invoke(
        {"messages": [HumanMessage(content="Create a rejected widget")]},
        config=config,
    )

    # Verify interrupted
    snap = compiled.get_state(config)
    assert "approval_gate" in snap.next
    print("   Interrupted at approval_gate")

    # Resume with rejection
    result = compiled.invoke(
        Command(resume={"rejected": True, "reason": "Too expensive"}),
        config=config,
    )

    assert result.get("approved_action") == "rejected"
    print(f"   approved_action: {result['approved_action']}")

    last_msg = result["messages"][-1]
    assert "rejection" in last_msg.content.lower() or "skipped" in last_msg.content.lower()
    print(f"   Last message: {last_msg.content}")

    print("\nREJECT FLOW TEST PASSED")


def test_optimistic_concurrency():
    """Test that stale checkpoint_id causes rejection."""
    print("\n" + "=" * 60)
    print("TOWER: Optimistic Concurrency Test")
    print("=" * 60)

    checkpointer = get_checkpointer()
    graph = build_test_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    run_id = create_run(workflow_id="test_concurrency")
    config = {"configurable": {"thread_id": run_id}}

    # Run until interrupt
    compiled.invoke(
        {"messages": [HumanMessage(content="test concurrency")]},
        config=config,
    )

    snap = compiled.get_state(config)
    checkpoint_id = snap.config["configurable"]["checkpoint_id"]
    interrupt_obj = snap.tasks[0].interrupts[0]

    # Create ticket
    ticket_id = create_ticket(
        run_id=run_id,
        checkpoint_id=checkpoint_id,
        interrupt_id=str(interrupt_obj.id),
    )

    # Try to decide with wrong checkpoint_id
    try:
        decide_ticket(
            ticket_id, "approve",
            expected_checkpoint_id="wrong_checkpoint_id",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Stale ticket" in str(e)
        print(f"   Correctly rejected stale checkpoint: {e}")

    # Now decide with correct checkpoint_id
    decided = decide_ticket(
        ticket_id, "approve",
        expected_checkpoint_id=checkpoint_id,
    )
    assert decided["status"] == "approved"
    print(f"   Correctly approved with matching checkpoint")

    print("\nOPTIMISTIC CONCURRENCY TEST PASSED")


if __name__ == "__main__":
    test_full_interrupt_resume()
    test_reject_flow()
    test_optimistic_concurrency()
    shutdown_checkpointer()
    print("\n" + "=" * 60)
    print("ALL PHASE 0 TESTS PASSED")
    print("=" * 60)
