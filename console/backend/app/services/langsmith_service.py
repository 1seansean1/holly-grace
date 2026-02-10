"""LangSmith integration service — fetches traces, runs, and aggregated data."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from langsmith import Client

from app.config import settings

logger = logging.getLogger(__name__)

# Cost rates per 1M tokens (published pricing)
MODEL_COSTS: dict[str, dict[str, float]] = {
    "qwen2.5:3b": {"input": 0.0, "output": 0.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
}

# Cache for trace list (avoid hammering LangSmith)
_trace_cache: dict[str, Any] = {"data": None, "expires": 0}
CACHE_TTL = 60  # seconds

# Cache for cost summary (expensive computation, refresh every 5 min)
_cost_cache: dict[str, Any] = {}


def _get_client() -> Client | None:
    if not settings.langsmith_api_key:
        return None
    return Client(api_key=settings.langsmith_api_key)


def _calc_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost for a given model and token counts. Rates are per 1M tokens."""
    rates = MODEL_COSTS.get(model_name, {})
    input_cost = (prompt_tokens / 1_000_000) * rates.get("input", 0)
    output_cost = (completion_tokens / 1_000_000) * rates.get("output", 0)
    return round(input_cost + output_cost, 6)


def _extract_model_name(run: Any) -> str:
    """Extract model name from a LangSmith run."""
    extra = getattr(run, "extra", {}) or {}
    invocation = extra.get("invocation_params", {}) or {}
    model = invocation.get("model", "") or invocation.get("model_name", "")
    if not model:
        metadata = extra.get("metadata", {}) or {}
        model = metadata.get("ls_model_name", "")
    return model or "unknown"


def _run_to_dict(run: Any) -> dict[str, Any]:
    """Convert a LangSmith run to a serializable dict."""
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    if run.total_tokens:
        total_tokens = run.total_tokens
    if run.prompt_tokens:
        prompt_tokens = run.prompt_tokens
    if run.completion_tokens:
        completion_tokens = run.completion_tokens

    model_name = _extract_model_name(run)
    cost = _calc_cost(model_name, prompt_tokens, completion_tokens)
    duration_ms = 0
    if run.end_time and run.start_time:
        duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)

    return {
        "run_id": str(run.id),
        "name": run.name or "",
        "run_type": run.run_type or "",
        "status": run.status or "unknown",
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "duration_ms": duration_ms,
        "model": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "error": run.error or None,
        "inputs_preview": _safe_preview(run.inputs),
        "outputs_preview": _safe_preview(run.outputs),
    }


def _safe_preview(data: Any, max_len: int = 200) -> str:
    if not data:
        return ""
    import json
    try:
        text = json.dumps(data, default=str)
        return text[:max_len] + ("..." if len(text) > max_len else "")
    except Exception:
        return str(data)[:max_len]


def list_traces(
    limit: int = 50,
    offset: int = 0,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """List top-level trace runs from LangSmith."""
    client = _get_client()
    if not client:
        return []

    now = time.time()
    cache_key = f"{limit}:{offset}:{start_time}:{end_time}"

    if _trace_cache.get("key") == cache_key and _trace_cache["expires"] > now:
        return _trace_cache["data"]

    try:
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=7)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        runs = list(client.list_runs(
            project_name=settings.langsmith_project,
            is_root=True,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        ))

        result = [_run_to_dict(r) for r in runs]
        _trace_cache.update({"key": cache_key, "data": result, "expires": now + CACHE_TTL})
        return result
    except Exception as e:
        logger.warning("Failed to fetch traces from LangSmith: %s", e)
        return []


def get_trace_detail(run_id: str) -> dict[str, Any] | None:
    """Get detailed trace with child runs for a specific run."""
    client = _get_client()
    if not client:
        return None

    try:
        run = client.read_run(run_id)
        result = _run_to_dict(run)

        # Get child runs (steps)
        children = list(client.list_runs(
            project_name=settings.langsmith_project,
            trace_id=run_id,
            limit=100,
        ))

        steps = []
        for child in children:
            if str(child.id) == run_id:
                continue  # Skip the root run itself
            steps.append(_run_to_dict(child))

        # Sort by start_time
        steps.sort(key=lambda s: s["start_time"] or "")
        result["steps"] = steps
        return result
    except Exception as e:
        logger.warning("Failed to fetch trace detail from LangSmith: %s", e)
        return None


COST_CACHE_TTL = 300  # 5 minutes

# Map model name variants to canonical names
_MODEL_ALIASES: dict[str, str] = {
    "qwen2.5:3b": "qwen2.5:3b",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "gpt-4o-2024-08-06": "gpt-4o",
    "gpt-4o-2024-11-20": "gpt-4o",
    "claude-opus-4-6": "claude-opus-4-6",
    "claude-opus-4-6-20250514": "claude-opus-4-6",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
}

# Agent names associated with each model
_MODEL_AGENT_MAP: dict[str, str] = {
    "qwen2.5:3b": "orchestrator",
    "gpt-4o-mini": "operations",
    "gpt-4o": "sales_marketing",
    "claude-opus-4-6": "revenue_analytics",
    "claude-sonnet-4-5": "revenue_analytics",
}


def _normalize_model(raw: str) -> str:
    """Normalize model name to canonical form."""
    return _MODEL_ALIASES.get(raw, raw)


def get_cost_summary_from_langsmith(days: int = 30) -> dict[str, Any]:
    """Aggregate costs from individual LLM runs (actual model + actual tokens).

    Queries all runs in the project and filters for LLM-type runs locally.
    Each LLM run has the real model name and exact token counts — this is
    the same data providers bill from.
    """
    client = _get_client()
    if not client:
        return _empty_cost_summary("langsmith")

    cache_key = f"costs_llm:{days}"
    now_ts = time.time()
    if cache_key in _cost_cache and _cost_cache[cache_key]["expires"] > now_ts:
        return _cost_cache[cache_key]["data"]

    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)

        # Get only LLM runs directly (much faster than fetching all runs)
        all_runs = client.list_runs(
            project_name=settings.langsmith_project,
            run_type="llm",
            start_time=start,
            end_time=now,
        )

        total = 0.0
        today_cost = 0.0
        week_cost = 0.0
        by_model: dict[str, float] = {}
        by_agent: dict[str, float] = {}
        daily: dict[str, float] = {}
        llm_count = 0

        for run in all_runs:
            llm_count += 1
            if llm_count > 5000:  # Safety limit
                break
            raw_model = _extract_model_name(run)
            model = _normalize_model(raw_model)
            pt = run.prompt_tokens or 0
            ct = run.completion_tokens or 0
            cost = _calc_cost(model, pt, ct)

            if cost == 0 and model not in ("qwen2.5:3b", "unknown"):
                # Unknown model with tokens — try parent rates
                cost = _calc_cost(raw_model, pt, ct)

            total += cost
            by_model[model] = by_model.get(model, 0) + cost

            agent = _MODEL_AGENT_MAP.get(model, "unknown")
            if agent != "unknown":
                by_agent[agent] = by_agent.get(agent, 0) + cost

            if run.start_time:
                st = run.start_time
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
                day_key = st.strftime("%Y-%m-%d")
                daily[day_key] = daily.get(day_key, 0) + cost
                if st >= today_start:
                    today_cost += cost
                if st >= week_start:
                    week_cost += cost

        by_model = {k: v for k, v in by_model.items() if v > 0}
        by_agent = {k: v for k, v in by_agent.items() if v > 0}

        result = {
            "source": "langsmith",
            "source_detail": f"Per-LLM-run token data ({llm_count} LLM calls)",
            "total": round(total, 4),
            "today": round(today_cost, 4),
            "week": round(week_cost, 4),
            "month": round(total, 4),
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
            "by_agent": {k: round(v, 4) for k, v in sorted(by_agent.items(), key=lambda x: -x[1])},
            "daily": {k: round(v, 4) for k, v in sorted(daily.items())},
        }
        _cost_cache[cache_key] = {"data": result, "expires": time.time() + COST_CACHE_TTL}
        return result
    except Exception as e:
        logger.warning("Failed to aggregate LLM-level costs from LangSmith: %s", e)
        return _empty_cost_summary("langsmith")


def _empty_cost_summary(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "source_detail": "No data available",
        "total": 0, "today": 0, "week": 0, "month": 0,
        "by_model": {}, "by_agent": {}, "daily": {},
    }
