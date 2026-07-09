"""
Edge Telemetry — FastAPI Application
App factory with lifespan, CORS, WebSocket, and all routers.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_database
from app.services.websocket import manager
from app.routes import telemetry, analytics, devices
from app.routes.telemetry import router_debug

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s: %(message)s"
)
logger = logging.getLogger("edge.main")


# ─────────────────────────────────────────────
# LIFESPAN: Startup / Shutdown
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and start WebSocket broadcast worker on startup."""
    logger.info("═══════════════════════════════════════")
    logger.info("  EDGE TELEMETRY ENGINE — Starting Up  ")
    logger.info("═══════════════════════════════════════")

    # Init database tables
    init_database()

    # Start batched WebSocket broadcast worker
    await manager.start()

    logger.info(f"API Key: {settings.edge_api_key[:8]}...")
    logger.info(f"SQLite: {settings.sqlite_path}")
    logger.info(f"WS Broadcast Interval: {settings.ws_broadcast_interval_ms}ms")
    logger.info(f"Alert Thresholds: Power>{settings.alert_power_threshold_w}W, Battery<{settings.alert_battery_low_v}V, Temp>{settings.alert_temp_high_c}°C")
    logger.info("Engine ready. Waiting for edge devices...")

    yield

    # Shutdown
    await manager.stop()
    logger.info("Edge Telemetry Engine shut down.")


# ─────────────────────────────────────────────
# APP FACTORY
# ─────────────────────────────────────────────
app = FastAPI(
    title="Edge Telemetry API",
    version="1.0.0",
    description="High-speed telemetry ingestion engine for edge IoT devices",
    lifespan=lifespan
)

# CORS — allow dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────
app.include_router(telemetry.router)
app.include_router(analytics.router)
app.include_router(devices.router)
app.include_router(router_debug)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/violations", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─────────────────────────────────────────────
# WEBSOCKET ENDPOINT
# ─────────────────────────────────────────────
import json

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Clients connect here and receive telemetry. If client sends text,
    we check if it's a phone frame broadcast request.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "phone_frame":
                    await manager.broadcast_text(data)
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "operational",
        "engine": "Edge Telemetry",
        "version": "1.0.0",
        "ws_clients": len(manager.active_connections)
    }
