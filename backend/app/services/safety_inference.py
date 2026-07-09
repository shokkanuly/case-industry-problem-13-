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
    Compares the cropped face against all base64 photos in the database.
    Returns (worker_name, similarity_score) or (None, 0.0)
    """
    if cropped_face is None or not db_workers:
        return None, 0.0
        
    try:
        gray_crop = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2GRAY)
        gray_crop = cv2.equalizeHist(gray_crop)
        gray_crop = cv2.resize(gray_crop, (80, 80))
    except Exception:
        return None, 0.0
    
    best_name = None
    best_score = 0.0
    
    for worker in db_workers:
        photo_b64 = worker.get("photo")
        if not photo_b64:
            continue
        try:
            # Decode base64 photo
            if "," in photo_b64:
                photo_b64 = photo_b64.split(",")[1]
            import base64
            import numpy as np
            img_data = base64.b64decode(photo_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            db_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if db_img is None:
                continue
                
            db_gray = cv2.cvtColor(db_img, cv2.COLOR_BGR2GRAY)
            # Detect face in database photo
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            db_faces = face_cascade.detectMultiScale(db_gray, scaleFactor=1.1, minNeighbors=2, minSize=(30, 30))
            
            if len(db_faces) > 0:
                (x, y, w, h) = db_faces[0]
                db_face_cropped = db_gray[y:y+h, x:x+w]
            else:
                db_face_cropped = db_gray
                
            db_face_cropped = cv2.equalizeHist(db_face_cropped)
            db_face_resized = cv2.resize(db_face_cropped, (80, 80))
            
            res = cv2.matchTemplate(gray_crop, db_face_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            score = (max_val + 1.0) / 2.0  # normalize [-1, 1] to [0, 1]
            
            if score > best_score:
                best_score = score
                best_name = worker["name"]
        except Exception as e:
            logger.debug(f"Error matching face: {e}")
            
    return best_name, best_score

def analyze_frame(image_bytes: bytes):
    global FRAME_HISTORY
    
    # Load workers from SQLite for face recognition
    db_workers = []
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, photo FROM workers")
            db_workers = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.debug(f"Failed to fetch workers: {e}")

    # Detect faces in frame if cv2 is available
    face_detections = []
    recognized_names = []
    img_decoded = None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_decoded is not None:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(img_decoded, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=2, minSize=(30, 30))
            for (x, y, w, h) in faces:
                cropped_face = img_decoded[y:y+h, x:x+w]
                matched_name, score = match_face_in_db(cropped_face, db_workers)
                
                # Check with relaxed matching threshold for higher sensitivity
                if matched_name and score > 0.55:
                    label = f"{matched_name} ({int(score * 100)}% Match)"
                    color = "#3b82f6"  # Blue for recognized
                    recognized_names.append(matched_name)
                else:
                    label = "Неопознанный сотрудник"
                    color = "#ef4444"  # Red for unidentified
                    
                face_detections.append({
                    "box": [float(x), float(y), float(x+w), float(y+h)],
                    "label": f"👤 {label}",
                    "conf": float(score) if score > 0 else 0.99,
                    "color": color
                })
    except Exception as e:
        logger.debug(f"Local face detector error: {e}")

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

        # Append face detections
        out_detections.extend(face_detections)

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
            "compliance_pct": compliance_pct,
            "recognized_workers": recognized_names
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
        
        # Fallback Head Region Face Matcher
        # If Haar cascade face detector failed to match a name for the worker in this person box,
        # crop the top 25% of the YOLO person box and match it directly against base64 DB photos!
        p_width = px2 - px1
        p_height = py2 - py1
        head_box = [px1, py1, px1 + p_width, py1 + p_height * 0.25]
        hx1, hy1, hx2, hy2 = map(int, head_box)
        hx1 = max(0, min(hx1, w_img - 1))
        hy1 = max(0, min(hy1, h_img - 1))
        hx2 = max(0, min(hx2, w_img - 1))
        hy2 = max(0, min(hy2, h_img - 1))
        
        if hx2 > hx1 and hy2 > hy1:
            cropped_head = img[hy1:hy2, hx1:hx2]
            matched_name, score = match_face_in_db(cropped_head, db_workers)
            if matched_name and score > 0.45:
                # Avoid duplicates
                if matched_name not in recognized_names:
                    recognized_names.append(matched_name)
                    # Append a face box specifically on the screen to label Alikhan Aibek!
                    face_detections.append({
                        "box": [float(hx1), float(hy1), float(hx2), float(hy2)],
                        "label": f"👤 {matched_name} ({int(score * 100)}% Match)",
                        "conf": float(score),
                        "color": "#3b82f6"
                    })
        
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

    # Append face recognition detections to the ML detections output list
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
        "recognized_workers": recognized_names
    }
