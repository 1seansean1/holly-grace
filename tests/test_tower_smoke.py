"""Smoke test for Tower store — run this directly to verify tables + CRUD."""
import os
os.environ.setdefault("TESTING", "1")

from src.tower.store import (
    init_tower_tables,
    create_run,
    get_run,
    log_event,
    get_events,
    create_ticket,
    get_ticket,
    list_tickets,
    decide_ticket,
    prepare_effect,
    get_effect,
    commit_effect,
    claim_queued_run,
    update_run_status,
    list_runs,
)


def test_tower_store():
    # Init tables
    init_tower_tables()
    print("Tables created OK")

    # Clean up any leftover queued runs from previous test runs
    from src.tower.store import _get_conn
    with _get_conn() as conn:
        conn.execute("UPDATE tower_runs SET status = 'cancelled' WHERE status = 'queued'")

    # Create a run
    rid = create_run(workflow_id="test", run_name="smoke test")
    print(f"Created run: {rid}")

    # Get it back
    r = get_run(rid)
    assert r is not None
    assert r["status"] == "queued"
    print(f"Run status: {r['status']}")

    # List runs
    runs = list_runs()
    assert len(runs) >= 1
    print(f"Listed {len(runs)} runs")

    # Claim the run
    claimed = claim_queued_run()
    assert claimed is not None
    assert claimed["run_id"] == rid
    assert claimed["status"] == "running"
    print(f"Claimed run: {claimed['run_id']}")

    # Log an event
    eid = log_event(rid, "test.event", {"hello": "world"})
    print(f"Logged event: {eid}")

    # Get events
    evts = get_events(rid)
    assert len(evts) >= 2  # run.queued + run.started + test.event
    print(f"Events count: {len(evts)}")

    # Create a ticket
    tid = create_ticket(
        run_id=rid,
        ticket_type="tool_call",
        risk_level="high",
        proposed_action={"tool": "stripe_create_product", "params": {"price": "50"}},
        context_pack={"tldr": "Create a product on Stripe"},
        checkpoint_id="cp_abc123",
    )
    print(f"Created ticket: {tid}")

    # Get ticket
    t = get_ticket(tid)
    assert t is not None
    assert t["status"] == "pending"
    assert t["risk_level"] == "high"
    print(f"Ticket status: {t['status']}")

    # List pending tickets
    tix = list_tickets(status="pending")
    assert len(tix) >= 1
    print(f"Pending tickets: {len(tix)}")

    # Decide ticket
    decided = decide_ticket(tid, "approve", decided_by="test", decision_payload={"ok": True})
    assert decided["status"] == "approved"
    print(f"Ticket decided: {decided['status']}")

    # Prepare an effect
    eff_id = prepare_effect(
        run_id=rid,
        tool_name="stripe_create_product",
        params={"name": "Test Product", "price": "50.00"},
        ticket_id=tid,
    )
    print(f"Prepared effect: {eff_id}")

    # Get effect
    eff = get_effect(eff_id)
    assert eff is not None
    assert eff["status"] == "prepared"
    print(f"Effect status: {eff['status']}")

    # Commit effect
    commit_effect(eff_id, {"product_id": "prod_xyz123"})
    eff2 = get_effect(eff_id)
    assert eff2["status"] == "committed"
    print(f"Effect committed: {eff2['status']}")

    # Idempotency: prepare same effect again
    eff_id2 = prepare_effect(
        run_id=rid,
        tool_name="stripe_create_product",
        params={"name": "Test Product", "price": "50.00"},
    )
    assert eff_id2 == eff_id  # Same deterministic ID
    eff3 = get_effect(eff_id2)
    assert eff3["status"] == "committed"  # Still committed, not re-prepared
    print("Effect idempotency: OK")

    # Update run to completed
    update_run_status(rid, "completed")
    r2 = get_run(rid)
    assert r2["status"] == "completed"
    assert r2["finished_at"] is not None
    print(f"Run completed: {r2['status']}")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    test_tower_store()
