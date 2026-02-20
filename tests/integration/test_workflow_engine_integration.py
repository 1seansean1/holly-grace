"""Integration tests for workflow engine module."""

import asyncio
from datetime import datetime, timezone

import pytest

from holly.engine.workflow_engine import (
    TaskExecutionError,
    WorkflowDAG,
    WorkflowEdge,
    WorkflowEngine,
    WorkflowTask,
    WorkflowTaskState,
)

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


class PingPongExecutor:
    """Executor that implements ping-pong pattern."""

    def __init__(self, name: str, results: dict):
        self.name = name
        self.results = results

    async def execute(self, task_id: str, payload):
        """Execute ping-pong task."""
        self.results[f"{self.name}_started"] = datetime.now(timezone.utc)
        await asyncio.sleep(0.01)
        self.results[f"{self.name}_completed"] = datetime.now(timezone.utc)
        return {"pong": self.name, "input": payload}


class CompensatingExecutor:
    """Executor that supports compensation."""

    def __init__(self, name: str, results: dict, state: dict):
        self.name = name
        self.results = results
        self.state = state

    async def execute(self, task_id: str, payload):
        """Execute task."""
        self.state[self.name] = "executed"
        self.results[self.name] = {"status": "executed", "payload": payload}
        return {"task": self.name, "executed": True}

    async def compensate(self, task_id: str, forward_result):
        """Compensate task."""
        self.state[self.name] = "compensated"
        self.results[f"{self.name}_compensated"] = {"status": "compensated"}
        return {"task": self.name, "compensated": True}


class FlakyExecutor:
    """Executor that fails on specific invocations."""

    def __init__(self, name: str, fail_on_count: int = 1, results: dict | None = None):
        self.name = name
        self.fail_on_count = fail_on_count
        self.results = results or {}
        self.call_count = 0

    async def execute(self, task_id: str, payload):
        """Execute with potential failure."""
        self.call_count += 1
        if self.call_count == self.fail_on_count:
            raise RuntimeError(f"{self.name} failing on call {self.call_count}")
        self.results[self.name] = {"call": self.call_count, "payload": payload}
        return {"task": self.name, "calls": self.call_count}


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_engine_linear_chain_execution():
    """Test linear chain of dependent tasks."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="linear_workflow")
    results = {}

    executors = [
        PingPongExecutor(f"task{i}", results) for i in range(5)
    ]

    for i, executor in enumerate(executors):
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=executor,
            payload={"seq": i},
            idempotency_key=f"linear_key_{i}",
        )
        dag.add_task(task)

    for i in range(len(executors) - 1):
        dag.add_edge(WorkflowEdge(f"task{i}", f"task{i+1}"))

    execution = await engine.execute(dag)

    assert execution.state["task0"] == WorkflowTaskState.SUCCEEDED
    assert execution.state["task4"] == WorkflowTaskState.SUCCEEDED
    for i in range(5):
        assert f"task{i}_started" in results
        assert f"task{i}_completed" in results


@pytest.mark.asyncio
async def test_workflow_engine_branching_execution():
    """Test branching workflow DAG."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="branching_workflow")
    results = {}

    task0 = WorkflowTask(
        task_id="task0",
        executor=PingPongExecutor("task0", results),
        payload={"root": True},
        idempotency_key="branch_key_0",
    )
    dag.add_task(task0)

    for i in range(1, 5):
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=PingPongExecutor(f"task{i}", results),
            payload={"branch": i},
            idempotency_key=f"branch_key_{i}",
        )
        dag.add_task(task)
        dag.add_edge(WorkflowEdge("task0", f"task{i}"))

    execution = await engine.execute(dag)

    assert execution.state["task0"] == WorkflowTaskState.SUCCEEDED
    for i in range(1, 5):
        assert execution.state[f"task{i}"] == WorkflowTaskState.SUCCEEDED


@pytest.mark.asyncio
async def test_workflow_engine_diamond_dependency():
    """Test diamond-shaped dependency pattern."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="diamond_workflow")
    results = {}

    task0 = WorkflowTask(
        task_id="task0",
        executor=PingPongExecutor("task0", results),
        payload={"root": True},
        idempotency_key="diamond_key_0",
    )
    dag.add_task(task0)

    task1 = WorkflowTask(
        task_id="task1",
        executor=PingPongExecutor("task1", results),
        payload={"left": True},
        idempotency_key="diamond_key_1",
    )
    dag.add_task(task1)
    dag.add_edge(WorkflowEdge("task0", "task1"))

    task2 = WorkflowTask(
        task_id="task2",
        executor=PingPongExecutor("task2", results),
        payload={"right": True},
        idempotency_key="diamond_key_2",
    )
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task0", "task2"))

    task3 = WorkflowTask(
        task_id="task3",
        executor=PingPongExecutor("task3", results),
        payload={"converge": True},
        idempotency_key="diamond_key_3",
    )
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task1", "task3"))
    dag.add_edge(WorkflowEdge("task2", "task3"))

    execution = await engine.execute(dag)

    assert execution.state["task3"] == WorkflowTaskState.SUCCEEDED
    assert len(execution.results) == 4


@pytest.mark.asyncio
async def test_workflow_engine_compensation_chain():
    """Test compensation chain on failure."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="compensation_workflow")
    state = {}
    results = {}

    executor1 = CompensatingExecutor("task1", results, state)
    executor2 = CompensatingExecutor("task2", results, state)
    executor3 = FlakyExecutor("task3", fail_on_count=1, results=results)

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"order": 1},
        idempotency_key="comp_key_1",
    )
    dag.add_task(task1)

    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"order": 2},
        idempotency_key="comp_key_2",
    )
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task1", "task2"))

    task3 = WorkflowTask(
        task_id="task3",
        executor=executor3,
        payload={"order": 3},
        idempotency_key="comp_key_3",
    )
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task2", "task3"))

    with pytest.raises(TaskExecutionError):
        await engine.execute(dag)

    assert state["task1"] == "executed"
    assert state["task2"] == "executed"


@pytest.mark.asyncio
async def test_workflow_engine_concurrent_independent_tasks():
    """Test concurrent execution of independent tasks."""
    engine = WorkflowEngine(max_concurrent_tasks=3)
    dag = WorkflowDAG(workflow_id="concurrent_workflow")
    results = {}

    for i in range(5):
        executor = PingPongExecutor(f"task{i}", results)
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=executor,
            payload={"index": i},
            idempotency_key=f"conc_key_{i}",
        )
        dag.add_task(task)

    start_time = datetime.now(timezone.utc)
    execution = await engine.execute(dag)
    _elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    assert all(
        execution.state[f"task{i}"] == WorkflowTaskState.SUCCEEDED
        for i in range(5)
    )


@pytest.mark.asyncio
async def test_workflow_engine_dead_letter_tracking():
    """Test dead-letter queue integration with failed tasks."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="dlq_workflow")
    results = {}

    executor1 = PingPongExecutor("task1", results)
    executor2 = FlakyExecutor("task2", fail_on_count=1, results=results)

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"order": 1},
        idempotency_key="dlq_key_1",
    )
    dag.add_task(task1)

    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"order": 2},
        idempotency_key="dlq_key_2",
    )
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task1", "task2"))

    with pytest.raises(TaskExecutionError):
        await engine.execute(dag)

    dlq_events = await engine.dead_letter_queue.query_by_workflow(
        "dlq_workflow"
    )
    assert len(dlq_events) > 0
    assert any(e.task_id == "task2" for e in dlq_events)


@pytest.mark.asyncio
async def test_workflow_engine_checkpoint_recovery():
    """Test checkpoint creation during execution."""
    engine = WorkflowEngine(checkpoint_interval=2)
    dag = WorkflowDAG(workflow_id="checkpoint_workflow")
    results = {}

    for i in range(5):
        executor = PingPongExecutor(f"task{i}", results)
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=executor,
            payload={"index": i},
            idempotency_key=f"ckpt_key_{i}",
        )
        dag.add_task(task)
        if i > 0:
            dag.add_edge(WorkflowEdge(f"task{i-1}", f"task{i}"))

    execution = await engine.execute(dag)

    assert len(execution.checkpoints) >= 2
    for checkpoint in execution.checkpoints:
        assert checkpoint.workflow_id == "checkpoint_workflow"
        assert len(checkpoint.completed_tasks) > 0


@pytest.mark.asyncio
async def test_workflow_engine_large_dag_execution():
    """Test execution of large DAG."""
    engine = WorkflowEngine(max_concurrent_tasks=5)
    dag = WorkflowDAG(workflow_id="large_workflow")
    results = {}

    executors = [PingPongExecutor(f"task{i}", results) for i in range(20)]

    for i, executor in enumerate(executors):
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=executor,
            payload={"index": i},
            idempotency_key=f"large_key_{i}",
        )
        dag.add_task(task)

    for i in range(19):
        dag.add_edge(WorkflowEdge(f"task{i}", f"task{i+1}"))

    execution = await engine.execute(dag)

    assert len(execution.results) == 20
    assert all(
        execution.state[f"task{i}"] == WorkflowTaskState.SUCCEEDED
        for i in range(20)
    )


@pytest.mark.asyncio
async def test_workflow_engine_complex_dag():
    """Test execution of complex DAG with multiple dependency patterns."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="complex_workflow")
    results = {}

    task_a = WorkflowTask(
        task_id="task_a",
        executor=PingPongExecutor("task_a", results),
        payload={"root": True},
        idempotency_key="complex_a",
    )
    dag.add_task(task_a)

    task_b = WorkflowTask(
        task_id="task_b",
        executor=PingPongExecutor("task_b", results),
        payload={"branch": 1},
        idempotency_key="complex_b",
    )
    dag.add_task(task_b)
    dag.add_edge(WorkflowEdge("task_a", "task_b"))

    task_c = WorkflowTask(
        task_id="task_c",
        executor=PingPongExecutor("task_c", results),
        payload={"branch": 2},
        idempotency_key="complex_c",
    )
    dag.add_task(task_c)
    dag.add_edge(WorkflowEdge("task_a", "task_c"))

    task_d = WorkflowTask(
        task_id="task_d",
        executor=PingPongExecutor("task_d", results),
        payload={"converge": 1},
        idempotency_key="complex_d",
    )
    dag.add_task(task_d)
    dag.add_edge(WorkflowEdge("task_b", "task_d"))
    dag.add_edge(WorkflowEdge("task_c", "task_d"))

    task_e = WorkflowTask(
        task_id="task_e",
        executor=PingPongExecutor("task_e", results),
        payload={"final": True},
        idempotency_key="complex_e",
    )
    dag.add_task(task_e)
    dag.add_edge(WorkflowEdge("task_d", "task_e"))

    execution = await engine.execute(dag)

    assert execution.state["task_e"] == WorkflowTaskState.SUCCEEDED
    assert len(execution.results) == 5


@pytest.mark.asyncio
async def test_workflow_engine_failure_injection():
    """Test workflow resilience to injected failures with compensation."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="failure_injection_workflow")
    state = {}
    results = {}

    executor1 = CompensatingExecutor("task1", results, state)
    executor2 = CompensatingExecutor("task2", results, state)
    executor3 = FlakyExecutor("task3", fail_on_count=1, results=results)

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"order": 1},
        idempotency_key="fail_inj_1",
    )
    dag.add_task(task1)

    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"order": 2},
        idempotency_key="fail_inj_2",
    )
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task1", "task2"))

    task3 = WorkflowTask(
        task_id="task3",
        executor=executor3,
        payload={"order": 3},
        idempotency_key="fail_inj_3",
    )
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task2", "task3"))

    with pytest.raises(TaskExecutionError):
        await engine.execute(dag)

    assert state["task1"] == "executed"
    assert state["task2"] == "executed"
