"""Evaluation suite API routes — proxies to ecom-agents /eval endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/eval", tags=["evaluations"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.post("/run")
async def run_eval():
    """Trigger a golden evaluation suite run."""
    client = get_client()
    try:
        resp = await client.post("/eval/run", timeout=300.0)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/results")
async def eval_history():
    """Get eval suite run history."""
    client = get_client()
    try:
        resp = await client.get("/eval/results")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "history": []}, status_code=503)


@router.get("/results/{suite_id}")
async def eval_detail(suite_id: str):
    """Get detailed results for a specific eval suite run."""
    client = get_client()
    try:
        resp = await client.get(f"/eval/results/{suite_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
