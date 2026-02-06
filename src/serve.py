"""LangServe FastAPI app: exposes the agent graph as REST endpoints."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langserve import add_routes

from src.graph import build_graph
from src.llm.config import LLMSettings
from src.llm.router import LLMRouter
from src.scheduler.autonomous import AutonomousScheduler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build the graph
settings = LLMSettings()
router = LLMRouter(settings)
graph = build_graph(router)
compiled_graph = graph.compile()

# Create the scheduler
scheduler = AutonomousScheduler(compiled_graph.invoke)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on startup, stop on shutdown."""
    scheduler.start()
    logger.info("Autonomous scheduler started — store is now running 24/7")
    yield
    scheduler.stop()
    logger.info("Autonomous scheduler stopped")


app = FastAPI(
    title="E-Commerce Agents",
    description="Autonomous print-on-demand e-commerce agent system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    from src.resilience.health import run_health_checks

    health = run_health_checks()
    all_healthy = all(v for v in health.values())
    status = "healthy" if all_healthy else "degraded"
    return JSONResponse(
        {"status": status, "service": "ecom-agents", "checks": health},
        status_code=200 if all_healthy else 503,
    )


@app.get("/scheduler/jobs")
async def scheduler_jobs():
    """List all scheduled jobs."""
    jobs = [
        {"id": job.id, "next_run": str(job.next_run_time), "trigger": str(job.trigger)}
        for job in scheduler.jobs
    ]
    return JSONResponse({"jobs": jobs, "count": len(jobs)})


# Add LangServe routes
add_routes(app, compiled_graph, path="/agent")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8050)
