"""ChromaDB memory tool: semantic storage and retrieval of decisions and lessons.

Connects to ChromaDB running in Docker for long-term vector memory.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Lazy-initialized client
_chroma_client = None


def _get_chroma_client():
    """Get or create the ChromaDB HTTP client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        chroma_url = os.environ.get("CHROMA_URL", "http://localhost:8100")
        # Parse host/port from URL
        from urllib.parse import urlparse

        parsed = urlparse(chroma_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8100

        _chroma_client = chromadb.HttpClient(host=host, port=port)
    return _chroma_client


def _get_collection(name: str):
    """Get or create a ChromaDB collection."""
    client = _get_chroma_client()
    return client.get_or_create_collection(name=name)


# Valid collection names for organized memory
COLLECTIONS = [
    "campaign_results",
    "pricing_decisions",
    "product_performance",
    "agent_lessons",
]


class StoreDecisionInput(BaseModel):
    collection: str = Field(
        description=f"Collection name, one of: {COLLECTIONS}"
    )
    text: str = Field(description="The decision or lesson text to store")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


@tool(args_schema=StoreDecisionInput)
def memory_store_decision(collection: str, text: str, metadata: dict | None = None) -> dict:
    """Store a decision or lesson in long-term vector memory."""
    if collection not in COLLECTIONS:
        return {"error": f"Invalid collection. Must be one of: {COLLECTIONS}"}

    coll = _get_collection(collection)
    doc_id = f"{collection}_{int(time.time() * 1000)}"

    meta = metadata or {}
    meta["timestamp"] = time.time()
    # ChromaDB metadata values must be str, int, float, or bool
    meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in meta.items()}

    coll.add(documents=[text], ids=[doc_id], metadatas=[meta])

    return {"id": doc_id, "collection": collection, "stored": True}


class RetrieveSimilarInput(BaseModel):
    collection: str = Field(description=f"Collection name, one of: {COLLECTIONS}")
    query: str = Field(description="Semantic search query")
    k: int = Field(default=5, description="Number of results to return")


@tool(args_schema=RetrieveSimilarInput)
def memory_retrieve_similar(collection: str, query: str, k: int = 5) -> dict:
    """Retrieve semantically similar decisions from long-term memory."""
    if collection not in COLLECTIONS:
        return {"error": f"Invalid collection. Must be one of: {COLLECTIONS}"}

    coll = _get_collection(collection)
    results = coll.query(query_texts=[query], n_results=k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return {
        "collection": collection,
        "query": query,
        "count": len(documents),
        "results": [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(documents, metadatas, distances)
        ],
    }


def get_memory_tools() -> list:
    """Return all memory tools for agent use."""
    return [memory_store_decision, memory_retrieve_similar]
