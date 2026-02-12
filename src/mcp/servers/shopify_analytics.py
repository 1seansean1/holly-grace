"""Shopify Analytics MCP server — read-only Shopify store observability.

Stdio MCP server that exposes 4 tools:
- store_analytics: Total orders, revenue, AOV, product count
- product_performance: Per-product metrics (variants, inventory)
- order_trends: Daily order/revenue trends for a given time window
- customer_segments: New vs returning, by-country breakdown

Uses urllib.request (stdlib) — no external dependencies.
Runs as: python -m src.mcp.servers.shopify_analytics
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

# Defaults — configurable via env vars
_SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "liberty-forge-2")
_SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
_API_VERSION = "2024-01"


def _shopify_get(endpoint: str, params: str = "") -> Any:
    """Make a GET request to Shopify REST Admin API."""
    base = f"https://{_SHOPIFY_STORE}.myshopify.com/admin/api/{_API_VERSION}"
    url = f"{base}{endpoint}"
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{params}"

    req = urllib.request.Request(url)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Shopify-Access-Token", _SHOPIFY_TOKEN)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": body[:500]}
    except Exception as e:
        return {"error": str(e)}


def _shopify_get_paginated(endpoint: str, resource_key: str, params: str = "", max_pages: int = 5) -> list:
    """Fetch multiple pages of a Shopify resource using Link header pagination."""
    all_items: list = []
    base = f"https://{_SHOPIFY_STORE}.myshopify.com/admin/api/{_API_VERSION}"
    url = f"{base}{endpoint}"
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{params}"

    for _ in range(max_pages):
        req = urllib.request.Request(url)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Shopify-Access-Token", _SHOPIFY_TOKEN)

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get(resource_key, [])
                all_items.extend(items)

                # Check for next page via Link header
                link_header = resp.headers.get("Link", "")
                next_url = _parse_next_link(link_header)
                if not next_url or not items:
                    break
                url = next_url
        except Exception:
            break

    return all_items


def _parse_next_link(link_header: str) -> str | None:
    """Parse the 'next' URL from a Shopify Link header."""
    if not link_header:
        return None
    parts = link_header.split(",")
    for part in parts:
        segments = part.strip().split(";")
        if len(segments) >= 2 and 'rel="next"' in segments[1]:
            url = segments[0].strip().strip("<>")
            return url
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _store_analytics(args: dict) -> str:
    """Calculate store-wide analytics: total orders, revenue, AOV, product count."""
    try:
        if not _SHOPIFY_TOKEN:
            return json.dumps({"error": "SHOPIFY_ACCESS_TOKEN not configured"})

        # Fetch orders (up to 250, all statuses)
        orders = _shopify_get_paginated(
            "/orders.json?status=any&limit=250",
            "orders",
            max_pages=4,
        )

        if isinstance(orders, dict) and orders.get("error"):
            return json.dumps(orders)

        # Calculate order metrics
        total_orders = len(orders)
        total_revenue = 0.0
        currency = "USD"
        for order in orders:
            try:
                total_revenue += float(order.get("total_price", 0))
            except (ValueError, TypeError):
                pass
            if order.get("currency"):
                currency = order["currency"]

        avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

        # Fetch product count
        product_count_data = _shopify_get("/products/count.json")
        product_count = 0
        if isinstance(product_count_data, dict) and not product_count_data.get("error"):
            product_count = product_count_data.get("count", 0)

        result = {
            "store": _SHOPIFY_STORE,
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "average_order_value": avg_order_value,
            "currency": currency,
            "product_count": product_count,
            "note": f"Based on up to 1000 most recent orders",
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"store_analytics failed: {str(e)}"})


def _product_performance(args: dict) -> str:
    """Per-product metrics: title, variants, inventory levels."""
    try:
        if not _SHOPIFY_TOKEN:
            return json.dumps({"error": "SHOPIFY_ACCESS_TOKEN not configured"})

        limit = int(args.get("limit", 50))

        products_data = _shopify_get(f"/products.json?limit={min(limit, 250)}")
        if isinstance(products_data, dict) and products_data.get("error"):
            return json.dumps(products_data)

        products = products_data.get("products", [])
        product_metrics = []
        for p in products:
            variants = p.get("variants", [])
            total_inventory = 0
            variant_info = []
            for v in variants:
                qty = v.get("inventory_quantity", 0)
                total_inventory += qty
                variant_info.append({
                    "title": v.get("title", "Default"),
                    "price": v.get("price", "0.00"),
                    "inventory_quantity": qty,
                    "sku": v.get("sku", ""),
                })

            product_metrics.append({
                "id": p.get("id"),
                "title": p.get("title", ""),
                "status": p.get("status", ""),
                "product_type": p.get("product_type", ""),
                "vendor": p.get("vendor", ""),
                "created_at": p.get("created_at", ""),
                "variant_count": len(variants),
                "total_inventory": total_inventory,
                "variants": variant_info,
                "tags": p.get("tags", ""),
                "image_count": len(p.get("images", [])),
            })

        result = {
            "store": _SHOPIFY_STORE,
            "product_count": len(product_metrics),
            "products": product_metrics,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"product_performance failed: {str(e)}"})


def _order_trends(args: dict) -> str:
    """Daily order and revenue trends over a time window."""
    try:
        if not _SHOPIFY_TOKEN:
            return json.dumps({"error": "SHOPIFY_ACCESS_TOKEN not configured"})

        days = int(args.get("days", 30))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%S%z")

        # Fetch orders from the time window
        orders = _shopify_get_paginated(
            f"/orders.json?created_at_min={cutoff_iso}&status=any&limit=250",
            "orders",
            max_pages=4,
        )

        if isinstance(orders, dict) and orders.get("error"):
            return json.dumps(orders)

        # Group by date
        daily: dict[str, dict] = {}
        currency = "USD"
        for order in orders:
            created = order.get("created_at", "")
            if not created:
                continue
            date_str = created[:10]  # YYYY-MM-DD
            if date_str not in daily:
                daily[date_str] = {"date": date_str, "orders": 0, "revenue": 0.0}
            daily[date_str]["orders"] += 1
            try:
                daily[date_str]["revenue"] += float(order.get("total_price", 0))
            except (ValueError, TypeError):
                pass
            if order.get("currency"):
                currency = order["currency"]

        # Sort by date
        trend = sorted(daily.values(), key=lambda d: d["date"])
        for day in trend:
            day["revenue"] = round(day["revenue"], 2)

        total_orders = sum(d["orders"] for d in trend)
        total_revenue = round(sum(d["revenue"] for d in trend), 2)

        result = {
            "store": _SHOPIFY_STORE,
            "days": days,
            "start_date": cutoff.strftime("%Y-%m-%d"),
            "end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "currency": currency,
            "daily_trend": trend,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"order_trends failed: {str(e)}"})


def _customer_segments(args: dict) -> str:
    """Customer segmentation: new vs returning, by country."""
    try:
        if not _SHOPIFY_TOKEN:
            return json.dumps({"error": "SHOPIFY_ACCESS_TOKEN not configured"})

        limit = int(args.get("limit", 250))

        customers = _shopify_get_paginated(
            f"/customers.json?limit={min(limit, 250)}",
            "customers",
            max_pages=4,
        )

        if isinstance(customers, dict) and customers.get("error"):
            return json.dumps(customers)

        total = len(customers)
        new_customers = 0
        returning_customers = 0
        by_country: dict[str, int] = {}
        total_spend = 0.0

        for c in customers:
            orders_count = c.get("orders_count", 0)
            if orders_count <= 1:
                new_customers += 1
            else:
                returning_customers += 1

            # Total spend
            try:
                total_spend += float(c.get("total_spent", 0))
            except (ValueError, TypeError):
                pass

            # Country from default address
            addr = c.get("default_address") or {}
            country = addr.get("country", "Unknown") or "Unknown"
            by_country[country] = by_country.get(country, 0) + 1

        # Sort countries by count
        country_breakdown = sorted(
            [{"country": k, "customers": v} for k, v in by_country.items()],
            key=lambda x: x["customers"],
            reverse=True,
        )

        result = {
            "store": _SHOPIFY_STORE,
            "total_customers": total,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "returning_rate": round(returning_customers / total * 100, 1) if total > 0 else 0.0,
            "total_lifetime_spend": round(total_spend, 2),
            "avg_lifetime_value": round(total_spend / total, 2) if total > 0 else 0.0,
            "by_country": country_breakdown,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"customer_segments failed: {str(e)}"})


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "store_analytics",
        "description": "Store-wide analytics: total orders, total revenue, average order value, product count.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "product_performance",
        "description": "Per-product performance metrics: title, variants, inventory levels, status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max products to return (default: 50, max: 250)"},
            },
        },
    },
    {
        "name": "order_trends",
        "description": "Daily order and revenue trends over a time window. Groups orders by day.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to look back (default: 30)"},
            },
        },
    },
    {
        "name": "customer_segments",
        "description": "Customer segmentation: new vs returning customers, country breakdown, lifetime value.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max customers to analyze (default: 250)"},
            },
        },
    },
]

_TOOL_DISPATCH = {
    "store_analytics": _store_analytics,
    "product_performance": _product_performance,
    "order_trends": _order_trends,
    "customer_segments": _customer_segments,
}


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications (no id) — ignore
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(req_id, {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "shopify-analytics", "version": "1.0.0"},
            })
            continue

        if method == "ping":
            _result(req_id, {})
            continue

        if method == "tools/list":
            _result(req_id, {"tools": _TOOLS})
            continue

        if method == "tools/call":
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments") or {}
            handler = _TOOL_DISPATCH.get(name)
            if not handler:
                _error(req_id, -32601, f"Unknown tool: {name}")
                continue
            try:
                text = handler(arguments if isinstance(arguments, dict) else {})
            except Exception as e:
                text = json.dumps({"error": str(e)})
            _result(req_id, {"content": [{"type": "text", "text": text}]})
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
