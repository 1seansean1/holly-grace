"""Unit tests for workflow engine module."""

import asyncio
import contextlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from holly.engine.workflow_engine import (
    CompensationAction,
    CompensationExecutor,
    CompensationFailedError,
    CycleDetectedError,
    DAGCompiler,
    DAGValidationError,
    DeadLetterEvent,
    DeadLetterQueue,
    DeadLetterQueueFullError,
    ExecutionCheckpoint,
    SagaPhase,
    SagaStep,
    TaskExecutor,
    TaskExecutionError,
    WorkflowDAG,
    WorkflowEdge,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowTask,
    WorkflowTaskState,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


class MockTaskExecutor:
    """Mock task executor for testing."""

    def __init__(self, should_fail: bool = False, delay: float = 0.01):
        self.should_fail = should_fail
        self.delay = delay
        self.call_count = 0

    async def execute(self, task_id: str, payload):
        """Execute mock task."""
        self.call_count += 1
        await asyncio.sleep(self.delay)
        if self.should_fail:
            raise RuntimeError(f"mock task {task_id} failed")
        return {"task_id": task_id, "result": f"executed {payload}"}


class MockCompensationExecutor:
    """Mock compensation executor for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0

    async def compensate(self, task_id: str, forward_result):
        """Execute mock compensation."""
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError(f"compensation for {task_id} failed")
        return {"task_id": task_id, "compensated": True}


@pytest.fixture
def mock_executor():
    """Fixture for mock executor."""
    return MockTaskExecutor()


@pytest.fixture
def mock_compensation():
    """Fixture for mock compensation executor."""
    return MockCompensationExecutor()


# ---------------------------------------------------------------------------
# WorkflowTask Tests
# ---------------------------------------------------------------------------


def test_workflow_task_creation(mock_executor):
    """Test WorkflowTask creation."""
    task = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={"key": "value"},
        idempotency_key="idempotency_1",
        timeout_ms=5000,
    )
    assert task.task_id == "task1"
    assert task.payload == {"key": "value"}
    assert task.timeout_ms == 5000


def test_workflow_task_requires_task_id(mock_executor):
    """Test that WorkflowTask requires task_id."""
    with pytest.raises(ValueError):
        WorkflowTask(
            task_id="",
            executor=mock_executor,
            payload={},
            idempotency_key="key",
        )


def test_workflow_task_requires_positive_timeout(mock_executor):
    """Test that WorkflowTask requires positive timeout."""
    with pytest.raises(ValueError):
        WorkflowTask(
            task_id="task1",
            executor=mock_executor,
            payload={},
            idempotency_key="key",
            timeout_ms=0,
        )


def test_workflow_task_requires_idempotency_key(mock_executor):
    """Test that WorkflowTask requires idempotency_key."""
    with pytest.raises(ValueError):
        WorkflowTask(
            task_id="task1",
            executor=mock_executor,
            payload={},
            idempotency_key="",
        )


# ---------------------------------------------------------------------------
# WorkflowEdge Tests
# ---------------------------------------------------------------------------


def test_workflow_edge_creation():
    """Test WorkflowEdge creation."""
    edge = WorkflowEdge(
        source_task_id="task1",
        target_task_id="task2",
    )
    assert edge.source_task_id == "task1"
    assert edge.target_task_id == "task2"


def test_workflow_edge_no_self_loop():
    """Test that WorkflowEdge rejects self-loops."""
    with pytest.raises(ValueError):
        WorkflowEdge(
            source_task_id="task1",
            target_task_id="task1",
        )


# ---------------------------------------------------------------------------
# WorkflowDAG Tests
# ---------------------------------------------------------------------------


def test_workflow_dag_creation(mock_executor):
    """Test WorkflowDAG creation."""
    dag = WorkflowDAG(workflow_id="workflow1")
    assert dag.workflow_id == "workflow1"
    assert len(dag.tasks) == 0
    assert len(dag.edges) == 0


def test_workflow_dag_add_task(mock_executor):
    """Test adding tasks to DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    dag.add_task(task)
    assert "task1" in dag.tasks
    assert dag.tasks["task1"] == task


def test_workflow_dag_add_duplicate_task(mock_executor):
    """Test that DAG rejects duplicate task IDs."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    dag.add_task(task1)
    with pytest.raises(ValueError):
        dag.add_task(task2)


def test_workflow_dag_add_edge(mock_executor):
    """Test adding edges to DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    edge = WorkflowEdge(
        source_task_id="task1",
        target_task_id="task2",
    )
    dag.add_edge(edge)
    assert len(dag.edges) == 1


def test_workflow_dag_edge_unknown_source(mock_executor):
    """Test that DAG rejects edges with unknown source."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    dag.add_task(task)
    edge = WorkflowEdge(
        source_task_id="unknown",
        target_task_id="task1",
    )
    with pytest.raises(ValueError):
        dag.add_edge(edge)


def test_workflow_dag_get_dependencies(mock_executor):
    """Test getting task dependencies."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    task3 = WorkflowTask(
        task_id="task3",
        executor=mock_executor,
        payload={},
        idempotency_key="key3",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task1", "task3"))
    dag.add_edge(WorkflowEdge("task2", "task3"))

    deps = dag.get_dependencies("task3")
    assert deps == {"task1", "task2"}


def test_workflow_dag_get_dependents(mock_executor):
    """Test getting dependent tasks."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    task3 = WorkflowTask(
        task_id="task3",
        executor=mock_executor,
        payload={},
        idempotency_key="key3",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task1", "task2"))
    dag.add_edge(WorkflowEdge("task1", "task3"))

    dependents = dag.get_dependents("task1")
    assert dependents == {"task2", "task3"}


def test_workflow_dag_topological_sort(mock_executor):
    """Test topological sorting of DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    task3 = WorkflowTask(
        task_id="task3",
        executor=mock_executor,
        payload={},
        idempotency_key="key3",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task1", "task2"))
    dag.add_edge(WorkflowEdge("task2", "task3"))

    sorted_tasks = dag.topological_sort()
    assert sorted_tasks.index("task1") < sorted_tasks.index("task2")
    assert sorted_tasks.index("task2") < sorted_tasks.index("task3")


def test_workflow_dag_cycle_detection(mock_executor):
    """Test cycle detection in DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task1", "task2"))
    dag.add_edge(WorkflowEdge("task2", "task1"))

    with pytest.raises(CycleDetectedError):
        dag.topological_sort()


# ---------------------------------------------------------------------------
# DAGCompiler Tests
# ---------------------------------------------------------------------------


def test_dag_compiler_validate_empty_dag():
    """Test DAG compiler rejects empty DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    with pytest.raises(DAGValidationError):
        DAGCompiler.validate(dag)


def test_dag_compiler_validate_valid_dag(mock_executor):
    """Test DAG compiler accepts valid DAG."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    dag.add_task(task)
    DAGCompiler.validate(dag)


def test_dag_compiler_validate_cycle(mock_executor):
    """Test DAG compiler detects cycles."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task1 = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=mock_executor,
        payload={},
        idempotency_key="key2",
    )
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_edge(WorkflowEdge("task1", "task2"))
    dag.add_edge(WorkflowEdge("task2", "task1"))

    with pytest.raises(CycleDetectedError):
        DAGCompiler.validate(dag)


def test_dag_compiler_compile(mock_executor):
    """Test DAG compiler compilation."""
    dag = WorkflowDAG(workflow_id="workflow1")
    task = WorkflowTask(
        task_id="task1",
        executor=mock_executor,
        payload={},
        idempotency_key="key1",
    )
    dag.add_task(task)
    compiled = DAGCompiler.compile(dag)
    assert compiled == dag


# ---------------------------------------------------------------------------
# DeadLetterQueue Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dead_letter_queue_creation():
    """Test DeadLetterQueue creation."""
    queue = DeadLetterQueue(max_size=100, ttl_hours=24)
    assert queue.max_size == 100
    assert queue.ttl_hours == 24
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_dead_letter_queue_enqueue():
    """Test enqueuing events."""
    queue = DeadLetterQueue()
    event = DeadLetterEvent(
        event_id=str(uuid4()),
        workflow_id="workflow1",
        task_id="task1",
        timestamp=datetime.now(timezone.utc),
        error_message="test error",
        payload={"key": "value"},
    )
    await queue.enqueue(event)
    assert await queue.size() == 1


@pytest.mark.asyncio
async def test_dead_letter_queue_full():
    """Test DeadLetterQueue overflow."""
    queue = DeadLetterQueue(max_size=2)
    for i in range(2):
        event = DeadLetterEvent(
            event_id=str(uuid4()),
            workflow_id="workflow1",
            task_id=f"task{i}",
            timestamp=datetime.now(timezone.utc),
            error_message="test error",
            payload={},
        )
        await queue.enqueue(event)

    event3 = DeadLetterEvent(
        event_id=str(uuid4()),
        workflow_id="workflow1",
        task_id="task3",
        timestamp=datetime.now(timezone.utc),
        error_message="test error",
        payload={},
    )
    with pytest.raises(DeadLetterQueueFullError):
        await queue.enqueue(event3)


@pytest.mark.asyncio
async def test_dead_letter_queue_dequeue():
    """Test dequeuing events."""
    queue = DeadLetterQueue()
    event = DeadLetterEvent(
        event_id="event1",
        workflow_id="workflow1",
        task_id="task1",
        timestamp=datetime.now(timezone.utc),
        error_message="test error",
        payload={},
    )
    await queue.enqueue(event)
    retrieved = await queue.dequeue("event1")
    assert retrieved == event
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_dead_letter_queue_peek():
    """Test peeking at events without removal."""
    queue = DeadLetterQueue()
    event = DeadLetterEvent(
        event_id="event1",
        workflow_id="workflow1",
        task_id="task1",
        timestamp=datetime.now(timezone.utc),
        error_message="test error",
        payload={},
    )
    await queue.enqueue(event)
    retrieved = await queue.peek("event1")
    assert retrieved == event
    assert await queue.size() == 1


@pytest.mark.asyncio
async def test_dead_letter_queue_query_by_workflow():
    """Test querying events by workflow."""
    queue = DeadLetterQueue()
    for i in range(3):
        event = DeadLetterEvent(
            event_id=f"event{i}",
            workflow_id="workflow1",
            task_id=f"task{i}",
            timestamp=datetime.now(timezone.utc),
            error_message="test error",
            payload={},
        )
        await queue.enqueue(event)

    events = await queue.query_by_workflow("workflow1")
    assert len(events) == 3


@pytest.mark.asyncio
async def test_dead_letter_queue_query_by_task():
    """Test querying events by task."""
    queue = DeadLetterQueue()
    for i in range(3):
        event = DeadLetterEvent(
            event_id=f"event{i}",
            workflow_id="workflow1",
            task_id="task1",
            timestamp=datetime.now(timezone.utc),
            error_message="test error",
            payload={},
        )
        await queue.enqueue(event)

    events = await queue.query_by_task("workflow1", "task1")
    assert len(events) == 3


# ---------------------------------------------------------------------------
# WorkflowEngine Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_engine_creation():
    """Test WorkflowEngine creation."""
    engine = WorkflowEngine(max_concurrent_tasks=5)
    assert engine.max_concurrent_tasks == 5


@pytest.mark.asyncio
async def test_workflow_engine_simple_execution():
    """Test simple workflow execution."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")
    executor = MockTaskExecutor()
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
    )
    dag.add_task(task)

    execution = await engine.execute(dag)
    assert execution.workflow_id == "workflow1"
    assert execution.state["task1"] == WorkflowTaskState.SUCCEEDED
    assert executor.call_count == 1


@pytest.mark.asyncio
async def test_workflow_engine_multi_task_execution():
    """Test multi-task workflow execution."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor1 = MockTaskExecutor()
    executor2 = MockTaskExecutor()
    executor3 = MockTaskExecutor()

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"test": "data1"},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"test": "data2"},
        idempotency_key="key2",
    )
    task3 = WorkflowTask(
        task_id="task3",
        executor=executor3,
        payload={"test": "data3"},
        idempotency_key="key3",
    )

    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_task(task3)
    dag.add_edge(WorkflowEdge("task1", "task2"))
    dag.add_edge(WorkflowEdge("task2", "task3"))

    execution = await engine.execute(dag)
    assert execution.state["task1"] == WorkflowTaskState.SUCCEEDED
    assert execution.state["task2"] == WorkflowTaskState.SUCCEEDED
    assert execution.state["task3"] == WorkflowTaskState.SUCCEEDED


@pytest.mark.asyncio
async def test_workflow_engine_task_failure():
    """Test workflow execution with task failure."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor1 = MockTaskExecutor()
    executor2 = MockTaskExecutor(should_fail=True)

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"test": "data1"},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"test": "data2"},
        idempotency_key="key2",
    )

    dag.add_task(task1)
    dag.add_task(task2)

    with pytest.raises(TaskExecutionError):
        await engine.execute(dag)


@pytest.mark.asyncio
async def test_workflow_engine_compensation():
    """Test workflow compensation on failure."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor(should_fail=True)
    compensation = MockCompensationExecutor()

    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
        compensation_executor=compensation,
    )
    dag.add_task(task)

    with contextlib.suppress(TaskExecutionError):
        await engine.execute(dag)

    assert compensation.call_count == 0


@pytest.mark.asyncio
async def test_workflow_engine_dead_letter_queue():
    """Test dead-letter queue integration."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor(should_fail=True)
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
    )
    dag.add_task(task)

    with contextlib.suppress(TaskExecutionError):
        await engine.execute(dag)

    dlq_size = await engine.dead_letter_queue.size()
    assert dlq_size > 0


@pytest.mark.asyncio
async def test_workflow_engine_checkpoint():
    """Test execution checkpointing."""
    engine = WorkflowEngine(checkpoint_interval=1)
    dag = WorkflowDAG(workflow_id="workflow1")

    executor1 = MockTaskExecutor()
    executor2 = MockTaskExecutor()

    task1 = WorkflowTask(
        task_id="task1",
        executor=executor1,
        payload={"test": "data1"},
        idempotency_key="key1",
    )
    task2 = WorkflowTask(
        task_id="task2",
        executor=executor2,
        payload={"test": "data2"},
        idempotency_key="key2",
    )

    dag.add_task(task1)
    dag.add_task(task2)

    execution = await engine.execute(dag)
    assert len(execution.checkpoints) >= 1


@pytest.mark.asyncio
async def test_workflow_engine_concurrent_tasks():
    """Test concurrent task execution."""
    engine = WorkflowEngine(max_concurrent_tasks=2)
    dag = WorkflowDAG(workflow_id="workflow1")

    executors = [MockTaskExecutor(delay=0.05) for _ in range(4)]
    for i, executor in enumerate(executors):
        task = WorkflowTask(
            task_id=f"task{i}",
            executor=executor,
            payload={"test": f"data{i}"},
            idempotency_key=f"key{i}",
        )
        dag.add_task(task)

    execution = await engine.execute(dag)

    assert execution.state[f"task{len(executors)-1}"] == WorkflowTaskState.SUCCEEDED


@pytest.mark.asyncio
async def test_workflow_engine_task_timeout():
    """Test task timeout handling."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor(delay=0.5)
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
        timeout_ms=100,
    )
    dag.add_task(task)

    with pytest.raises(TaskExecutionError):
        await engine.execute(dag)


@pytest.mark.asyncio
async def test_workflow_engine_execution_state_tracking():
    """Test execution state tracking."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor()
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
    )
    dag.add_task(task)

    execution = await engine.execute(dag)
    assert execution.state["task1"] == WorkflowTaskState.SUCCEEDED
    assert "task1" in execution.results


@pytest.mark.asyncio
async def test_workflow_engine_get_execution():
    """Test retrieving execution by ID."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor()
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"test": "data"},
        idempotency_key="key1",
    )
    dag.add_task(task)

    execution = await engine.execute(dag)
    retrieved = await engine.get_execution(execution.execution_id)
    assert retrieved == execution


@pytest.mark.asyncio
async def test_workflow_engine_list_executions():
    """Test listing executions for workflow."""
    engine = WorkflowEngine()

    for w_id in range(2):
        dag = WorkflowDAG(workflow_id=f"workflow{w_id}")
        executor = MockTaskExecutor()
        task = WorkflowTask(
            task_id="task1",
            executor=executor,
            payload={"test": "data"},
            idempotency_key=f"key{w_id}",
        )
        dag.add_task(task)
        await engine.execute(dag)

    executions = await engine.list_executions("workflow0")
    assert len(executions) > 0
    assert all(e.workflow_id == "workflow0" for e in executions)


@pytest.mark.asyncio
async def test_workflow_engine_dag_validation_error():
    """Test DAG validation error handling."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    with pytest.raises(DAGValidationError):
        await engine.execute(dag)


@pytest.mark.asyncio
async def test_workflow_engine_execution_results():
    """Test execution results collection."""
    engine = WorkflowEngine()
    dag = WorkflowDAG(workflow_id="workflow1")

    executor = MockTaskExecutor()
    task = WorkflowTask(
        task_id="task1",
        executor=executor,
        payload={"key": "value"},
        idempotency_key="key1",
    )
    dag.add_task(task)

    execution = await engine.execute(dag)
    assert "task1" in execution.results
    assert execution.results["task1"]["task_id"] == "task1"
