"""Autonomous scheduler: APScheduler jobs that trigger the agent graph.

Schedule:
- Every 30 min: order check -> Operations agent
- 9am + 3pm daily: Instagram content -> Sales agent (simple)
- Monday 9am: full campaign -> Sales agent (spawns sub-agents)
- Daily 8am: revenue report -> Revenue agent
- Every 15 min: health check
- Every 5 min: DLQ retry + approval expiry

Failed tasks are routed to a dead letter queue (DLQ) with auto-retry.
All scheduled tasks have a 5-minute timeout.
"""

from __future__ import annotations

import concurrent.futures
import logging
import traceback
import uuid

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

TASK_TIMEOUT_SECONDS = 300  # 5 minutes


class AutonomousScheduler:
    """Manages autonomous agent triggers via APScheduler."""

    def __init__(self, graph_invoke_fn):
        """Initialize with a function that invokes the compiled graph.

        Args:
            graph_invoke_fn: Callable that takes AgentState dict and invokes the graph.
        """
        self._invoke = graph_invoke_fn
        self._scheduler = BackgroundScheduler()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def _start_tower_run(
        self,
        trigger_source: str,
        task_description: str,
        payload: dict | None = None,
        *,
        exploratory: bool = False,
        workflow_id: str = "default",
        run_name: str | None = None,
    ):
        """Start a durable Tower run instead of direct graph.invoke().

        Tower runs support interrupt/resume, so they can pause for human
        approval and resume later. Use this for tasks that may need HITL
        (tool approval gates, high-risk actions).

        Returns immediately after creating the run. The Tower worker handles
        execution, interrupt detection, and ticket creation.
        """
        if exploratory:
            try:
                from src.aps.revenue_epsilon import is_exploration_allowed
                if not is_exploration_allowed():
                    logger.info(
                        "Skipping exploratory Tower run (revenue epsilon too low): %s",
                        trigger_source,
                    )
                    return
            except Exception:
                pass

        try:
            from src.tower.store import create_run

            input_state = {
                "messages": [{"type": "human", "content": task_description}],
                "trigger_source": trigger_source,
                "trigger_payload": payload or {"task": task_description},
                "retry_count": 0,
            }

            run_id = create_run(
                workflow_id=workflow_id,
                run_name=run_name or trigger_source,
                input_state=input_state,
                metadata={"trigger_source": trigger_source, "exploratory": exploratory},
                created_by="scheduler",
            )
            logger.info("Tower run created: %s (trigger=%s)", run_id, trigger_source)

            # Publish to message bus (fire-and-forget)
            from src.bus import STREAM_SYSTEM_HEALTH, publish
            publish(STREAM_SYSTEM_HEALTH, "scheduler.fired", {
                "trigger_source": trigger_source,
                "run_id": run_id,
                "exploratory": exploratory,
                "workflow_id": workflow_id,
            }, source="scheduler")
        except Exception:
            logger.exception("Failed to create Tower run for %s, falling back to direct invoke", trigger_source)
            self._invoke_task(trigger_source, task_description, payload, exploratory=exploratory)

    def _invoke_task(
        self,
        trigger_source: str,
        task_description: str,
        payload: dict | None = None,
        *,
        exploratory: bool = False,
    ):
        """Invoke the graph with a task payload, with timeout and DLQ routing.

        Args:
            exploratory: If True, the task is gated by revenue epsilon.
                         It will be skipped (not run) when the company
                         cannot afford exploration.
        """
        if exploratory:
            try:
                from src.aps.revenue_epsilon import is_exploration_allowed
                if not is_exploration_allowed():
                    logger.info(
                        "Skipping exploratory task (revenue epsilon too low): %s",
                        trigger_source,
                    )
                    return
            except Exception:
                pass  # If check fails, run the task anyway

        # Apply revenue-aware cost budget
        try:
            from src.aps.revenue_epsilon import get_revenue_cost_budget
            cost_budget = get_revenue_cost_budget()
        except Exception:
            cost_budget = 1.00  # default

        state = {
            "messages": [HumanMessage(content=task_description)],
            "trigger_source": trigger_source,
            "trigger_payload": payload or {"task": task_description},
            "retry_count": 0,
            "_revenue_cost_budget": cost_budget,
        }

        config = {"configurable": {"thread_id": f"sched-{uuid.uuid4().hex[:8]}"}}
        future = self._executor.submit(self._invoke, state, config)
        try:
            result = future.result(timeout=TASK_TIMEOUT_SECONDS)
            logger.info(
                "Scheduled task completed: source=%s type=%s",
                trigger_source,
                result.get("task_type", "unknown"),
            )
        except concurrent.futures.TimeoutError:
            future.cancel()
            error_msg = f"Task timed out after {TASK_TIMEOUT_SECONDS}s"
            logger.error("Scheduled task timeout: %s - %s", trigger_source, error_msg)
            self._send_to_dlq(trigger_source, task_description, payload, error_msg)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            logger.exception("Scheduled task failed: %s", trigger_source)
            self._send_to_dlq(trigger_source, task_description, payload, error_msg)

    def _send_to_dlq(self, trigger_source: str, task_description: str, payload: dict | None, error: str):
        """Route a failed task to the dead letter queue."""
        try:
            from src.aps.store import dlq_insert

            dlq_insert(
                job_id=trigger_source,
                payload={
                    "trigger_source": trigger_source,
                    "task_description": task_description,
                    "original_payload": payload,
                },
                error=error,
            )
        except Exception:
            logger.exception("Failed to insert into DLQ for %s", trigger_source)

    def _retry_dead_letters(self):
        """Retry tasks from the dead letter queue."""
        try:
            from src.aps.store import dlq_get_pending, dlq_increment_attempt, dlq_resolve

            pending = dlq_get_pending()
            for entry in pending:
                p = entry["payload"]
                logger.info(
                    "DLQ retry %d/%d for %s",
                    entry["attempts"] + 1,
                    entry["max_attempts"],
                    entry["job_id"],
                )
                try:
                    state = {
                        "messages": [HumanMessage(content=p.get("task_description", ""))],
                        "trigger_source": f"dlq_retry:{entry['job_id']}",
                        "trigger_payload": p.get("original_payload") or {},
                        "retry_count": 0,
                    }
                    dlq_config = {"configurable": {"thread_id": f"dlq-{uuid.uuid4().hex[:8]}"}}
                    future = self._executor.submit(self._invoke, state, dlq_config)
                    future.result(timeout=TASK_TIMEOUT_SECONDS)
                    dlq_resolve(entry["id"])
                    logger.info("DLQ entry %d resolved successfully", entry["id"])
                except Exception as e:
                    dlq_increment_attempt(entry["id"], str(e))
                    logger.warning("DLQ retry failed for %d: %s", entry["id"], e)
        except Exception:
            logger.exception("DLQ retry job failed")

    def _expire_approvals(self):
        """Expire stale approval requests."""
        try:
            from src.aps.store import approval_expire_stale

            count = approval_expire_stale()
            if count > 0:
                logger.info("Expired %d stale approval requests", count)
        except Exception:
            logger.exception("Approval expiry job failed")

    def start(self):
        """Register all jobs and start the scheduler."""
        # Order check every 30 minutes
        self._scheduler.add_job(
            self._invoke_task,
            trigger=IntervalTrigger(minutes=30),
            args=["scheduler", "Check for new orders and process any pending fulfillments"],
            id="order_check",
            replace_existing=True,
        )

        # Instagram post at 9am and 3pm daily — Tower runs (may need tool approval)
        # Content creation is exploratory — gated by revenue epsilon
        for hour in [9, 15]:
            self._scheduler.add_job(
                self._start_tower_run,
                trigger=CronTrigger(hour=hour, minute=0),
                args=[
                    "scheduler:instagram",
                    "Create and publish an engaging Instagram post for our store",
                ],
                kwargs={"exploratory": True, "run_name": f"Instagram Post ({hour}:00)"},
                id=f"instagram_post_{hour}",
                replace_existing=True,
            )

        # Full campaign on Monday 9am — Tower run (may need tool approval)
        # Campaigns are exploratory — skipped when revenue epsilon is too low
        self._scheduler.add_job(
            self._start_tower_run,
            trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
            args=[
                "scheduler:campaign",
                "Plan and execute a full marketing campaign for this week",
                {"task": "full_campaign", "scope": "weekly"},
            ],
            kwargs={"exploratory": True, "run_name": "Weekly Campaign"},
            id="weekly_campaign",
            replace_existing=True,
        )

        # Revenue report daily at 8am
        self._scheduler.add_job(
            self._invoke_task,
            trigger=CronTrigger(hour=8, minute=0),
            args=[
                "scheduler",
                "Generate daily revenue report with sales analysis and recommendations",
            ],
            id="daily_revenue",
            replace_existing=True,
        )

        # Health check every 15 minutes
        self._scheduler.add_job(
            self._health_check,
            trigger=IntervalTrigger(minutes=15),
            id="health_check",
            replace_existing=True,
        )

        # APS evaluation every 5 minutes
        from src.aps.scheduler_jobs import aps_evaluation_job
        self._scheduler.add_job(
            aps_evaluation_job,
            trigger=IntervalTrigger(minutes=5),
            id="aps_evaluation",
            replace_existing=True,
        )

        # Efficacy aggregation every 30 minutes
        from src.aps.scheduler_jobs import efficacy_aggregation_job
        self._scheduler.add_job(
            efficacy_aggregation_job,
            trigger=IntervalTrigger(minutes=30),
            id="efficacy_aggregation",
            replace_existing=True,
        )

        # Financial health check every 30 minutes (feeds revenue epsilon)
        from src.aps.scheduler_jobs import financial_health_job
        self._scheduler.add_job(
            financial_health_job,
            trigger=IntervalTrigger(minutes=30),
            id="financial_health",
            replace_existing=True,
        )

        # Morphogenetic evaluation every 15 minutes
        from src.morphogenetic.scheduler_jobs import morphogenetic_evaluation_job
        self._scheduler.add_job(
            morphogenetic_evaluation_job,
            trigger=IntervalTrigger(minutes=15),
            id="morphogenetic_evaluation",
            replace_existing=True,
        )

        # Hierarchy observation every 15 minutes
        from src.hierarchy.observer import hierarchy_observation_job
        self._scheduler.add_job(
            hierarchy_observation_job,
            trigger=IntervalTrigger(minutes=15),
            id="hierarchy_observation",
            replace_existing=True,
        )

        # Solana mining profitability check every 6 hours
        # Gated by hierarchy L5 gate (Celestial must pass)
        self._scheduler.add_job(
            self._solana_mining_check,
            trigger=IntervalTrigger(hours=6),
            id="solana_mining_check",
            replace_existing=True,
        )

        # Sage inbox listener — persistent IMAP IDLE (instant, not polled)
        from src.tools.email_inbox import start_inbox_listener
        start_inbox_listener(self._handle_inbound_message)

        # Sage morning greeting daily at 7am
        self._scheduler.add_job(
            self._invoke_task,
            trigger=CronTrigger(hour=7, minute=0),
            args=[
                "scheduler",
                "Send Sean a morning greeting via email and SMS. Be funny, "
                "absurd, kind, and use eggplant emoji. Include a brief system "
                "status summary if anything noteworthy happened overnight.",
            ],
            id="sage_morning_greeting",
            replace_existing=True,
        )

        # DLQ retry every 5 minutes
        self._scheduler.add_job(
            self._retry_dead_letters,
            trigger=IntervalTrigger(minutes=5),
            id="dlq_retry",
            replace_existing=True,
        )

        # Approval expiry every 5 minutes
        self._scheduler.add_job(
            self._expire_approvals,
            trigger=IntervalTrigger(minutes=5),
            id="approval_expiry",
            replace_existing=True,
        )

        # Tower ticket expiry every 5 minutes
        self._scheduler.add_job(
            self._expire_tower_tickets,
            trigger=IntervalTrigger(minutes=5),
            id="tower_ticket_expiry",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Autonomous scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def _handle_inbound_message(self, msg):
        """Handle an inbound message from the IMAP IDLE listener.

        Creates a Tower run so that any tool calls (email send, SMS reply)
        can be interrupted for approval if needed.
        """
        label = "sms_reply" if msg.source == "sms" else "email_inbound"
        task_desc = (
            f"Sean sent you a message via {msg.source}. "
            f"Subject: {msg.subject or '(none)'}. "
            f"Message: {msg.body}\n\n"
            f"Reply to Sean via {msg.source}."
        )
        self._start_tower_run(
            f"sage_inbox:{label}",
            task_desc,
            {
                "task": "sage_chat",
                "source": msg.source,
                "sender": msg.sender,
                "body": msg.body,
            },
            run_name=f"Sage: {label} from {msg.sender or 'unknown'}",
        )

    def _solana_mining_check(self):
        """Check Solana mining profitability. Gated by hierarchy L5 gate."""
        try:
            from src.hierarchy.store import get_gate_status
            gates = get_gate_status(5)
            if gates and not gates[0].is_open:
                failing = gates[0].failing_predicates
                logger.info(
                    "Solana mining check skipped — L5 gate closed (failing: %s)",
                    failing,
                )
                return
        except Exception:
            logger.debug("Hierarchy gate check unavailable, proceeding with mining check")

        self._start_tower_run(
            "scheduler:solana_mining",
            (
                "Run a comprehensive Solana mining profitability check. "
                "Use the solana_check_profitability tool to assess ROI, "
                "solana_validator_health to check validator status, and "
                "solana_mining_report to generate a full report. "
                "Summarize findings and recommend whether to continue, "
                "pause, or halt mining operations."
            ),
            {"task": "solana_mining_check"},
            workflow_id="solana_mining",
            run_name="Solana Mining Check",
        )

    def _expire_tower_tickets(self):
        """Expire stale Tower tickets."""
        try:
            from src.tower.store import expire_stale_tickets

            count = expire_stale_tickets()
            if count > 0:
                logger.info("Expired %d stale Tower tickets", count)
        except Exception:
            logger.exception("Tower ticket expiry job failed")

    def _health_check(self):
        """Run health checks on all services."""
        from src.resilience.health import run_health_checks

        try:
            results = run_health_checks()
            unhealthy = [name for name, ok in results.items() if not ok]
            if unhealthy:
                logger.warning("Unhealthy services: %s", unhealthy)
            else:
                logger.info("All services healthy")
        except Exception:
            logger.exception("Health check failed")

    def stop(self):
        """Stop the scheduler."""
        self._executor.shutdown(wait=False)
        self._scheduler.shutdown()
        logger.info("Autonomous scheduler stopped")

    @property
    def jobs(self):
        return self._scheduler.get_jobs()


# ---------------------------------------------------------------------------
# Global accessor — avoids circular imports (serve.py → holly → serve.py)
# ---------------------------------------------------------------------------

_global_scheduler: AutonomousScheduler | None = None


def set_global_scheduler(s: AutonomousScheduler) -> None:
    global _global_scheduler
    _global_scheduler = s


def get_global_scheduler() -> AutonomousScheduler | None:
    return _global_scheduler
