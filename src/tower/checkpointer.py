"""Tower checkpointer: PostgresSaver singleton for durable LangGraph checkpointing.

Uses psycopg_pool.ConnectionPool for a long-lived PostgresSaver instance
that can be shared across graph compilations and worker invocations.
"""

from __future__ import annotations

import logging
import os

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
)

_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


def setup_checkpointer() -> None:
    """Initialize the connection pool and PostgresSaver.

    Creates the LangGraph checkpoint tables (checkpoints, checkpoint_blobs,
    checkpoint_writes, checkpoint_migrations) if they don't exist.
    Call once during lifespan startup.
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return

    _pool = ConnectionPool(
        conninfo=_DB_URL,
        open=True,
        min_size=2,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()
    logger.info("Tower PostgresSaver initialized (checkpoint tables created)")


def get_checkpointer() -> PostgresSaver:
    """Get the singleton PostgresSaver instance.

    Raises RuntimeError if setup_checkpointer() hasn't been called.
    """
    if _checkpointer is None:
        raise RuntimeError(
            "Tower checkpointer not initialized. "
            "Call setup_checkpointer() during startup."
        )
    return _checkpointer


def shutdown_checkpointer() -> None:
    """Close the connection pool on shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("Tower PostgresSaver shut down")
