"""Trace explorer API routes — LangSmith integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.langsmith_service import get_trace_detail, list_traces

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("")
async def traces(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    days: int = Query(7, ge=1, le=90),
):
    """List recent traces from LangSmith."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)
    result = await asyncio.to_thread(list_traces, limit=limit, offset=offset, start_time=start_time, end_time=now)
    return {"traces": result, "count": len(result)}


@router.get("/{run_id}")
async def trace_detail(run_id: str):
    """Get detailed trace with all child runs."""
    result = await asyncio.to_thread(get_trace_detail, run_id)
    if result is None:
        return JSONResponse({"error": "Trace not found"}, status_code=404)
    return result
