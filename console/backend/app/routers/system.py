"""System image export/import routes — proxies to ecom-agents /system endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client

router = APIRouter(prefix="/api/system", tags=["system"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("/export")
async def export_image():
    """Export the full system configuration as a portable image."""
    client = get_client()
    try:
        resp = await client.get("/system/export", timeout=30.0)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/import")
async def import_image(request: Request):
    """Import a system image. Applies changes to current system."""
    client = get_client()
    try:
        body = await request.json()
        resp = await client.post("/system/import", json=body, timeout=30.0)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.post("/import/preview")
async def import_preview(request: Request):
    """Preview what an import would change (dry run)."""
    client = get_client()
    try:
        body = await request.json()
        resp = await client.post("/system/import/preview", json=body, timeout=30.0)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)


@router.get("/images")
async def list_images():
    """List previously exported system images."""
    client = get_client()
    try:
        resp = await client.get("/system/images")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse({**_503, "images": []}, status_code=503)


@router.get("/images/{image_id}")
async def get_image(image_id: int):
    """Get a full system image by ID."""
    client = get_client()
    try:
        resp = await client.get(f"/system/images/{image_id}")
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(_503, status_code=503)
