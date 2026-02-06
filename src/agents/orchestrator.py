"""Orchestrator agent: classifies tasks and routes to the correct specialist agent.

Uses Ollama Qwen 2.5 3B (free, local) for classification.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from src.llm.config import ModelID
from src.llm.fallback import get_model_with_fallbacks
from src.llm.router import LLMRouter
from src.state import AgentState

logger = logging.getLogger(__name__)

VALID_TASK_TYPES = [
    "content_post",
    "full_campaign",
    "product_launch",
    "order_check",
    "inventory_sync",
    "revenue_report",
    "pricing_review",
]

VALID_COMPLEXITIES = ["trivial", "simple", "moderate", "complex"]

VALID_ROUTES = ["sales_marketing", "operations", "revenue_analytics"]

# Task types that trigger sub-agent spawning in the sales agent
SUB_AGENT_TASK_TYPES = {"full_campaign", "product_launch"}

CLASSIFICATION_PROMPT = """You are a task classifier for an e-commerce automation system.
Analyze the incoming task and respond with ONLY a JSON object (no markdown, no explanation):

{{
  "task_type": one of {task_types},
  "task_complexity": one of {complexities},
  "route_to": one of {routes}
}}

Routing rules:
- content_post, full_campaign, product_launch → sales_marketing
- order_check, inventory_sync → operations
- revenue_report, pricing_review → revenue_analytics

Complexity rules:
- trivial: simple lookups, status checks
- simple: single-step operations
- moderate: content generation, multi-step workflows
- complex: strategic analysis, full campaigns
"""


def build_orchestrator_node(router: LLMRouter):
    """Build the orchestrator graph node function."""
    model = get_model_with_fallbacks(router, ModelID.OLLAMA_QWEN)

    def orchestrator_node(state: AgentState) -> dict:
        """Classify the incoming task and determine routing."""
        logger.info("Orchestrator classifying task")

        system_msg = SystemMessage(
            content=CLASSIFICATION_PROMPT.format(
                task_types=VALID_TASK_TYPES,
                complexities=VALID_COMPLEXITIES,
                routes=VALID_ROUTES,
            )
        )

        # Use the last human message or trigger payload as the task description
        task_description = ""
        if state.get("trigger_payload"):
            task_description = json.dumps(state["trigger_payload"])
        elif state.get("messages"):
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    task_description = msg.content
                    break

        if not task_description:
            return {
                "error": "No task description provided",
                "current_agent": "orchestrator",
            }

        response = model.invoke([system_msg, HumanMessage(content=task_description)])
        content = response.content.strip()

        # Parse JSON response (handle potential markdown wrapping)
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            classification = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse orchestrator response: %s", content)
            return {
                "task_type": "content_post",
                "task_complexity": "simple",
                "route_to": "sales_marketing",
                "current_agent": "orchestrator",
                "should_spawn_sub_agents": False,
                "error": "",
            }

        task_type = classification.get("task_type", "content_post")
        if task_type not in VALID_TASK_TYPES:
            task_type = "content_post"

        complexity = classification.get("task_complexity", "simple")
        if complexity not in VALID_COMPLEXITIES:
            complexity = "simple"

        route = classification.get("route_to", "sales_marketing")
        if route not in VALID_ROUTES:
            route = "sales_marketing"

        should_spawn = task_type in SUB_AGENT_TASK_TYPES

        logger.info(
            "Orchestrator classified: type=%s complexity=%s route=%s spawn=%s",
            task_type,
            complexity,
            route,
            should_spawn,
        )

        return {
            "task_type": task_type,
            "task_complexity": complexity,
            "route_to": route,
            "current_agent": "orchestrator",
            "should_spawn_sub_agents": should_spawn,
            "error": "",
        }

    return orchestrator_node
