"""Holly Grace agent — Claude Opus 4.6 super-orchestrator with function calling.

The agent loop:
1. Load session history + pending notifications
2. Build messages array with system prompt
3. Call Anthropic API with tools
4. Execute tool calls, collect results
5. Repeat until the model returns a final text response (max 5 rounds)
6. Store response in session and return

This is a direct LLM loop (not a LangGraph StateGraph). Holly Grace doesn't
need checkpointing/interrupts herself — she *manages* those for other workflows.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import anthropic

from src.holly.consumer import get_pending_notifications, mark_notification_surfaced
from src.holly.prompts import HOLLY_GREETING, HOLLY_SYSTEM_PROMPT
from src.holly.session import append_message, get_messages
from src.holly.tools import HOLLY_TOOL_SCHEMAS, HOLLY_TOOLS

logger = logging.getLogger(__name__)

_MODEL = os.environ.get("HOLLY_MODEL", "claude-opus-4-6")
_MAX_TOOL_ROUNDS = 5
_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set — "
                "Holly Grace cannot start without it"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Context injection — pending notifications become a system message
# ---------------------------------------------------------------------------

def _build_notification_context(session_id: str = "default") -> str | None:
    """Build a context string from pending notifications.

    Returns None if there are no pending notifications.
    Marks surfaced notifications so they aren't repeated.
    """
    notifications = get_pending_notifications(limit=20)
    if not notifications:
        return None

    lines = [f"[{len(notifications)} pending notification(s) since your last message]"]
    for n in notifications:
        payload = n.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        priority_marker = ""
        if n.get("priority") in ("critical", "high"):
            priority_marker = " [URGENT]"

        msg_type = n.get("msg_type", "unknown")
        lines.append(f"- {msg_type}{priority_marker}: {_summarize_payload(msg_type, payload)}")

        # Mark as surfaced
        try:
            mark_notification_surfaced(n["id"], session_id)
        except Exception:
            logger.warning("Failed to mark notification %s as surfaced", n.get("id"))

    return "\n".join(lines)


def _summarize_payload(msg_type: str, payload: dict) -> str:
    """Produce a human-readable one-liner from a notification payload."""
    if msg_type == "ticket.created":
        tldr = payload.get("tldr") or payload.get("ticket_type", "approval request")
        risk = payload.get("risk_level", "?")
        tid = payload.get("ticket_id", "?")
        return f"Ticket #{tid} ({risk} risk): {tldr}"

    if msg_type == "run.failed":
        rid = payload.get("run_id", "?")
        err = payload.get("error", payload.get("last_error", "unknown"))
        return f"Run {rid} failed: {err}"

    if msg_type == "run.completed":
        rid = payload.get("run_id", "?")
        name = payload.get("run_name", "")
        return f"Run {rid} completed{': ' + name if name else ''}"

    if msg_type == "scheduler.fired":
        job = payload.get("job_name", payload.get("run_name", "scheduled job"))
        return f"Scheduler fired: {job}"

    if msg_type == "cascade.completed":
        return f"Cascade completed: {payload.get('cascade_id', '?')}"

    if msg_type == "tool.approval_requested":
        tool = payload.get("tool_name", "?")
        risk = payload.get("risk", "?")
        return f"Tool approval needed: {tool} ({risk} risk)"

    if msg_type == "human.message":
        return payload.get("content", payload.get("message", "new message"))

    # Fallback
    return json.dumps(payload, default=str)[:200]


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------

def generate_greeting(session_id: str = "default") -> str:
    """Generate Holly Grace's greeting with current system status."""
    hour = datetime.now(timezone.utc).hour
    if hour < 12:
        tod = "morning"
    elif hour < 17:
        tod = "afternoon"
    else:
        tod = "evening"

    # Build status summary
    status_parts = []
    try:
        from src.holly.tools import query_system_health
        health = query_system_health()
        active = health.get("active_runs", 0)
        waiting = health.get("waiting_approval", 0)
        pending = health.get("pending_tickets", 0)
        overall = health.get("overall", "unknown")

        if active > 0:
            status_parts.append(f"{active} workflow(s) running")
        if waiting > 0:
            status_parts.append(f"{waiting} waiting for approval")
        if pending > 0:
            status_parts.append(f"{pending} ticket(s) need your attention")
        if overall != "healthy":
            status_parts.append(f"System status: {overall}")
        if not status_parts:
            status_parts.append("All systems nominal. No pending items.")
    except Exception:
        status_parts.append("System status loading...")

    summary = " ".join(status_parts) if status_parts else "All clear."

    return HOLLY_GREETING.format(time_of_day=tod, status_summary=summary)


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def handle_message(
    user_message: str,
    *,
    session_id: str = "default",
    stream_callback: Any = None,
) -> str:
    """Process a human message and return Holly Grace's response.

    Args:
        user_message: The human's message text.
        session_id: Conversation session ID.
        stream_callback: Optional callable(token: str) for streaming tokens.

    Returns:
        Holly Grace's final text response.
    """
    client = _get_client()

    # 1. Store human message in session
    append_message("human", user_message, session_id=session_id)

    # 2. Load session history
    history = get_messages(session_id)

    # 3. Build Anthropic messages from session history
    messages = _build_anthropic_messages(history)

    # 4. Inject notification context if any
    notification_ctx = _build_notification_context(session_id)
    if notification_ctx and len(messages) > 0:
        # Insert as a system-injected user message before the latest human message
        insert_idx = max(0, len(messages) - 1)
        messages.insert(insert_idx, {
            "role": "user",
            "content": f"[SYSTEM CONTEXT — new events since last turn]\n{notification_ctx}",
        })
        # Need an assistant ack so the API alternation rule is satisfied
        messages.insert(insert_idx + 1, {
            "role": "assistant",
            "content": "Noted, I'll factor these into my response.",
        })

    # 5. Agent loop — call Anthropic, execute tools, repeat
    final_text = ""
    for round_num in range(_MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=HOLLY_SYSTEM_PROMPT,
            tools=HOLLY_TOOL_SCHEMAS,
            messages=messages,
        )

        # Process the response content blocks
        text_parts = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                if stream_callback and block.text:
                    stream_callback(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # If no tool calls, we're done
        if not tool_uses:
            final_text = "\n".join(text_parts)
            break

        # Build assistant message with all content blocks
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute tool calls and build tool results
        tool_results = []
        for tu in tool_uses:
            result = _execute_tool(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
            logger.info(
                "Holly tool call: %s(%s) → %s",
                tu.name,
                json.dumps(tu.input, default=str)[:200],
                json.dumps(result, default=str)[:200],
            )

        messages.append({"role": "user", "content": tool_results})

        # Capture any text from rounds with tool calls
        if text_parts:
            final_text += "\n".join(text_parts) + "\n"

    else:
        # Max rounds reached — the last text we have is the response
        if not final_text:
            final_text = "I've gathered the information but hit my tool-call limit. Let me summarize what I found."

    # 6. Store Holly's response in session
    final_text = final_text.strip()
    if final_text:
        append_message("holly", final_text, session_id=session_id)

    return final_text


# ---------------------------------------------------------------------------
# Streaming variant
# ---------------------------------------------------------------------------

async def handle_message_stream(
    user_message: str,
    *,
    session_id: str = "default",
):
    """Async generator that yields (event_type, data) tuples for WebSocket streaming.

    Event types:
    - ("token", str): streaming text token
    - ("tool_call", dict): tool being called
    - ("tool_result", dict): tool result
    - ("done", str): final complete response
    - ("error", str): error message
    """
    client = _get_client()

    # Store human message
    append_message("human", user_message, session_id=session_id)

    history = get_messages(session_id)
    messages = _build_anthropic_messages(history)

    # Inject notifications
    notification_ctx = _build_notification_context(session_id)
    if notification_ctx:
        messages.insert(-1, {
            "role": "user",
            "content": f"[SYSTEM CONTEXT — new events since last turn]\n{notification_ctx}",
        })
        messages.insert(-1, {
            "role": "assistant",
            "content": "Noted, I'll factor these into my response.",
        })

    full_text = ""

    for round_num in range(_MAX_TOOL_ROUNDS):
        try:
            with client.messages.stream(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=HOLLY_SYSTEM_PROMPT,
                tools=HOLLY_TOOL_SCHEMAS,
                messages=messages,
            ) as stream:
                response = None
                text_this_round = ""
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield ("token", event.delta.text)
                                text_this_round += event.delta.text

                response = stream.get_final_message()

        except Exception as e:
            logger.exception("Holly streaming error")
            yield ("error", str(e))
            return

        # Gather tool uses
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            full_text += text_this_round
            break

        # Build assistant message for context
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools
        tool_results = []
        for tu in tool_uses:
            yield ("tool_call", {"name": tu.name, "input": tu.input})
            result = _execute_tool(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
            logger.info(
                "Holly tool call (stream): %s(%s) → %s",
                tu.name,
                json.dumps(tu.input, default=str)[:200],
                json.dumps(result, default=str)[:200],
            )
            yield ("tool_result", {"name": tu.name, "result": result})

        messages.append({"role": "user", "content": tool_results})
        full_text += text_this_round

    # Store response
    full_text = full_text.strip()
    if full_text:
        append_message("holly", full_text, session_id=session_id)

    yield ("done", full_text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_anthropic_messages(history: list[dict]) -> list[dict]:
    """Convert session history to Anthropic-format messages.

    Maps roles: 'human' → 'user', 'holly' → 'assistant', 'system' → 'user' (prefixed).
    Ensures alternating user/assistant turns (Anthropic API requirement).
    """
    messages = []
    last_role = None

    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "human":
            api_role = "user"
        elif role == "holly":
            api_role = "assistant"
        elif role == "system":
            api_role = "user"
            content = f"[System] {content}"
        else:
            api_role = "user"

        # Merge consecutive same-role messages
        if api_role == last_role and messages:
            prev = messages[-1]
            if isinstance(prev["content"], str):
                prev["content"] = prev["content"] + "\n" + content
            continue

        messages.append({"role": api_role, "content": content})
        last_role = api_role

    # Ensure the conversation starts with a user message
    if messages and messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "[Session start]"})

    # Ensure alternation — insert bridging messages where needed
    fixed = []
    for i, msg in enumerate(messages):
        if fixed and msg["role"] == fixed[-1]["role"]:
            # Insert a bridge
            if msg["role"] == "user":
                fixed.append({"role": "assistant", "content": "..."})
            else:
                fixed.append({"role": "user", "content": "[continue]"})
        fixed.append(msg)

    return fixed


def _execute_tool(name: str, inputs: dict) -> dict:
    """Execute a Holly Grace tool by name and return the result."""
    fn = HOLLY_TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        result = fn(**inputs)
        if not isinstance(result, dict):
            result = {"result": result}
        return result
    except Exception as e:
        logger.exception("Holly tool error: %s", name)
        return {"error": f"Tool {name} failed: {e}"}
