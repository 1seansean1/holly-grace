"""AgentState: shared state for the LangGraph workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state flowing through the LangGraph StateGraph.

    Fields:
        messages: Accumulated conversation messages (auto-merged via add_messages).
        task_type: Classified task type from orchestrator.
        task_complexity: Complexity rating (trivial/simple/moderate/complex).
        current_agent: Name of the currently active agent.
        route_to: Target agent for routing (sales_marketing/operations/revenue_analytics).
        trigger_source: Where the task originated (scheduler/api/manual).
        trigger_payload: Raw payload from the trigger.
        should_spawn_sub_agents: Whether the sales agent should spawn sub-agents.
        sub_agents_spawned: List of sub-agent names that were spawned.
        memory_context: Retrieved long-term memory context for the current task.
        sales_result: Output from the sales/marketing agent.
        operations_result: Output from the operations agent.
        revenue_result: Output from the revenue/analytics agent.
        sub_agent_results: Outputs from spawned sub-agents.
        error: Error message if something failed.
        retry_count: Number of retries attempted.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str
    task_complexity: str
    current_agent: str
    route_to: str
    trigger_source: str
    trigger_payload: dict[str, Any]
    should_spawn_sub_agents: bool
    sub_agents_spawned: list[str]
    memory_context: str
    sales_result: dict[str, Any]
    operations_result: dict[str, Any]
    revenue_result: dict[str, Any]
    sub_agent_results: dict[str, Any]
    error: str
    retry_count: int
