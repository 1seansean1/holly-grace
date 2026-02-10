"""Cost dashboard API routes — real provider billing data with LangSmith fallback."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.config import settings
from app.services.langsmith_service import get_cost_summary_from_langsmith
from app.services.provider_costs import (
    get_anthropic_costs,
    get_openai_costs,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("/summary")
async def cost_summary(days: int = Query(30, ge=1, le=90)):
    """Get cost summary. Tries provider billing APIs first, falls back to LangSmith."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    has_anthropic = bool(settings.anthropic_admin_key)
    has_openai = bool(settings.openai_admin_key)

    # If we have admin keys, fetch real billing data from providers
    if has_anthropic or has_openai:
        tasks = []
        if has_anthropic:
            tasks.append(get_anthropic_costs(settings.anthropic_admin_key, start, now))
        else:
            tasks.append(_noop())
        if has_openai:
            tasks.append(get_openai_costs(settings.openai_admin_key, start, now))
        else:
            tasks.append(_noop())

        results = await asyncio.gather(*tasks)
        anthropic_data = results[0] if has_anthropic else None
        openai_data = results[1] if has_openai else None

        if anthropic_data or openai_data:
            return _merge_provider_data(anthropic_data, openai_data, today_start, week_start)

    # Fallback: LangSmith per-LLM-run data (actual tokens × published rates)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_cost_summary_from_langsmith, days=days),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        logger.warning("LangSmith cost aggregation timed out after 15s")
        return {
            "source": "langsmith",
            "source_detail": "Timed out — too many runs to aggregate. Try a shorter period.",
            "total": 0, "today": 0, "week": 0, "month": 0,
            "by_model": {}, "by_agent": {}, "daily": {},
        }


async def _noop():
    return None


def _merge_provider_data(
    anthropic: dict | None,
    openai: dict | None,
    today_start: datetime,
    week_start: datetime,
) -> dict:
    """Merge cost data from Anthropic and OpenAI provider APIs."""
    total = 0.0
    by_model: dict[str, float] = {}
    daily: dict[str, float] = {}
    sources = []

    for provider_data in (anthropic, openai):
        if not provider_data:
            continue
        sources.append(provider_data["provider"])
        total += provider_data.get("total_usd", 0)
        for model, cost in provider_data.get("by_model", {}).items():
            by_model[model] = by_model.get(model, 0) + cost
        for day, cost in provider_data.get("daily", {}).items():
            daily[day] = daily.get(day, 0) + cost

    today_cost = 0.0
    week_cost = 0.0
    today_str = today_start.strftime("%Y-%m-%d")
    week_str = week_start.strftime("%Y-%m-%d")
    for day, cost in daily.items():
        if day >= today_str:
            today_cost += cost
        if day >= week_str:
            week_cost += cost

    by_model = {k: v for k, v in by_model.items() if v > 0}

    return {
        "source": "providers",
        "source_detail": f"Real billing data from {', '.join(sources)}",
        "total": round(total, 4),
        "today": round(today_cost, 4),
        "week": round(week_cost, 4),
        "month": round(total, 4),
        "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
        "by_agent": {},
        "daily": {k: round(v, 4) for k, v in sorted(daily.items())},
    }
