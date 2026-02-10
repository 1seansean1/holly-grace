"""Dynamic Executor: universal agent node builder for any AgentConfig.

Builds a LangGraph node function from an AgentConfig that:
1. Reads the agent's system prompt and model from the registry
2. Optionally binds tools via model.bind_tools()
3. Invokes the LLM with system prompt + task description
4. Handles tool calls (execute tools, feed results back for final response)
5. For tools requiring approval: calls interrupt() to pause for HITL
6. Writes results to state["agent_results"][agent_id]
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agent_registry import AgentConfigRegistry
from src.agents.constitution import build_system_prompt
from src.approval import ApprovalGate
from src.llm.config import ModelID
from src.llm.fallback import get_model_with_fallbacks
from src.llm.router import LLMRouter
from src.state import AgentState
from src.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 3


def _extract_task_description(state: AgentState) -> str:
    """Extract the task description from state messages or trigger payload."""
    if state.get("trigger_payload"):
        return json.dumps(state["trigger_payload"])
    if state.get("messages"):
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                return msg.content
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
    return ""


def _execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    tools_by_name: dict[str, Any],
    *,
    agent_id: str = "",
) -> list[ToolMessage]:
    """Execute tool calls and return ToolMessage results.

    For tools that require approval (medium/high risk), calls interrupt()
    to pause execution and wait for human decision. On resume, the decision
    determines whether the tool executes or is skipped.
    """
    from langgraph.types import interrupt

    results = []
    for call in tool_calls:
        name = call.get("name", "")
        args = call.get("args", {})
        call_id = call.get("id", name)

        tool = tools_by_name.get(name)
        if not tool:
            results.append(
                ToolMessage(
                    content=f"Error: tool '{name}' not found",
                    tool_call_id=call_id,
                )
            )
            continue

        # Check if this tool requires approval
        if ApprovalGate.requires_approval(name, args):
            risk = ApprovalGate.classify_risk(name, args)
            logger.info("Tool %s requires approval (risk=%s), interrupting", name, risk)

            # Publish to message bus before interrupting (fire-and-forget)
            from src.bus import STREAM_TOWER_EVENTS, publish
            publish(STREAM_TOWER_EVENTS, "tool.approval_requested", {
                "tool": name,
                "risk": risk,
                "agent_id": agent_id,
                "args_preview": str(args)[:200],
            }, source="dynamic_executor")

            # Pause execution — this returns only after resume
            decision = interrupt({
                "ticket_type": "tool_call",
                "risk_level": risk,
                "tldr": f"Execute {name}",
                "why_stopped": f"Tool {name} is {risk}-risk and requires human approval",
                "proposed_action": {"tool": name, "params": args},
                "impact": f"Will execute {name} with provided parameters",
                "risk_flags": [f"risk:{risk}", f"tool:{name}"],
                "agent_id": agent_id,
            })

            # decision comes from Command(resume=...)
            if isinstance(decision, dict) and decision.get("rejected"):
                reason = decision.get("reason", "Operator rejected")
                results.append(
                    ToolMessage(
                        content=f"Tool {name} was rejected by operator: {reason}",
                        tool_call_id=call_id,
                    )
                )
                continue

        # Execute the tool
        try:
            output = tool.invoke(args)
            content = output if isinstance(output, str) else json.dumps(output, default=str)
        except Exception as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            content = f"Error executing {name}: {exc}"

        results.append(ToolMessage(content=content, tool_call_id=call_id))

    return results


def build_dynamic_node(
    agent_id: str,
    registry: AgentConfigRegistry,
    router: LLMRouter,
    tool_registry: ToolRegistry,
):
    """Build a LangGraph node function for any agent config.

    The returned closure reads the agent config at invocation time (not build
    time), so config changes via the UI take effect on the next invocation.

    Returns:
        A callable(state: AgentState) -> dict suitable for StateGraph.add_node().
    """

    def dynamic_node(state: AgentState) -> dict:
        config = registry.get(agent_id)
        logger.info(
            "Dynamic executor running agent=%s model=%s tools=%d",
            agent_id,
            config.model_id,
            len(config.tool_ids),
        )

        # Build model with fallbacks
        model = get_model_with_fallbacks(router, ModelID(config.model_id))

        # Optionally bind tools
        tools = []
        tools_by_name: dict[str, Any] = {}
        if config.tool_ids:
            tools = tool_registry.get_tools_for_agent(config.tool_ids)
            if tools:
                tools_by_name = {t.name: t for t in tools}
                model = model.bind_tools(tools)

        # Extract task description
        task_description = _extract_task_description(state)
        if not task_description:
            return {
                "current_agent": agent_id,
                "agent_results": {
                    **state.get("agent_results", {}),
                    agent_id: {"status": "error", "error": "No task description provided"},
                },
                "error": "No task description provided",
            }

        # Build conversation
        messages = [
            SystemMessage(content=build_system_prompt(agent_id, config.system_prompt)),
            HumanMessage(content=task_description),
        ]

        # Invoke with tool call loop (up to MAX_TOOL_ROUNDS)
        final_response = None
        for round_num in range(MAX_TOOL_ROUNDS + 1):
            response = model.invoke(messages)

            # Check for tool calls
            if hasattr(response, "tool_calls") and response.tool_calls and tools_by_name:
                logger.info(
                    "Agent %s made %d tool call(s) (round %d)",
                    agent_id,
                    len(response.tool_calls),
                    round_num + 1,
                )
                messages.append(response)
                tool_results = _execute_tool_calls(response.tool_calls, tools_by_name, agent_id=agent_id)
                messages.extend(tool_results)

                if round_num == MAX_TOOL_ROUNDS:
                    # Force a final text response on last round
                    final_response = response
                    break
            else:
                final_response = response
                break

        content = final_response.content.strip() if final_response else ""

        # Try to parse as JSON
        try:
            if content.startswith("```"):
                inner = content.split("```")[1]
                if inner.startswith("json"):
                    inner = inner[4:]
                result = json.loads(inner.strip())
            elif content.startswith("{"):
                result = json.loads(content)
            else:
                result = {"raw_content": content}
        except (json.JSONDecodeError, IndexError):
            result = {"raw_content": content}

        result["status"] = result.get("status", "completed")

        # Update agent_results
        agent_results = dict(state.get("agent_results", {}))
        agent_results[agent_id] = result

        return {
            "current_agent": agent_id,
            "agent_results": agent_results,
            "messages": [
                AIMessage(
                    content=f"Agent {config.display_name} completed: "
                    f"{result.get('summary', result.get('caption', content[:200]))}"
                )
            ],
        }

    return dynamic_node
