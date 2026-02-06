"""Master LangGraph StateGraph: orchestrates all agents and routing."""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from src.agents.orchestrator import build_orchestrator_node
from src.agents.operations import build_operations_node
from src.agents.revenue import build_revenue_node
from src.agents.sales_marketing import build_sales_marketing_node
from src.agents.sub_agents import build_sub_agent_subgraph
from src.llm.router import LLMRouter
from src.state import AgentState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _route_from_orchestrator(state: AgentState) -> str:
    """Route from orchestrator to the target agent."""
    route = state.get("route_to", "")
    if state.get("error"):
        return "error_handler"
    if route == "sales_marketing":
        return "sales_marketing"
    elif route == "operations":
        return "operations"
    elif route == "revenue_analytics":
        return "revenue_analytics"
    return "error_handler"


def _route_from_sales(state: AgentState) -> str:
    """Route from sales: to sub-agents if needed, otherwise END."""
    if state.get("should_spawn_sub_agents"):
        return "sub_agents"
    return END


def _error_handler(state: AgentState) -> dict:
    """Handle errors with retry logic."""
    retry_count = state.get("retry_count", 0)
    error = state.get("error", "Unknown error")

    if retry_count < MAX_RETRIES:
        logger.warning("Retrying (attempt %d/%d): %s", retry_count + 1, MAX_RETRIES, error)
        return {
            "retry_count": retry_count + 1,
            "error": "",
            "current_agent": "error_handler",
        }

    logger.error("Max retries exceeded: %s", error)
    return {
        "current_agent": "error_handler",
        "messages": [
            AIMessage(
                content=f"Task failed after {MAX_RETRIES} retries: {error}"
            )
        ],
    }


def _route_from_error(state: AgentState) -> str:
    """Route from error handler: retry or END."""
    if state.get("retry_count", 0) < MAX_RETRIES and not state.get("error"):
        return "orchestrator"
    return END


def build_graph(router: LLMRouter) -> StateGraph:
    """Build the master agent graph.

    Flow:
    START → orchestrator → {sales_marketing, operations, revenue_analytics}
    sales_marketing → sub_agents (conditional) → END
    operations → END
    revenue_analytics → END
    error_handler → orchestrator (retry) or END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("orchestrator", build_orchestrator_node(router))
    graph.add_node("sales_marketing", build_sales_marketing_node(router))
    graph.add_node("operations", build_operations_node(router))
    graph.add_node("revenue_analytics", build_revenue_node(router))
    graph.add_node("error_handler", _error_handler)

    # Build and add sub-agent subgraph
    sub_graph = build_sub_agent_subgraph(router)
    graph.add_node("sub_agents", sub_graph.compile())

    # Entry point
    graph.set_entry_point("orchestrator")

    # Routing edges
    graph.add_conditional_edges(
        "orchestrator",
        _route_from_orchestrator,
        {
            "sales_marketing": "sales_marketing",
            "operations": "operations",
            "revenue_analytics": "revenue_analytics",
            "error_handler": "error_handler",
        },
    )

    graph.add_conditional_edges(
        "sales_marketing",
        _route_from_sales,
        {
            "sub_agents": "sub_agents",
            END: END,
        },
    )

    graph.add_edge("sub_agents", END)
    graph.add_edge("operations", END)
    graph.add_edge("revenue_analytics", END)

    graph.add_conditional_edges(
        "error_handler",
        _route_from_error,
        {
            "orchestrator": "orchestrator",
            END: END,
        },
    )

    return graph
