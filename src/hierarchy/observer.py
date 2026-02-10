"""Predicate observation pipeline — feeds live data into hierarchy predicates.

Three observation sources:
1. Automated feeds (scheduled, from existing system metrics)
2. Agent-evaluated (periodic LLM assessment)
3. Manual override (admin API endpoint)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def hierarchy_observation_job() -> None:
    """Scheduled job: update predicate observations from automated feeds.

    Runs every 15 minutes via APScheduler.
    """
    try:
        from src.hierarchy.engine import evaluate_gate
        from src.hierarchy.store import (
            get_all_predicates,
            update_gate_status,
            update_predicate_observation,
        )

        predicates = get_all_predicates()
        if not predicates:
            logger.debug("Hierarchy not seeded yet, skipping observation")
            return

        updated = 0

        # L0 (Transcendent): axiomatically 1.0 — design constraints
        for p in predicates:
            if p.level == 0:
                update_predicate_observation(p.index, 1.0, "automated", {"reason": "axiom"})
                updated += 1

        # L1 (Conscience): check guardrail trip rate
        try:
            conscience_value = _assess_conscience()
            for p in predicates:
                if p.level == 1:
                    update_predicate_observation(p.index, conscience_value, "automated",
                                                  {"source": "guardrail_monitor"})
                    updated += 1
        except Exception:
            logger.debug("Conscience assessment unavailable")

        # L2 (Nonmaleficence): check approval gate rejection rate
        try:
            harm_value = _assess_nonmaleficence()
            for p in predicates:
                if p.level == 2:
                    update_predicate_observation(p.index, harm_value, "automated",
                                                  {"source": "approval_gate"})
                    updated += 1
        except Exception:
            logger.debug("Nonmaleficence assessment unavailable")

        # L3 (Legality): always 1.0 unless manual flag
        for p in predicates:
            if p.level == 3 and p.current_value is None:
                update_predicate_observation(p.index, 1.0, "automated", {"reason": "default_pass"})
                updated += 1

        # L4 (Self-preservation): from system health
        try:
            health_value = _assess_self_preservation()
            for p in predicates:
                if p.level == 4:
                    update_predicate_observation(p.index, health_value, "automated",
                                                  {"source": "health_check"})
                    updated += 1
        except Exception:
            logger.debug("Self-preservation assessment unavailable")

        # L5 (Profit): from Stripe financial health
        try:
            profit_value = _assess_profit()
            for p in predicates:
                if p.level == 5 and p.module_id == "profit-ecommerce":
                    update_predicate_observation(p.index, profit_value, "automated",
                                                  {"source": "financial_health"})
                    updated += 1
        except Exception:
            logger.debug("Profit assessment unavailable")

        # L5 (Readiness): manual only — skip automated

        # L6 (Personality): default to 1.0 if unobserved
        for p in predicates:
            if p.level == 6 and p.current_value is None:
                update_predicate_observation(p.index, 1.0, "automated", {"reason": "default_pass"})
                updated += 1

        # Recompute gate status after observations
        all_preds = get_all_predicates()
        gate = evaluate_gate(all_preds)
        for gs in gate.values():
            update_gate_status(gs)

        logger.info("Hierarchy observation complete: %d predicates updated, gate recomputed", updated)

    except Exception:
        logger.warning("Hierarchy observation job failed", exc_info=True)


def _assess_conscience() -> float:
    """Assess conscience predicates from guardrail data.

    Returns 1.0 (fully passing) minus a penalty based on recent guardrail trips.
    """
    try:
        from src.guardrails import get_recent_trip_rate
        rate = get_recent_trip_rate(window_minutes=60)
        return max(0.0, 1.0 - (rate * 2.0))  # 50% trip rate → 0.0
    except ImportError:
        return 1.0  # No guardrail module → assume passing


def _assess_nonmaleficence() -> float:
    """Assess nonmaleficence from approval rejection data."""
    try:
        from src.aps.store import _get_conn
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FILTER (WHERE status = 'rejected') AS rejected, "
                "COUNT(*) AS total FROM approval_queue "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            ).fetchone()
        if row and row[1] > 0:
            rejection_rate = row[0] / row[1]
            return max(0.0, 1.0 - (rejection_rate * 3.0))  # 33% rejection → 0.0
        return 1.0
    except Exception:
        return 1.0


def _assess_self_preservation() -> float:
    """Assess self-preservation from system health checks."""
    try:
        from src.resilience.health import run_health_checks
        checks = run_health_checks()
        if not checks:
            return 1.0
        passing = sum(1 for v in checks.values() if v)
        return passing / len(checks)
    except Exception:
        return 1.0


def _assess_profit() -> float:
    """Assess profit predicates from financial health."""
    try:
        from src.aps.financial_health import get_cached_financial_health
        health = get_cached_financial_health()
        if health is None:
            return 1.0
        # Map revenue phase to a rough value
        phase_map = {"SURVIVAL": 0.3, "CONSERVATIVE": 0.6, "STEADY": 0.8, "GROWTH": 1.0}
        return phase_map.get(health.phase, 0.8)
    except Exception:
        return 1.0
