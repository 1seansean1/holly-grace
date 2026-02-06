"""LangServe FastAPI app: exposes the agent graph as REST endpoints."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langserve import add_routes

from src.graph import build_graph
from src.llm.config import LLMSettings
from src.llm.router import LLMRouter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="E-Commerce Agents",
    description="Autonomous print-on-demand e-commerce agent system",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "ecom-agents"})


# Build the graph
settings = LLMSettings()
router = LLMRouter(settings)
graph = build_graph(router)
compiled_graph = graph.compile()

# Add LangServe routes
add_routes(app, compiled_graph, path="/agent")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8050)
