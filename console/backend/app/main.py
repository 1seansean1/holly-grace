"""Forge Console backend — FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agents, approvals, costs, evaluations, execution, graph, health, morphogenetic, scheduler, system, tools, traces, workflows
from app.services.ecom_client import close_client
from app.services.event_bridge import event_bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown resources."""
    logger.info("Forge Scope backend starting — connecting to %s", settings.ecom_agents_url)
    await event_bridge.start()
    yield
    await event_bridge.stop()
    await close_client()
    logger.info("Forge Scope backend stopped")


app = FastAPI(
    title="Forge Scope",
    description="Agent orchestration dashboard backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(graph.router)
app.include_router(health.router)
app.include_router(scheduler.router)
app.include_router(execution.router)
app.include_router(traces.router)
app.include_router(costs.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(workflows.router)
app.include_router(approvals.router)
app.include_router(evaluations.router)
app.include_router(morphogenetic.router)
app.include_router(system.router)


@app.get("/")
async def root():
    return {"service": "forge-scope", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8060)
