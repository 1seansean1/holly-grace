"""Printful REST API tool.

Wraps the Printful API for catalog browsing, product creation, and order management.
API base: https://api.printful.com
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PRINTFUL_BASE = "https://api.printful.com"


def _printful_request(method: str, path: str, json_body: dict | None = None) -> dict:
    """Make an authenticated Printful API request."""
    api_key = os.environ.get("PRINTFUL_API_KEY", "")

    response = httpx.request(
        method,
        f"{PRINTFUL_BASE}{path}",
        json=json_body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


@tool
def printful_list_catalog() -> dict:
    """List available product categories from Printful catalog."""
    result = _printful_request("GET", "/catalog/categories")
    categories = result.get("result", [])[:20]  # Limit for brevity

    return {
        "count": len(categories),
        "categories": [
            {"id": c["id"], "title": c["title"]} for c in categories
        ],
    }


class CatalogProductsInput(BaseModel):
    category_id: int = Field(description="Printful catalog category ID")


@tool(args_schema=CatalogProductsInput)
def printful_list_products(category_id: int) -> dict:
    """List products in a Printful catalog category."""
    result = _printful_request("GET", f"/catalog/categories/{category_id}")
    products = result.get("result", {}).get("products", [])[:20]

    return {
        "count": len(products),
        "products": [
            {"id": p["id"], "title": p["title"], "type": p.get("type", "")}
            for p in products
        ],
    }


@tool
def printful_get_store_products() -> dict:
    """List products in the connected Printful store."""
    result = _printful_request("GET", "/store/products?limit=20")
    products = result.get("result", [])

    return {
        "count": len(products),
        "products": [
            {
                "id": p["id"],
                "external_id": p.get("external_id"),
                "name": p["name"],
                "synced": p["synced"],
                "variants": p.get("variants", 0),
            }
            for p in products
        ],
    }


class OrderStatusInput(BaseModel):
    order_id: int = Field(description="Printful order ID")


@tool(args_schema=OrderStatusInput)
def printful_order_status(order_id: int) -> dict:
    """Check the status of a Printful order."""
    result = _printful_request("GET", f"/orders/{order_id}")
    order = result.get("result", {})

    return {
        "id": order.get("id"),
        "status": order.get("status"),
        "created": order.get("created"),
        "shipping": order.get("shipping_service_name"),
        "items": len(order.get("items", [])),
    }


def get_printful_tools() -> list:
    """Return all Printful tools for agent use."""
    return [
        printful_list_catalog,
        printful_list_products,
        printful_get_store_products,
        printful_order_status,
    ]
