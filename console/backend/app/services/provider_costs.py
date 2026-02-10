"""Fetch real billing data from Anthropic and OpenAI admin APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def get_anthropic_costs(
    admin_key: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any] | None:
    """Fetch actual cost breakdown from Anthropic Cost API.

    Requires an admin key (sk-ant-admin...).
    Returns {total_usd, by_model: {model: usd}, daily: {date: usd}} or None on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/organizations/cost_report",
                headers={
                    "x-api-key": admin_key,
                    "anthropic-version": "2023-06-01",
                },
                params={
                    "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ending_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "group_by[]": "description",
                    "bucket_width": "1d",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            total = 0.0
            by_model: dict[str, float] = {}
            daily: dict[str, float] = {}

            for bucket in data.get("data", []):
                # Each bucket has: snapshot_date, costs
                date_str = bucket.get("snapshot_date", "")[:10]
                for cost_entry in bucket.get("costs", []):
                    # cost is in cents (string)
                    amount = float(cost_entry.get("amount", "0")) / 100.0
                    total += amount

                    if date_str:
                        daily[date_str] = daily.get(date_str, 0) + amount

                    desc = cost_entry.get("description", "")
                    # Description contains model info, e.g. "claude-opus-4-6 API"
                    model = _parse_anthropic_model(desc)
                    if model:
                        by_model[model] = by_model.get(model, 0) + amount

            return {
                "provider": "anthropic",
                "total_usd": round(total, 4),
                "by_model": {k: round(v, 4) for k, v in by_model.items()},
                "daily": {k: round(v, 4) for k, v in sorted(daily.items())},
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            logger.info("Anthropic admin key not authorized for cost API (need sk-ant-admin key)")
        else:
            logger.warning("Anthropic cost API error: %s %s", e.response.status_code, e.response.text[:200])
        return None
    except Exception as e:
        logger.warning("Failed to fetch Anthropic costs: %s", e)
        return None


async def get_anthropic_usage(
    admin_key: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any] | None:
    """Fetch token usage from Anthropic Usage API grouped by model."""
    try:
        async with httpx.AsyncClient() as client:
            params: list[tuple[str, str]] = [
                ("starting_at", start.strftime("%Y-%m-%dT%H:%M:%SZ")),
                ("ending_at", end.strftime("%Y-%m-%dT%H:%M:%SZ")),
                ("group_by[]", "model"),
                ("bucket_width", "1d"),
            ]
            resp = await client.get(
                "https://api.anthropic.com/v1/organizations/usage_report/messages",
                headers={
                    "x-api-key": admin_key,
                    "anthropic-version": "2023-06-01",
                },
                params=params,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            logger.info("Anthropic admin key not authorized for usage API")
        else:
            logger.warning("Anthropic usage API error: %s", e.response.status_code)
        return None
    except Exception as e:
        logger.warning("Failed to fetch Anthropic usage: %s", e)
        return None


async def get_openai_costs(
    admin_key: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any] | None:
    """Fetch actual costs from OpenAI Costs API.

    Requires an admin key with api.usage.read scope.
    """
    try:
        start_unix = int(start.timestamp())
        end_unix = int(end.timestamp())

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openai.com/v1/organization/costs",
                headers={"Authorization": f"Bearer {admin_key}"},
                params={
                    "start_time": start_unix,
                    "end_time": end_unix,
                    "limit": 31,
                    "group_by": "line_item",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            total = 0.0
            by_model: dict[str, float] = {}
            daily: dict[str, float] = {}

            for bucket in data.get("data", []):
                # Each bucket has: start_time, results[]
                bucket_date = ""
                if bucket.get("start_time"):
                    bucket_date = datetime.utcfromtimestamp(bucket["start_time"]).strftime("%Y-%m-%d")

                for result in bucket.get("results", []):
                    amount = float(result.get("amount", {}).get("value", 0)) / 100.0
                    total += amount

                    if bucket_date:
                        daily[bucket_date] = daily.get(bucket_date, 0) + amount

                    line_item = result.get("line_item", "")
                    model = _parse_openai_model(line_item)
                    if model:
                        by_model[model] = by_model.get(model, 0) + amount

            return {
                "provider": "openai",
                "total_usd": round(total, 4),
                "by_model": {k: round(v, 4) for k, v in by_model.items()},
                "daily": {k: round(v, 4) for k, v in sorted(daily.items())},
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            logger.info("OpenAI admin key not authorized for costs API")
        else:
            logger.warning("OpenAI costs API error: %s %s", e.response.status_code, e.response.text[:200])
        return None
    except Exception as e:
        logger.warning("Failed to fetch OpenAI costs: %s", e)
        return None


def _parse_anthropic_model(description: str) -> str:
    """Extract model name from Anthropic cost description."""
    desc_lower = description.lower()
    for model in ("claude-opus-4-6", "claude-sonnet-4-5", "claude-haiku-4-5",
                   "claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"):
        if model in desc_lower:
            return model
    return description.split(" ")[0] if description else ""


def _parse_openai_model(line_item: str) -> str:
    """Extract model name from OpenAI cost line item."""
    item_lower = line_item.lower()
    for model in ("gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"):
        if model in item_lower:
            return model
    return line_item.split(" ")[0] if line_item else ""
