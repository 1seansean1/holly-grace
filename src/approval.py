"""Human-in-the-Loop approval gate for high-risk tool calls.

Risk classification:
- HIGH: stripe_create_payment_link, shopify_create_product (price > $100)
- MEDIUM: instagram_publish_post, stripe_create_product
- LOW: all read/query tools (auto-approved)
"""

from __future__ import annotations

import logging
from typing import Any

from src.aps.store import approval_create, approval_get

logger = logging.getLogger(__name__)

# Risk classification rules
_RISK_RULES: dict[str, str] = {
    # HIGH risk — always require approval
    "stripe_create_payment_link": "high",
    # MEDIUM risk — require approval
    "stripe_create_product": "medium",
    "instagram_publish_post": "medium",
    # Shopify create is HIGH by default, MEDIUM if price <= $100
    "shopify_create_product": "high",
    # App Factory: Play Store upload is HIGH risk (irreversible)
    "af_play_store": "high",
}

# Tools that are always safe (auto-approved)
_AUTO_APPROVED_TOOLS = {
    "stripe_list_products",
    "stripe_revenue_query",
    "shopify_query_products",
    "shopify_query_orders",
    "instagram_get_insights",
    "printful_list_catalog",
    "printful_list_products",
    "printful_get_store_products",
    "printful_order_status",
    # App Factory tools (sandboxed in Docker — safe)
    "af_write_file",
    "af_read_file",
    "af_list_files",
    "af_shell",
    "af_docker_start",
    "af_docker_stop",
    "af_state",
}


class ApprovalGate:
    """Determines if a tool call requires human approval and manages the flow."""

    @staticmethod
    def classify_risk(tool_name: str, params: dict[str, Any]) -> str:
        """Classify the risk level of a tool call.

        Returns: 'high', 'medium', or 'low'
        """
        if tool_name in _AUTO_APPROVED_TOOLS:
            return "low"

        # MCP tools default to medium unless explicitly configured otherwise.
        if tool_name.startswith("mcp_"):
            try:
                from src.mcp.store import get_tool

                row = get_tool(tool_name)
                risk = (row or {}).get("risk_level") or "medium"
                if risk not in ("low", "medium", "high"):
                    risk = "medium"
                return risk
            except Exception:
                return "medium"

        risk = _RISK_RULES.get(tool_name, "low")

        # Shopify: downgrade to medium if price <= $100
        if tool_name == "shopify_create_product":
            price_str = params.get("price", "0.00")
            try:
                if float(price_str) <= 100.0:
                    risk = "medium"
            except (ValueError, TypeError):
                pass

        return risk

    @staticmethod
    def requires_approval(tool_name: str, params: dict[str, Any]) -> bool:
        """Check if a tool call requires human approval.

        Low-risk tools are auto-approved. Medium and high risk require approval.
        """
        risk = ApprovalGate.classify_risk(tool_name, params)
        return risk != "low"

    @staticmethod
    def request_approval(
        tool_name: str,
        params: dict[str, Any],
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an approval request and return its status.

        Returns a dict with approval_id and status.
        """
        risk = ApprovalGate.classify_risk(tool_name, params)

        if risk == "low":
            return {"status": "auto_approved", "risk_level": "low"}

        approval_id = approval_create(
            action_type="tool_call",
            agent_id=agent_id,
            tool_name=tool_name,
            parameters=params,
            risk_level=risk,
        )

        if approval_id is None:
            logger.error("Failed to create approval request for %s", tool_name)
            return {"status": "error", "error": "Failed to create approval request"}

        logger.info(
            "Approval requested: id=%d tool=%s risk=%s",
            approval_id,
            tool_name,
            risk,
        )
        return {
            "status": "pending_approval",
            "approval_id": approval_id,
            "risk_level": risk,
            "tool_name": tool_name,
        }

    @staticmethod
    def check_approval(approval_id: int) -> str:
        """Check the current status of an approval request.

        Returns: 'pending', 'approved', 'rejected', or 'expired'
        """
        entry = approval_get(approval_id)
        if entry is None:
            return "not_found"
        return entry["status"]
