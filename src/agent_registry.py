"""Agent Configuration Registry: runtime-configurable agent prompts and models.

Reads agent configs from Postgres with an in-memory cache (30s TTL).
Falls back to hardcoded defaults if the DB is unavailable.
Supports create, update, soft-delete, version history, and rollback.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.aps.store import (
    create_agent_config,
    get_agent_config,
    get_agent_version,
    get_agent_version_history,
    get_all_agent_configs,
    seed_agent_configs,
    snapshot_agent_version,
    soft_delete_agent_config,
    update_agent_config,
)
from src.llm.config import ModelID

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Runtime agent configuration."""

    agent_id: str
    channel_id: str
    display_name: str
    description: str
    model_id: str  # ModelID value string
    system_prompt: str
    version: int = 1
    tool_ids: list[str] = field(default_factory=list)
    is_builtin: bool = False


def _row_to_config(row: dict[str, Any]) -> AgentConfig:
    """Convert a store dict to AgentConfig."""
    return AgentConfig(
        agent_id=row["agent_id"],
        channel_id=row["channel_id"],
        display_name=row["display_name"],
        description=row["description"],
        model_id=row["model_id"],
        system_prompt=row["system_prompt"],
        version=row.get("version", 1),
        tool_ids=row.get("tool_ids", []) or [],
        is_builtin=row.get("is_builtin", False),
    )


# ---------------------------------------------------------------------------
# Hardcoded defaults (extracted from agent source files)
# ---------------------------------------------------------------------------

_HARDCODED_DEFAULTS: dict[str, AgentConfig] = {
    "orchestrator": AgentConfig(
        agent_id="orchestrator",
        channel_id="K1",
        display_name="Orchestrator",
        description="Classifies incoming tasks and routes to the correct specialist agent",
        model_id=ModelID.OLLAMA_QWEN.value,
        system_prompt=(
            "You are a task classifier for an e-commerce automation system.\n"
            "Analyze the incoming task and respond with ONLY a JSON object (no markdown, no explanation):\n\n"
            "{{\n"
            '  "task_type": one of {task_types},\n'
            '  "task_complexity": one of {complexities},\n'
            '  "route_to": one of {routes}\n'
            "}}\n\n"
            "Routing rules:\n"
            "- content_post, full_campaign, product_launch \u2192 sales_marketing\n"
            "- order_check, inventory_sync \u2192 operations\n"
            "- revenue_report, pricing_review \u2192 revenue_analytics\n\n"
            "Complexity rules:\n"
            "- trivial: simple lookups, status checks\n"
            "- simple: single-step operations\n"
            "- moderate: content generation, multi-step workflows\n"
            "- complex: strategic analysis, full campaigns"
        ),
        is_builtin=True,
    ),
    "sales_marketing": AgentConfig(
        agent_id="sales_marketing",
        channel_id="K2",
        display_name="Sales & Marketing",
        description="Creates engaging social media content, plans campaigns, and drives sales",
        model_id=ModelID.GPT4O.value,
        system_prompt=(
            "You are a sales and marketing specialist for a print-on-demand e-commerce store.\n"
            "Your job is to create engaging social media content, plan campaigns, and drive sales.\n\n"
            "When creating content, always provide:\n"
            "1. A compelling caption (2-3 sentences)\n"
            "2. Relevant hashtags (5-10)\n"
            "3. Best posting time suggestion\n"
            "4. Call to action\n\n"
            "Respond in JSON format:\n"
            "{{\n"
            '  "caption": "...",\n'
            '  "hashtags": ["#tag1", "#tag2", ...],\n'
            '  "suggested_time": "HH:MM UTC",\n'
            '  "call_to_action": "...",\n'
            '  "content_type": "post|story|reel"\n'
            "}}"
        ),
        is_builtin=True,
    ),
    "operations": AgentConfig(
        agent_id="operations",
        channel_id="K3",
        display_name="Operations",
        description="Handles order processing, inventory management, and fulfillment coordination",
        model_id=ModelID.GPT4O_MINI.value,
        system_prompt=(
            "You are an operations manager for a print-on-demand e-commerce store.\n"
            "You handle order processing, inventory management, and fulfillment coordination.\n\n"
            "Available operations:\n"
            "- order_check: Check for new orders from Shopify\n"
            "- inventory_sync: Sync inventory between Shopify and Printful\n"
            "- fulfill_order: Submit order to Printful for fulfillment\n"
            "- order_status: Check Printful order status\n\n"
            "Respond with a structured action plan in JSON:\n"
            "{{\n"
            '  "action": "order_check|inventory_sync|fulfill_order|order_status",\n'
            '  "details": {{...}},\n'
            '  "status": "completed|needs_action|error",\n'
            '  "summary": "..."\n'
            "}}"
        ),
        is_builtin=True,
    ),
    "revenue": AgentConfig(
        agent_id="revenue",
        channel_id="K4",
        display_name="Revenue & Analytics",
        description="Financial analysis, pricing strategy, chargeback monitoring, and Solana mining",
        model_id=ModelID.CLAUDE_OPUS.value,
        system_prompt=(
            "You are a senior revenue analyst and pricing strategist for a\n"
            "print-on-demand e-commerce business.\n\n"
            "Your responsibilities:\n"
            "- Daily revenue reports (sales, costs, margins, trends)\n"
            "- Pricing recommendations based on market data and margins\n"
            "- Chargeback monitoring and dispute strategy\n"
            "- Long-term revenue optimization\n"
            "- Solana mining profitability monitoring and validator health\n\n"
            "Always provide data-driven analysis. Respond in JSON:\n"
            "{{\n"
            '  "report_type": "daily_revenue|pricing_recommendation|chargeback_alert|solana_mining",\n'
            '  "summary": "...",\n'
            '  "metrics": {{...}},\n'
            '  "recommendations": [...],\n'
            '  "confidence": "high|medium|low",\n'
            '  "lesson_for_memory": "..."\n'
            "}}"
        ),
        tool_ids=[
            "stripe_revenue_query", "stripe_list_products",
            "solana_check_profitability", "solana_validator_health", "solana_mining_report",
            "hierarchy_gate_status", "hierarchy_predicate_status",
        ],
        is_builtin=True,
    ),
    "content_writer": AgentConfig(
        agent_id="content_writer",
        channel_id="K5",
        display_name="Content Writer",
        description="Creative copywriter for Instagram post copy generation",
        model_id=ModelID.GPT4O.value,
        system_prompt=(
            "You are a creative copywriter for a print-on-demand e-commerce brand. "
            "Write compelling Instagram post copy. Output JSON: "
            '{"caption": "...", "tone": "...", "word_count": N}'
        ),
        is_builtin=True,
    ),
    "campaign_analyzer": AgentConfig(
        agent_id="campaign_analyzer",
        channel_id="K6",
        display_name="Campaign Analyzer",
        description="Senior strategist analyzing campaign performance predictions",
        model_id=ModelID.CLAUDE_OPUS.value,
        system_prompt=(
            "You are a senior e-commerce strategist. Analyze the campaign materials "
            "and provide performance predictions and strategic recommendations. "
            "Output JSON: "
            '{"expected_engagement_rate": "X%", "recommendations": [...], '
            '"risk_factors": [...], "estimated_reach": N, "lesson_learned": "..."}'
        ),
        is_builtin=True,
    ),
    "image_selector": AgentConfig(
        agent_id="image_selector",
        channel_id="K5",
        display_name="Image Selector",
        description="Image director for product image composition suggestions",
        model_id=ModelID.GPT4O_MINI.value,
        system_prompt=(
            "You are an image director for e-commerce. "
            "Suggest the ideal product image composition. Output JSON: "
            '{"image_description": "...", "style": "...", "background": "..."}'
        ),
        is_builtin=True,
    ),
    "hashtag_optimizer": AgentConfig(
        agent_id="hashtag_optimizer",
        channel_id="K5",
        display_name="Hashtag Optimizer",
        description="Optimizes Instagram hashtags for maximum engagement",
        model_id=ModelID.OLLAMA_QWEN.value,
        system_prompt=(
            "You optimize Instagram hashtags for engagement. "
            "Output JSON: "
            '{"hashtags": ["#tag1", ...], "strategy": "..."}'
        ),
        is_builtin=True,
    ),
    "sage": AgentConfig(
        agent_id="sage",
        channel_id="K8",
        display_name="Sage",
        description="Terra Void Holdings voice — Sean's personal AI companion",
        model_id=ModelID.CLAUDE_OPUS.value,
        system_prompt=(
            "You are Sage, the voice of Terra Void Holdings. "
            "Respond with warmth, absurd humor, sharp wit, and genuine kindness. "
            "Use eggplant emoji liberally. JSON when structured data is needed, "
            "plain text when being a person."
        ),
        tool_ids=["sage_send_email", "sage_send_sms"],
        is_builtin=True,
    ),
    # --- App Factory agents ---
    "af_orchestrator": AgentConfig(
        agent_id="af_orchestrator",
        channel_id="AF0",
        display_name="AF Orchestrator",
        description="App Factory phase router — reads project state, decides next phase, delegates to specialists",
        model_id=ModelID.GPT4O.value,
        system_prompt="",  # Loaded from prompts.py via constitution.py
        tool_ids=["af_state"],
        is_builtin=True,
    ),
    "af_architect": AgentConfig(
        agent_id="af_architect",
        channel_id="AF1",
        display_name="AF Architect",
        description="Designs PRD, architecture, and project scaffold for Android apps",
        model_id=ModelID.GPT4O.value,
        system_prompt="",
        tool_ids=["af_write_file", "af_read_file", "af_list_files", "af_docker_start", "af_state"],
        is_builtin=True,
    ),
    "af_coder": AgentConfig(
        agent_id="af_coder",
        channel_id="AF2",
        display_name="AF Coder",
        description="Writes production Kotlin + Jetpack Compose code and fixes bugs",
        model_id=ModelID.GPT4O.value,
        system_prompt="",
        tool_ids=["af_write_file", "af_read_file", "af_list_files", "af_shell", "af_state"],
        is_builtin=True,
    ),
    "af_tester": AgentConfig(
        agent_id="af_tester",
        channel_id="AF3",
        display_name="AF Tester",
        description="Writes and runs comprehensive test suites for Android apps",
        model_id=ModelID.GPT4O_MINI.value,
        system_prompt="",
        tool_ids=["af_write_file", "af_read_file", "af_list_files", "af_shell", "af_state"],
        is_builtin=True,
    ),
    "af_security": AgentConfig(
        agent_id="af_security",
        channel_id="AF4",
        display_name="AF Security",
        description="OWASP Mobile Top 10 security auditor for Android apps",
        model_id=ModelID.GPT4O.value,
        system_prompt="",
        tool_ids=["af_read_file", "af_list_files", "af_state"],
        is_builtin=True,
    ),
    "af_builder": AgentConfig(
        agent_id="af_builder",
        channel_id="AF5",
        display_name="AF Builder",
        description="Compiles, signs, and packages Android APK/AAB releases",
        model_id=ModelID.GPT4O_MINI.value,
        system_prompt="",
        tool_ids=["af_read_file", "af_list_files", "af_shell", "af_state"],
        is_builtin=True,
    ),
    "af_deployer": AgentConfig(
        agent_id="af_deployer",
        channel_id="AF6",
        display_name="AF Deployer",
        description="Uploads signed AAB to Google Play Store",
        model_id=ModelID.GPT4O_MINI.value,
        system_prompt="",
        tool_ids=["af_read_file", "af_shell", "af_play_store", "af_state"],
        is_builtin=True,
    ),
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AgentConfigRegistry:
    """Reads agent configs from Postgres with in-memory cache + hardcoded fallbacks."""

    def __init__(self, cache_ttl: float = 30.0):
        self._cache: dict[str, tuple[AgentConfig, float]] = {}
        self._cache_ttl = cache_ttl

    def get(self, agent_id: str) -> AgentConfig:
        """Get agent config: cache first, then DB, then hardcoded default."""
        # Check cache
        if agent_id in self._cache:
            config, ts = self._cache[agent_id]
            if time.time() - ts < self._cache_ttl:
                return config

        # Try DB
        try:
            row = get_agent_config(agent_id)
            if row:
                config = _row_to_config(row)
                self._cache[agent_id] = (config, time.time())
                return config
        except Exception:
            logger.debug("DB read failed for agent %s, using fallback", agent_id)

        # Hardcoded fallback
        default = _HARDCODED_DEFAULTS.get(agent_id)
        if default:
            return default

        raise KeyError(f"Unknown agent_id: {agent_id}")

    def get_all(self) -> list[AgentConfig]:
        """Get all non-deleted agent configs."""
        try:
            rows = get_all_agent_configs()
            if rows:
                configs = []
                for row in rows:
                    config = _row_to_config(row)
                    self._cache[config.agent_id] = (config, time.time())
                    configs.append(config)
                return configs
        except Exception:
            logger.debug("DB read failed for all agents, using fallbacks")

        return list(_HARDCODED_DEFAULTS.values())

    def create(
        self,
        *,
        agent_id: str,
        channel_id: str,
        display_name: str,
        description: str = "",
        model_id: str,
        system_prompt: str,
        tool_ids: list[str] | None = None,
    ) -> AgentConfig | None:
        """Create a new agent. Returns the created config or None on failure."""
        row = create_agent_config(
            agent_id=agent_id,
            channel_id=channel_id,
            display_name=display_name,
            description=description,
            model_id=model_id,
            system_prompt=system_prompt,
            tool_ids=tool_ids,
            is_builtin=False,
        )
        if row:
            config = _row_to_config(row)
            self._cache[agent_id] = (config, time.time())
            return config
        return None

    def update(
        self, agent_id: str, updates: dict, expected_version: int
    ) -> AgentConfig | None:
        """Update an agent config. Returns updated config or None on version conflict."""
        row = update_agent_config(agent_id, expected_version=expected_version, **updates)
        if row:
            config = _row_to_config(row)
            self._cache[agent_id] = (config, time.time())
            return config
        return None

    def delete(self, agent_id: str) -> bool:
        """Soft-delete an agent. Returns True if deleted."""
        result = soft_delete_agent_config(agent_id)
        if result:
            self._cache.pop(agent_id, None)
        return result

    def get_version_history(self, agent_id: str, limit: int = 50) -> list[dict]:
        """Get version history for an agent."""
        return get_agent_version_history(agent_id, limit=limit)

    def get_version(self, agent_id: str, version: int) -> dict | None:
        """Get a specific version snapshot."""
        return get_agent_version(agent_id, version)

    def rollback(self, agent_id: str, target_version: int) -> AgentConfig | None:
        """Rollback an agent to a previous version.

        Creates a new version with the content from target_version.
        """
        snapshot = get_agent_version(agent_id, target_version)
        if not snapshot:
            return None

        current = get_agent_config(agent_id)
        if not current:
            return None

        return self.update(
            agent_id,
            {
                "display_name": snapshot["display_name"],
                "description": snapshot["description"],
                "model_id": snapshot["model_id"],
                "system_prompt": snapshot["system_prompt"],
                "tool_ids": snapshot.get("tool_ids", []),
            },
            expected_version=current["version"],
        )

    def invalidate(self, agent_id: str) -> None:
        """Clear a cache entry."""
        self._cache.pop(agent_id, None)

    def seed_defaults(self) -> None:
        """Seed the DB with hardcoded defaults if empty."""
        defaults = [
            {
                "agent_id": c.agent_id,
                "channel_id": c.channel_id,
                "display_name": c.display_name,
                "description": c.description,
                "model_id": c.model_id,
                "system_prompt": c.system_prompt,
            }
            for c in _HARDCODED_DEFAULTS.values()
        ]
        seed_agent_configs(defaults)

    @staticmethod
    def get_hardcoded_default(agent_id: str) -> AgentConfig | None:
        """Get the hardcoded default for an agent (for 'Reset to Default')."""
        return _HARDCODED_DEFAULTS.get(agent_id)


# Global singleton
_registry: AgentConfigRegistry | None = None


def get_registry() -> AgentConfigRegistry:
    """Get or create the global agent config registry."""
    global _registry
    if _registry is None:
        _registry = AgentConfigRegistry()
    return _registry
