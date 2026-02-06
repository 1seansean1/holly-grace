"""Sub-agent subgraph for campaign tasks.

Spawned conditionally by the Sales & Marketing agent for full campaigns
and product launches. Runs 4 sub-agents in a LangGraph subgraph:
1. content_writer (GPT-4o) — generates post copy
2. image_selector (GPT-4o-mini) — selects/describes product image
3. hashtag_optimizer (Ollama) — optimizes hashtags (free)
4. campaign_analyzer (Opus 4.6) — analyzes expected performance
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.llm.config import ModelID
from src.llm.fallback import get_model_with_fallbacks
from src.llm.router import LLMRouter
from src.state import AgentState

logger = logging.getLogger(__name__)


def _build_content_writer(router: LLMRouter):
    model = get_model_with_fallbacks(router, ModelID.GPT4O)

    def content_writer(state: AgentState) -> dict:
        logger.info("Sub-agent: content_writer starting")
        task = json.dumps(state.get("trigger_payload", {}))

        response = model.invoke([
            SystemMessage(
                content="You are a creative copywriter for a print-on-demand e-commerce brand. "
                "Write compelling Instagram post copy. Output JSON: "
                '{"caption": "...", "tone": "...", "word_count": N}'
            ),
            HumanMessage(content=f"Write post copy for this campaign: {task}"),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"caption": content}
        except json.JSONDecodeError:
            result = {"caption": content}

        sub_results = dict(state.get("sub_agent_results", {}))
        sub_results["content_writer"] = result

        return {
            "sub_agent_results": sub_results,
            "sub_agents_spawned": list(state.get("sub_agents_spawned", [])) + ["content_writer"],
        }

    return content_writer


def _build_image_selector(router: LLMRouter):
    model = get_model_with_fallbacks(router, ModelID.GPT4O_MINI)

    def image_selector(state: AgentState) -> dict:
        logger.info("Sub-agent: image_selector starting")
        task = json.dumps(state.get("trigger_payload", {}))

        response = model.invoke([
            SystemMessage(
                content="You are an image director for e-commerce. "
                "Suggest the ideal product image composition. Output JSON: "
                '{"image_description": "...", "style": "...", "background": "..."}'
            ),
            HumanMessage(content=f"Select/describe the ideal image for: {task}"),
        ])

        content = response.content.strip()
        try:
            result = (
                json.loads(content) if content.startswith("{") else {"image_description": content}
            )
        except json.JSONDecodeError:
            result = {"image_description": content}

        sub_results = dict(state.get("sub_agent_results", {}))
        sub_results["image_selector"] = result

        return {
            "sub_agent_results": sub_results,
            "sub_agents_spawned": list(state.get("sub_agents_spawned", [])) + ["image_selector"],
        }

    return image_selector


def _build_hashtag_optimizer(router: LLMRouter):
    model = get_model_with_fallbacks(router, ModelID.OLLAMA_QWEN)

    def hashtag_optimizer(state: AgentState) -> dict:
        logger.info("Sub-agent: hashtag_optimizer starting")
        sub_results = state.get("sub_agent_results", {})
        caption = sub_results.get("content_writer", {}).get("caption", "")

        response = model.invoke([
            SystemMessage(
                content="You optimize Instagram hashtags for engagement. "
                "Output JSON: "
                '{"hashtags": ["#tag1", ...], "strategy": "..."}'
            ),
            HumanMessage(content=f"Optimize hashtags for this caption: {caption}"),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"hashtags": [content]}
        except json.JSONDecodeError:
            result = {"hashtags": [content]}

        sub_results = dict(sub_results)
        sub_results["hashtag_optimizer"] = result

        return {
            "sub_agent_results": sub_results,
            "sub_agents_spawned": list(state.get("sub_agents_spawned", []))
            + ["hashtag_optimizer"],
        }

    return hashtag_optimizer


def _build_campaign_analyzer(router: LLMRouter):
    model = get_model_with_fallbacks(router, ModelID.CLAUDE_OPUS)

    def campaign_analyzer(state: AgentState) -> dict:
        logger.info("Sub-agent: campaign_analyzer starting")
        sub_results = state.get("sub_agent_results", {})

        response = model.invoke([
            SystemMessage(
                content="You are a senior e-commerce strategist. Analyze the campaign materials "
                "and provide performance predictions and strategic recommendations. "
                "Output JSON: "
                '{"expected_engagement_rate": "X%", "recommendations": [...], '
                '"risk_factors": [...], "estimated_reach": N, "lesson_learned": "..."}'
            ),
            HumanMessage(content=f"Analyze this campaign: {json.dumps(sub_results)}"),
        ])

        content = response.content.strip()
        try:
            result = json.loads(content) if content.startswith("{") else {"analysis": content}
        except json.JSONDecodeError:
            result = {"analysis": content}

        sub_results = dict(sub_results)
        sub_results["campaign_analyzer"] = result

        return {
            "sub_agent_results": sub_results,
            "sub_agents_spawned": list(state.get("sub_agents_spawned", []))
            + ["campaign_analyzer"],
            "sales_result": {
                "status": "campaign_completed",
                "sub_agents_used": list(state.get("sub_agents_spawned", []))
                + ["campaign_analyzer"],
                "campaign_data": sub_results,
            },
            "messages": [
                AIMessage(
                    content=f"Campaign analysis complete: {result.get('expected_engagement_rate', 'N/A')} "
                    f"expected engagement"
                )
            ],
        }

    return campaign_analyzer


def build_sub_agent_subgraph(router: LLMRouter) -> StateGraph:
    """Build the sub-agent subgraph for campaign tasks.

    Flow:
    START → [content_writer, image_selector] (parallel)
          → hashtag_optimizer
          → campaign_analyzer
          → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("content_writer", _build_content_writer(router))
    graph.add_node("image_selector", _build_image_selector(router))
    graph.add_node("hashtag_optimizer", _build_hashtag_optimizer(router))
    graph.add_node("campaign_analyzer", _build_campaign_analyzer(router))

    # Both content_writer and image_selector start from entry
    graph.set_entry_point("content_writer")
    # image_selector also starts from entry — use parallel fan-out
    graph.add_edge("content_writer", "hashtag_optimizer")
    graph.add_edge("image_selector", "hashtag_optimizer")
    graph.add_edge("hashtag_optimizer", "campaign_analyzer")
    graph.add_edge("campaign_analyzer", END)

    return graph
