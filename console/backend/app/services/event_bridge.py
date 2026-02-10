"""Event bridge: connects to ecom-agents WebSocket and fans out to browser clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from app.config import settings

logger = logging.getLogger(__name__)


class EventBridge:
    """Maintains a persistent WebSocket connection to ecom-agents
    and fans out events to all connected browser clients."""

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._ws_task: asyncio.Task | None = None
        self._running = False
        self._event_buffer: list[dict[str, Any]] = []
        self._max_buffer = 100

    def subscribe(self) -> tuple[str, asyncio.Queue]:
        """Register a browser client subscriber."""
        import uuid
        import time
        sub_id = str(uuid.uuid4())[:8]
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers[sub_id] = queue
        # Send current bridge status to new subscriber
        status = "connected" if self._running else "disconnected"
        try:
            queue.put_nowait({"type": "bridge_status", "status": status, "timestamp": time.time()})
        except asyncio.QueueFull:
            pass
        logger.info("Browser subscriber connected: %s (total: %d)", sub_id, len(self._subscribers))
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a browser client subscriber."""
        self._subscribers.pop(sub_id, None)
        logger.info("Browser subscriber disconnected: %s (total: %d)", sub_id, len(self._subscribers))

    def _broadcast(self, event: dict[str, Any]) -> None:
        """Fan out an event to all browser subscribers."""
        # Buffer recent events
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._max_buffer:
            self._event_buffer = self._event_buffer[-self._max_buffer:]

        for sub_id, queue in list(self._subscribers.items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    async def _connect_loop(self) -> None:
        """Persistent connection loop to ecom-agents WebSocket."""
        ws_url = settings.ecom_agents_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/events"
        if settings.ecom_agents_token:
            ws_url = f"{ws_url}?token={settings.ecom_agents_token}"

        while self._running:
            try:
                logger.info("Connecting to ecom-agents WebSocket: %s", ws_url)
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("Connected to ecom-agents WebSocket")
                    self._broadcast({"type": "bridge_status", "status": "connected"})
                    async for message in ws:
                        try:
                            event = json.loads(message)
                            self._broadcast(event)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from ecom-agents WS: %s", message[:100])
            except Exception as e:
                logger.warning("ecom-agents WebSocket disconnected: %s — reconnecting in 3s", e)
                self._broadcast({"type": "bridge_status", "status": "disconnected"})
                await asyncio.sleep(3)

    async def start(self) -> None:
        """Start the background WebSocket connection."""
        if self._running:
            return
        self._running = True
        self._ws_task = asyncio.create_task(self._connect_loop())
        logger.info("Event bridge started")

    async def stop(self) -> None:
        """Stop the background WebSocket connection."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bridge stopped")

    @property
    def recent_events(self) -> list[dict[str, Any]]:
        """Return recent buffered events."""
        return list(self._event_buffer)


# Global singleton
event_bridge = EventBridge()
