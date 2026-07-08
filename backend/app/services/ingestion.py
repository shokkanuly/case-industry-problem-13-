import time
import logging
import json
import os
from app.database import get_db
from app.models import TelemetryPacket, TelemetryResponse
from app.services.websocket import manager

logger = logging.getLogger("edge.ingestion")

# ── Load Case Registry ──
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "case_registry.json")

try:
    with open(REGISTRY_PATH, "r") as f:
        registry_data = json.load(f)
        CASE_REGISTRY = {c["device_id"]: c for c in registry_data["cases"]}
except Exception as e:
    logger.error(f"Failed to load case registry: {e}")
    CASE_REGISTRY = {}


def process_telemetry(packet: TelemetryPacket) -> TelemetryResponse:
    """
    Registry-driven Ingestion Pipeline:
    1. Parse payload and fix timestamps
    2. Log raw telemetry and update devices registry
    3. Look up device_id in Case Registry
    4. Route processing by output_type (status, recommendation, batch_report)
    5. Detect status transitions and log to 'alerts' table
    6. Upsert Digital Twin ('assets') table and broadcast via WebSocket
    """
    server_ts = int(time.time())
    device_ts = packet.timestamp if packet.timestamp else server_ts

    # ── Step 1: Raw Telemetry Log & Device Tracker ──
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO telemetry_log
                (device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            packet.device_id,
            packet.device_type,
            packet.event,
            packet.value,
            packet.unit,
            device_ts,
            packet.battery_v,
            packet.rssi_dbm,
            server_ts
        ))

        cur.execute("""
            INSERT INTO devices (device_id, device_type, first_seen, last_seen, last_value, last_unit, battery_v, rssi_dbm, total_events)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(device_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                last_value = excluded.last_value,
                last_unit = excluded.last_unit,
                battery_v = excluded.battery_v,
                rssi_dbm = excluded.rssi_dbm,
                total_events = total_events + 1
        """, (
            packet.device_id,
            packet.device_type,
            server_ts,
            server_ts,
            packet.value,
            packet.unit,
            packet.battery_v,
            packet.rssi_dbm
        ))
        conn.commit()

    # ── Step 2: Case Registry Lookup ──
    case_entry = CASE_REGISTRY.get(packet.device_id)
    alerts_fired = 0

    if case_entry:
        asset_id = case_entry["asset_id"]
        asset_name = case_entry["asset_name"]
        asset_type = case_entry["category"]
        parent_asset_id = case_entry.get("zone_id")
        zone_id = case_entry.get("zone_id")
        output_type = case_entry["output_type"]

        # Default twin parameters
        status = None
        risk_score = packet.risk_score if packet.risk_score is not None else 0.0
        recommended_value = None
        current_deviation = None
        report_ref = None

        meta_dict = packet.metadata if packet.metadata is not None else {}

        # Fetch previous status for transition detection
        prev_status = None
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM assets WHERE asset_id = ?", (asset_id,))
            row = cur.fetchone()
            if row:
                prev_status = row["status"]

        # ── Step 3: Route Ingestion by Output Type ──
        if output_type == "status":
            if risk_score < 40.0:
                status = "Normal"
            elif risk_score < 75.0:
                status = "Warning"
            else:
                status = "Critical"

        elif output_type == "recommendation":
            if asset_id == "vanyukov_furnace_1":
                recommended_value = 12.5
            elif asset_id == "conveyor_ore_analyzer":
                recommended_value = 1.5
            elif asset_id == "grinding_mill_energy":
                recommended_value = 2200.0
            else:
                recommended_value = 0.0

            current_deviation = round(packet.value - recommended_value, 2)
            abs_dev = abs(current_deviation)

            if asset_id == "grinding_mill_energy":
                if abs_dev < 200.0:
                    status = "Normal"
                elif abs_dev < 400.0:
                    status = "Warning"
                else:
                    status = "Critical"
            elif asset_id == "conveyor_ore_analyzer":
                if abs_dev < 0.2:
                    status = "Normal"
                elif abs_dev < 0.5:
                    status = "Warning"
                else:
                    status = "Critical"
            else:
                if abs_dev < 1.0:
                    status = "Normal"
                elif abs_dev < 2.0:
                    status = "Warning"
                else:
                    status = "Critical"

            meta_dict["recommended_value"] = recommended_value
            meta_dict["current_deviation"] = current_deviation

        elif output_type == "batch_report":
            status = None
            report_ref = f"/reports/{asset_id}_{device_ts}.json"
            meta_dict["report_url"] = report_ref
            meta_dict["scan_timestamp"] = device_ts

        # ── Step 4: Status Transition & Alert History Logger ──
        if status != prev_status:
            alert_id = f"alt_{device_ts}_{asset_id}"
            severity = status if status in ["Warning", "Critical"] else "Normal"

            if status == "Normal":
                message = f"Asset '{asset_name}' returned to Normal state."
            elif status == "Warning":
                if output_type == "recommendation":
                    message = f"Asset '{asset_name}' optimal deviation Warning: {current_deviation:+.2f}% deviation."
                else:
                    message = f"Asset '{asset_name}' entered Warning state. (Risk: {risk_score}%)"
            else:  # Critical
                if output_type == "recommendation":
                    message = f"Asset '{asset_name}' optimal deviation Critical: {current_deviation:+.2f}% deviation."
                else:
                    message = f"Asset '{asset_name}' entered Critical state! (Risk: {risk_score}%)"

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO alerts (alert_id, asset_id, severity, message, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (alert_id, asset_id, severity, message, device_ts))
                conn.commit()

            alerts_fired = 1

            # Push alert to WebSocket
            manager.enqueue({
                "type": "alert",
                "alert_id": alert_id,
                "asset_id": asset_id,
                "severity": severity,
                "message": message,
                "created_at": device_ts
            })

            # Trigger Gemini Vision analysis for Warning or Critical safety events
            if asset_id == "haul_road_zone_b" and status in ["Warning", "Critical"]:
                import asyncio
                from app.services.gemini_incident import call_gemini_incident_description
                
                # Check for label summaries in metadata
                label_summary = ""
                if meta_dict.get("zone_breaches", 0) > 0:
                    label_summary = "Intrusion in restricted Crusher Zone"
                else:
                    violations = meta_dict.get("active_violations", 0)
                    label_summary = f"Safety compliance drop ({violations} active PPE violations)"
                
                async def run_gemini_vision(aid=alert_id, lsum=label_summary):
                    description = await call_gemini_incident_description(None, lsum)
                    # Broadcast description updates via WebSockets
                    manager.enqueue({
                        "type": "violation_description",
                        "alert_id": aid,
                        "description": description
                    })
                    # Update SQLite alerts table
                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE alerts SET message = ? WHERE alert_id = ?",
                            (description, aid)
                        )
                        conn.commit()
                
                asyncio.create_task(run_gemini_vision())

        # ── Step 5: Save Digital Twin Asset ──
        meta_json = json.dumps(meta_dict)
        
        last_value_to_save = packet.value
        if asset_id == "haul_road_zone_b" and "ppe_compliance_pct" in meta_dict:
            last_value_to_save = meta_dict["ppe_compliance_pct"]

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO assets (
                    asset_id, asset_name, asset_type, parent_asset_id, zone_id,
                    output_type, status, risk_score, recommended_value, current_deviation,
                    report_ref, last_value, last_unit, last_seen, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    status = excluded.status,
                    risk_score = excluded.risk_score,
                    recommended_value = COALESCE(excluded.recommended_value, recommended_value),
                    current_deviation = COALESCE(excluded.current_deviation, current_deviation),
                    report_ref = COALESCE(excluded.report_ref, report_ref),
                    last_value = excluded.last_value,
                    last_unit = excluded.last_unit,
                    last_seen = excluded.last_seen,
                    metadata = excluded.metadata
            """, (
                asset_id, asset_name, asset_type, parent_asset_id, zone_id,
                output_type, status, risk_score, recommended_value, current_deviation,
                report_ref, last_value_to_save, packet.unit, device_ts, meta_json
            ))
            conn.commit()

        # Enqueue updated asset details for WebSocket broadcast
        manager.enqueue({
            "type": "asset",
            "asset_id": asset_id,
            "asset_name": asset_name,
            "asset_type": asset_type,
            "parent_asset_id": parent_asset_id,
            "zone_id": zone_id,
            "output_type": output_type,
            "status": status,
            "risk_score": risk_score,
            "recommended_value": recommended_value,
            "current_deviation": current_deviation,
            "report_ref": report_ref,
            "last_value": packet.value,
            "last_unit": packet.unit,
            "last_seen": device_ts,
            "metadata": meta_dict
        })
    else:
        logger.warning(f"Ingested device '{packet.device_id}' has no matching registry config.")

    return TelemetryResponse(
        device_id=packet.device_id,
        server_ts=server_ts,
        alerts_fired=alerts_fired
    )

