"""Scheduler API routes — proxies to ecom-agents."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/jobs")
async def list_jobs():
    """List all scheduled jobs from ecom-agents."""
    client = get_client()
    try:
        resp = await client.get("/scheduler/jobs")
        return resp.json()
    except Exception:
        return JSONResponse(
            {"jobs": [], "count": 0, "error": "Cannot reach ecom-agents server"},
            status_code=503,
        )


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job."""
    client = get_client()
    try:
        resp = await client.post(f"/scheduler/trigger/{job_id}")
        return resp.json()
    except Exception:
        return JSONResponse(
            {"error": "Cannot reach ecom-agents server"},
            status_code=503,
        )
