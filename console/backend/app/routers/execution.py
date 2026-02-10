"""Execution API routes — invoke graph and stream events."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.ecom_client import get_client
from app.services.event_bridge import event_bridge

router = APIRouter(tags=["execution"])


class InvokeRequest(BaseModel):
    task: str


@router.post("/api/execute")
async def execute_task(req: InvokeRequest):
    """Invoke the agent graph with a task."""
    client = get_client()
    try:
        resp = await client.post(
            "/agent/invoke",
            json={
                "input": {
                    "messages": [{"type": "human", "content": req.task}],
                    "trigger_source": "forge_console",
                    "retry_count": 0,
                }
            },
            timeout=120.0,
        )
        return resp.json()
    except Exception as e:
        return JSONResponse(
            {"error": f"Execution failed: {e}"},
            status_code=500,
        )


async def _forward_events(websocket: WebSocket, queue: asyncio.Queue, filter_type: str | None = None):
    """Read events from queue and send to websocket."""
    try:
        while True:
            event = await queue.get()
            if filter_type and event.get("type") != filter_type:
                continue
            await websocket.send_text(json.dumps(event, default=str))
    except (WebSocketDisconnect, Exception):
        pass


async def _wait_disconnect(websocket: WebSocket):
    """Block until the client disconnects."""
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/execution")
async def ws_execution(websocket: WebSocket):
    """WebSocket endpoint for browser clients to receive real-time execution events."""
    await websocket.accept()
    sub_id, queue = event_bridge.subscribe()
    try:
        send_task = asyncio.create_task(_forward_events(websocket, queue))
        recv_task = asyncio.create_task(_wait_disconnect(websocket))
        done, pending = await asyncio.wait(
            [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    except Exception:
        pass
    finally:
        event_bridge.unsubscribe(sub_id)


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    """WebSocket endpoint for streaming log events only."""
    await websocket.accept()
    sub_id, queue = event_bridge.subscribe()
    try:
        send_task = asyncio.create_task(_forward_events(websocket, queue, filter_type="log"))
        recv_task = asyncio.create_task(_wait_disconnect(websocket))
        done, pending = await asyncio.wait(
            [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    except Exception:
        pass
    finally:
        event_bridge.unsubscribe(sub_id)
