import os
import time
import logging
import threading
from collections import deque

logger = logging.getLogger("edge.safety_inference")

# Trailing window for rolling compliance (60 seconds)
FRAME_HISTORY = deque()
history_lock = threading.Lock()

# Geofence Polygon (Restricted Crusher/Conveyor Zone)
# Normalized coordinates: [(x1, y1), (x2, y2), ...]
GEOFENCE_POLYGON = [
    (0.55, 0.15),
    (0.95, 0.15),
    (0.95, 0.85),
    (0.55, 0.85)
]

try:
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    import cv2
    import numpy as np
    ML_AVAILABLE = True
    logger.info("Imported ML dependencies successfully.")
except ImportError as e:
    logger.warning(f"ML dependencies not found. Running in high-fidelity simulated CV mode. Details: {e}")
    ML_AVAILABLE = False

MODEL = None

def get_model():
    global MODEL
    if not ML_AVAILABLE:
        return None
    if MODEL is None:
        try:
            logger.info("Retrieving YOLO11 PPE model weights from Hugging Face...")
            model_path = hf_hub_download(repo_id="melihuzunoglu/ppe-detection", filename="best.pt")
            logger.info(f"Loading YOLO11 model from: {model_path}")
            MODEL = YOLO(model_path)
            logger.info("YOLO11 model initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing YOLO11 model: {e}")
            raise e
    return MODEL

def is_point_in_polygon(x, y, polygon):
    """Ray casting algorithm to check if point (x, y) is inside a polygon."""
    num = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(num + 1):
        p2x, p2y = polygon[i % num]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def box_contains_or_intersects(box_h, box_g, threshold=0.4):
    hx1, hy1, hx2, hy2 = box_h
    gx1, gy1, gx2, gy2 = box_g
    
    g_cx = (gx1 + gx2) / 2
    g_cy = (gy1 + gy2) / 2
    if hx1 <= g_cx <= hx2 and hy1 <= g_cy <= hy2:
        return True
        
    ix1 = max(hx1, gx1)
    iy1 = max(hy1, gy1)
    ix2 = min(hx2, gx2)
    iy2 = min(gy2, gy2)
    
    if ix1 < ix2 and iy1 < iy2:
        intersection_area = (ix2 - ix1) * (iy2 - iy1)
        gear_area = (gx2 - gx1) * (gy2 - gy1)
        if gear_area > 0 and (intersection_area / gear_area) >= threshold:
            return True
            
    return False

def analyze_frame(image_bytes: bytes):
    global FRAME_HISTORY
    
    if not ML_AVAILABLE:
        # High-Fidelity Simulation Fallback
        is_anomaly = False
        try:
            from app.database import get_db
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT is_anomaly FROM devices WHERE device_id = 'dev_cv_safety'")
                row = cur.fetchone()
                if row:
                    is_anomaly = bool(row["is_anomaly"])
        except Exception as e:
            logger.debug(f"Failed to read device override status: {e}")

        now = time.time()
        out_detections = []
        
        if is_anomaly:
            # Simulate worker in danger zone with missing helmet (x: 0.75, y: 0.5)
            p_box = [420.0, 160.0, 540.0, 410.0]
            person_count = 1
            active_violations = 1
            zone_breaches = 1
            
            out_detections.append({
                "box": p_box,
                "label": "Worker Violations: NO HELMET, ZONE BREACH",
                "conf": 0.94,
                "color": "#ec4899", # Pink
                "helmet_compliant": False,
                "vest_compliant": True,
                "in_restricted_zone": True
            })
            # Vest
            out_detections.append({
                "box": [430.0, 210.0, 520.0, 330.0],
                "label": "Safety Vest",
                "conf": 0.89,
                "color": "#eab308"
            })
            # Missing helmet alert
            out_detections.append({
                "box": [455.0, 160.0, 505.0, 200.0],
                "label": "Missing Helmet Alert",
                "conf": 0.97,
                "color": "#ef4444"
            })
        else:
            # Simulate fully compliant worker outside danger zone (x: 0.25, y: 0.5)
            p_box = [130.0, 150.0, 230.0, 400.0]
            person_count = 1
            active_violations = 0
            zone_breaches = 0
            
            out_detections.append({
                "box": p_box,
                "label": "Worker (Compliant)",
                "conf": 0.96,
                "color": "#10b981", # Green
                "helmet_compliant": True,
                "vest_compliant": True,
                "in_restricted_zone": False
            })
            # Helmet
            out_detections.append({
                "box": [160.0, 150.0, 210.0, 185.0],
                "label": "Helmet",
                "conf": 0.92,
                "color": "#3b82f6"
            })
            # Safety Vest
            out_detections.append({
                "box": [140.0, 200.0, 220.0, 310.0],
                "label": "Safety Vest",
                "conf": 0.95,
                "color": "#eab308"
            })

        # Update trailing compliance window
        with history_lock:
            cutoff = now - 60.0
            while FRAME_HISTORY and FRAME_HISTORY[0][0] < cutoff:
                FRAME_HISTORY.popleft()
                
            frame_is_compliant = (active_violations == 0) and (zone_breaches == 0)
            FRAME_HISTORY.append((now, True, frame_is_compliant))
            
            total_frames_with_person = sum(1 for item in FRAME_HISTORY if item[1])
            compliant_frames_with_person = sum(1 for item in FRAME_HISTORY if item[1] and item[2])
            
            if total_frames_with_person > 0:
                compliance_pct = round((compliant_frames_with_person / total_frames_with_person) * 100.0, 1)
            else:
                compliance_pct = 100.0

        return {
            "detections": out_detections,
            "person_count": person_count,
            "active_violations": active_violations,
            "zone_breaches": zone_breaches,
            "compliance_pct": compliance_pct
        }

    # Real YOLO11 pipeline
    model = get_model()
    
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
        
    h_img, w_img, _ = img.shape
    
    results = model(img, conf=0.25, verbose=False)
    detections = results[0]
    names = model.names
    
    people = []
    helmets = []
    no_helmets = []
    vests = []
    
    boxes = detections.boxes
    for box in boxes:
        cls_id = int(box.cls[0].item())
        cls_name = names[cls_id].lower()
        conf = float(box.conf[0].item())
        xyxy = box.xyxy[0].tolist()
        
        det_obj = {
            "box": xyxy,
            "conf": conf,
            "cls_id": cls_id,
            "cls_name": cls_name
        }
        
        if "human" in cls_name or "person" in cls_name:
            people.append(det_obj)
        elif "helmet" in cls_name and "no-" not in cls_name:
            helmets.append(det_obj)
        elif "no-helmet" in cls_name:
            no_helmets.append(det_obj)
        elif "vest" in cls_name:
            vests.append(det_obj)
            
    out_detections = []
    violations_count = 0
    breaches_count = 0
    person_count = len(people)
    
    for person in people:
        p_box = person["box"]
        px1, py1, px2, py2 = p_box
        
        p_cx = ((px1 + px2) / 2) / w_img
        p_cy = ((py1 + py2) / 2) / h_img
        
        in_restricted_zone = is_point_in_polygon(p_cx, p_cy, GEOFENCE_POLYGON)
        if in_restricted_zone:
            breaches_count += 1
            
        has_helmet = any(box_contains_or_intersects(p_box, h["box"]) for h in helmets)
        direct_no_helmet = any(box_contains_or_intersects(p_box, nh["box"]) for nh in no_helmets)
        helmet_compliant = has_helmet and not direct_no_helmet
        
        has_vest = any(box_contains_or_intersects(p_box, v["box"]) for v in vests)
        vest_compliant = has_vest
        
        has_violation = (not helmet_compliant) or (not vest_compliant) or in_restricted_zone
        if has_violation:
            violations_count += 1
            
        label_parts = []
        if not helmet_compliant:
            label_parts.append("NO HELMET")
        if not vest_compliant:
            label_parts.append("NO VEST")
        if in_restricted_zone:
            label_parts.append("ZONE BREACH")
            
        label = "Worker (Compliant)" if not has_violation else f"Worker Violations: {', '.join(label_parts)}"
        color = "#ec4899" if has_violation else "#10b981"
        
        out_detections.append({
            "box": p_box,
            "label": label,
            "conf": person["conf"],
            "color": color,
            "helmet_compliant": helmet_compliant,
            "vest_compliant": vest_compliant,
            "in_restricted_zone": in_restricted_zone
        })
        
    for h in helmets:
        out_detections.append({
            "box": h["box"],
            "label": "Helmet",
            "conf": h["conf"],
            "color": "#3b82f6"
        })
    for v in vests:
        out_detections.append({
            "box": v["box"],
            "label": "Safety Vest",
            "conf": v["conf"],
            "color": "#eab308"
        })
    for nh in no_helmets:
        out_detections.append({
            "box": nh["box"],
            "label": "Missing Helmet Alert",
            "conf": nh["conf"],
            "color": "#ef4444"
        })

    now = time.time()
    with history_lock:
        cutoff = now - 60.0
        while FRAME_HISTORY and FRAME_HISTORY[0][0] < cutoff:
            FRAME_HISTORY.popleft()
            
        if person_count > 0:
            frame_is_compliant = (violations_count == 0) and (breaches_count == 0)
            FRAME_HISTORY.append((now, True, frame_is_compliant))
            
        total_frames_with_person = sum(1 for item in FRAME_HISTORY if item[1])
        compliant_frames_with_person = sum(1 for item in FRAME_HISTORY if item[1] and item[2])
        
        if total_frames_with_person > 0:
            compliance_pct = round((compliant_frames_with_person / total_frames_with_person) * 100.0, 1)
        else:
            compliance_pct = 100.0

    return {
        "detections": out_detections,
        "person_count": person_count,
        "active_violations": violations_count,
        "zone_breaches": breaches_count,
        "compliance_pct": compliance_pct
    }
