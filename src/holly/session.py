"""Holly Grace conversation session persistence.

Stores conversation history in Postgres (holly_sessions table).
Supports session compaction when message count exceeds threshold.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://holly:holly_dev_password@localhost:5434/holly_grace",
)

# Compact session when message count exceeds this threshold
COMPACTION_THRESHOLD = 200
# Keep the most recent N messages after compaction
COMPACTION_KEEP = 50

_DEFAULT_SESSION_ID = "default"


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(_DB_URL, autocommit=True, row_factory=dict_row)


def get_or_create_session(session_id: str | None = None) -> dict:
    """Get or create a conversation session. Returns session dict."""
    sid = session_id or _DEFAULT_SESSION_ID
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM holly_sessions WHERE session_id = %s", (sid,)
        ).fetchone()

    if row:
        return dict(row)

    # Create new session
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO holly_sessions (session_id, messages, metadata, message_count)
               VALUES (%s, '[]'::JSONB, '{}'::JSONB, 0)
               ON CONFLICT (session_id) DO NOTHING""",
            (sid,),
        )
        row = conn.execute(
            "SELECT * FROM holly_sessions WHERE session_id = %s", (sid,)
        ).fetchone()

    return dict(row) if row else {"session_id": sid, "messages": [], "message_count": 0}


def get_messages(session_id: str | None = None) -> list[dict]:
    """Get all messages in a session."""
    session = get_or_create_session(session_id)
    messages = session.get("messages", [])
    if isinstance(messages, str):
        messages = json.loads(messages)
    return messages


def append_message(
    role: str,
    content: str,
    *,
    session_id: str | None = None,
    metadata: dict | None = None,
    _retry: bool = True,
) -> int:
    """Append a message to the session. Returns new message count.

    role: 'human', 'holly', or 'system'
    """
    sid = session_id or _DEFAULT_SESSION_ID
    msg = {
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        msg["metadata"] = metadata

    with _get_conn() as conn:
        row = conn.execute(
            """UPDATE holly_sessions
               SET messages = messages || %s::JSONB,
                   message_count = message_count + 1,
                   updated_at = NOW()
               WHERE session_id = %s
               RETURNING message_count""",
            (json.dumps([msg], default=str), sid),
        ).fetchone()

    if row is None:
        if not _retry:
            raise RuntimeError(f"Failed to create or find session {sid}")
        # Session doesn't exist yet — create and retry once
        get_or_create_session(sid)
        return append_message(role, content, session_id=sid, metadata=metadata, _retry=False)

    count = row["message_count"]

    # Compact if needed
    if count > COMPACTION_THRESHOLD:
        _compact_session(sid)

    return count


def _compact_session(session_id: str) -> None:
    """Compact a session by keeping only the most recent messages.

    Uses a single connection with FOR UPDATE lock to prevent messages
    appended between read and write from being silently dropped.
    """
    conn = psycopg.connect(_DB_URL, autocommit=False, row_factory=dict_row)
    try:
        row = conn.execute(
            "SELECT messages FROM holly_sessions WHERE session_id = %s FOR UPDATE",
            (session_id,),
        ).fetchone()

        if not row:
            conn.rollback()
            return

        messages = row["messages"]
        if isinstance(messages, str):
            messages = json.loads(messages)

        if len(messages) <= COMPACTION_KEEP:
            conn.rollback()
            return

        original_count = len(messages)

        # Keep the most recent COMPACTION_KEEP messages
        compacted = messages[-COMPACTION_KEEP:]

        # Add a system message noting the compaction
        summary_msg = {
            "role": "system",
            "content": f"[Session compacted: {original_count - COMPACTION_KEEP} older messages removed]",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        compacted.insert(0, summary_msg)

        conn.execute(
            """UPDATE holly_sessions
               SET messages = %s::JSONB,
                   message_count = %s,
                   updated_at = NOW()
               WHERE session_id = %s""",
            (json.dumps(compacted, default=str), len(compacted), session_id),
        )
        conn.commit()

        logger.info(
            "Session %s compacted: %d → %d messages",
            session_id, original_count, len(compacted),
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_session(session_id: str | None = None) -> None:
    """Clear all messages in a session."""
    sid = session_id or _DEFAULT_SESSION_ID
    with _get_conn() as conn:
        conn.execute(
            """UPDATE holly_sessions
               SET messages = '[]'::JSONB, message_count = 0, updated_at = NOW()
               WHERE session_id = %s""",
            (sid,),
        )
