import time
import uuid
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from app.database import get_db
from app.middleware import verify_api_key

logger = logging.getLogger("edge.integrations")

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def init_integrations_db():
    """Dynamically initialize CMMS work orders table if it doesn't exist."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cmms_work_orders (
                work_order_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                alert_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_to TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.commit()


# Initialize database
init_integrations_db()


@router.get("/cmms/work-orders")
async def get_cmms_work_orders(limit: int = 50):
    """Retrieve CMMS work orders logged automatically from twin safety alerts."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM cmms_work_orders 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        
    return [{
        "work_order_id": r["work_order_id"],
        "asset_id": r["asset_id"],
        "alert_id": r["alert_id"],
        "title": r["title"],
        "description": r["description"],
        "status": r["status"],
        "assigned_to": r["assigned_to"],
        "created_at": r["created_at"]
    } for r in rows]


@router.get("/fms/dispatch")
async def get_fms_dispatch_flags():
    """
    Fleet Management System (FMS) dispatcher integrations.
    Returns dynamic truck dispatch commands based on digital twin safety events.
    """
    # Fetch active assets status from digital twin
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT asset_id, asset_name, status, risk_score, metadata FROM assets")
        rows = cur.fetchall()
        
    dispatch_actions = []
    zone_b_status = "Normal"
    crusher_breached = False
    active_violations_count = 0
    
    for r in rows:
        aid = r["asset_id"]
        status = r["status"]
        if aid == "haul_road_zone_b":
            zone_b_status = status
            try:
                import json
                meta = json.loads(r["metadata"])
                crusher_breached = meta.get("worker_in_danger_zone", False) or meta.get("zone_breaches", 0) > 0
                active_violations_count = meta.get("active_violations", 0)
            except Exception:
                pass
                
    # Rule 1: Crusher zone breached
    if crusher_breached:
        dispatch_actions.append({
            "rule_id": "RULE-FMS-001",
            "action": "TEMPORARY STOP",
            "target": "ALL DUMP TRUCKS in Sector 3 (Crusher Access Road)",
            "reason": "CRITICAL: Unidentified worker or PPE breach inside restricted Crusher Zone boundary.",
            "severity": "Critical",
            "timestamp": int(time.time())
        })
    elif zone_b_status == "Warning" or active_violations_count > 0:
        dispatch_actions.append({
            "rule_id": "RULE-FMS-002",
            "action": "SLOW ZONE (15 km/h)",
            "target": "Dump Trucks passing Crusher conveyor line",
            "reason": "WARNING: Worker spotted on Crusher Road with incomplete PPE safety gear.",
            "severity": "Warning",
            "timestamp": int(time.time())
        })
    else:
        dispatch_actions.append({
            "rule_id": "RULE-FMS-003",
            "action": "NORMAL DISPATCH",
            "target": "Dump Trucks Sectors 1-4",
            "reason": "All safety checks passing. Normal operating routes.",
            "severity": "Normal",
            "timestamp": int(time.time())
        })
        
    return {
        "fms_status": "Operational",
        "crusher_sector_state": zone_b_status,
        "dispatch_commands": dispatch_actions
    }


@router.get("/dcs/registers")
async def get_dcs_modbus_registers():
    """
    SCADA/DCS interface.
    Exposes industrial digital twin states as simulated Modbus TCP registers (4xxxx holding registers).
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT asset_id, last_value, status, risk_score FROM assets")
        assets_list = cur.fetchall()
        
    # Map key assets to holding register addresses
    registers = {}
    
    # 40001: System Status (1 = Ok, 2 = Warning, 3 = Critical)
    system_status = 1
    worst_status = "Normal"
    
    for r in assets_list:
        aid = r["asset_id"]
        val = r["last_value"] if r["last_value"] is not None else 0.0
        status = r["status"]
        
        if status == "Critical":
            worst_status = "Critical"
        elif status == "Warning" and worst_status != "Critical":
            worst_status = "Warning"
            
        if aid == "haul_road_zone_b":
            # 40005: Conveyor zone compliance % (rounded)
            registers["40005"] = int(val)
            # 40006: Danger zone breach flag (0 or 1)
            registers["40006"] = 1 if status == "Critical" else 0
        elif aid == "vanyukov_furnace_1":
            # 40010: Furnace Temperature (x10 scaling)
            registers["40010"] = int(val * 10)
        elif aid == "conveyor_ore_analyzer":
            # 40012: Grade analyzer % (x100 scaling)
            registers["40012"] = int(val * 100)
            
    if worst_status == "Critical":
        system_status = 3
    elif worst_status == "Warning":
        system_status = 2
        
    registers["40001"] = system_status
    # 40002: Live connected WebSocket clients count
    try:
        from app.services.websocket import manager
        ws_count = len(manager.active_connections)
    except Exception:
        ws_count = 0
    registers["40002"] = ws_count
    
    return {
        "dcs_station_id": "DCS_TWIN_GW_01",
        "protocol": "Modbus TCP/IP (Simulated)",
        "holding_registers": registers,
        "sync_time": int(time.time())
    }


# Background broker consumer to ingest alerts and create CMMS work orders automatically
async def handle_alert_for_cmms(topic: str, payload: dict):
    """
    Subscribes to 'industrial/alerts' topic and automatically creates CMMS work orders.
    """
    alert_type = payload.get("type")
    
    # We only process actual new alerts, not secondary vision descriptions
    if alert_type != "alert":
        return
        
    severity = payload.get("severity", "Normal")
    
    # Only raise CMMS work orders for Warning and Critical alerts
    if severity not in ["Warning", "Critical"]:
        return
        
    alert_id = payload.get("alert_id")
    asset_id = payload.get("asset_id", "haul_road_zone_b")
    message = payload.get("message", "")
    
    # Create auto-generated CMMS work order
    wo_id = f"WO-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
    title = f"SAFETY CHECK: {severity} compliance alert on '{asset_id}'"
    description = f"Automated twin alert triggered CMMS ticket. Alert details: {message}"
    assigned_to = "Safety Supervisor (Shift A)" if severity == "Critical" else "Safety Inspector"
    status = "Pending"
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO cmms_work_orders (work_order_id, asset_id, alert_id, title, description, status, assigned_to, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (wo_id, asset_id, alert_id, title, description, status, assigned_to, int(time.time())))
            conn.commit()
        logger.info(f"Automatically created CMMS Work Order: {wo_id} for alert {alert_id}")
    except Exception as e:
        logger.error(f"Failed to automatically log CMMS work order: {e}")
