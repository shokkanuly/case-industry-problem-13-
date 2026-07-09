from fastapi import APIRouter, Depends, File, UploadFile
from app.models import TelemetryPacket, TelemetryResponse
from app.services.ingestion import process_telemetry
from app.services import analytics as analytics_svc
from app.middleware import verify_api_key
from app.services.safety_inference import analyze_frame
import time
import json
from app.database import get_db
from app.services.websocket import manager

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryResponse)
async def ingest_telemetry(
    packet: TelemetryPacket,
    _: str = Depends(verify_api_key)
):
    """Ingest a telemetry packet from an edge device."""
    return process_telemetry(packet)


@router.get("/latest")
async def get_latest(
    limit: int = 20,
    _: str = Depends(verify_api_key)
):
    """Get the most recent telemetry readings."""
    return analytics_svc.get_telemetry_latest(limit=min(limit, 100))


@router.get("/history")
async def get_history(
    device_id: str,
    hours: int = 24,
    _: str = Depends(verify_api_key)
):
    """Get telemetry history for a specific device."""
    return analytics_svc.get_telemetry_history(device_id=device_id, hours=min(hours, 168))


@router.post("/case13/inference")
async def case13_inference(
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key)
):
    """
    Case 13 PPE & Safety Compliance Inference Endpoint.
    Accepts a frame upload, runs YOLO11, pairs workers with gear,
    calculates rolling compliance, updates the assets + alerts db tables,
    and broadcasts via websocket.
    """
    # Read image bytes
    img_bytes = await file.read()
    
    # Run inference and compliance checks
    result = analyze_frame(img_bytes)
    
    # Get current timestamp
    now_ts = int(time.time())
    
    # Extract values
    compliance_pct = result["compliance_pct"]
    active_violations = result["active_violations"]
    zone_breaches = result["zone_breaches"]
    person_count = result["person_count"]
    
    # Determine overall status
    if zone_breaches > 0:
        new_status = "Critical"
    elif compliance_pct >= 90.0:
        new_status = "Normal"
    elif compliance_pct >= 70.0:
        new_status = "Warning"
    else:
        new_status = "Critical"
        
    # Fetch previous status from DB to check for transitions
    prev_status = None
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM assets WHERE asset_id = 'haul_road_zone_b'")
        row = cur.fetchone()
        if row:
            prev_status = row["status"]
            
    # Update telemetry log
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO telemetry_log
                (device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "dev_cv_safety",
            "logistics_safety",
            "safety_scan",
            float(compliance_pct),
            "%",
            now_ts,
            4.2,
            -45,
            now_ts
        ))
        conn.commit()
        
    # Update recognized workers status and compliance ratings in DB
    recognized_workers = result.get("recognized_workers", [])
    if recognized_workers:
        with get_db() as conn:
            cur = conn.cursor()
            for worker_name in recognized_workers:
                has_violation = (active_violations > 0) or (zone_breaches > 0)
                new_w_status = "Violation" if has_violation else "Normal"
                
                cur.execute("SELECT compliance_score FROM workers WHERE name = ?", (worker_name,))
                row = cur.fetchone()
                if row:
                    score = row["compliance_score"]
                    if has_violation:
                        score = max(0.0, score - 5.0)
                    else:
                        score = min(100.0, score + 1.0)
                    cur.execute(
                        "UPDATE workers SET status = ?, compliance_score = ? WHERE name = ?",
                        (new_w_status, score, worker_name)
                    )
            conn.commit()

    alerts_fired = 0
    
    # Transition Alert
    if new_status != prev_status:
        import uuid
        alert_id = f"alt_{now_ts}_{uuid.uuid4().hex[:6]}_haul_road_zone_b"
        if new_status == "Normal":
            message = "Safety compliance status: normal. PPE compliance recovered to 90%+."
        elif new_status == "Warning":
            message = f"Warning: PPE Compliance dropped to {compliance_pct}%. Missing gear detected."
        else:
            if zone_breaches > 0:
                message = f"CRITICAL: Intrusion detected in Restricted Crusher Zone!"
            else:
                message = f"CRITICAL: PPE Compliance dropped below 70% (current: {compliance_pct}%)."
                
        # Prefix the message with the recognized worker name(s) for the alerts log
        if recognized_workers:
            worker_prefix = ", ".join(recognized_workers)
            message = f"[{worker_prefix}] {message}"

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO alerts (alert_id, asset_id, severity, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (alert_id, "haul_road_zone_b", new_status, message, now_ts))
            conn.commit()
            
        alerts_fired += 1
        
        # Push to WebSocket
        manager.enqueue({
            "type": "alert",
            "alert_id": alert_id,
            "asset_id": "haul_road_zone_b",
            "severity": new_status,
            "message": message,
            "created_at": now_ts
        })
        
        # Trigger Gemini Vision analysis in the background if a violation occurs
        if new_status in ["Warning", "Critical"]:
            import asyncio
            from app.services.gemini_incident import call_gemini_incident_description
            
            # Construct description label summary
            label_summary = ""
            if zone_breaches > 0:
                label_summary = "Intrusion in geofenced Crusher Zone"
            else:
                violations_list = []
                for det in result.get("detections", []):
                    if "no-helmet" in det.get("label", "") or "no-vest" in det.get("label", ""):
                        violations_list.append(det["label"])
                label_summary = ", ".join(violations_list) if violations_list else "Missing safety gear"
                
            async def run_gemini_vision(aid=alert_id, lsum=label_summary, img_b=img_bytes):
                description = await call_gemini_incident_description(img_b, lsum)
                
                final_desc = description
                if recognized_workers:
                    worker_prefix = ", ".join(recognized_workers)
                    final_desc = f"[{worker_prefix}] {description}"
                
                # Broadcast description update via WebSockets
                manager.enqueue({
                    "type": "violation_description",
                    "alert_id": aid,
                    "description": final_desc
                })
                # Update SQLite alerts table
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE alerts SET message = ? WHERE alert_id = ?",
                        (final_desc, aid)
                    )
                    conn.commit()
            
            asyncio.create_task(run_gemini_vision())
        
    # Save Digital Twin Asset Update
    meta_dict = {
        "ppe_compliance_pct": compliance_pct,
        "active_violations": active_violations,
        "zone_breaches": zone_breaches,
        "person_count": person_count,
        "worker_in_danger_zone": zone_breaches > 0
    }
    
    # Risk score calculation (high compliance = low risk)
    risk_score = 100.0 if zone_breaches > 0 else (100.0 - compliance_pct)
    
    meta_json = json.dumps(meta_dict)
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
                last_value = excluded.last_value,
                last_unit = excluded.last_unit,
                last_seen = excluded.last_seen,
                metadata = excluded.metadata
        """, (
            "haul_road_zone_b", "Haul Road Zone B", "logistics_safety", "haul_road_b", "haul_road_b",
            "status", new_status, risk_score, None, None,
            None, compliance_pct, "%", now_ts, meta_json
        ))
        conn.commit()
        
    # Broadcast asset twin update
    manager.enqueue({
        "type": "asset",
        "asset_id": "haul_road_zone_b",
        "asset_name": "Haul Road Zone B",
        "asset_type": "logistics_safety",
        "parent_asset_id": "haul_road_b",
        "zone_id": "haul_road_b",
        "output_type": "status",
        "status": new_status,
        "risk_score": risk_score,
        "last_value": compliance_pct,
        "last_unit": "%",
        "last_seen": now_ts,
        "metadata": meta_dict
    })
    
    return {
        "status": "ok",
        "detections": result["detections"],
        "person_count": person_count,
        "active_violations": active_violations,
        "zone_breaches": zone_breaches,
        "compliance_pct": compliance_pct,
        "current_status": new_status,
        "alerts_fired": alerts_fired
    }
