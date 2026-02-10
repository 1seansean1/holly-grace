"""Graph definition API routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ecom_client import get_client
from app.services.graph_introspection import get_graph_definition

router = APIRouter(prefix="/api/graph", tags=["graph"])

_503 = {"error": "Cannot reach ecom-agents server"}


@router.get("/definition")
async def graph_definition():
    """Return the agent graph topology for canvas rendering."""
    return get_graph_definition().model_dump()


@router.get("/metadata")
async def graph_metadata():
    """Batch metadata for all graph nodes (proxied to ecom-agents)."""
    client = get_client()
    try:
        resp = await client.get("/graph/metadata")
        return resp.json()
    except Exception:
        return JSONResponse({**_503, "nodes": {}}, status_code=503)
