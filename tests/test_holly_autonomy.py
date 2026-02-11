"""Tests for Holly Grace autonomy loop and memory system."""

import json
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("TESTING", "1")


# ── Memory system tests ──────────────────────────────────────────────────


class TestMemoryEpisodes(unittest.TestCase):
    """Test medium-term episode storage and retrieval."""

    @patch("src.holly.memory._get_conn")
    def test_store_episode_returns_id(self, mock_conn):
        from src.holly.memory import store_episode

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 42}
        mock_conn.return_value.__enter__ = lambda s: MagicMock(execute=lambda *a, **kw: mock_cursor)
        mock_conn.return_value.__exit__ = lambda *a: None

        ep_id = store_episode("Did a thing", outcome="success")
        self.assertEqual(ep_id, 42)

    @patch("src.holly.memory._get_conn")
    def test_get_recent_episodes(self, mock_conn):
        from src.holly.memory import get_recent_episodes

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "summary": "Task A",
                "key_decisions": [],
                "tools_used": [],
                "outcome": "ok",
                "objective": "do A",
                "created_at": "2026-02-10T12:00:00",
            }
        ]
        mock_conn.return_value.__enter__ = lambda s: MagicMock(execute=lambda *a, **kw: mock_cursor)
        mock_conn.return_value.__exit__ = lambda *a: None

        episodes = get_recent_episodes(limit=5)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["summary"], "Task A")


class TestMemoryFacts(unittest.TestCase):
    """Test long-term fact storage and retrieval."""

    @patch("src.holly.memory._get_conn")
    def test_store_fact_returns_id(self, mock_conn):
        from src.holly.memory import store_fact

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 7}
        mock_conn.return_value.__enter__ = lambda s: MagicMock(execute=lambda *a, **kw: mock_cursor)
        mock_conn.return_value.__exit__ = lambda *a: None

        fact_id = store_fact("system", "Redis is on port 6381")
        self.assertEqual(fact_id, 7)

    @patch("src.holly.memory._get_conn")
    def test_get_facts_by_category(self, mock_conn):
        from src.holly.memory import get_facts

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "category": "system",
                "content": "Redis on 6381",
                "source": None,
                "confidence": 1.0,
                "access_count": 0,
                "created_at": "2026-02-10T12:00:00",
            }
        ]
        mock_conn.return_value.__enter__ = lambda s: MagicMock(execute=lambda *a, **kw: mock_cursor)
        mock_conn.return_value.__exit__ = lambda *a: None

        facts = get_facts(category="system", limit=10)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["category"], "system")


class TestMemoryContextBuilder(unittest.TestCase):
    """Test context assembly from all memory tiers."""

    @patch("src.holly.memory.get_facts")
    @patch("src.holly.memory.get_recent_episodes")
    def test_build_context_includes_episodes_and_facts(self, mock_eps, mock_facts):
        from src.holly.memory import build_memory_context

        mock_eps.return_value = [
            {"summary": "Did X", "outcome": "ok", "created_at": "2026-02-10T12:00"},
        ]
        mock_facts.return_value = [
            {"category": "system", "content": "Redis on 6381"},
        ]

        ctx = build_memory_context()
        self.assertIn("Recent Task History", ctx)
        self.assertIn("Did X", ctx)
        self.assertIn("Key Facts", ctx)
        self.assertIn("Redis on 6381", ctx)

    @patch("src.holly.memory.get_facts")
    @patch("src.holly.memory.get_recent_episodes")
    def test_build_context_empty_when_no_memories(self, mock_eps, mock_facts):
        from src.holly.memory import build_memory_context

        mock_eps.return_value = []
        mock_facts.return_value = []

        ctx = build_memory_context()
        self.assertEqual(ctx, "")


class TestCompaction(unittest.TestCase):
    """Test session compaction to episode."""

    @patch("src.holly.memory.store_episode")
    def test_compact_creates_episode(self, mock_store):
        from src.holly.memory import compact_session_to_episode

        mock_store.return_value = 99
        messages = [{"role": "human", "content": f"msg {i}"} for i in range(30)]

        kept, ep_id = compact_session_to_episode(messages, keep_recent=10)
        self.assertEqual(len(kept), 10)
        self.assertEqual(ep_id, 99)
        mock_store.assert_called_once()

    @patch("src.holly.memory.store_episode")
    def test_compact_noop_when_few_messages(self, mock_store):
        from src.holly.memory import compact_session_to_episode

        messages = [{"role": "human", "content": f"msg {i}"} for i in range(5)]
        kept, ep_id = compact_session_to_episode(messages, keep_recent=15)
        self.assertEqual(len(kept), 5)
        self.assertEqual(ep_id, 0)
        mock_store.assert_not_called()


# ── Autonomy loop tests ──────────────────────────────────────────────────


class TestTaskQueue(unittest.TestCase):
    """Test Redis-backed task queue."""

    @patch("src.holly.autonomy._get_redis")
    def test_submit_task_returns_id(self, mock_redis):
        from src.holly.autonomy import submit_task

        r = MagicMock()
        mock_redis.return_value = r

        task_id = submit_task("do something")
        self.assertIsInstance(task_id, str)
        self.assertTrue(len(task_id) > 0)
        r.rpush.assert_called_once()

    @patch("src.holly.autonomy._get_redis")
    def test_high_priority_uses_lpush(self, mock_redis):
        from src.holly.autonomy import submit_task

        r = MagicMock()
        mock_redis.return_value = r

        submit_task("urgent thing", priority="high")
        r.lpush.assert_called_once()
        r.rpush.assert_not_called()

    @patch("src.holly.autonomy._get_redis")
    def test_pop_task_returns_none_when_empty(self, mock_redis):
        from src.holly.autonomy import _pop_task

        r = MagicMock()
        r.lpop.return_value = None
        mock_redis.return_value = r

        result = _pop_task()
        self.assertIsNone(result)

    @patch("src.holly.autonomy._get_redis")
    def test_pop_task_parses_json(self, mock_redis):
        from src.holly.autonomy import _pop_task

        r = MagicMock()
        r.lpop.return_value = json.dumps({"id": "abc", "objective": "test"})
        mock_redis.return_value = r

        result = _pop_task()
        self.assertEqual(result["id"], "abc")
        self.assertEqual(result["objective"], "test")

    @patch("src.holly.autonomy._get_redis")
    def test_get_queue_depth(self, mock_redis):
        from src.holly.autonomy import get_queue_depth

        r = MagicMock()
        r.llen.return_value = 5
        mock_redis.return_value = r

        self.assertEqual(get_queue_depth(), 5)


class TestAutonomyLoop(unittest.TestCase):
    """Test the autonomy loop daemon lifecycle."""

    def test_loop_starts_and_stops(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        self.assertFalse(loop.running)

        # Mock _run_loop to block until stopped (simulates real daemon behavior)
        def fake_run():
            while loop._running:
                time.sleep(0.05)

        with patch.object(loop, "_run_loop", side_effect=fake_run):
            loop.start()
            time.sleep(0.1)  # Let thread start
            self.assertTrue(loop.running)
            loop.stop()
            time.sleep(0.1)  # Let thread exit
            self.assertFalse(loop.running)

    def test_build_task_prompt_includes_objective(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {
            "id": "test123",
            "objective": "Do the thing",
            "priority": "high",
            "type": "test",
            "metadata": {},
        }

        # Lazy import inside _build_task_prompt — patch at source module
        with patch("src.holly.memory.build_memory_context", return_value=""):
            prompt = loop._build_task_prompt(task)

        self.assertIn("Do the thing", prompt)
        self.assertIn("AUTONOMOUS", prompt)
        self.assertIn("high", prompt)

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.memory.store_episode", return_value=1)
    @patch("src.holly.agent.handle_message", return_value="Task completed successfully")
    def test_execute_task_calls_handle_message(self, mock_handle, mock_episode, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {"id": "t1", "objective": "test task", "priority": "normal", "type": "test", "metadata": {}}

        with patch("src.holly.memory.build_memory_context", return_value=""):
            loop._execute_task(task)

        mock_handle.assert_called_once()
        self.assertEqual(loop._tasks_completed, 1)

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.autonomy._requeue_task")
    @patch("src.holly.memory.store_episode", return_value=1)
    @patch("src.holly.agent.handle_message", side_effect=RuntimeError("API error"))
    def test_execute_task_handles_error(self, mock_handle, mock_episode, mock_requeue, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {"id": "t2", "objective": "fail task", "priority": "normal", "type": "test", "metadata": {}}

        with patch("src.holly.memory.build_memory_context", return_value=""):
            loop._execute_task(task)

        # Should not crash, should record 0 completed, should requeue (retries < MAX)
        self.assertEqual(loop._tasks_completed, 0)
        mock_requeue.assert_called_once()


class TestSeedObjectives(unittest.TestCase):
    """Test seeding of initial autonomous objectives."""

    @patch("src.holly.autonomy._get_redis")
    def test_seed_creates_6_objectives(self, mock_redis):
        from src.holly.autonomy import seed_startup_objectives

        r = MagicMock()
        r.exists.return_value = 0  # Flag not set — allow seeding
        mock_redis.return_value = r

        seed_startup_objectives()

        # 5 normal (rpush) + 1 high (lpush) = 6 total
        total_pushes = r.rpush.call_count + r.lpush.call_count
        self.assertEqual(total_pushes, 6)

    @patch("src.holly.autonomy._get_redis")
    def test_seed_skips_when_already_seeded(self, mock_redis):
        from src.holly.autonomy import seed_startup_objectives

        r = MagicMock()
        r.exists.return_value = 1  # Flag set — skip seeding
        mock_redis.return_value = r

        seed_startup_objectives()

        r.rpush.assert_not_called()
        r.lpush.assert_not_called()


class TestAutonomyStatus(unittest.TestCase):
    """Test status tracking."""

    @patch("src.holly.autonomy._get_redis")
    def test_update_and_get_status(self, mock_redis):
        from src.holly.autonomy import _update_status, get_autonomy_status

        r = MagicMock()
        r.hgetall.return_value = {"status": "running", "detail": "test"}
        mock_redis.return_value = r

        _update_status("running", "test")
        status = get_autonomy_status()
        self.assertEqual(status["status"], "running")


# ── Tool registration tests ──────────────────────────────────────────────


class TestNewToolsRegistered(unittest.TestCase):
    """Verify the 4 new tools are properly registered."""

    def test_holly_now_has_25_tools(self):
        from src.holly.tools import HOLLY_TOOLS
        self.assertEqual(len(HOLLY_TOOLS), 25)

    def test_new_tools_in_registry(self):
        from src.holly.tools import HOLLY_TOOLS
        for name in ["store_memory_fact", "query_memory", "query_autonomy_status", "submit_autonomous_task"]:
            self.assertIn(name, HOLLY_TOOLS, f"{name} missing from HOLLY_TOOLS")

    def test_new_tools_have_schemas(self):
        from src.holly.tools import HOLLY_TOOL_SCHEMAS
        schema_names = {s["name"] for s in HOLLY_TOOL_SCHEMAS}
        for name in ["store_memory_fact", "query_memory", "query_autonomy_status", "submit_autonomous_task"]:
            self.assertIn(name, schema_names, f"{name} missing from HOLLY_TOOL_SCHEMAS")

    def test_schemas_count_matches_tools(self):
        from src.holly.tools import HOLLY_TOOLS, HOLLY_TOOL_SCHEMAS
        self.assertEqual(len(HOLLY_TOOLS), len(HOLLY_TOOL_SCHEMAS))


# ── Prompt tests ──────────────────────────────────────────────────────────


class TestPromptPersonality(unittest.TestCase):
    """Verify the personality section was added."""

    def test_prompt_has_personality_section(self):
        from src.holly.prompts import HOLLY_SYSTEM_PROMPT
        self.assertIn("Jennifer Lawrence", HOLLY_SYSTEM_PROMPT)
        self.assertIn("Scarlett Johansson", HOLLY_SYSTEM_PROMPT)
        self.assertIn("Natalie Portman", HOLLY_SYSTEM_PROMPT)

    def test_prompt_has_autonomous_section(self):
        from src.holly.prompts import HOLLY_SYSTEM_PROMPT
        self.assertIn("Autonomous Operation Mode", HOLLY_SYSTEM_PROMPT)
        self.assertIn("autonomy loop", HOLLY_SYSTEM_PROMPT)

    def test_prompt_version_updated(self):
        from src.holly.prompts import HOLLY_SYSTEM_PROMPT
        self.assertIn("v2.1", HOLLY_SYSTEM_PROMPT)

    def test_greeting_is_concise(self):
        from src.holly.prompts import HOLLY_GREETING
        self.assertIn("Hey.", HOLLY_GREETING)
        self.assertNotIn("I'm Holly Grace", HOLLY_GREETING)


# ── Resilience fix tests ────────────────────────────────────────────────


class TestTaskRetry(unittest.TestCase):
    """Test retry-with-budget for failed tasks (Fix 1)."""

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.autonomy._requeue_task")
    @patch("src.holly.memory.build_memory_context", return_value="")
    @patch("src.holly.agent.handle_message", side_effect=RuntimeError("API timeout"))
    def test_first_failure_requeues_task(self, mock_handle, mock_mem, mock_requeue, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {"id": "r1", "objective": "retry me", "priority": "normal", "type": "test", "metadata": {}}

        loop._execute_task(task)

        # Task should be requeued with retries=1
        mock_requeue.assert_called_once()
        requeued_task = mock_requeue.call_args[0][0]
        self.assertEqual(requeued_task["retries"], 1)

        # Audit should show "retrying"
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args[0][1], "retrying")

        # Should not count as completed
        self.assertEqual(loop._tasks_completed, 0)

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.autonomy._requeue_task")
    @patch("src.holly.memory.build_memory_context", return_value="")
    @patch("src.holly.agent.handle_message", side_effect=RuntimeError("API timeout"))
    def test_second_failure_requeues_again(self, mock_handle, mock_mem, mock_requeue, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {"id": "r2", "objective": "retry again", "priority": "normal",
                "type": "test", "metadata": {}, "retries": 1}

        loop._execute_task(task)

        mock_requeue.assert_called_once()
        requeued_task = mock_requeue.call_args[0][0]
        self.assertEqual(requeued_task["retries"], 2)
        self.assertEqual(mock_audit.call_args[0][1], "retrying")

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.autonomy._requeue_task")
    @patch("src.holly.memory.store_episode", return_value=1)
    @patch("src.holly.memory.build_memory_context", return_value="")
    @patch("src.holly.agent.handle_message", side_effect=RuntimeError("API timeout"))
    def test_exhausted_retries_not_requeued(self, mock_handle, mock_mem, mock_episode,
                                            mock_requeue, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop, MAX_TASK_RETRIES

        loop = HollyAutonomyLoop()
        task = {"id": "r3", "objective": "give up", "priority": "normal",
                "type": "test", "metadata": {}, "retries": MAX_TASK_RETRIES}

        loop._execute_task(task)

        # Should NOT requeue
        mock_requeue.assert_not_called()

        # Audit should show "exhausted_retries"
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args[0][1], "exhausted_retries")

    @patch("src.holly.autonomy._log_audit")
    @patch("src.holly.autonomy._requeue_task")
    @patch("src.holly.memory.build_memory_context", return_value="")
    @patch("src.holly.agent.handle_message", side_effect=RuntimeError("credit balance is too low"))
    def test_credit_error_still_requeues_without_retry_count(self, mock_handle, mock_mem,
                                                              mock_requeue, mock_audit):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        task = {"id": "c1", "objective": "credit test", "priority": "normal",
                "type": "test", "metadata": {}}

        loop._execute_task(task)

        # Credit errors use the existing requeue path, NOT the retry counter
        mock_requeue.assert_called_once()
        requeued_task = mock_requeue.call_args[0][0]
        # retries should NOT be incremented for credit errors
        self.assertEqual(requeued_task.get("retries", 0), 0)
        self.assertTrue(loop._credit_exhausted)


class TestEnsureRunning(unittest.TestCase):
    """Test thread watchdog auto-restart (Fix 2)."""

    def test_ensure_running_restarts_dead_thread(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        loop._running = True

        # Simulate dead thread
        dead_thread = MagicMock()
        dead_thread.is_alive.return_value = False
        loop._thread = dead_thread

        with patch.object(loop, "_run_loop"):
            restarted = loop.ensure_running()

        self.assertTrue(restarted)
        self.assertIsNotNone(loop._thread)
        self.assertNotEqual(loop._thread, dead_thread)

    def test_ensure_running_noop_when_alive(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        loop._running = True

        alive_thread = MagicMock()
        alive_thread.is_alive.return_value = True
        loop._thread = alive_thread

        restarted = loop.ensure_running()

        self.assertFalse(restarted)
        self.assertEqual(loop._thread, alive_thread)

    def test_ensure_running_noop_when_not_running(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        loop._running = False
        loop._thread = None

        restarted = loop.ensure_running()

        self.assertFalse(restarted)

    def test_ensure_running_restarts_when_thread_is_none(self):
        from src.holly.autonomy import HollyAutonomyLoop

        loop = HollyAutonomyLoop()
        loop._running = True
        loop._thread = None

        with patch.object(loop, "_run_loop"):
            restarted = loop.ensure_running()

        self.assertTrue(restarted)
        self.assertIsNotNone(loop._thread)


class TestMaxTaskRetries(unittest.TestCase):
    """Test the MAX_TASK_RETRIES constant."""

    def test_constant_is_positive(self):
        from src.holly.autonomy import MAX_TASK_RETRIES
        self.assertGreater(MAX_TASK_RETRIES, 0)

    def test_constant_is_reasonable(self):
        from src.holly.autonomy import MAX_TASK_RETRIES
        self.assertLessEqual(MAX_TASK_RETRIES, 5)
