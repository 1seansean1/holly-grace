"""Tests for the Holly autonomy control plane.

Covers:
- Pause / resume
- Queue inspection (list, cancel, clear)
- Audit table init + logging + query
- Seed idempotency (Redis flag)
- Error alerting
- Enriched status
- API endpoints
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Pause / Resume
# =========================================================================


class TestPauseResume:
    """Tests for HollyAutonomyLoop pause/resume."""

    def test_initial_state_not_paused(self):
        from src.holly.autonomy import HollyAutonomyLoop
        loop = HollyAutonomyLoop()
        assert loop.paused is False
        assert loop.running is False

    def test_pause_sets_flag(self):
        from src.holly.autonomy import HollyAutonomyLoop
        loop = HollyAutonomyLoop()
        loop._running = True
        with patch("src.holly.autonomy._update_status"):
            loop.pause()
        assert loop.paused is True

    def test_resume_clears_flag(self):
        from src.holly.autonomy import HollyAutonomyLoop
        loop = HollyAutonomyLoop()
        loop._running = True
        loop._paused = True
        with patch("src.holly.autonomy._update_status"):
            loop.resume()
        assert loop.paused is False

    def test_start_clears_paused(self):
        from src.holly.autonomy import HollyAutonomyLoop
        loop = HollyAutonomyLoop()
        loop._paused = True
        with patch("src.holly.autonomy._update_status"):
            with patch.object(loop, "_run_loop"):
                loop.start()
        assert loop.paused is False
        assert loop.running is True
        loop.stop()

    def test_properties_exposed(self):
        from src.holly.autonomy import HollyAutonomyLoop
        loop = HollyAutonomyLoop()
        loop._tasks_completed = 42
        loop._consecutive_errors = 3
        loop._idle_sweeps = 7
        loop._current_monitor_interval = 600.0
        assert loop.tasks_completed == 42
        assert loop.consecutive_errors == 3
        assert loop.idle_sweeps == 7
        assert loop.monitor_interval == 600.0


# =========================================================================
# Queue Inspection
# =========================================================================


class TestQueueInspection:
    """Tests for list_queued_tasks, cancel_task, clear_queue."""

    def test_list_queued_tasks_empty(self):
        from src.holly.autonomy import list_queued_tasks
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            result = list_queued_tasks()
        assert result == []
        mock_redis.lrange.assert_called_once_with("holly:autonomy:tasks", 0, 49)

    def test_list_queued_tasks_returns_parsed(self):
        from src.holly.autonomy import list_queued_tasks
        task = {"id": "abc", "objective": "test", "priority": "normal"}
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [json.dumps(task)]
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            result = list_queued_tasks(limit=10)
        assert len(result) == 1
        assert result[0]["id"] == "abc"
        mock_redis.lrange.assert_called_once_with("holly:autonomy:tasks", 0, 9)

    def test_list_queued_tasks_skips_malformed(self):
        from src.holly.autonomy import list_queued_tasks
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = ["not-json", json.dumps({"id": "ok"})]
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            result = list_queued_tasks()
        assert len(result) == 1
        assert result[0]["id"] == "ok"

    def test_cancel_task_found(self):
        from src.holly.autonomy import cancel_task
        task = json.dumps({"id": "abc123", "objective": "test"})
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [task]
        mock_redis.lrem.return_value = 1
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            assert cancel_task("abc123") is True
        mock_redis.lrem.assert_called_once()

    def test_cancel_task_not_found(self):
        from src.holly.autonomy import cancel_task
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [json.dumps({"id": "other"})]
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            assert cancel_task("missing") is False

    def test_clear_queue_deletes_key(self):
        from src.holly.autonomy import clear_queue
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 5
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            count = clear_queue()
        assert count == 5
        mock_redis.delete.assert_called_once_with("holly:autonomy:tasks")

    def test_clear_queue_empty_noop(self):
        from src.holly.autonomy import clear_queue
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 0
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            count = clear_queue()
        assert count == 0
        mock_redis.delete.assert_not_called()


# =========================================================================
# Audit Table + Logging
# =========================================================================


class TestAuditLogging:
    """Tests for init_autonomy_tables, _log_audit, list_audit_logs."""

    def test_init_autonomy_tables_runs(self):
        from src.holly.autonomy import init_autonomy_tables
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("psycopg.connect", return_value=mock_conn):
            init_autonomy_tables()
        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "holly_autonomy_audit" in sql
        assert "CREATE TABLE IF NOT EXISTS" in sql

    def test_log_audit_writes_row(self):
        from src.holly.autonomy import _log_audit
        task = {"id": "t1", "type": "objective", "objective": "test obj", "priority": "normal", "metadata": {}}
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("psycopg.connect", return_value=mock_conn):
            _log_audit(task, "completed", time.time() - 5.0)
        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO holly_autonomy_audit" in sql
        params = mock_conn.execute.call_args[0][1]
        assert params[0] == "t1"
        assert params[4] == "completed"

    def test_log_audit_handles_error_gracefully(self):
        from src.holly.autonomy import _log_audit
        with patch("psycopg.connect", side_effect=Exception("db down")):
            # Should not raise
            _log_audit({"id": "t1"}, "failed", time.time())

    def test_list_audit_logs_returns_structure(self):
        from src.holly.autonomy import list_audit_logs
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = {"cnt": 2}
        mock_conn.execute.return_value.fetchall.return_value = [
            {
                "id": 1, "task_id": "t1", "task_type": "objective",
                "objective": "test", "priority": "normal", "outcome": "completed",
                "error_message": "", "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc), "duration_sec": 5.0,
                "metadata": {},
            },
        ]
        with patch("psycopg.connect", return_value=mock_conn):
            result = list_audit_logs(limit=10, offset=0)
        assert result["total"] == 2
        assert len(result["logs"]) == 1
        assert result["logs"][0]["task_id"] == "t1"
        # Datetimes should be serialized
        assert isinstance(result["logs"][0]["started_at"], str)

    def test_list_audit_logs_handles_error(self):
        from src.holly.autonomy import list_audit_logs
        with patch("psycopg.connect", side_effect=Exception("db down")):
            result = list_audit_logs()
        assert result == {"logs": [], "total": 0}


# =========================================================================
# Seed Idempotency
# =========================================================================


class TestSeedIdempotency:
    """Tests for seed flag-based idempotency."""

    def test_seed_sets_flag(self):
        from src.holly.autonomy import seed_startup_objectives, SEED_FLAG_KEY
        mock_redis = MagicMock()
        mock_redis.exists.return_value = False
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            seed_startup_objectives()
        # Should have set the flag
        mock_redis.set.assert_called_once()
        assert mock_redis.set.call_args[0][0] == SEED_FLAG_KEY

    def test_seed_skips_if_flag_exists(self):
        from src.holly.autonomy import seed_startup_objectives
        mock_redis = MagicMock()
        mock_redis.exists.return_value = True
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            seed_startup_objectives()
        # Should NOT have pushed any tasks
        mock_redis.rpush.assert_not_called()
        mock_redis.lpush.assert_not_called()

    def test_seed_submits_tasks_when_fresh(self):
        from src.holly.autonomy import seed_startup_objectives
        mock_redis = MagicMock()
        mock_redis.exists.return_value = False
        with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
            seed_startup_objectives()
        # Should have submitted 6 objectives (1 high priority = lpush, 5 normal = rpush)
        assert mock_redis.rpush.call_count == 5
        assert mock_redis.lpush.call_count == 1


# =========================================================================
# Error Alerting
# =========================================================================


class TestErrorAlerting:
    """Tests for _send_error_alert."""

    def test_send_error_alert_calls_dock(self):
        from src.holly.autonomy import _send_error_alert
        mock_dock = MagicMock()
        with patch("src.channels.protocol.dock", mock_dock):
            _send_error_alert(5, "test error")
        mock_dock.send.assert_called_once()
        call_kwargs = mock_dock.send.call_args
        assert "email" in str(call_kwargs)

    def test_send_error_alert_handles_failure(self):
        from src.holly.autonomy import _send_error_alert
        mock_dock = MagicMock()
        mock_dock.send.side_effect = Exception("send failed")
        with patch("src.channels.protocol.dock", mock_dock):
            # Should not raise
            _send_error_alert(5, "test error")


# =========================================================================
# Enriched Status
# =========================================================================


class TestEnrichedStatus:
    """Tests for get_autonomy_status with loop metadata."""

    def test_status_includes_loop_data(self):
        from src.holly.autonomy import get_autonomy_status, HollyAutonomyLoop
        import src.holly.autonomy as mod

        loop = HollyAutonomyLoop()
        loop._running = True
        loop._paused = False
        loop._tasks_completed = 10
        loop._consecutive_errors = 1
        loop._idle_sweeps = 2
        loop._current_monitor_interval = 450.0

        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {"status": "running", "detail": "ok"}

        old_loop = mod._loop
        mod._loop = loop
        try:
            with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
                result = get_autonomy_status()
            assert result["running"] is True
            assert result["paused"] is False
            assert result["tasks_completed"] == 10
            assert result["consecutive_errors"] == 1
            assert result["idle_sweeps"] == 2
            assert result["monitor_interval"] == 450
        finally:
            mod._loop = old_loop

    def test_status_without_loop(self):
        from src.holly.autonomy import get_autonomy_status
        import src.holly.autonomy as mod

        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {"status": "unknown"}

        old_loop = mod._loop
        mod._loop = None
        try:
            with patch("src.holly.autonomy._get_redis", return_value=mock_redis):
                result = get_autonomy_status()
            assert "running" not in result
            assert result["status"] == "unknown"
        finally:
            mod._loop = old_loop


# =========================================================================
# API Endpoints (via ASGI TestClient)
# =========================================================================


class TestAPIEndpoints:
    """Tests for serve.py autonomy endpoints."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Set TESTING=1 to skip lifespan side effects."""
        import os
        os.environ["TESTING"] = "1"
        yield
        os.environ.pop("TESTING", None)

    def _auth_headers(self) -> dict:
        from src.security.auth import create_token
        meta = create_token(role="admin")
        return {"Authorization": f"Bearer {meta.token}"}

    def test_get_status(self):
        with patch("src.holly.autonomy.get_autonomy_status", return_value={"status": "idle", "running": True}):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/holly/autonomy/status", headers=self._auth_headers())
            assert resp.status_code == 200
            assert resp.json()["status"] == "idle"

    def test_pause_not_running(self):
        from src.holly.autonomy import HollyAutonomyLoop
        mock_loop = HollyAutonomyLoop()
        mock_loop._running = False
        with patch("src.holly.autonomy.get_autonomy_loop", return_value=mock_loop):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/holly/autonomy/pause", headers=self._auth_headers())
            assert resp.status_code == 400

    def test_resume_not_paused(self):
        from src.holly.autonomy import HollyAutonomyLoop
        mock_loop = HollyAutonomyLoop()
        mock_loop._running = True
        mock_loop._paused = False
        with patch("src.holly.autonomy.get_autonomy_loop", return_value=mock_loop):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/holly/autonomy/resume", headers=self._auth_headers())
            assert resp.status_code == 400

    def test_get_queue(self):
        with patch("src.holly.autonomy.list_queued_tasks", return_value=[{"id": "t1"}]):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/holly/autonomy/queue", headers=self._auth_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 1

    def test_cancel_task_not_found(self):
        with patch("src.holly.autonomy.cancel_task", return_value=False):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.delete("/holly/autonomy/queue/missing", headers=self._auth_headers())
            assert resp.status_code == 404

    def test_clear_queue(self):
        with patch("src.holly.autonomy.clear_queue", return_value=3):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.delete("/holly/autonomy/queue", headers=self._auth_headers())
            assert resp.status_code == 200
            assert resp.json()["count"] == 3

    def test_get_audit(self):
        with patch("src.holly.autonomy.list_audit_logs", return_value={"logs": [], "total": 0}):
            from src.serve import app
            from starlette.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/holly/autonomy/audit", headers=self._auth_headers())
            assert resp.status_code == 200
            assert resp.json()["total"] == 0


# =========================================================================
# Workflow Descriptions
# =========================================================================


class TestWorkflowDescriptions:
    """Tests for plain-English workflow descriptions."""

    def test_signal_generator_description_no_jargon(self):
        from src.workflow_registry import SIGNAL_GENERATOR_WORKFLOW
        desc = SIGNAL_GENERATOR_WORKFLOW.description
        assert "epsilon" not in desc.lower()
        assert "Shopify" in desc
        assert "scores" in desc.lower() or "score" in desc.lower()

    def test_revenue_engine_description_no_abbreviations(self):
        from src.workflow_registry import REVENUE_ENGINE_WORKFLOW
        desc = REVENUE_ENGINE_WORKFLOW.description
        assert "APS" not in desc
        assert "SEO" in desc
        assert "audit" in desc.lower() or "Audit" in desc

    def test_all_workflows_have_descriptions(self):
        from src.workflow_registry import (
            DEFAULT_WORKFLOW, APP_FACTORY_WORKFLOW,
            SOLANA_MINING_WORKFLOW, SIGNAL_GENERATOR_WORKFLOW,
            REVENUE_ENGINE_WORKFLOW,
        )
        for wf in [DEFAULT_WORKFLOW, APP_FACTORY_WORKFLOW, SOLANA_MINING_WORKFLOW,
                    SIGNAL_GENERATOR_WORKFLOW, REVENUE_ENGINE_WORKFLOW]:
            assert wf.description, f"{wf.workflow_id} has empty description"
            assert len(wf.description) >= 20, f"{wf.workflow_id} description too short"
