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
    """
    Add a new worker to the safety database.
    Computes a 512-dimensional ArcFace embedding from the uploaded photo.
    The embedding is stored in face_encoding and used for live camera face recognition.
    """
    import uuid
    import json
    import base64
    import numpy as np
    import cv2
    from fastapi import HTTPException

    worker_id = f"w_{uuid.uuid4().hex[:6]}"
    section = worker.role  # role field = assigned work section
    face_encoding_json = "[]"

    if worker.photo:
        try:
            photo_b64 = worker.photo
            if "," in photo_b64:
                photo_b64 = photo_b64.split(",")[1]
            img_data = base64.b64decode(photo_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                raise HTTPException(status_code=400, detail="Could not decode the uploaded photo.")

            # Try InsightFace ArcFace first (512-d neural embedding — preferred)
            try:
                from app.services.safety_inference import get_face_app, INSIGHTFACE_AVAILABLE
                face_app = get_face_app()
                if face_app is not None:
                    # Resize to at least 640px wide so RetinaFace can detect the face
                    h, w = img.shape[:2]
                    if w < 320:
                        scale = 320 / w
                        img = cv2.resize(img, (int(w * scale), int(h * scale)))

                    faces = face_app.get(img)
                    if not faces:
                        # Try with a larger det_size if face not found
                        logger.warning("InsightFace: no face found in enrollment photo. Try a clearer, front-facing photo.")
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "No face detected in the uploaded photo. "
                                "Please use a clear, front-facing photo with good lighting."
                            )
                        )

                    # Use the largest face (closest to camera)
                    largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                    emb = largest.embedding.astype(np.float32)
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb = emb / norm
                    face_encoding_json = json.dumps(emb.tolist())
                    logger.info(f"ArcFace enrollment success for '{worker.name}': 512-d embedding computed (face score={largest.det_score:.3f})")
                else:
                    raise RuntimeError("InsightFace app not initialized")
            except HTTPException:
                raise  # Re-raise 400 errors directly
            except Exception as e:
                logger.warning(f"InsightFace enrollment failed, falling back to Haar+grayscale: {e}")
                # Fallback: Haar Cascade + grayscale embedding (128-d — lower accuracy)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                detected = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
                face_crop = img[detected[0][1]:detected[0][1]+detected[0][3], detected[0][0]:detected[0][0]+detected[0][2]] if len(detected) > 0 else img
                gray_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                gray_crop = cv2.equalizeHist(gray_crop)
                gray_crop = cv2.resize(gray_crop, (16, 8))
                vec = gray_crop.flatten().astype(np.float32)
                vec = vec - np.mean(vec)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                face_encoding_json = json.dumps(vec.tolist())
                logger.warning(f"Used Haar fallback embedding (128-d) for '{worker.name}' — accuracy will be lower.")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during enrollment for '{worker.name}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process photo: {str(e)}")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workers (worker_id, name, section, face_encoding, status, compliance_score, photo)
            VALUES (?, ?, ?, ?, 'Normal', 100.0, ?)
        """, (worker_id, worker.name, section, face_encoding_json, worker.photo))
        conn.commit()

    embedding_dim = len(json.loads(face_encoding_json)) if face_encoding_json != "[]" else 0
    logger.info(f"Worker enrolled: {worker.name} (id={worker_id}, section={section}, embedding_dim={embedding_dim})")
    return {
        "status": "ok",
        "worker_id": worker_id,
        "name": worker.name,
        "section": section,
        "embedding_dim": embedding_dim,
        "photo": worker.photo
    }



@router.delete("/personnel/{worker_id}")
async def delete_personnel(worker_id: str, _: str = Depends(verify_api_key)):
    """Remove a worker from the safety database."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))
        conn.commit()
        return {"status": "ok", "deleted_id": worker_id}


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


@router.get("/debug/raw-db-dump")
async def raw_db_dump():
    """Returns raw rows from assets, alerts, workers, and telemetry for transparency verification."""
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM assets")
        assets = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM alerts ORDER BY created_at DESC")
        alerts = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT name, role, status, compliance_score FROM workers")
        workers = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM telemetry_log ORDER BY timestamp DESC LIMIT 50")
        telemetry = [dict(row) for row in cur.fetchall()]
        
    return {
        "assets": assets,
        "alerts": alerts,
        "workers": workers,
        "telemetry_log_latest_50": telemetry
    }

