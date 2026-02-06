"""Autonomous scheduler: APScheduler jobs that trigger the agent graph.

Schedule:
- Every 30 min: order check → Operations agent
- 9am + 3pm daily: Instagram content → Sales agent (simple)
- Monday 9am: full campaign → Sales agent (spawns sub-agents)
- Daily 8am: revenue report → Revenue agent
- Every 15 min: health check
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class AutonomousScheduler:
    """Manages autonomous agent triggers via APScheduler."""

    def __init__(self, graph_invoke_fn):
        """Initialize with a function that invokes the compiled graph.

        Args:
            graph_invoke_fn: Callable that takes AgentState dict and invokes the graph.
        """
        self._invoke = graph_invoke_fn
        self._scheduler = BackgroundScheduler()

    def _invoke_task(self, trigger_source: str, task_description: str, payload: dict | None = None):
        """Invoke the graph with a task payload."""
        try:
            state = {
                "messages": [HumanMessage(content=task_description)],
                "trigger_source": trigger_source,
                "trigger_payload": payload or {"task": task_description},
                "retry_count": 0,
            }
            result = self._invoke(state)
            logger.info(
                "Scheduled task completed: source=%s type=%s",
                trigger_source,
                result.get("task_type", "unknown"),
            )
        except Exception:
            logger.exception("Scheduled task failed: %s", trigger_source)

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

        # Instagram post at 9am and 3pm daily
        for hour in [9, 15]:
            self._scheduler.add_job(
                self._invoke_task,
                trigger=CronTrigger(hour=hour, minute=0),
                args=[
                    "scheduler",
                    "Create and publish an engaging Instagram post for our store",
                ],
                id=f"instagram_post_{hour}",
                replace_existing=True,
            )

        # Full campaign on Monday 9am
        self._scheduler.add_job(
            self._invoke_task,
            trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
            args=[
                "scheduler",
                "Plan and execute a full marketing campaign for this week",
                {"task": "full_campaign", "scope": "weekly"},
            ],
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

        self._scheduler.start()
        logger.info("Autonomous scheduler started with %d jobs", len(self._scheduler.get_jobs()))

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
        self._scheduler.shutdown()
        logger.info("Autonomous scheduler stopped")

    @property
    def jobs(self):
        return self._scheduler.get_jobs()
