"""Tests for the Shopify Analytics MCP server.

Covers: _parse_next_link, _store_analytics, _product_performance,
_order_trends, _customer_segments, token-missing error paths,
and MCP stdio JSON-RPC protocol (initialize, tools/list, tools/call, ping,
unknown tool, unknown method).
"""

from __future__ import annotations

import json
import unittest
from io import StringIO
from unittest.mock import patch

from src.mcp.servers.shopify_analytics import (
    _customer_segments,
    _order_trends,
    _parse_next_link,
    _product_performance,
    _store_analytics,
    main,
)


# ---------------------------------------------------------------------------
# Helpers — reusable mock data
# ---------------------------------------------------------------------------

def _make_order(order_id: int, total_price: str, created_at: str, currency: str = "USD") -> dict:
    return {
        "id": order_id,
        "total_price": total_price,
        "created_at": created_at,
        "currency": currency,
    }


def _make_product(product_id: int, title: str, variants: list[dict] | None = None,
                  images: list | None = None, status: str = "active") -> dict:
    return {
        "id": product_id,
        "title": title,
        "status": status,
        "product_type": "Apparel",
        "vendor": "TestVendor",
        "created_at": "2025-01-01T00:00:00-05:00",
        "variants": variants or [],
        "tags": "test",
        "images": images or [],
    }


def _make_variant(title: str = "Default", price: str = "29.99",
                  inventory_quantity: int = 10, sku: str = "SKU-001") -> dict:
    return {
        "title": title,
        "price": price,
        "inventory_quantity": inventory_quantity,
        "sku": sku,
    }


def _make_customer(customer_id: int, orders_count: int, total_spent: str,
                   country: str | None = "United States") -> dict:
    addr = {"country": country} if country is not None else None
    return {
        "id": customer_id,
        "orders_count": orders_count,
        "total_spent": total_spent,
        "default_address": addr,
    }


# ---------------------------------------------------------------------------
# 1. _parse_next_link
# ---------------------------------------------------------------------------

class TestParseNextLink(unittest.TestCase):
    """Tests for Shopify Link header parsing."""

    def test_finds_next_url(self):
        header = '<https://shop.myshopify.com/admin/api/2024-01/orders.json?page_info=abc>; rel="next"'
        result = _parse_next_link(header)
        self.assertEqual(result, "https://shop.myshopify.com/admin/api/2024-01/orders.json?page_info=abc")

    def test_returns_none_for_empty_header(self):
        self.assertIsNone(_parse_next_link(""))

    def test_handles_multiple_rels(self):
        header = (
            '<https://shop.myshopify.com/page1>; rel="previous", '
            '<https://shop.myshopify.com/page3>; rel="next"'
        )
        result = _parse_next_link(header)
        self.assertEqual(result, "https://shop.myshopify.com/page3")

    def test_returns_none_when_no_next_rel(self):
        header = '<https://shop.myshopify.com/page1>; rel="previous"'
        self.assertIsNone(_parse_next_link(header))


# ---------------------------------------------------------------------------
# 2. _store_analytics
# ---------------------------------------------------------------------------

class TestStoreAnalytics(unittest.TestCase):
    """Tests for the store_analytics tool."""

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_happy_path(self, mock_paginated, mock_get):
        mock_paginated.return_value = [
            _make_order(1, "49.99", "2025-06-01T12:00:00-05:00"),
            _make_order(2, "100.01", "2025-06-02T12:00:00-05:00"),
        ]
        mock_get.return_value = {"count": 5}

        result = json.loads(_store_analytics({}))

        self.assertEqual(result["total_orders"], 2)
        self.assertAlmostEqual(result["total_revenue"], 150.00, places=2)
        self.assertAlmostEqual(result["average_order_value"], 75.00, places=2)
        self.assertEqual(result["product_count"], 5)
        self.assertEqual(result["currency"], "USD")

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_empty_orders(self, mock_paginated, mock_get):
        mock_paginated.return_value = []
        mock_get.return_value = {"count": 3}

        result = json.loads(_store_analytics({}))

        self.assertEqual(result["total_orders"], 0)
        self.assertEqual(result["total_revenue"], 0.0)
        self.assertEqual(result["average_order_value"], 0.0)
        self.assertEqual(result["product_count"], 3)

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "")
    def test_missing_token(self):
        result = json.loads(_store_analytics({}))
        self.assertIn("error", result)
        self.assertIn("SHOPIFY_ACCESS_TOKEN", result["error"])


# ---------------------------------------------------------------------------
# 3. _product_performance
# ---------------------------------------------------------------------------

class TestProductPerformance(unittest.TestCase):
    """Tests for the product_performance tool."""

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get")
    def test_happy_path(self, mock_get):
        variants = [
            _make_variant("Small", "19.99", 5, "SKU-S"),
            _make_variant("Large", "24.99", 15, "SKU-L"),
        ]
        mock_get.return_value = {
            "products": [
                _make_product(101, "Cool T-Shirt", variants=variants, images=[{"id": 1}]),
                _make_product(102, "Cap", variants=[_make_variant()]),
            ]
        }

        result = json.loads(_product_performance({}))

        self.assertEqual(result["product_count"], 2)
        shirt = result["products"][0]
        self.assertEqual(shirt["title"], "Cool T-Shirt")
        self.assertEqual(shirt["variant_count"], 2)
        self.assertEqual(shirt["total_inventory"], 20)  # 5 + 15
        self.assertEqual(shirt["image_count"], 1)
        self.assertEqual(len(shirt["variants"]), 2)
        self.assertEqual(shirt["variants"][0]["sku"], "SKU-S")

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get")
    def test_respects_limit(self, mock_get):
        """Verify the limit arg is forwarded to the API URL."""
        mock_get.return_value = {"products": []}

        _product_performance({"limit": 10})

        call_url = mock_get.call_args[0][0]
        self.assertIn("limit=10", call_url)

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "")
    def test_missing_token(self):
        result = json.loads(_product_performance({}))
        self.assertIn("error", result)
        self.assertIn("SHOPIFY_ACCESS_TOKEN", result["error"])


# ---------------------------------------------------------------------------
# 4. _order_trends
# ---------------------------------------------------------------------------

class TestOrderTrends(unittest.TestCase):
    """Tests for the order_trends tool."""

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_happy_path_grouping(self, mock_paginated):
        mock_paginated.return_value = [
            _make_order(1, "30.00", "2025-06-01T08:00:00-05:00"),
            _make_order(2, "20.00", "2025-06-01T14:00:00-05:00"),
            _make_order(3, "50.00", "2025-06-02T10:00:00-05:00"),
        ]

        result = json.loads(_order_trends({"days": 7}))

        self.assertEqual(result["total_orders"], 3)
        self.assertAlmostEqual(result["total_revenue"], 100.00, places=2)
        self.assertEqual(len(result["daily_trend"]), 2)

        # Day 1: two orders totalling 50.00
        day1 = result["daily_trend"][0]
        self.assertEqual(day1["date"], "2025-06-01")
        self.assertEqual(day1["orders"], 2)
        self.assertAlmostEqual(day1["revenue"], 50.00, places=2)

        # Day 2: one order at 50.00
        day2 = result["daily_trend"][1]
        self.assertEqual(day2["date"], "2025-06-02")
        self.assertEqual(day2["orders"], 1)
        self.assertAlmostEqual(day2["revenue"], 50.00, places=2)

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "")
    def test_missing_token(self):
        result = json.loads(_order_trends({}))
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# 5. _customer_segments
# ---------------------------------------------------------------------------

class TestCustomerSegments(unittest.TestCase):
    """Tests for the customer_segments tool."""

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_happy_path(self, mock_paginated):
        mock_paginated.return_value = [
            _make_customer(1, orders_count=1, total_spent="50.00", country="United States"),
            _make_customer(2, orders_count=3, total_spent="200.00", country="United States"),
            _make_customer(3, orders_count=0, total_spent="0.00", country="Canada"),
            _make_customer(4, orders_count=5, total_spent="750.00", country="Canada"),
        ]

        result = json.loads(_customer_segments({}))

        self.assertEqual(result["total_customers"], 4)
        # New: orders_count <= 1 (customers 1 and 3)
        self.assertEqual(result["new_customers"], 2)
        # Returning: orders_count > 1 (customers 2 and 4)
        self.assertEqual(result["returning_customers"], 2)
        # Returning rate: 2/4 * 100 = 50.0
        self.assertAlmostEqual(result["returning_rate"], 50.0, places=1)
        # Total spend: 50 + 200 + 0 + 750 = 1000
        self.assertAlmostEqual(result["total_lifetime_spend"], 1000.00, places=2)
        # Avg lifetime value: 1000 / 4 = 250
        self.assertAlmostEqual(result["avg_lifetime_value"], 250.00, places=2)

        # Country breakdown — sorted descending by count
        countries = result["by_country"]
        self.assertEqual(len(countries), 2)
        self.assertEqual(countries[0]["country"], "United States")
        self.assertEqual(countries[0]["customers"], 2)
        self.assertEqual(countries[1]["country"], "Canada")
        self.assertEqual(countries[1]["customers"], 2)

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_customer_without_address(self, mock_paginated):
        """Customer with no default_address should map to 'Unknown' country."""
        mock_paginated.return_value = [
            {"id": 10, "orders_count": 2, "total_spent": "100.00", "default_address": None},
        ]

        result = json.loads(_customer_segments({}))

        self.assertEqual(result["by_country"][0]["country"], "Unknown")

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "")
    def test_missing_token(self):
        result = json.loads(_customer_segments({}))
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# 6. Token missing — all tools return error
# ---------------------------------------------------------------------------

class TestTokenMissing(unittest.TestCase):
    """All 4 tools should return an error dict when SHOPIFY_ACCESS_TOKEN is empty."""

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "")
    def test_all_tools_error_without_token(self):
        for tool_fn in (_store_analytics, _product_performance, _order_trends, _customer_segments):
            with self.subTest(tool=tool_fn.__name__):
                result = json.loads(tool_fn({}))
                self.assertIn("error", result)
                self.assertIn("SHOPIFY_ACCESS_TOKEN", result["error"])


# ---------------------------------------------------------------------------
# 7. MCP stdio protocol
# ---------------------------------------------------------------------------

def _run_mcp_session(messages: list[dict]) -> list[dict]:
    """Feed JSON-RPC messages into main() and collect stdout responses."""
    stdin_text = "\n".join(json.dumps(m) for m in messages) + "\n"
    responses: list[dict] = []
    with patch("sys.stdin", StringIO(stdin_text)):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            main()
            for line in mock_stdout.getvalue().strip().split("\n"):
                if line.strip():
                    responses.append(json.loads(line))
    return responses


class TestMCPProtocol(unittest.TestCase):
    """Tests for the MCP stdio JSON-RPC protocol handler."""

    def test_initialize_response(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        resp = responses[0]
        self.assertEqual(resp["id"], 1)
        result = resp["result"]
        self.assertEqual(result["protocolVersion"], "2025-11-25")
        self.assertEqual(result["serverInfo"]["name"], "shopify-analytics")
        self.assertIn("tools", result["capabilities"])

    def test_tools_list_returns_4_tools(self):
        msgs = [{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        tools = responses[0]["result"]["tools"]
        self.assertEqual(len(tools), 4)
        tool_names = {t["name"] for t in tools}
        self.assertEqual(tool_names, {"store_analytics", "product_performance", "order_trends", "customer_segments"})

    @patch("src.mcp.servers.shopify_analytics._SHOPIFY_TOKEN", "shpat_test_token")
    @patch("src.mcp.servers.shopify_analytics._shopify_get")
    @patch("src.mcp.servers.shopify_analytics._shopify_get_paginated")
    def test_tools_call_dispatches(self, mock_paginated, mock_get):
        """tools/call should dispatch to the handler and return content."""
        mock_paginated.return_value = [_make_order(1, "25.00", "2025-06-01T00:00:00Z")]
        mock_get.return_value = {"count": 1}

        msgs = [{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "store_analytics", "arguments": {}}}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        content = responses[0]["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        payload = json.loads(content[0]["text"])
        self.assertEqual(payload["total_orders"], 1)

    def test_tools_call_unknown_tool_error(self):
        msgs = [{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": "nonexistent_tool", "arguments": {}}}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertIn("nonexistent_tool", responses[0]["error"]["message"])

    def test_ping(self):
        msgs = [{"jsonrpc": "2.0", "id": 5, "method": "ping"}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 5)
        self.assertEqual(responses[0]["result"], {})

    def test_unknown_method_error(self):
        msgs = [{"jsonrpc": "2.0", "id": 6, "method": "resources/list"}]
        responses = _run_mcp_session(msgs)

        self.assertEqual(len(responses), 1)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertIn("resources/list", responses[0]["error"]["message"])

    def test_notification_without_id_is_ignored(self):
        """Messages without an 'id' field are notifications and produce no response."""
        msgs = [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
        responses = _run_mcp_session(msgs)
        self.assertEqual(len(responses), 0)


if __name__ == "__main__":
    unittest.main()
