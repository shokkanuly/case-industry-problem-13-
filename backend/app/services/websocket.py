"""
Edge Telemetry — WebSocket Connection Manager
Batched broadcast worker: collects packets and fires a unified array every 500ms.
"""

import asyncio
import json
import logging
import time
from typing import Any
from fastapi import WebSocket
from app.config import settings

logger = logging.getLogger("edge.websocket")


class ConnectionManager:
    """
    Manages WebSocket clients and batched broadcasting.

    Instead of broadcasting on every individual POST (which hammers memory
    when 3+ devices ping simultaneously), we collect packets into a buffer
    and a background asyncio task flushes the buffer to all clients every
    WS_BROADCAST_INTERVAL_MS milliseconds.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._buffer: list[dict[str, Any]] = []
        self._broadcast_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the batched broadcast background worker."""
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("WebSocket broadcast worker started")

    async def stop(self):
        """Stop the broadcast worker."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket broadcast worker stopped")

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket client."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    def enqueue(self, data: dict[str, Any]):
        """Add a telemetry packet to the broadcast buffer."""
        self._buffer.append(data)

    async def _broadcast_loop(self):
        """
        Background worker: flushes the buffer every INTERVAL ms.
        Sends a JSON array of all buffered packets to every connected client.
        """
        interval = settings.ws_broadcast_interval_ms / 1000.0

        while self._running:
            await asyncio.sleep(interval)

            if not self._buffer or not self.active_connections:
                continue

            # Drain the buffer atomically
            batch = self._buffer.copy()
            self._buffer.clear()

            # Build the unified payload
            payload = json.dumps({
                "type": "telemetry_batch",
                "data": batch,
                "count": len(batch),
                "server_ts": int(time.time())
            })

            # Broadcast to all clients, remove dead connections
            dead = []
            for ws in self.active_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self.disconnect(ws)

            if batch:
                logger.debug(f"Broadcast {len(batch)} packets to {len(self.active_connections)} clients")


# Singleton instance
manager = ConnectionManager()
