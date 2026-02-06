"""Tests for tool integrations (mocked external APIs)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestStripeTools:
    def test_get_stripe_tools_returns_list(self):
        from src.tools.stripe_tool import get_stripe_tools

        tools = get_stripe_tools()
        assert len(tools) == 4

    def test_stripe_tool_names(self):
        from src.tools.stripe_tool import get_stripe_tools

        tools = get_stripe_tools()
        names = {t.name for t in tools}
        assert "stripe_create_product" in names
        assert "stripe_create_payment_link" in names
        assert "stripe_revenue_query" in names
        assert "stripe_list_products" in names


class TestShopifyTools:
    def test_get_shopify_tools_returns_list(self):
        from src.tools.shopify_tool import get_shopify_tools

        tools = get_shopify_tools()
        assert len(tools) == 3

    def test_shopify_tool_names(self):
        from src.tools.shopify_tool import get_shopify_tools

        tools = get_shopify_tools()
        names = {t.name for t in tools}
        assert "shopify_query_products" in names
        assert "shopify_create_product" in names
        assert "shopify_query_orders" in names


class TestPrintfulTools:
    def test_get_printful_tools_returns_list(self):
        from src.tools.printful_tool import get_printful_tools

        tools = get_printful_tools()
        assert len(tools) == 4

    def test_printful_tool_names(self):
        from src.tools.printful_tool import get_printful_tools

        tools = get_printful_tools()
        names = {t.name for t in tools}
        assert "printful_list_catalog" in names
        assert "printful_order_status" in names


class TestInstagramTools:
    def test_get_instagram_tools_returns_list(self):
        from src.tools.instagram_tool import get_instagram_tools

        tools = get_instagram_tools()
        assert len(tools) == 2

    def test_instagram_tool_names(self):
        from src.tools.instagram_tool import get_instagram_tools

        tools = get_instagram_tools()
        names = {t.name for t in tools}
        assert "instagram_publish_post" in names
        assert "instagram_get_insights" in names

    def test_rate_limit_tracking(self):
        from src.tools.instagram_tool import _check_rate_limit, _post_timestamps

        _post_timestamps.clear()
        assert _check_rate_limit() is True


class TestMemoryTools:
    def test_get_memory_tools_returns_list(self):
        from src.tools.memory_tool import get_memory_tools

        tools = get_memory_tools()
        assert len(tools) == 2

    def test_memory_tool_names(self):
        from src.tools.memory_tool import get_memory_tools

        tools = get_memory_tools()
        names = {t.name for t in tools}
        assert "memory_store_decision" in names
        assert "memory_retrieve_similar" in names

    def test_valid_collections(self):
        from src.tools.memory_tool import COLLECTIONS

        assert "campaign_results" in COLLECTIONS
        assert "pricing_decisions" in COLLECTIONS
        assert "agent_lessons" in COLLECTIONS


class TestToolCount:
    def test_minimum_five_tools(self):
        """System requirement: at least 5 tool calls."""
        from src.tools.stripe_tool import get_stripe_tools
        from src.tools.shopify_tool import get_shopify_tools
        from src.tools.printful_tool import get_printful_tools
        from src.tools.instagram_tool import get_instagram_tools
        from src.tools.memory_tool import get_memory_tools

        total = (
            len(get_stripe_tools())
            + len(get_shopify_tools())
            + len(get_printful_tools())
            + len(get_instagram_tools())
            + len(get_memory_tools())
        )
        assert total >= 5, f"Need at least 5 tools, got {total}"
        # We have 4 + 3 + 4 + 2 + 2 = 15 tools
        assert total == 15
