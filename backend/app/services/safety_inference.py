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

def match_face_in_db(cropped_face, db_workers):
    """
    Compares the cropped face embedding against all enrolled workers' embeddings in database.
    Returns (worker_id, worker_name, worker_section, similarity_score) or (None, None, None, 0.0)
    """
    if cropped_face is None or not db_workers:
        return None, None, None, 0.0
        
    try:
        gray_crop = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2GRAY)
        gray_crop = cv2.equalizeHist(gray_crop)
        gray_crop = cv2.resize(gray_crop, (16, 8))
        vec = gray_crop.flatten().astype(np.float32)
        vec = vec - np.mean(vec)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        curr_embedding = vec.tolist()
    except Exception:
        return None, None, None, 0.0
    
    best_id = None
    best_name = None
    best_section = None
    best_score = 0.0
    
    import json
    for worker in db_workers:
        encoding_str = worker.get("face_encoding")
        if not encoding_str or encoding_str == "[]" or encoding_str == "":
            continue
        try:
            db_embedding = json.loads(encoding_str)
            if not db_embedding or len(db_embedding) != len(curr_embedding):
                continue
                
            # Cosine similarity (dot product of unit normalized vectors)
            score = float(np.dot(curr_embedding, db_embedding))
            # Map similarity from [-1, 1] to [0, 1]
            score = (score + 1.0) / 2.0
            
            if score > best_score:
                best_score = score
                best_id = worker["worker_id"]
                best_name = worker["name"]
                best_section = worker["section"]
        except Exception as e:
            logger.debug(f"Error matching embedding: {e}")
            
    return best_id, best_name, best_section, best_score

def analyze_frame(image_bytes: bytes):
    global FRAME_HISTORY
    
    db_workers = []
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT worker_id, name, section, face_encoding, photo FROM workers")
            db_workers = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.debug(f"Failed to fetch workers: {e}")

    # Decode frame image bytes
    img_decoded = None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.debug(f"Failed to decode image: {e}")

    if img_decoded is None:
        img_decoded = np.zeros((480, 640, 3), dtype=np.uint8)

    h_img, w_img, _ = img_decoded.shape
    face_detections = []
    recognized_names = []
    recognized_info = []

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
        person_count = 0
        violations_count = 0
        breaches_count = 0
        
        if is_anomaly:
            p_box = [420.0, 160.0, 540.0, 410.0]
            person_count = 1
            violations_count = 1
            breaches_count = 1
            
            simulated_worker_id = "w_001"
            simulated_name = "Иванов А.С."
            simulated_section = "Участок №3 — Дробление"
            if db_workers:
                simulated_worker_id = db_workers[0]["worker_id"]
                simulated_name = db_workers[0]["name"]
                simulated_section = db_workers[0]["section"]

            recognized_names.append(simulated_name)
            recognized_info.append({
                "worker_id": simulated_worker_id,
                "name": simulated_name,
                "section": simulated_section,
                "helmet_compliant": False,
                "wrong_section": False,
                "has_violation": True,
                "rule_broken": "no_helmet"
            })
            
            out_detections.append({
                "box": p_box,
                "label": f"Worker Violations: NO HELMET, ZONE BREACH (👤 {simulated_name})",
                "conf": 0.94,
                "color": "#ec4899",
                "helmet_compliant": False,
                "vest_compliant": True,
                "in_restricted_zone": True
            })
            
            out_detections.append({
                "box": [450.0, 170.0, 510.0, 240.0],
                "label": f"👤 {simulated_name} (94% Match)",
                "conf": 0.94,
                "color": "#3b82f6"
            })

        with history_lock:
            cutoff = now - 60.0
            while FRAME_HISTORY and FRAME_HISTORY[0][0] < cutoff:
                FRAME_HISTORY.popleft()
                
            if person_count > 0:
                FRAME_HISTORY.append((now, True, False))
                
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
            "compliance_pct": compliance_pct,
            "recognized_workers": recognized_names,
            "recognized_info": recognized_info
        }

    # Real YOLO11 pipeline
    model = get_model()
    results = model(img_decoded, conf=0.25, verbose=False)
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
            
    # Fallback to Face Cascade detector if YOLO failed to locate a person
    if len(people) == 0:
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(img_decoded, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=2, minSize=(30, 30))
            for (x, y, w, h) in faces:
                px1 = float(max(0, x - w))
                py1 = float(max(0, y))
                px2 = float(min(w_img - 1, x + 2*w))
                py2 = float(min(h_img - 1, y + 4*h))
                people.append({
                    "box": [px1, py1, px2, py2],
                    "conf": 0.85,
                    "cls_id": 1,
                    "cls_name": "human"
                })
        except Exception as e:
            logger.debug(f"Full-frame face cascade error: {e}")

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
        
        # Crop head region (top 35% of person bounding box)
        p_width = px2 - px1
        p_height = py2 - py1
        head_box = [px1, py1, px1 + p_width, py1 + p_height * 0.35]
        hx1, hy1, hx2, hy2 = map(int, head_box)
        hx1 = max(0, min(hx1, w_img - 1))
        hy1 = max(0, min(hy1, h_img - 1))
        hx2 = max(0, min(hx2, w_img - 1))
        hy2 = max(0, min(hy2, h_img - 1))
        
        matched_id = None
        matched_name = None
        matched_section = None
        score = 0.0
        
        if hx2 > hx1 and hy2 > hy1:
            cropped_head = img_decoded[hy1:hy2, hx1:hx2]
            matched_id, matched_name, matched_section, score = match_face_in_db(cropped_head, db_workers)
            
        is_recognized = matched_name is not None and score > 0.55
        
        # Verify section assignment
        section_detected = "Участок №3 — Дробление"
        wrong_section = False
        if is_recognized:
            if matched_section != section_detected:
                wrong_section = True
                
        has_violation = (not helmet_compliant) or wrong_section
        if has_violation:
            violations_count += 1
            
        rules = []
        if not helmet_compliant:
            rules.append("no_helmet")
        if wrong_section:
            rules.append("wrong_section")
        rule_broken = ", ".join(rules) if rules else "none"

        if is_recognized:
            recognized_info.append({
                "worker_id": matched_id,
                "name": matched_name,
                "section": matched_section,
                "helmet_compliant": helmet_compliant,
                "wrong_section": wrong_section,
                "has_violation": has_violation,
                "rule_broken": rule_broken
            })
            recognized_names.append(matched_name)
            
            face_detections.append({
                "box": [float(hx1), float(hy1), float(hx2), float(hy2)],
                "label": f"👤 {matched_name} ({int(score * 100)}%)",
                "conf": float(score),
                "color": "#3b82f6"
            })
        else:
            recognized_info.append({
                "worker_id": None,
                "name": "Неопознанный сотрудник",
                "section": "Неизвестно",
                "helmet_compliant": helmet_compliant,
                "wrong_section": False,
                "has_violation": has_violation,
                "rule_broken": rule_broken
            })
            
        label_parts = []
        if not helmet_compliant:
            label_parts.append("NO HELMET")
        if wrong_section:
            label_parts.append("WRONG SECTION")
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
            "vest_compliant": True,
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

    out_detections.extend(face_detections)

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
        "compliance_pct": compliance_pct,
        "recognized_workers": recognized_names,
        "recognized_info": recognized_info
    }
