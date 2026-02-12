"""Holly Grace backend — FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agents, app_factory, approvals, auth, autonomy, chat, costs, evaluations, execution, graph, health, hierarchy, holly, im, mcp, morphogenetic, scheduler, system, tools, tower, traces, workflows
from app.services.holly_client import close_client
from app.services.event_bridge import event_bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown resources."""
    logger.info("Holly Grace backend starting — connecting to %s", settings.agents_url)
    await event_bridge.start()
    yield
    await event_bridge.stop()
    await close_client()
    logger.info("Holly Grace backend stopped")


app = FastAPI(
    title="Holly Grace",
    description="Agent orchestration dashboard backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — must be added before routers for middleware ordering
from app.auth import ConsoleAuthMiddleware

app.add_middleware(ConsoleAuthMiddleware)

# Mount routers
app.include_router(auth.router)
app.include_router(graph.router)
app.include_router(health.router)
app.include_router(scheduler.router)
app.include_router(execution.router)
app.include_router(traces.router)
app.include_router(costs.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(mcp.router)
app.include_router(workflows.router)
app.include_router(approvals.router)
app.include_router(evaluations.router)
app.include_router(morphogenetic.router)
app.include_router(system.router)
app.include_router(tower.router)
app.include_router(hierarchy.router)
app.include_router(im.router)
app.include_router(app_factory.router)
app.include_router(chat.router)
app.include_router(holly.router)
app.include_router(autonomy.router)


@app.get("/")
async def root():
    return {"service": "holly-grace", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8060)
