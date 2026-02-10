"""Tower worker: claims queued runs and executes them.

Simplified single-instance model:
- Polls for queued runs every N seconds
- Claims one run at a time via FOR UPDATE SKIP LOCKED
- Executes until completion or interrupt
- On interrupt: parks the run and releases compute
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time

from langgraph.graph.state import CompiledStateGraph

from src.tower.runner import execute_run
from src.tower.store import claim_queued_run, recover_stale_runs

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2
EXECUTION_TIMEOUT_SECONDS = 600  # 10 minutes max per invocation


class TowerWorker:
    """Background worker that claims and executes Tower runs."""

    def __init__(self, compiled_graph: CompiledStateGraph):
        self._graph = compiled_graph
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tower-worker"
        )
        self._running = False
        self._poll_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the worker poll loop in a background thread."""
        if self._running:
            return
        self._running = True

        # Recover any stale runs from a previous crash
        recovered = recover_stale_runs(max_age_minutes=10)
        if recovered:
            logger.info("Tower worker recovered %d stale runs on startup", recovered)

        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="tower-worker-poll"
        )
        self._poll_thread.start()
        logger.info("Tower worker started (poll interval: %ds)", POLL_INTERVAL_SECONDS)

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        self._executor.shutdown(wait=False)
        logger.info("Tower worker stopped")

    def _poll_loop(self) -> None:
        """Main poll loop: claim and execute runs."""
        while self._running:
            try:
                run = claim_queued_run()
                if run is not None:
                    logger.info(
                        "Tower worker claimed run: %s (workflow=%s)",
                        run["run_id"],
                        run["workflow_id"],
                    )
                    self._execute_with_timeout(run)
                else:
                    time.sleep(POLL_INTERVAL_SECONDS)
            except Exception:
                logger.exception("Tower worker poll error")
                time.sleep(POLL_INTERVAL_SECONDS)

    def _execute_with_timeout(self, run: dict) -> None:
        """Execute a run with a timeout guard."""
        future = self._executor.submit(execute_run, self._graph, run)
        try:
            future.result(timeout=EXECUTION_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            future.cancel()
            from src.tower.store import update_run_status, log_event
            update_run_status(
                run["run_id"],
                "failed",
                last_error=f"Execution timed out after {EXECUTION_TIMEOUT_SECONDS}s",
            )
            log_event(run["run_id"], "run.failed", {
                "error": f"Timeout after {EXECUTION_TIMEOUT_SECONDS}s",
            })
            logger.error("Tower run %s timed out", run["run_id"])
        except Exception:
            # execute_run already handles failure — this catches unexpected errors
            logger.exception("Tower worker unexpected error for run %s", run["run_id"])
