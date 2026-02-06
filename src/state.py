"""AgentState: shared state for the LangGraph workflow."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


class AgentState(TypedDict):
    """Shared state flowing through the LangGraph StateGraph.

    Only `messages` is required at invocation time. All other fields
    are populated by agents during graph execution.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    task_type: NotRequired[str]
    task_complexity: NotRequired[str]
    current_agent: NotRequired[str]
    route_to: NotRequired[str]
    trigger_source: NotRequired[str]
    trigger_payload: NotRequired[dict[str, Any]]
    should_spawn_sub_agents: NotRequired[bool]
    sub_agents_spawned: NotRequired[list[str]]
    memory_context: NotRequired[str]
    sales_result: NotRequired[dict[str, Any]]
    operations_result: NotRequired[dict[str, Any]]
    revenue_result: NotRequired[dict[str, Any]]
    sub_agent_results: NotRequired[dict[str, Any]]
    error: NotRequired[str]
    retry_count: NotRequired[int]
