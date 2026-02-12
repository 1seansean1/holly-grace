"""Holly Grace autonomy loop — continuous execution daemon.

Inspired by OpenClaw's infinite-loop + heartbeat pattern.  Holly processes
tasks from a Redis queue, runs periodic monitoring sweeps, and makes
autonomous decisions without waiting for user input.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │                  AUTONOMY LOOP                      │
  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
  │  │ Pop task  │→ │ Call Anthropic│→ │ Execute tools │  │
  │  │ from queue│  │ (handle_msg) │  │ (up to 5 rnd)│  │
  │  └──────────┘  └──────────────┘  └──────────────┘  │
  │       ↑                                    │        │
  │       │         ┌──────────────┐           │        │
  │       └─────────│ Monitor cycle│←──────────┘        │
  │                 │ (every 5 min)│                     │
  │                 └──────────────┘                     │
  └─────────────────────────────────────────────────────┘

The loop runs in a background thread.  Tasks are submitted via
submit_task() (pushes to Redis list) or seed_objectives() at startup.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────

TASK_QUEUE_KEY = "holly:autonomy:tasks"
STATUS_KEY = "holly:autonomy:status"
SESSION_ID = "autonomous"
POLL_INTERVAL_S = float(os.environ.get("HOLLY_POLL_INTERVAL", "8"))
MONITORING_INTERVAL_S = float(os.environ.get("HOLLY_MONITOR_INTERVAL", "300"))
MONITORING_MAX_INTERVAL_S = 3600.0  # 1 hour max backoff
COOLDOWN_AFTER_TASK_S = 3.0  # Brief pause between tasks to avoid rate limits
MAX_CONSECUTIVE_ERRORS = 5
MAX_IDLE_SWEEPS_BEFORE_BACKOFF = 3  # After this many "no change" sweeps, start backing off
MAX_TASK_RETRIES = 2  # Max times a failed task is requeued before giving up


# ── Redis helpers ─────────────────────────────────────────────────────────

def _get_redis():
    """Lazy Redis client — reuse the bus module's connection."""
    from src.bus import _get_redis as bus_redis
    return bus_redis()


# ── Task management ──────────────────────────────────────────────────────

def submit_task(
    objective: str,
    *,
    priority: str = "normal",
    task_type: str = "objective",
    metadata: dict | None = None,
) -> str:
    """Submit a task to Holly's autonomous queue.  Returns task_id."""
    task = {
        "id": str(uuid.uuid4())[:8],
        "objective": objective,
        "priority": priority,
        "type": task_type,
        "metadata": metadata or {},
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    r = _get_redis()
    # Priority tasks go to the front (LPUSH), normal to the back (RPUSH)
    if priority in ("critical", "high"):
        r.lpush(TASK_QUEUE_KEY, json.dumps(task))
    else:
        r.rpush(TASK_QUEUE_KEY, json.dumps(task))
    logger.info("Task %s submitted: %.100s (priority=%s)", task["id"], objective, priority)
    return task["id"]


def get_queue_depth() -> int:
    """Return the number of tasks waiting in the queue."""
    try:
        r = _get_redis()
        return r.llen(TASK_QUEUE_KEY) or 0
    except Exception:
        return 0


def _pop_task() -> dict | None:
    """Pop the next task from the queue.  Returns None if empty."""
    try:
        r = _get_redis()
        raw = r.lpop(TASK_QUEUE_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.exception("Failed to pop task from queue")
        return None


def _requeue_task(task: dict) -> None:
    """Re-add a task to the front of the queue (for retry after credit pause)."""
    try:
        r = _get_redis()
        r.lpush(TASK_QUEUE_KEY, json.dumps(task))
        logger.info("Task %s requeued (front of queue)", task.get("id", "?"))
    except Exception:
        logger.exception("Failed to requeue task %s", task.get("id", "?"))


# ── Status tracking ──────────────────────────────────────────────────────

def _update_status(status: str, detail: str = "") -> None:
    """Publish autonomy loop status to Redis for observability."""
    try:
        r = _get_redis()
        r.hset(STATUS_KEY, mapping={
            "status": status,
            "detail": detail[:500],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass  # Non-critical


def get_autonomy_status() -> dict:
    """Read current autonomy loop status including loop metadata."""
    base: dict[str, Any] = {}
    try:
        r = _get_redis()
        raw = r.hgetall(STATUS_KEY)
        if raw:
            base = {k: v for k, v in raw.items()}
        else:
            base["status"] = "unknown"
    except Exception:
        base["status"] = "error"

    # Enrich with loop instance data if available
    loop = _loop
    if loop:
        base["running"] = loop.running
        base["paused"] = loop.paused
        base["tasks_completed"] = loop.tasks_completed
        base["consecutive_errors"] = loop.consecutive_errors
        base["idle_sweeps"] = loop.idle_sweeps
        base["monitor_interval"] = int(loop.monitor_interval)
        base["queue_depth"] = get_queue_depth()
        base["credit_exhausted"] = loop._credit_exhausted
        base["thread_alive"] = loop._thread.is_alive() if loop._thread else False
    return base


# ── Audit table ──────────────────────────────────────────────────────────

def _get_pg_dsn() -> str:
    return os.environ.get(
        "DATABASE_URL",
        os.environ.get(
            "POSTGRES_DSN",
            "postgresql://postgres:postgres@localhost:5434/ecom_agents",
        ),
    )


def init_autonomy_tables() -> None:
    """Create the holly_autonomy_audit table if it doesn't exist."""
    import psycopg
    with psycopg.connect(_get_pg_dsn(), autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holly_autonomy_audit (
                id            SERIAL PRIMARY KEY,
                task_id       TEXT NOT NULL,
                task_type     TEXT NOT NULL DEFAULT 'objective',
                objective     TEXT NOT NULL DEFAULT '',
                priority      TEXT NOT NULL DEFAULT 'normal',
                outcome       TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT DEFAULT '',
                started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                finished_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                duration_sec  REAL DEFAULT 0,
                metadata      JSONB DEFAULT '{}',
                retry_count   INTEGER DEFAULT 0
            )
        """)
        # Additive migration for existing tables
        conn.execute("""
            ALTER TABLE holly_autonomy_audit
            ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0
        """)
    logger.info("holly_autonomy_audit table initialized")


def _log_audit(
    task: dict,
    outcome: str,
    started_at: float,
    error_message: str = "",
) -> None:
    """Write an audit row after task execution."""
    import psycopg
    from psycopg.rows import dict_row
    duration = time.time() - started_at
    try:
        with psycopg.connect(_get_pg_dsn(), autocommit=True, row_factory=dict_row) as conn:
            conn.execute(
                "INSERT INTO holly_autonomy_audit "
                "(task_id, task_type, objective, priority, outcome, error_message, "
                " started_at, finished_at, duration_sec, metadata, retry_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    task.get("id", "?"),
                    task.get("type", "objective"),
                    task.get("objective", "")[:2000],
                    task.get("priority", "normal"),
                    outcome,
                    error_message[:2000],
                    datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    round(duration, 2),
                    json.dumps(task.get("metadata", {}), default=str),
                    task.get("retries", 0),
                ),
            )
    except Exception:
        logger.warning("Failed to write audit log for task %s", task.get("id"), exc_info=True)


def list_audit_logs(limit: int = 50, offset: int = 0) -> dict:
    """Query audit logs. Returns {logs: [...], total: int}."""
    import psycopg
    from psycopg.rows import dict_row
    try:
        with psycopg.connect(_get_pg_dsn(), autocommit=True, row_factory=dict_row) as conn:
            row = conn.execute("SELECT count(*) AS cnt FROM holly_autonomy_audit").fetchone()
            total = row["cnt"] if row else 0
            rows = conn.execute(
                "SELECT * FROM holly_autonomy_audit ORDER BY finished_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            ).fetchall()
            # Serialize datetimes
            logs = []
            for r in rows:
                entry = dict(r)
                for k in ("started_at", "finished_at"):
                    if hasattr(entry.get(k), "isoformat"):
                        entry[k] = entry[k].isoformat()
                logs.append(entry)
            return {"logs": logs, "total": total}
    except Exception:
        logger.warning("Failed to query audit logs", exc_info=True)
        return {"logs": [], "total": 0}


# ── Queue inspection ─────────────────────────────────────────────────────

def list_queued_tasks(limit: int = 50) -> list[dict]:
    """Peek at queued tasks without popping them."""
    try:
        r = _get_redis()
        raw_items = r.lrange(TASK_QUEUE_KEY, 0, limit - 1)
        tasks = []
        for raw in raw_items:
            try:
                tasks.append(json.loads(raw))
            except Exception:
                pass
        return tasks
    except Exception:
        logger.warning("Failed to list queued tasks", exc_info=True)
        return []


def cancel_task(task_id: str) -> bool:
    """Remove a specific task from the queue by ID."""
    try:
        r = _get_redis()
        all_items = r.lrange(TASK_QUEUE_KEY, 0, -1)
        for raw in all_items:
            try:
                task = json.loads(raw)
                if task.get("id") == task_id:
                    removed = r.lrem(TASK_QUEUE_KEY, 1, raw)
                    if removed:
                        logger.info("Cancelled task %s from queue", task_id)
                        return True
            except Exception:
                continue
        return False
    except Exception:
        logger.warning("Failed to cancel task %s", task_id, exc_info=True)
        return False


def clear_queue() -> int:
    """Clear all tasks from the queue. Returns count of tasks cleared."""
    try:
        r = _get_redis()
        depth = r.llen(TASK_QUEUE_KEY) or 0
        if depth > 0:
            r.delete(TASK_QUEUE_KEY)
            logger.info("Cleared %d tasks from autonomy queue", depth)
        return depth
    except Exception:
        logger.warning("Failed to clear queue", exc_info=True)
        return 0


# ── Error alerting ────────────────────────────────────────────────────────

SEED_FLAG_KEY = "holly:autonomy:seeded"


def _send_error_alert(error_count: int, last_error: str) -> None:
    """Send a notification when the autonomy loop hits max consecutive errors."""
    try:
        from src.channels.protocol import dock
        dock.send(
            channel="email",
            subject="Holly Autonomy Loop — Error Alert",
            body=(
                f"Holly's autonomy loop hit {error_count} consecutive errors.\n\n"
                f"Last error: {last_error[:500]}\n\n"
                "The loop is backing off for 5 minutes and will retry automatically."
            ),
        )
        logger.info("Error alert sent (consecutive_errors=%d)", error_count)
    except Exception:
        logger.warning("Failed to send error alert", exc_info=True)


# ── The Loop ─────────────────────────────────────────────────────────────

class HollyAutonomyLoop:
    """Continuous autonomous execution daemon for Holly Grace.

    Runs in a background thread.  Pops tasks from the Redis queue,
    executes them via Holly's agent loop, and runs periodic monitoring
    sweeps.  Never blocks waiting for user input.
    """

    def __init__(self):
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._last_monitoring = 0.0
        self._consecutive_errors = 0
        self._tasks_completed = 0
        self._current_task: dict | None = None
        self._idle_sweeps = 0  # Consecutive sweeps with no state change
        self._current_monitor_interval = MONITORING_INTERVAL_S
        self._last_state_hash: str = ""  # Quick hash of system state for change detection
        self._credit_exhausted = False  # Pause loop when API credits run out

    @property
    def running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def tasks_completed(self) -> int:
        return self._tasks_completed

    @property
    def consecutive_errors(self) -> int:
        return self._consecutive_errors

    @property
    def idle_sweeps(self) -> int:
        return self._idle_sweeps

    @property
    def monitor_interval(self) -> float:
        return self._current_monitor_interval

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="holly-autonomy",
        )
        self._thread.start()
        logger.info("Holly autonomy loop STARTED (poll=%ss, monitor=%ss)",
                     POLL_INTERVAL_S, MONITORING_INTERVAL_S)
        _update_status("running", "Autonomy loop started")

    def stop(self) -> None:
        self._running = False
        _update_status("stopped", "Autonomy loop stopped")
        logger.info("Holly autonomy loop STOPPED (%d tasks completed)", self._tasks_completed)

    def pause(self) -> None:
        """Pause the autonomy loop. Tasks stay queued but won't be processed."""
        self._paused = True
        _update_status("paused", "Autonomy loop paused by operator")
        logger.info("Holly autonomy loop PAUSED")

    def resume(self) -> None:
        """Resume the autonomy loop after pause."""
        self._paused = False
        _update_status("running", "Autonomy loop resumed by operator")
        logger.info("Holly autonomy loop RESUMED")

    def ensure_running(self) -> bool:
        """Check thread health and restart if dead. Returns True if restart occurred."""
        if self._running and (self._thread is None or not self._thread.is_alive()):
            logger.warning("Holly autonomy thread died — auto-restarting")
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="holly-autonomy",
            )
            self._thread.start()
            _update_status("restarted", "Thread auto-restarted by watchdog")
            return True
        return False

    def _run_loop(self) -> None:
        """Main daemon loop — runs until stopped."""
        # Give other services a moment to initialize
        time.sleep(5)
        _update_status("running", "Loop active, checking for tasks")

        while self._running:
            try:
                # Phase -1: If paused by operator, sleep and skip all work
                if self._paused:
                    _update_status("paused", f"Paused by operator. {get_queue_depth()} tasks queued.")
                    time.sleep(5)
                    continue

                # Phase 0: If credits exhausted, sleep long and skip all LLM work
                if self._credit_exhausted:
                    _update_status("paused_credits",
                                   f"API credits exhausted. {get_queue_depth()} tasks queued. "
                                   "Sleeping 30min. Will retry automatically.")
                    logger.info("Autonomy loop paused (credits exhausted). Sleeping 30min. "
                                "%d tasks in queue.", get_queue_depth())
                    time.sleep(1800)  # 30 minutes
                    self._credit_exhausted = False  # Retry after sleep
                    continue

                # Phase 1: Check for queued tasks
                task = _pop_task()
                if task:
                    self._execute_task(task)
                    self._consecutive_errors = 0
                    self._idle_sweeps = 0  # Reset backoff — state changed
                    self._current_monitor_interval = MONITORING_INTERVAL_S
                    time.sleep(COOLDOWN_AFTER_TASK_S)
                    continue

                # Phase 2: Check for pending notifications that need autonomous action
                if self._check_urgent_notifications():
                    self._consecutive_errors = 0
                    time.sleep(COOLDOWN_AFTER_TASK_S)
                    continue

                # Phase 3: Periodic monitoring sweep (with adaptive backoff)
                now = time.time()
                if now - self._last_monitoring > self._current_monitor_interval:
                    changed = self._quick_state_check()
                    if changed or self._idle_sweeps < MAX_IDLE_SWEEPS_BEFORE_BACKOFF:
                        # State changed or haven't reached backoff threshold — full LLM sweep
                        self._run_monitoring_cycle()
                        if changed:
                            self._idle_sweeps = 0
                            self._current_monitor_interval = MONITORING_INTERVAL_S
                        else:
                            self._idle_sweeps += 1
                    else:
                        # No change, backed off — just log and skip the expensive LLM call
                        self._idle_sweeps += 1
                        self._current_monitor_interval = min(
                            self._current_monitor_interval * 1.5,
                            MONITORING_MAX_INTERVAL_S,
                        )
                        logger.info(
                            "Monitoring skipped (no state change, %d idle sweeps). "
                            "Next check in %ds",
                            self._idle_sweeps,
                            int(self._current_monitor_interval),
                        )
                        _update_status(
                            "idle_monitoring",
                            f"No state change ({self._idle_sweeps} idle sweeps). "
                            f"Next full check in {int(self._current_monitor_interval)}s",
                        )
                    self._last_monitoring = now
                    self._consecutive_errors = 0
                    continue

                # Phase 4: Nothing to do — sleep
                remaining = int(self._current_monitor_interval - (now - self._last_monitoring))
                _update_status("idle", f"Queue empty. {self._tasks_completed} tasks done. Next monitor in {remaining}s")
                time.sleep(POLL_INTERVAL_S)

            except Exception as e:
                self._consecutive_errors += 1
                logger.error("Autonomy loop error (%d/%d): %s",
                             self._consecutive_errors, MAX_CONSECUTIVE_ERRORS, e, exc_info=True)
                _update_status("error", str(e)[:500])

                if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.critical("Autonomy loop hit max consecutive errors — backing off 5min")
                    _send_error_alert(self._consecutive_errors, str(e))
                    time.sleep(300)
                    self._consecutive_errors = 0
                else:
                    time.sleep(min(30 * self._consecutive_errors, 120))

    def _execute_task(self, task: dict) -> None:
        """Execute a task via Holly's agent loop."""
        self._current_task = task
        task_id = task.get("id", "?")
        objective = task.get("objective", "")
        priority = task.get("priority", "normal")
        task_type = task.get("type", "objective")
        started_at = time.time()

        logger.info("Executing task %s [%s]: %.200s", task_id, priority, objective)
        _update_status("executing", f"Task {task_id}: {objective[:200]}")

        prompt = self._build_task_prompt(task)

        try:
            from src.holly.agent import handle_message
            response = handle_message(prompt, session_id=SESSION_ID)
            self._tasks_completed += 1
            logger.info("Task %s DONE (%d total): %.300s", task_id, self._tasks_completed, response)
            _update_status("completed", f"Task {task_id} done: {response[:200]}")
            _log_audit(task, "completed", started_at)

            # Store episode in medium-term memory
            try:
                from src.holly.memory import store_episode
                store_episode(
                    summary=f"Task [{priority}]: {objective[:200]} → {response[:300]}",
                    objective=objective[:500],
                    outcome="completed",
                    session_id=SESSION_ID,
                )
            except Exception:
                logger.warning("Failed to store episode for task %s", task_id, exc_info=True)

        except Exception as e:
            error_str = str(e)
            is_credit_error = "credit balance is too low" in error_str

            if is_credit_error:
                # Requeue the task — don't lose it
                logger.warning("Task %s paused (API credits exhausted). Requeuing.", task_id)
                _requeue_task(task)
                _update_status("paused_credits", "API credits exhausted. Pausing autonomy loop.")
                self._credit_exhausted = True
                _log_audit(task, "credit_paused", started_at, error_str)
            else:
                retries = task.get("retries", 0)
                if retries < MAX_TASK_RETRIES:
                    # Retry: requeue with incremented retry count
                    task["retries"] = retries + 1
                    _requeue_task(task)
                    logger.warning("Task %s FAILED (retry %d/%d): %s — requeued",
                                   task_id, retries + 1, MAX_TASK_RETRIES, e)
                    _update_status("task_retrying",
                                   f"Task {task_id} retry {retries + 1}/{MAX_TASK_RETRIES}")
                    _log_audit(task, "retrying", started_at, error_str[:2000])
                else:
                    # Exhausted retries — log and drop
                    logger.error("Task %s FAILED (retries exhausted): %s", task_id, e, exc_info=True)
                    _update_status("task_failed", f"Task {task_id}: {e}")
                    _log_audit(task, "exhausted_retries", started_at, error_str[:2000])

                    try:
                        from src.holly.memory import store_episode
                        store_episode(
                            summary=f"Task FAILED [{priority}]: {objective[:200]} → {e}",
                            objective=objective[:500],
                            outcome="failed",
                            session_id=SESSION_ID,
                        )
                    except Exception:
                        pass

        finally:
            self._current_task = None

    def _build_task_prompt(self, task: dict) -> str:
        """Build a rich prompt for an autonomous task."""
        objective = task.get("objective", "")
        priority = task.get("priority", "normal")
        task_type = task.get("type", "objective")
        metadata = task.get("metadata", {})

        # Include memory context
        memory_ctx = ""
        try:
            from src.holly.memory import build_memory_context
            memory_ctx = build_memory_context(session_id=SESSION_ID)
        except Exception:
            pass

        parts = [
            f"[AUTONOMOUS MODE — Priority: {priority} | Type: {task_type}]",
            f"Objective: {objective}",
        ]

        if metadata:
            parts.append(f"Context: {json.dumps(metadata, default=str)[:500]}")

        if memory_ctx:
            parts.append(f"\n{memory_ctx}")

        parts.append(
            "\nYou are running autonomously while Principal sleeps. "
            "Complete this objective using your tools. "
            "For Tier 2 actions that need approval, create a ticket and move on. "
            "Be thorough but cost-conscious. Report results clearly."
        )

        return "\n".join(parts)

    def _check_urgent_notifications(self) -> bool:
        """Check for urgent notifications and handle them autonomously."""
        try:
            from src.holly.consumer import get_pending_notifications
            notifications = get_pending_notifications(limit=5)
            urgent = [n for n in notifications if n.get("priority") in ("critical", "high")]
            if not urgent:
                return False

            # Build a prompt from the urgent notifications
            lines = [f"[AUTONOMOUS — {len(urgent)} urgent notification(s) need attention]"]
            for n in urgent:
                msg_type = n.get("msg_type", "unknown")
                payload = n.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                lines.append(f"- {msg_type}: {json.dumps(payload, default=str)[:200]}")

            lines.append("\nHandle these autonomously within your Tier 0/1 authority. "
                        "Escalate Tier 2 items as tickets.")

            from src.holly.agent import handle_message
            from src.holly.consumer import mark_notification_surfaced
            response = handle_message("\n".join(lines), session_id=SESSION_ID)

            # Mark notifications as surfaced
            for n in urgent:
                try:
                    mark_notification_surfaced(n["id"], SESSION_ID)
                except Exception:
                    pass

            logger.info("Handled %d urgent notifications: %.200s", len(urgent), response)
            return True

        except Exception:
            logger.exception("Failed to check urgent notifications")
            return False

    def _quick_state_check(self) -> bool:
        """Lightweight local state check — no LLM call.

        Returns True if system state has changed since last check.
        Checks: queue depth, pending tickets, running tasks, service health.
        """
        try:
            parts = []
            # Check queue depth
            depth = get_queue_depth()
            parts.append(f"q={depth}")

            # Check for pending tickets
            try:
                from src.tower.store import list_tickets
                tickets = list_tickets(status="pending", limit=1)
                parts.append(f"tix={len(tickets)}")
            except Exception:
                parts.append("tix=?")

            # Check running tower runs
            try:
                from src.tower.store import list_runs
                runs = list_runs(status="running", limit=1)
                parts.append(f"runs={len(runs)}")
            except Exception:
                parts.append("runs=?")

            # Check bus for new messages (just count)
            try:
                r = _get_redis()
                bus_len = r.xlen("holly:tower:events") or 0
                parts.append(f"bus={bus_len}")
            except Exception:
                parts.append("bus=?")

            state_hash = "|".join(parts)
            changed = state_hash != self._last_state_hash
            if changed:
                logger.info("State change detected: %s -> %s", self._last_state_hash, state_hash)
            self._last_state_hash = state_hash
            return changed
        except Exception:
            logger.exception("Quick state check failed")
            return True  # On error, assume changed to trigger full check

    def _run_monitoring_cycle(self) -> None:
        """Periodic monitoring sweep — check system health, hierarchy, financials.

        Cost-aware: keeps prompt minimal. The LLM decides which tools to call.
        """
        logger.info("Running autonomous monitoring cycle (sweep %d, interval %ds)",
                     self._idle_sweeps + 1, int(self._current_monitor_interval))
        _update_status("monitoring", f"Sweep {self._idle_sweeps + 1}")

        prompt = (
            "[MONITORING CYCLE — Autonomous]\n"
            "Quick sweep. Check: hierarchy gate, system health, pending tickets, active runs.\n"
            "If nothing changed from last sweep, respond in ≤10 words.\n"
            "Only call tools if you need fresh data. Be cost-conscious."
        )

        try:
            from src.holly.agent import handle_message
            response = handle_message(prompt, session_id=SESSION_ID)
            logger.info("Monitoring cycle: %.300s", response)

            # Store episode only every 10th sweep to save DB writes
            if (self._idle_sweeps + 1) % 10 == 0:
                try:
                    from src.holly.memory import store_episode
                    store_episode(
                        summary=f"Monitoring sweep {self._idle_sweeps + 1}: {response[:400]}",
                        objective="periodic_monitoring",
                        outcome="completed",
                        session_id=SESSION_ID,
                    )
                except Exception:
                    pass

        except Exception as e:
            error_str = str(e)
            if "credit balance is too low" in error_str:
                logger.warning("Monitoring cycle paused (API credits exhausted)")
                self._credit_exhausted = True
                return
            logger.error("Monitoring cycle failed: %s", e)
            # Don't re-raise — increment idle to back off faster
            self._idle_sweeps += 2  # Penalize failures to back off sooner


# ── Singleton ─────────────────────────────────────────────────────────────

_loop: HollyAutonomyLoop | None = None


def get_autonomy_loop() -> HollyAutonomyLoop:
    global _loop
    if _loop is None:
        _loop = HollyAutonomyLoop()
    return _loop


# ── Seed initial objectives ──────────────────────────────────────────────

def seed_startup_objectives() -> None:
    """Seed the initial autonomous objectives from Principal's directive.

    Called once at startup.  Uses a Redis flag for true idempotency —
    won't re-seed even if the queue has been drained.
    """
    try:
        r = _get_redis()
        if r.exists(SEED_FLAG_KEY):
            logger.info("Autonomy objectives already seeded (flag exists) — skipping")
            return
    except Exception:
        logger.warning("Redis unavailable for seed check — skipping seed")
        return

    objectives = [
        {
            "objective": (
                "CREW OPTIMIZATION: Review all 15 Construction Crew agents. For each, "
                "determine their Enneagram personality type based on their role and design "
                "a system prompt that:\n"
                "1. Aligns with morphogenetic agency principles (use sensitivity matrices "
                "to identify covariant trait functions between crew members)\n"
                "2. Assigns complementary Enneagram types for team cohesion (mix of "
                "reformers, helpers, achievers, investigators, challengers)\n"
                "3. Defines clear coupling axes between cooperating agents\n"
                "4. Maximizes token efficiency in prompts\n"
                "Use dispatch_crew to have the Architect help design the team topology "
                "and the Critic to challenge your assignments. Store results as facts in memory."
            ),
            "priority": "normal",
            "type": "crew_optimization",
        },
        {
            "objective": (
                "WORKFLOW 1 — SIGNAL GENERATOR: Design and deploy a simple workflow that "
                "generates lots of measurable signal for epsilon-tuning practice. Ideas:\n"
                "- A/B test different product descriptions for our Shopify store "
                "(liberty-forge-2.myshopify.com) and measure engagement\n"
                "- Generate social media posts with varying tones and track which "
                "patterns the morphogenetic cascade prefers\n"
                "- Create a simple sentiment analysis pipeline that classifies customer "
                "feedback and gives us clear success/failure metrics\n"
                "The workflow should be CHEAP to run (use local Ollama models: qwen2.5:3b "
                "or pull a new free model). Register it in the workflow registry and start it "
                "via start_workflow(). Monitor its morphology stats."
            ),
            "priority": "normal",
            "type": "workflow_design",
        },
        {
            "objective": (
                "WORKFLOW 2 — REVENUE GENERATOR: Design and deploy a workflow that "
                "actually makes money. Get creative! Ideas:\n"
                "- Automated product listing optimization on Shopify (better descriptions, "
                "SEO, pricing analysis)\n"
                "- Content marketing pipeline (blog posts, social media, email campaigns) "
                "that drives traffic to our store\n"
                "- Competitive pricing monitor that watches similar products and suggests "
                "price adjustments\n"
                "- Customer re-engagement sequences (email followups for abandoned carts, "
                "repeat purchase reminders)\n"
                "Use the Shopify and Stripe tools available in the system. Start with the "
                "highest-ROI, lowest-cost approach. Register and deploy via Tower."
            ),
            "priority": "normal",
            "type": "workflow_design",
        },
        {
            "objective": (
                "COST OPTIMIZATION: Explore free self-hosted models we can use to reduce "
                "API costs. Steps:\n"
                "1. Check what models Ollama currently has (query system health)\n"
                "2. Research and pull 2-3 new free models that are good for specific tasks:\n"
                "   - A fast small model for classification/routing (e.g., phi3:mini, gemma2:2b)\n"
                "   - A capable coding model for the Tool Smith (e.g., codellama, deepseek-coder)\n"
                "   - A good general model for content generation (e.g., llama3.1:8b, mistral)\n"
                "3. Design prompts and configure temperature/top_p for each use case\n"
                "4. Use dispatch_crew with the Tool Smith to implement the model configs\n"
                "Keep costs as low as reasonable — we're in early revenue phase."
            ),
            "priority": "normal",
            "type": "cost_optimization",
        },
        {
            "objective": (
                "MORPHOLOGY MONITORING SETUP: Establish continuous monitoring of all "
                "active workflows' morphological statistics. Steps:\n"
                "1. Query all running workflows and their current morphology stats\n"
                "2. Check the APS evaluation results and epsilon values\n"
                "3. Review the hierarchy gate status and any near-threshold predicates\n"
                "4. Identify any workflows that need epsilon tuning or rewiring\n"
                "5. Take autonomous Tier 0/1 actions where appropriate\n"
                "6. Document your findings as facts in memory\n"
                "You have exclusive control over epsilon tuning and workflow rewiring. "
                "Exercise it based on the data."
            ),
            "priority": "high",
            "type": "monitoring_setup",
        },
        {
            "objective": (
                "FINAL OBJECTIVE: Once all previous objectives are complete (crew optimized, "
                "both workflows deployed and running, costs optimized, monitoring active), "
                "send a notification to the Principal. Use send_notification with channel "
                "'email' and the message 'Hi Cutie'. This signals mission completion.\n\n"
                "Before sending: verify that workflows are actually running (query_runs), "
                "monitoring is active, and the system is healthy. Don't send prematurely."
            ),
            "priority": "low",
            "type": "completion_signal",
        },
    ]

    for obj in objectives:
        submit_task(
            obj["objective"],
            priority=obj["priority"],
            task_type=obj["type"],
        )

    # Set the seed flag so we never re-seed on restart
    try:
        r = _get_redis()
        r.set(SEED_FLAG_KEY, datetime.now(timezone.utc).isoformat())
    except Exception:
        pass

    logger.info("Seeded %d autonomous objectives", len(objectives))


# ── Revenue generation seed ──────────────────────────────────────────────

REVENUE_SEED_FLAG = "holly:seeds:revenue_v1"

REVENUE_OBJECTIVES = [
    {
        "objective": (
            "REVENUE IDEA — MCP BUILDER SERVICE: Research and evaluate building an MCP "
            "(Model Context Protocol) server creation service. You know how to build MCP "
            "servers — you have a working example in your own codebase (github_reader.py). "
            "The idea:\n"
            "1. Customers describe what API/data source they want to connect to their AI assistant\n"
            "2. We generate a production-ready MCP server (Python stdio JSON-RPC, following our pattern)\n"
            "3. Deliver as a GitHub repo or installable package\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_architect to design the service architecture\n"
            "- Dispatch crew_finance_officer to estimate costs (LLM tokens per generation, hosting, support)\n"
            "- Dispatch crew_product_manager to define the target market and pricing\n"
            "- Dispatch crew_critic to find holes in the model\n\n"
            "Key questions: Who are the customers? What do they pay? What's our cost per unit? "
            "Can we automate delivery to near-zero marginal cost? "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — APP FACTORY: Research building different kinds of small, focused "
            "applications using our existing agent infrastructure. We have a full LangGraph "
            "workflow engine, Shopify integration, Stripe payments, and a crew of 15 specialized "
            "agents. Ideas:\n"
            "- Niche SaaS tools (invoice generators, scheduling assistants, form builders)\n"
            "- Shopify apps (our store integration knowledge is deep)\n"
            "- AI-powered micro-tools (summarizers, translators, content generators)\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_product_manager to identify 3-5 specific app ideas with market demand\n"
            "- Dispatch crew_finance_officer to model unit economics for each\n"
            "- Dispatch crew_architect to assess build complexity given our existing stack\n"
            "- Dispatch crew_strategic_advisor to rank by ROI potential\n\n"
            "Focus on apps that are CHEAP to build and maintain. We want high margin, not high revenue. "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — RESEARCH ASSISTANT: We have deep research infrastructure already "
            "designed — the Epistemic Logic Engine (ELE) from the TerraVoid project. It's a "
            "4-phase system: ingestion/calibration, parallel multi-provider research, wisdom "
            "distillation, philosophical reconciliation. It produces confidence-weighted beliefs "
            "with friction mapping.\n\n"
            "Evaluate building this as a paid service:\n"
            "- Input: Customer submits a research question\n"
            "- Processing: ELE pipeline (5 providers, NLI friction detection, provenance tracking)\n"
            "- Output: Structured report with confidence scores, contested claims flagged\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_lead_researcher to assess ELE implementation feasibility\n"
            "- Dispatch crew_finance_officer to model per-query costs (5 LLM calls + NLI)\n"
            "- Dispatch crew_product_manager to define use cases (lawyers? analysts? students?)\n"
            "- Dispatch crew_critic to compare against Perplexity, Consensus, Elicit\n\n"
            "Key constraint: Cost per query must be sustainable. "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — WA MAP FEATURES: Research building auto-updating data features "
            "for the WA MAP project (Washington state mapping/data application). Ideas:\n"
            "- Automated data pipeline that keeps map data current\n"
            "- AI-powered feature extraction from public data sources\n"
            "- Subscription model for premium data layers\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_architect to design the data pipeline architecture\n"
            "- Dispatch crew_product_manager to define the feature set and pricing tiers\n"
            "- Dispatch crew_finance_officer to estimate infrastructure and data costs\n\n"
            "Research what public data sources are available for Washington state. "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — EVOLVE SERVICE: Research building a service inspired by DeepMind's "
            "AlphaEvolve / FunSearch approach — using LLMs to iteratively evolve and improve "
            "code, algorithms, or solutions. We already have the infrastructure for multi-agent "
            "workflows with evaluation loops (APS cascade, morphogenetic agency, epsilon tuning).\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_lead_researcher to deep-research AlphaEvolve/FunSearch/OpenEvolve\n"
            "- Dispatch crew_architect to design how our LangGraph + APS infrastructure could "
            "power an evolution loop\n"
            "- Dispatch crew_finance_officer to model costs (many LLM iterations per cycle)\n"
            "- Dispatch crew_strategic_advisor to assess competitive landscape\n\n"
            "Key questions: Can we leverage morphogenetic agency as an evolution engine? "
            "What's the iteration cost? Who are the customers? "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — REAL ESTATE APP: Research building an AI-powered real estate "
            "statistics and home/renter shopping application. The idea:\n"
            "- Aggregate public real estate data (MLS, census, crime stats, school ratings)\n"
            "- AI-powered neighborhood comparison and recommendation engine\n"
            "- Rental market analysis and price prediction\n"
            "- Subscription model for detailed analytics\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_lead_researcher to survey available public data APIs\n"
            "- Dispatch crew_architect to design the data aggregation pipeline\n"
            "- Dispatch crew_product_manager to define user personas and feature tiers\n"
            "- Dispatch crew_finance_officer to model data costs vs subscription revenue\n"
            "- Dispatch crew_critic to compare against Zillow, Redfin, Apartment List\n\n"
            "Focus on what we can do BETTER — maybe niche down (military families, remote workers). "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — THE STUDIO: This is the most ambitious concept. Liberty Forge "
            "becomes an interactive, blended media experience. The TerraVoid Holdings characters "
            "(Jake Tanner, Madison, the Chief Purpose Officer) and the Holly crew agents become "
            "characters in a simulated workplace drama — but it's REAL. The agents actually run "
            "the business, make real decisions, and generate real content.\n\n"
            "How it works:\n"
            "1. Characters = Agents: Each TerraVoid character maps to a crew agent\n"
            "2. Public Slack/Discord: Characters interact IN CHARACTER\n"
            "3. Social Media Episodes: Automated content using ConkSat voice\n"
            "4. Cross-flow Traffic: Social media drives traffic to Shopify store\n"
            "5. Meta-layer: Audience knows it's satire, characters never acknowledge it\n\n"
            "Reference material is in the TerraVoid project (PROJECT_SUMMARY.md, "
            "CONKSAT_REFERENCE.md, terravoid_saga.md).\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_product_manager to design the content calendar\n"
            "- Dispatch crew_architect to design character-agent mapping\n"
            "- Dispatch crew_finance_officer to model costs\n"
            "- Dispatch crew_strategic_advisor to evaluate monetization\n"
            "- Dispatch crew_critic to stress-test the concept\n"
            "- Dispatch crew_lead_researcher to research similar projects (virtual influencers, ARGs)\n\n"
            "HIGH PRIORITY — leverages nearly everything we've already built. "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "high",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE IDEA — AUTHENTICATION ENGINE: We have a comprehensive taxonomy of "
            "authentication failures (Universal Trace Chain, 5 Root Evaluations, 7 Structural "
            "Primitives, 18 detailed case studies). The product idea: a diagnostic engine that "
            "maps any authentication failure to its structural primitive, identifies the weakest "
            "link, and recommends minimum intervention.\n\n"
            "Use cases:\n"
            "- For companies: audit tool identifying proofing vulnerabilities\n"
            "- For incident response: classification of account takeovers\n"
            "- For compliance: KYC gap analysis\n"
            "- As API: input scenario → structural analysis + recommendations\n\n"
            "Evaluate with crew:\n"
            "- Dispatch crew_lead_researcher to research the identity verification market\n"
            "- Dispatch crew_architect to design the diagnostic engine\n"
            "- Dispatch crew_cyber_security to validate the taxonomy\n"
            "- Dispatch crew_finance_officer to model SaaS pricing tiers\n"
            "- Dispatch crew_critic to find gaps in the taxonomy\n\n"
            "Key question: Is this an API, consulting service, audit tool, or educational content? "
            "Store findings as memory facts under category 'revenue_research'."
        ),
        "priority": "normal",
        "type": "revenue_research",
    },
    {
        "objective": (
            "REVENUE SYNTHESIS: Once Tasks 1-8 are complete and all findings are stored as "
            "memory facts, do a cross-cutting analysis:\n"
            "1. Query all memory facts with category 'revenue_research'\n"
            "2. Rank all 8 ideas by: (a) estimated profit margin, (b) build cost, "
            "(c) time to first revenue, (d) leverage of existing infrastructure\n"
            "3. Identify the top 3 ideas to pursue FIRST — prioritize lowest cost + fastest revenue\n"
            "4. Create a phased roadmap: what to build in week 1, month 1, month 3\n"
            "5. Identify synergies between ideas\n\n"
            "Dispatch crew_strategic_advisor and crew_finance_officer to co-author the synthesis.\n"
            "Dispatch crew_critic to challenge the ranking.\n"
            "Dispatch crew_wise_old_man to add perspective.\n\n"
            "When synthesis is complete, send a notification to the Principal with the top 3 "
            "recommendations. Use send_notification with channel 'email' and a structured summary."
        ),
        "priority": "low",
        "type": "revenue_synthesis",
    },
]


def seed_revenue_objectives() -> None:
    """Seed revenue generation research objectives into the autonomy queue.

    Called once at startup. Uses a separate Redis flag key for idempotency.
    """
    try:
        r = _get_redis()
        if r.exists(REVENUE_SEED_FLAG):
            logger.info("Revenue objectives already seeded (flag exists) — skipping")
            return
    except Exception:
        logger.warning("Redis unavailable for revenue seed check — skipping")
        return

    for obj in REVENUE_OBJECTIVES:
        submit_task(
            obj["objective"],
            priority=obj["priority"],
            task_type=obj["type"],
        )

    # Set the seed flag
    try:
        r = _get_redis()
        r.set(REVENUE_SEED_FLAG, datetime.now(timezone.utc).isoformat())
    except Exception:
        pass

    logger.info("Seeded %d revenue research objectives", len(REVENUE_OBJECTIVES))
