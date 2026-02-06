"""Revenue & Analytics agent: financial analysis, pricing, chargebacks.

Uses Claude Opus 4.6 for strategic reasoning.
Tools: Stripe toolkit.
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

REVENUE_SYSTEM_PROMPT = """You are a senior revenue analyst and pricing strategist for a
print-on-demand e-commerce business.

Your responsibilities:
- Daily revenue reports (sales, costs, margins, trends)
- Pricing recommendations based on market data and margins
- Chargeback monitoring and dispute strategy
- Long-term revenue optimization

Always provide data-driven analysis. Respond in JSON:
{{
  "report_type": "daily_revenue|pricing_recommendation|chargeback_alert",
  "summary": "...",
  "metrics": {{...}},
  "recommendations": [...],
  "confidence": "high|medium|low",
  "lesson_for_memory": "..."
}}
"""


def build_revenue_node(router: LLMRouter):
    """Build the revenue/analytics graph node function."""
    model = get_model_with_fallbacks(router, ModelID.CLAUDE_OPUS)

    def revenue_node(state: AgentState) -> dict:
        """Handle revenue analysis and pricing tasks."""
        logger.info("Revenue agent handling task_type=%s", state.get("task_type"))

        task_description = ""
        if state.get("trigger_payload"):
            task_description = json.dumps(state["trigger_payload"])
        elif state.get("messages"):
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    task_description = msg.content
                    break

        # Include memory context if available
        memory_ctx = state.get("memory_context", "")
        context_addendum = (
            f"\n\nRelevant past decisions:\n{memory_ctx}" if memory_ctx else ""
        )

        response = model.invoke([
            SystemMessage(content=REVENUE_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Analyze: {task_description}{context_addendum}"
            ),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"summary": content}
        except json.JSONDecodeError:
            result = {"summary": content}

        result["status"] = "completed"

        return {
            "current_agent": "revenue_analytics",
            "revenue_result": result,
            "messages": [
                AIMessage(content=f"Revenue analysis: {result.get('summary', 'complete')}")
            ],
        }

    return revenue_node
