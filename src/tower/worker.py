"""Tower worker: claims queued runs and executes them.

Simplified single-instance model:
- Polls for queued runs every N seconds
- Claims one run at a time via FOR UPDATE SKIP LOCKED
- Executes until completion or interrupt
- On interrupt: parks the run and releases compute

Crew dispatch support:
- Runs with workflow_id starting with "crew_solo_" get a dynamically
  compiled single-agent graph (agent -> END) instead of the default graph.
- The workflow_compiler handles tool resolution via ToolRegistry, which
  includes MCP tools from Postgres.
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

_CREW_SOLO_PREFIX = "crew_solo_"


class TowerWorker:
    """Background worker that claims and executes Tower runs."""

    def __init__(self, compiled_graph: CompiledStateGraph, router=None):
        self._graph = compiled_graph
        self._router = router
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tower-worker"
        )
        self._running = False
        self._poll_thread: threading.Thread | None = None
        self._crew_graph_cache: dict[str, CompiledStateGraph] = {}

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

    def _get_graph(self, run: dict) -> CompiledStateGraph:
        """Select the right compiled graph for a run.

        For crew solo runs (workflow_id like crew_solo_{agent_id}), compile
        a single-agent graph so the crew agent executes with its own system
        prompt and tools.  For all other runs, use the default graph.
        """
        wf_id = run.get("workflow_id", "default")

        if wf_id.startswith(_CREW_SOLO_PREFIX) and self._router is not None:
            agent_id = wf_id[len(_CREW_SOLO_PREFIX):]
            if agent_id:
                return self._get_crew_graph(agent_id)

        return self._graph

    def _get_crew_graph(self, agent_id: str) -> CompiledStateGraph:
        """Compile (or return cached) a single-agent crew graph."""
        if agent_id in self._crew_graph_cache:
            return self._crew_graph_cache[agent_id]

        from src.tower.checkpointer import get_checkpointer
        from src.workflow_compiler import compile_workflow
        from src.workflow_registry import (
            WorkflowDefinition,
            WorkflowEdgeDef,
            WorkflowNodeDef,
        )

        defn = WorkflowDefinition(
            workflow_id=f"crew_solo_{agent_id}",
            display_name=f"Crew: {agent_id}",
            description=f"Solo execution of crew agent {agent_id}",
            nodes=[
                WorkflowNodeDef(
                    agent_id, agent_id, {"x": 400, "y": 150}, is_entry_point=True
                ),
            ],
            edges=[
                WorkflowEdgeDef(
                    f"{agent_id}_end", agent_id, "__end__", "direct"
                ),
            ],
        )

        graph = compile_workflow(defn, self._router, use_cache=False)
        compiled = graph.compile(checkpointer=get_checkpointer())

        self._crew_graph_cache[agent_id] = compiled
        logger.info("Compiled crew solo graph for agent: %s", agent_id)
        return compiled

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
        graph = self._get_graph(run)
        future = self._executor.submit(execute_run, graph, run)
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
