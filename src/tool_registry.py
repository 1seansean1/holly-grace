"""Tool Registry: discovers and indexes all @tool functions from src/tools/.

Provides runtime lookup for tool assignment to agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""

    tool_id: str
    display_name: str
    description: str
    module_path: str
    function_name: str
    category: str
    # Provider metadata
    provider: str = "python"  # "python" | "mcp"
    server_id: str | None = None
    mcp_tool_name: str | None = None
    transport: str | None = None
    input_schema: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Tool discovery — statically defined for reliability
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS: list[ToolDefinition] = [
    # Shopify
    ToolDefinition("shopify_query_products", "Query Products", "Query products from Shopify store", "src.tools.shopify_tool", "shopify_query_products", "shopify"),
    ToolDefinition("shopify_create_product", "Create Product", "Create a new product in Shopify", "src.tools.shopify_tool", "shopify_create_product", "shopify"),
    ToolDefinition("shopify_query_orders", "Query Orders", "Query recent orders from Shopify", "src.tools.shopify_tool", "shopify_query_orders", "shopify"),
    # Stripe
    ToolDefinition("stripe_create_product", "Create Product", "Create a product and price in Stripe", "src.tools.stripe_tool", "stripe_create_product", "stripe"),
    ToolDefinition("stripe_create_payment_link", "Create Payment Link", "Create a Stripe payment link for a price", "src.tools.stripe_tool", "stripe_create_payment_link", "stripe"),
    ToolDefinition("stripe_revenue_query", "Revenue Query", "Query recent revenue data from Stripe", "src.tools.stripe_tool", "stripe_revenue_query", "stripe"),
    ToolDefinition("stripe_list_products", "List Products", "List active products in Stripe", "src.tools.stripe_tool", "stripe_list_products", "stripe"),
    # Printful
    ToolDefinition("printful_list_catalog", "List Catalog", "List available product categories from Printful catalog", "src.tools.printful_tool", "printful_list_catalog", "printful"),
    ToolDefinition("printful_list_products", "List Products", "List products in a Printful catalog category", "src.tools.printful_tool", "printful_list_products", "printful"),
    ToolDefinition("printful_get_store_products", "Store Products", "List products in the connected Printful store", "src.tools.printful_tool", "printful_get_store_products", "printful"),
    ToolDefinition("printful_order_status", "Order Status", "Check the status of a Printful order", "src.tools.printful_tool", "printful_order_status", "printful"),
    # Instagram
    ToolDefinition("instagram_publish_post", "Publish Post", "Publish an image post to Instagram", "src.tools.instagram_tool", "instagram_publish_post", "instagram"),
    ToolDefinition("instagram_get_insights", "Get Insights", "Get basic Instagram account insights", "src.tools.instagram_tool", "instagram_get_insights", "instagram"),
    # Memory
    ToolDefinition("memory_store_decision", "Store Decision", "Store a decision or lesson in long-term vector memory", "src.tools.memory_tool", "memory_store_decision", "memory"),
    ToolDefinition("memory_retrieve_similar", "Retrieve Similar", "Retrieve semantically similar decisions from long-term memory", "src.tools.memory_tool", "memory_retrieve_similar", "memory"),
    # Sage communication
    ToolDefinition("sage_send_email", "Send Email", "Send an email via Gmail SMTP", "src.tools.email_tool", "sage_send_email", "sage"),
    ToolDefinition("sage_send_sms", "Send SMS", "Send SMS to Sean via email-to-SMS gateway", "src.tools.sms_tool", "sage_send_sms", "sage"),
    # App Factory
    ToolDefinition("af_write_file", "Write File", "Write a file to the project workspace", "src.tools.app_factory_tools", "af_write_file", "app_factory"),
    ToolDefinition("af_read_file", "Read File", "Read a file from the project workspace", "src.tools.app_factory_tools", "af_read_file", "app_factory"),
    ToolDefinition("af_list_files", "List Files", "List files in the project workspace", "src.tools.app_factory_tools", "af_list_files", "app_factory"),
    ToolDefinition("af_shell", "Shell Exec", "Execute a whitelisted shell command in Docker", "src.tools.app_factory_tools", "af_shell", "app_factory"),
    ToolDefinition("af_docker_start", "Docker Start", "Start Android builder and create workspace", "src.tools.app_factory_tools", "af_docker_start", "app_factory"),
    ToolDefinition("af_docker_stop", "Docker Stop", "Clean up project workspace", "src.tools.app_factory_tools", "af_docker_stop", "app_factory"),
    ToolDefinition("af_play_store", "Play Store", "Upload AAB to Google Play Store (high risk)", "src.tools.app_factory_tools", "af_play_store", "app_factory"),
    ToolDefinition("af_state", "Project State", "Read/update App Factory project state", "src.tools.app_factory_tools", "af_state", "app_factory"),
    # Goal Hierarchy (read-only)
    ToolDefinition("hierarchy_gate_status", "Gate Status", "Check if the lexicographic gate is open at a given level", "src.tools.hierarchy_tool", "hierarchy_gate_status", "hierarchy"),
    ToolDefinition("hierarchy_feasibility_check", "Feasibility Check", "Run full feasibility verification (Statement 55)", "src.tools.hierarchy_tool", "hierarchy_feasibility_check", "hierarchy"),
    ToolDefinition("hierarchy_predicate_status", "Predicate Status", "Get current status of one or all predicates", "src.tools.hierarchy_tool", "hierarchy_predicate_status", "hierarchy"),
    ToolDefinition("hierarchy_eigenspectrum", "Eigenspectrum", "Get eigenspectrum decomposition with cod(G)", "src.tools.hierarchy_tool", "hierarchy_eigenspectrum", "hierarchy"),
    ToolDefinition("hierarchy_module_list", "Module List", "List all Terrestrial modules with status", "src.tools.hierarchy_tool", "hierarchy_module_list", "hierarchy"),
    ToolDefinition("hierarchy_upward_coupling_budget", "Coupling Budget", "Check upward coupling budget and O3 rank", "src.tools.hierarchy_tool", "hierarchy_upward_coupling_budget", "hierarchy"),
    # Solana Mining (read-only)
    ToolDefinition("solana_check_profitability", "SOL Profitability", "Check Solana mining/staking profitability and ROI", "src.tools.solana_tool", "solana_check_profitability", "solana"),
    ToolDefinition("solana_validator_health", "SOL Validator Health", "Check Solana validator uptime, skip rate, and delinquency", "src.tools.solana_tool", "solana_validator_health", "solana"),
    ToolDefinition("solana_mining_report", "SOL Mining Report", "Generate comprehensive mining report with profitability, health, and gate status", "src.tools.solana_tool", "solana_mining_report", "solana"),
]

# Lazy-loaded tool instances keyed by tool_id
_tool_instances: dict[str, BaseTool] = {}


def _load_tool_instance(defn: ToolDefinition) -> BaseTool:
    """Import and return the actual tool function."""
    if defn.provider == "mcp":
        from src.mcp.tool_adapter import build_mcp_tool

        if not defn.server_id or not defn.mcp_tool_name:
            raise ValueError(f"Invalid MCP tool definition: {defn.tool_id}")
        return build_mcp_tool(
            tool_id=defn.tool_id,
            server_id=defn.server_id,
            mcp_tool_name=defn.mcp_tool_name,
            description=defn.description,
            input_schema=defn.input_schema,
        )

    import importlib

    module = importlib.import_module(defn.module_path)
    return getattr(module, defn.function_name)


class ToolRegistry:
    """Registry of all available tools for agent binding."""

    def __init__(self, *, mcp_cache_ttl_s: float = 5.0) -> None:
        self._static_definitions = {t.tool_id: t for t in _TOOL_DEFINITIONS}
        self._mcp_cache_ttl_s = float(mcp_cache_ttl_s)
        self._mcp_cached_at = 0.0
        self._mcp_definitions: dict[str, ToolDefinition] = {}

    def _load_mcp_definitions(self) -> dict[str, ToolDefinition]:
        import time

        now = time.time()
        if self._mcp_definitions and (now - self._mcp_cached_at) < self._mcp_cache_ttl_s:
            return self._mcp_definitions

        try:
            from src.mcp.store import list_enabled_tools

            defs: dict[str, ToolDefinition] = {}
            for row in list_enabled_tools():
                tool_id = row.get("tool_id")
                if not tool_id:
                    continue

                input_schema = row.get("input_schema") or {}
                if isinstance(input_schema, str):
                    import json

                    try:
                        input_schema = json.loads(input_schema)
                    except Exception:
                        input_schema = {}

                defs[str(tool_id)] = ToolDefinition(
                    tool_id=str(tool_id),
                    display_name=str(row.get("display_name") or tool_id),
                    description=str(row.get("description") or ""),
                    module_path="",
                    function_name="",
                    category=str(row.get("category") or "mcp"),
                    provider="mcp",
                    server_id=str(row["server_id"]) if row.get("server_id") else None,
                    mcp_tool_name=str(row["mcp_tool_name"]) if row.get("mcp_tool_name") else None,
                    transport=str(row["transport"]) if row.get("transport") else None,
                    input_schema=input_schema if isinstance(input_schema, dict) else {},
                )

            self._mcp_definitions = defs
            self._mcp_cached_at = now
            return defs
        except Exception:
            # DB might be unavailable; fail open to built-in tools.
            self._mcp_definitions = {}
            self._mcp_cached_at = now
            return {}

    def _definitions(self) -> dict[str, ToolDefinition]:
        mcp_defs = self._load_mcp_definitions()
        return {**self._static_definitions, **mcp_defs}

    def get_all(self) -> list[ToolDefinition]:
        """Get all tool definitions."""
        return list(self._definitions().values())

    def get(self, tool_id: str) -> ToolDefinition | None:
        """Get a single tool definition."""
        return self._definitions().get(tool_id)

    def get_tools_for_agent(self, tool_ids: list[str]) -> list[BaseTool]:
        """Load and return actual tool instances for a list of tool_ids."""
        tools = []
        for tid in tool_ids:
            if tid in _tool_instances:
                tools.append(_tool_instances[tid])
                continue
            defn = self.get(tid)
            if defn:
                try:
                    instance = _load_tool_instance(defn)
                    _tool_instances[tid] = instance
                    tools.append(instance)
                except Exception:
                    logger.warning("Failed to load tool %s", tid, exc_info=True)
        return tools

    def seed_to_db(self) -> None:
        """Seed all tool definitions into the Postgres tool_registry table."""
        from src.aps.store import seed_tool_registry

        rows = [
            {
                "tool_id": t.tool_id,
                "display_name": t.display_name,
                "description": t.description,
                "module_path": t.module_path,
                "function_name": t.function_name,
                "category": t.category,
            }
            for t in self._static_definitions.values()
        ]
        seed_tool_registry(rows)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialize all definitions to dicts."""
        return [
            {
                "tool_id": t.tool_id,
                "display_name": t.display_name,
                "description": t.description,
                "module_path": t.module_path,
                "function_name": t.function_name,
                "category": t.category,
                "provider": t.provider,
                "server_id": t.server_id,
                "mcp_tool_name": t.mcp_tool_name,
                "transport": t.transport,
            }
            for t in self._definitions().values()
        ]


# Global singleton
_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
