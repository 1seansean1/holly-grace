"""Short-term memory: conversation buffer within a single run.

Uses LangGraph's built-in message accumulation via the `messages` field
in AgentState with `add_messages` annotation. This file provides a helper
to extract recent context from state.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from src.state import AgentState

DEFAULT_WINDOW_SIZE = 10


def get_recent_messages(state: AgentState, k: int = DEFAULT_WINDOW_SIZE) -> list[BaseMessage]:
    """Get the last k messages from state for context windowing."""
    messages = state.get("messages", [])
    return messages[-k:] if len(messages) > k else messages


def format_context_window(state: AgentState, k: int = DEFAULT_WINDOW_SIZE) -> str:
    """Format recent messages as a string for injection into prompts."""
    messages = get_recent_messages(state, k)
    lines = []
    for msg in messages:
        role = msg.__class__.__name__.replace("Message", "")
        lines.append(f"[{role}]: {msg.content}")
    return "\n".join(lines)
