"""Sales & Marketing agent: content generation and campaign management.

Uses GPT-4o for content generation. Conditionally spawns sub-agents for
full campaigns and product launches.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.llm.config import ModelID
from src.llm.fallback import get_model_with_fallbacks
from src.llm.router import LLMRouter
from src.state import AgentState

logger = logging.getLogger(__name__)

SALES_SYSTEM_PROMPT = """You are a sales and marketing specialist for a print-on-demand e-commerce store.
Your job is to create engaging social media content, plan campaigns, and drive sales.

When creating content, always provide:
1. A compelling caption (2-3 sentences)
2. Relevant hashtags (5-10)
3. Best posting time suggestion
4. Call to action

Respond in JSON format:
{{
  "caption": "...",
  "hashtags": ["#tag1", "#tag2", ...],
  "suggested_time": "HH:MM UTC",
  "call_to_action": "...",
  "content_type": "post|story|reel"
}}
"""


def build_sales_marketing_node(router: LLMRouter):
    """Build the sales/marketing graph node function."""
    model = get_model_with_fallbacks(router, ModelID.GPT4O)

    def sales_marketing_node(state: AgentState) -> dict:
        """Handle sales/marketing tasks. May delegate to sub-agents."""
        logger.info(
            "Sales agent handling task_type=%s, spawn_sub_agents=%s",
            state.get("task_type"),
            state.get("should_spawn_sub_agents"),
        )

        if state.get("should_spawn_sub_agents"):
            # For complex tasks, return control to graph which routes to sub-agent subgraph
            return {
                "current_agent": "sales_marketing",
                "sales_result": {"status": "delegated_to_sub_agents"},
            }

        # Simple task: generate content directly
        task_description = ""
        if state.get("trigger_payload"):
            task_description = json.dumps(state["trigger_payload"])
        elif state.get("messages"):
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    task_description = msg.content
                    break

        response = model.invoke([
            SystemMessage(content=SALES_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Create an Instagram post for our store. Context: {task_description}"
            ),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"raw_content": content}
        except json.JSONDecodeError:
            result = {"raw_content": content}

        result["status"] = "completed"

        return {
            "current_agent": "sales_marketing",
            "sales_result": result,
            "messages": [AIMessage(content=f"Sales agent completed: {result.get('caption', '')}")],
        }

    return sales_marketing_node
