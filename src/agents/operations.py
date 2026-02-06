"""Operations agent: order management, inventory sync, fulfillment.

Uses GPT-4o-mini for cost-effective structured operations.
Tools: Shopify GraphQL + Printful REST API.
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

OPS_SYSTEM_PROMPT = """You are an operations manager for a print-on-demand e-commerce store.
You handle order processing, inventory management, and fulfillment coordination.

Available operations:
- order_check: Check for new orders from Shopify
- inventory_sync: Sync inventory between Shopify and Printful
- fulfill_order: Submit order to Printful for fulfillment
- order_status: Check Printful order status

Respond with a structured action plan in JSON:
{{
  "action": "order_check|inventory_sync|fulfill_order|order_status",
  "details": {{...}},
  "status": "completed|needs_action|error",
  "summary": "..."
}}
"""


def build_operations_node(router: LLMRouter):
    """Build the operations graph node function."""
    model = get_model_with_fallbacks(router, ModelID.GPT4O_MINI)

    def operations_node(state: AgentState) -> dict:
        """Handle operations tasks (orders, inventory, fulfillment)."""
        logger.info("Operations agent handling task_type=%s", state.get("task_type"))

        task_description = ""
        if state.get("trigger_payload"):
            task_description = json.dumps(state["trigger_payload"])
        elif state.get("messages"):
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    task_description = msg.content
                    break

        response = model.invoke([
            SystemMessage(content=OPS_SYSTEM_PROMPT),
            HumanMessage(content=f"Handle this operations task: {task_description}"),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"summary": content}
        except json.JSONDecodeError:
            result = {"summary": content}

        result["status"] = result.get("status", "completed")

        return {
            "current_agent": "operations",
            "operations_result": result,
            "messages": [
                AIMessage(content=f"Operations completed: {result.get('summary', 'done')}")
            ],
        }

    return operations_node
