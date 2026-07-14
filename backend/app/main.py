"""
Edge Telemetry — FastAPI Application
App factory with lifespan, CORS, WebSocket, message broker, and all routers.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import json
import socket

from app.config import settings
from app.database import init_database
from app.services.websocket import manager
from app.services.broker import get_message_broker
from app.routes import telemetry, analytics, devices, integrations
from app.routes.telemetry import router_debug
from app.services.ingestion import process_telemetry_core
from app.models import TelemetryPacket

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
    """Initialize databases, start broker and background consumers on startup."""
    logger.info("═══════════════════════════════════════")
    logger.info("  EDGE TELEMETRY ENGINE — Starting Up  ")
    logger.info("═══════════════════════════════════════")

    # Init database tables
    init_database()

    # Start batched WebSocket broadcast worker
    await manager.start()

    # Start message broker
    broker = get_message_broker()
    await broker.start()

    # Background message consumers
    async def raw_telemetry_consumer(topic: str, payload: dict):
        try:
            packet = TelemetryPacket(**payload)
            await process_telemetry_core(packet)
        except Exception as e:
            logger.error(f"Error processing raw telemetry from broker: {e}")

    async def ws_forwarder(topic: str, payload: dict):
        # Forward updates to WebSocket enqueue
        manager.enqueue(payload)

    # Subscribe consumers to topics
    from app.routes.integrations import handle_alert_for_cmms
    await broker.subscribe("industrial/telemetry/raw", raw_telemetry_consumer)
    await broker.subscribe("industrial/twin/update", ws_forwarder)
    await broker.subscribe("industrial/alerts", ws_forwarder)
    await broker.subscribe("industrial/alerts", handle_alert_for_cmms)

    logger.info(f"API Key: {settings.edge_api_key[:8]}...")
    logger.info(f"SQLite: {settings.sqlite_path}")
    logger.info(f"Time-series Store Type: {settings.tsdb_type}")
    logger.info(f"WS Broadcast Interval: {settings.ws_broadcast_interval_ms}ms")
    logger.info(f"Alert Thresholds: Power>{settings.alert_power_threshold_w}W, Battery<{settings.alert_battery_low_v}V, Temp>{settings.alert_temp_high_c}°C")
    logger.info("Engine ready. Waiting for edge devices...")

    yield

    # Shutdown
    await manager.stop()
    broker_instance = get_message_broker()
    await broker_instance.stop()
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
app.include_router(integrations.router)
app.include_router(router_debug)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/violations", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─────────────────────────────────────────────
# WEBSOCKET ENDPOINT
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates AND phone camera frames.
    - Dashboard clients receive broadcast telemetry updates.
    - Phone clients send {type: 'phone_frame', frame: '<base64 JPEG>'} messages,
      which are run through analyze_frame() and results broadcast to all dashboards.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "phone_frame":
                    # Run YOLO + InsightFace analysis on phone frame (non-blocking)
                    frame_b64 = msg.get("frame", "")
                    if frame_b64:
                        # Strip data URL prefix if present
                        if "," in frame_b64:
                            frame_b64 = frame_b64.split(",")[1]
                        img_bytes = base64.b64decode(frame_b64)

                        # Run analyze_frame in thread pool so event loop stays responsive
                        from app.services.safety_inference import analyze_frame
                        result = await asyncio.to_thread(analyze_frame, img_bytes)

                        # Save violation to DB if any (reuse telemetry route logic)
                        try:
                            from app.routes.telemetry import _process_inference_result
                            await _process_inference_result(img_bytes, result)
                        except Exception as e:
                            logger.error(f"phone_frame DB save error: {e}")

                        # Broadcast result to all connected dashboard clients
                        broadcast_payload = json.dumps({
                            "type": "phone_analysis",
                            "source": "phone",
                            "person_count": result["person_count"],
                            "active_violations": result["active_violations"],
                            "zone_breaches": result["zone_breaches"],
                            "compliance_pct": result["compliance_pct"],
                            "recognized_workers": result["recognized_workers"],
                            "detections": result["detections"],
                        })
                        await manager.broadcast_text(broadcast_payload)
            except Exception as e:
                logger.debug(f"WS message error: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─────────────────────────────────────────────
# SYSTEM INFO ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/system/local-ip", tags=["system"])
async def get_local_ip():
    """Returns the machine's local network IP address for QR code generation."""
    try:
        # Connect to external address to determine outbound interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return {
        "local_ip": ip,
        "frontend_url": f"https://{ip}:5174",
        "phone_url": f"https://{ip}:5174/phone",
        "backend_ws": f"ws://{ip}:8000/ws"
    }


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
