from fastapi import APIRouter, Depends, File, UploadFile
from app.models import TelemetryPacket, TelemetryResponse
from app.services.ingestion import process_telemetry
from app.services import analytics as analytics_svc
from app.middleware import verify_api_key
from app.services.safety_inference import analyze_frame
import time
import json
import uuid
import os
import logging
from app.database import get_db
from app.services.websocket import manager

logger = logging.getLogger("edge.telemetry")
LAST_ALERT_LOG = {}


def _process_inference_result(img_bytes: bytes, result: dict):
    """
    Shared helper: save violations/alerts to DB and broadcast WebSocket updates.
    Called by both the HTTP inference endpoint and the WebSocket phone_frame handler.
    """
    now_ts = int(time.time())
    compliance_pct = result["compliance_pct"]
    active_violations = result["active_violations"]
    zone_breaches = result["zone_breaches"]
    person_count = result["person_count"]
    recognized_info = result.get("recognized_info", [])
    section_detected = "Участок №3 — Дробление"

    # Determine status
    if zone_breaches > 0:
        new_status = "Critical"
    elif compliance_pct >= 90.0:
        new_status = "Normal"
    elif compliance_pct >= 70.0:
        new_status = "Warning"
    else:
        new_status = "Critical"

    # Annotated frame for embedding in alerts
    frame_b64 = draw_detections_on_image(img_bytes, result.get("detections", []))

    # Update worker compliance scores
    for info in recognized_info:
        w_id = info.get("worker_id")
        if w_id:
            w_has_viol = info["has_violation"]
            w_status = "Violation" if w_has_viol else "Normal"
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT compliance_score FROM workers WHERE worker_id = ?", (w_id,))
                row = cur.fetchone()
                if row:
                    score = row["compliance_score"]
                    score = max(0.0, score - 5.0) if w_has_viol else min(100.0, score + 1.0)
                    cur.execute(
                        "UPDATE workers SET status = ?, compliance_score = ? WHERE worker_id = ?",
                        (w_status, score, w_id)
                    )
                    conn.commit()

    # Log violations with cooldown
    alerts_fired = 0
    for info in recognized_info:
        if not info["has_violation"]:
            continue
        worker_id = info.get("worker_id")
        worker_name = info["name"]
        rule_broken = info["rule_broken"]

        cooldown_key = worker_id if worker_id else "unidentified"
        last_alert_time = LAST_ALERT_LOG.get(cooldown_key, 0)
        if now_ts - last_alert_time < 5:
            continue
        LAST_ALERT_LOG[cooldown_key] = now_ts

        # Save frame to disk
        violation_id = f"viol_{now_ts}_{uuid.uuid4().hex[:6]}"
        frame_filename = f"frame_{violation_id}.jpg"
        frame_dir = "static/violations"
        os.makedirs(frame_dir, exist_ok=True)
        frame_filepath = os.path.join(frame_dir, frame_filename)
        try:
            with open(frame_filepath, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.error(f"Failed to write violation frame: {e}")

        frame_path = f"/static/violations/{frame_filename}"

        # Build human-readable reason string
        reason_parts = []
        if "no_helmet" in rule_broken:
            reason_parts.append("без каски")
        if "no_ear_protection" in rule_broken:
            reason_parts.append("без защиты ушей")
        if "no_vest" in rule_broken:
            reason_parts.append("без жилета")
        if "wrong_section" in rule_broken:
            reason_parts.append(f"не на своём участке")
        reason_str = ", ".join(reason_parts) if reason_parts else rule_broken
        message = f"[{worker_name}] Нарушение ТБ: {reason_str}"

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO violations (violation_id, worker_id, rule_broken, section_detected, frame_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (violation_id, worker_id, rule_broken, section_detected, frame_path, now_ts))
            conn.commit()

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO alerts (alert_id, asset_id, severity, message, created_at, frame_image)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (violation_id, "haul_road_zone_b", "Critical", message, now_ts, frame_b64))
            conn.commit()

        manager.enqueue({
            "type": "alert",
            "alert_id": violation_id,
            "asset_id": "haul_road_zone_b",
            "severity": "Critical",
            "message": message,
            "created_at": now_ts,
            "frame_image": frame_b64
        })
        alerts_fired += 1

    # Update asset digital twin
    meta_dict = {
        "ppe_compliance_pct": compliance_pct,
        "active_violations": active_violations,
        "zone_breaches": zone_breaches,
        "person_count": person_count,
        "worker_in_danger_zone": zone_breaches > 0
    }
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

    return alerts_fired, new_status



def draw_detections_on_image(img_bytes: bytes, detections: list) -> str:
    """Draws bounding boxes and labels on the image and returns a base64 string."""
    import cv2
    import numpy as np
    import base64
    
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("utf-8")
            
        for det in detections:
            box = det.get("box")
            if not box:
                continue
            x1, y1, x2, y2 = map(int, box)
            label = det.get("label", "")
            hex_color = det.get("color", "#ef4444").lstrip('#')
            if len(hex_color) == 6:
                color_bgr = tuple(int(hex_color[i:i+2], 16) for i in (4, 2, 0))
            else:
                color_bgr = (0, 0, 255)
                
            # Draw box
            cv2.rectangle(img, (x1, y1), (x2, y2), color_bgr, 2)
            # Draw label background
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            cv2.rectangle(img, (x1, y1 - 20), (x1 + w, y1), color_bgr, -1)
            # Draw text
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            
        _, encoded_img = cv2.imencode('.jpg', img)
        return "data:image/jpeg;base64," + base64.b64encode(encoded_img.tobytes()).decode("utf-8")
    except Exception as e:
        import base64
        return "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("utf-8")

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
    Accepts a JPEG frame, runs YOLO11 + InsightFace ArcFace,
    logs violations, updates DB, broadcasts WebSocket updates.
    """
    img_bytes = await file.read()
    result = analyze_frame(img_bytes)

    now_ts = int(time.time())
    compliance_pct = result["compliance_pct"]

    # Write telemetry log entry
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO telemetry_log
                (device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "dev_cv_safety", "logistics_safety", "safety_scan",
            float(compliance_pct), "%", now_ts, 4.2, -45, now_ts
        ))
        conn.commit()

    # Delegate all violation logging / DB updates / WebSocket broadcast to shared helper
    alerts_fired, new_status = _process_inference_result(img_bytes, result)

    return {
        "status": "ok",
        "detections": result["detections"],
        "person_count": result["person_count"],
        "active_violations": result["active_violations"],
        "zone_breaches": result["zone_breaches"],
        "compliance_pct": compliance_pct,
        "current_status": new_status,
        "alerts_fired": alerts_fired
    }



# ── Debug endpoint — per the final plan spec ────────────────────────────────
router_debug = APIRouter(prefix="/api/debug", tags=["debug"])

@router_debug.get("/raw-db-dump")
async def raw_db_dump():
    """
    Raw database dump for manual verification.
    Check that:
    1. workers table has 512-d embeddings (not 128-d pixel hashes)
    2. violations table has real rows written by the inference pipeline
    """
    import json
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT worker_id, name, section, face_encoding, status, compliance_score FROM workers")
        workers_raw = cur.fetchall()

        cur.execute("""
            SELECT v.violation_id, v.worker_id, w.name as worker_name,
                   v.rule_broken, v.section_detected, v.frame_path,
                   v.created_at,
                   CASE WHEN v.description IS NOT NULL THEN 'yes' ELSE 'pending' END as has_description
            FROM violations v
            LEFT JOIN workers w ON v.worker_id = w.worker_id
            ORDER BY v.created_at DESC
            LIMIT 50
        """)
        violations_raw = cur.fetchall()

    workers_out = []
    for w in workers_raw:
        enc = w["face_encoding"]
        try:
            parsed = json.loads(enc)
            emb_dim = len(parsed)
            emb_type = "ArcFace (512-d ✓)" if emb_dim == 512 else f"STALE pixel hash ({emb_dim}-d — re-enroll!)"
        except Exception:
            emb_dim = 0
            emb_type = "invalid / empty"

        workers_out.append({
            "worker_id": w["worker_id"],
            "name": w["name"],
            "section": w["section"],
            "embedding_dim": emb_dim,
            "embedding_type": emb_type,
            "status": w["status"],
            "compliance_score": w["compliance_score"]
        })

    violations_out = [dict(v) for v in violations_raw]

    return {
        "summary": {
            "total_workers": len(workers_out),
            "workers_with_arcface": sum(1 for w in workers_out if w["embedding_dim"] == 512),
            "workers_needing_reenrollment": sum(1 for w in workers_out if w["embedding_dim"] != 512),
            "total_violations": len(violations_out)
        },
        "workers": workers_out,
        "violations": violations_out
    }
