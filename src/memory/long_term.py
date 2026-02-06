"""Long-term memory: ChromaDB vector store for semantic retrieval.

Collections:
- campaign_results: Past campaign performance data
- pricing_decisions: Historical pricing changes and outcomes
- product_performance: Product-level metrics and trends
- agent_lessons: Lessons learned from agent operations

Queried by orchestrator before routing to inject memory_context into state.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

COLLECTIONS = [
    "campaign_results",
    "pricing_decisions",
    "product_performance",
    "agent_lessons",
]

_client = None


def _get_client():
    global _client
    if _client is None:
        import chromadb

        url = os.environ.get("CHROMA_URL", "http://localhost:8100")
        parsed = urlparse(url)
        _client = chromadb.HttpClient(
            host=parsed.hostname or "localhost", port=parsed.port or 8100
        )
    return _client


def store(collection_name: str, text: str, metadata: dict[str, Any] | None = None) -> str:
    """Store a document in the specified collection."""
    client = _get_client()
    coll = client.get_or_create_collection(name=collection_name)
    doc_id = f"{collection_name}_{int(time.time() * 1000)}"

    meta = metadata or {}
    meta["timestamp"] = time.time()
    meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in meta.items()}

    coll.add(documents=[text], ids=[doc_id], metadatas=[meta])
    return doc_id


def retrieve(collection_name: str, query: str, k: int = 5) -> list[dict[str, Any]]:
    """Retrieve the top-k most similar documents from a collection."""
    client = _get_client()
    coll = client.get_or_create_collection(name=collection_name)
    results = coll.query(query_texts=[query], n_results=k)

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(docs, metas, dists)
    ]


def build_memory_context(task_description: str, max_results: int = 3) -> str:
    """Query all collections and build a combined memory context string.

    Used by the orchestrator to inject relevant past decisions into state.
    """
    context_parts = []
    for coll_name in COLLECTIONS:
        try:
            results = retrieve(coll_name, task_description, k=max_results)
            if results:
                context_parts.append(f"[{coll_name}]")
                for r in results:
                    context_parts.append(f"  - {r['text'][:200]}")
        except Exception as e:
            logger.debug("Memory query failed for %s: %s", coll_name, e)

    return "\n".join(context_parts) if context_parts else ""
