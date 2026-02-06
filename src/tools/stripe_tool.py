"""Stripe tool: payment processing, product creation, revenue queries.

Uses stripe-agent-toolkit for LangChain-native tools plus custom revenue queries.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import stripe
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _get_stripe_client() -> stripe.StripeClient:
    """Get a configured Stripe client."""
    api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    return stripe.StripeClient(api_key=api_key)


class CreateProductInput(BaseModel):
    name: str = Field(description="Product name")
    description: str = Field(default="", description="Product description")
    price_cents: int = Field(description="Price in cents (e.g., 2999 for $29.99)")


@tool(args_schema=CreateProductInput)
def stripe_create_product(name: str, description: str = "", price_cents: int = 0) -> dict:
    """Create a product and price in Stripe."""
    client = _get_stripe_client()

    product = client.products.create(params={"name": name, "description": description})

    price = None
    if price_cents > 0:
        price = client.prices.create(
            params={
                "product": product.id,
                "unit_amount": price_cents,
                "currency": "usd",
            }
        )

    return {
        "product_id": product.id,
        "product_name": product.name,
        "price_id": price.id if price else None,
        "price_cents": price_cents,
    }


class CreatePaymentLinkInput(BaseModel):
    price_id: str = Field(description="Stripe price ID")
    quantity: int = Field(default=1, description="Quantity")


@tool(args_schema=CreatePaymentLinkInput)
def stripe_create_payment_link(price_id: str, quantity: int = 1) -> dict:
    """Create a Stripe payment link for a price."""
    client = _get_stripe_client()

    link = client.payment_links.create(
        params={"line_items": [{"price": price_id, "quantity": quantity}]}
    )

    return {"payment_link_id": link.id, "url": link.url}


class RevenueQueryInput(BaseModel):
    days: int = Field(default=7, description="Number of days to query")


@tool(args_schema=RevenueQueryInput)
def stripe_revenue_query(days: int = 7) -> dict:
    """Query recent revenue data from Stripe."""
    import time

    client = _get_stripe_client()
    since = int(time.time()) - (days * 86400)

    charges = client.charges.list(params={"created": {"gte": since}, "limit": 100})

    total_revenue = sum(c.amount for c in charges.data if c.status == "succeeded")
    total_refunded = sum(c.amount_refunded for c in charges.data)

    return {
        "period_days": days,
        "total_charges": len(charges.data),
        "total_revenue_cents": total_revenue,
        "total_refunded_cents": total_refunded,
        "net_revenue_cents": total_revenue - total_refunded,
        "currency": "usd",
    }


@tool
def stripe_list_products() -> dict:
    """List active products in Stripe."""
    client = _get_stripe_client()
    products = client.products.list(params={"active": True, "limit": 20})

    return {
        "count": len(products.data),
        "products": [
            {"id": p.id, "name": p.name, "description": p.description} for p in products.data
        ],
    }


def get_stripe_tools() -> list:
    """Return all Stripe tools for agent use."""
    return [
        stripe_create_product,
        stripe_create_payment_link,
        stripe_revenue_query,
        stripe_list_products,
    ]
