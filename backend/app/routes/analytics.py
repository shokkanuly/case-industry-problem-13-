"""
Edge Telemetry — Analytics Routes
GET /api/analytics/summary — Dashboard summary metrics
GET /api/analytics/power   — Power consumption hourly trend
GET /api/analytics/traffic  — Motion event hourly trend
GET /api/analytics/alerts   — Recent threshold-breach alerts
"""

import os
import json
import logging
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from typing import Optional
from app.services import analytics as analytics_svc
from app.middleware import verify_api_key
from app.models import SimulatorOverride
from app.database import get_db

logger = logging.getLogger("edge.analytics.routes")
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

class WorkerCreate(BaseModel):
    name: str
    role: str
    photo: Optional[str] = None

@router.get("/personnel")
async def get_personnel(_: str = Depends(verify_api_key)):
    """Retrieve all workers from the database."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM workers")
        rows = cur.fetchall()
        return [dict(row) for row in rows]

@router.post("/personnel")
async def create_personnel(worker: WorkerCreate, _: str = Depends(verify_api_key)):
    """Add a new worker to the safety database."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO workers (name, role, status, compliance_score, photo) VALUES (?, ?, 'Normal', 100.0, ?)",
            (worker.name, worker.role, worker.photo)
        )
        conn.commit()
        new_id = cur.lastrowid
        return {"status": "ok", "id": new_id, "name": worker.name, "role": worker.role, "photo": worker.photo}

@router.delete("/personnel/{id}")
async def delete_personnel(id: int, _: str = Depends(verify_api_key)):
    """Remove a worker from the safety database."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM workers WHERE id = ?", (id,))
        conn.commit()
        return {"status": "ok", "deleted_id": id}


# In-memory store for simulator overrides (anomaly trigger and connectivity status)
SIMULATOR_OVERRIDES = {}

# ── Load Case Registry ──
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "case_registry.json")
try:
    with open(REGISTRY_PATH, "r") as f:
        registry_data = json.load(f)
        CASE_REGISTRY = {c["device_id"]: c for c in registry_data["cases"]}
except Exception as e:
    logger.error(f"Failed to load case registry in routes/analytics: {e}")
    CASE_REGISTRY = {}



@router.get("/summary")
async def get_summary(_: str = Depends(verify_api_key)):
    """Dashboard summary: events, devices, power, alerts."""
    return analytics_svc.get_summary()


@router.get("/power")
async def get_power_trend(
    hours: int = 24,
    _: str = Depends(verify_api_key)
):
    """Hourly power consumption trend."""
    return analytics_svc.get_hourly_trend("power", hours=min(hours, 168))


@router.get("/traffic")
async def get_traffic_trend(
    hours: int = 24,
    _: str = Depends(verify_api_key)
):
    """Hourly motion event trend."""
    return analytics_svc.get_hourly_trend("motion", hours=min(hours, 168))


@router.get("/environment")
async def get_environment_trend(
    hours: int = 24,
    _: str = Depends(verify_api_key)
):
    """Hourly environment (temperature/humidity) trend."""
    return analytics_svc.get_hourly_trend("environment", hours=min(hours, 168))


@router.get("/alerts")
async def get_alerts(
    limit: int = 50,
    _: str = Depends(verify_api_key)
):
    """Recent threshold-breach alerts."""
    return analytics_svc.get_alerts(limit=min(limit, 200))


@router.get("/assets")
async def get_assets(_: str = Depends(verify_api_key)):
    """Get all registered Digital Twin assets."""
    return analytics_svc.get_assets()


@router.post("/simulator/override")
async def set_simulator_override(
    override: SimulatorOverride,
    _: str = Depends(verify_api_key)
):
    """Set simulation override for a device (e.g. inject anomaly or toggle offline)."""
    SIMULATOR_OVERRIDES[override.device_id] = {
        "anomaly_active": override.anomaly_active,
        "connection_active": override.connection_active
    }
    return {"status": "ok", "overrides": SIMULATOR_OVERRIDES}


@router.get("/simulator/override")
async def get_simulator_overrides(_: str = Depends(verify_api_key)):
    """Get all active simulation overrides."""
    return SIMULATOR_OVERRIDES


@router.get("/simulator/override/{device_id}")
async def get_device_override(
    device_id: str,
    _: str = Depends(verify_api_key)
):
    """Get simulation override status for a specific device."""
    override = SIMULATOR_OVERRIDES.get(device_id, {
        "anomaly_active": False,
        "connection_active": True
    }).copy()
    
    # Inherit global tunnel connection state for underground devices
    case_entry = CASE_REGISTRY.get(device_id)
    if case_entry and case_entry.get("underground", False):
        global_tunnel = SIMULATOR_OVERRIDES.get("tunnel_connected", {
            "anomaly_active": False,
            "connection_active": True
        })
        if not global_tunnel.get("connection_active", True):
            override["connection_active"] = False
            
    return override

