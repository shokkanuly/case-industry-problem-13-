"""
Case 13 — Safety Inference Engine
- YOLO11: PPE detection (helmet/no-helmet/vest/person) on every frame
- InsightFace buffalo_l: ArcFace 512-d embeddings for face recognition (only when violation detected)
- Section/zone logic: geofence polygon + worker section assignment check
"""
import os
import time
import json
import logging
import threading
from collections import deque

logger = logging.getLogger("edge.safety_inference")

# Rolling compliance window (60 seconds of frame history)
FRAME_HISTORY = deque()
history_lock = threading.Lock()

# Geofence Polygon (Restricted Crusher/Conveyor Zone on the camera frame)
# Normalized coordinates [(x_pct, y_pct)...] — right 40% of frame is the restricted zone
GEOFENCE_POLYGON = [
    (0.55, 0.15),
    (0.95, 0.15),
    (0.95, 0.85),
    (0.55, 0.85)
]

# ── YOLO model ──────────────────────────────────────────────────────────────
try:
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    import cv2
    import numpy as np
    ML_AVAILABLE = True
    logger.info("Imported YOLO + CV2 dependencies successfully.")
except ImportError as e:
    logger.warning(f"YOLO/CV2 not found: {e}. Running in simulation fallback mode.")
    ML_AVAILABLE = False

MODEL = None

def get_model():
    global MODEL
    if not ML_AVAILABLE:
        return None
    if MODEL is None:
        try:
            logger.info("Downloading YOLO PPE model from Hugging Face...")
            model_path = hf_hub_download(repo_id="melihuzunoglu/ppe-detection", filename="best.pt")
            logger.info(f"Loading YOLO model from: {model_path}")
            MODEL = YOLO(model_path)
            logger.info(f"YOLO model loaded. Classes: {MODEL.names}")
        except Exception as e:
            logger.error(f"Error loading YOLO model: {e}")
            raise e
    return MODEL

# ── InsightFace ArcFace model ─────────────────────────────────────────────
FACE_APP = None
INSIGHTFACE_AVAILABLE = False

def get_face_app():
    """Lazy-load InsightFace buffalo_l (RetinaFace detector + ArcFace 512-d embeddings)."""
    global FACE_APP, INSIGHTFACE_AVAILABLE
    if FACE_APP is not None:
        return FACE_APP
    try:
        import insightface
        from insightface.app import FaceAnalysis
        logger.info("Initializing InsightFace buffalo_l (ArcFace) model...")
        app = FaceAnalysis(
            name="buffalo_l",
            root=os.path.expanduser("~/.insightface"),
            providers=["CPUExecutionProvider"]
        )
        # det_size must be divisible by 32; 640 gives good accuracy/speed balance
        app.prepare(ctx_id=-1, det_size=(640, 640))
        FACE_APP = app
        INSIGHTFACE_AVAILABLE = True
        logger.info("InsightFace ArcFace initialized successfully (512-d embeddings).")
    except Exception as e:
        logger.warning(f"InsightFace not available: {e}. Face recognition will be disabled.")
        INSIGHTFACE_AVAILABLE = False
    return FACE_APP


# ── Geometry helpers ─────────────────────────────────────────────────────
def is_point_in_polygon(x, y, polygon):
    """Ray casting algorithm — returns True if (x, y) is inside the polygon."""
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
    """Return True if gear box centroid is inside person box, or overlap ratio ≥ threshold."""
    hx1, hy1, hx2, hy2 = box_h
    gx1, gy1, gx2, gy2 = box_g

    g_cx = (gx1 + gx2) / 2
    g_cy = (gy1 + gy2) / 2
    if hx1 <= g_cx <= hx2 and hy1 <= g_cy <= hy2:
        return True

    ix1 = max(hx1, gx1)
    iy1 = max(hy1, gy1)
    ix2 = min(hx2, gx2)
    iy2 = min(hy2, gy2)

    if ix1 < ix2 and iy1 < iy2:
        intersection_area = (ix2 - ix1) * (iy2 - iy1)
        gear_area = (gx2 - gx1) * (gy2 - gy1)
        if gear_area > 0 and (intersection_area / gear_area) >= threshold:
            return True

    return False


# ── InsightFace face recognition ────────────────────────────────────────
def match_face_arcface(img_bgr, db_workers):
    """
    Run InsightFace on the full frame → find faces → compare ArcFace embeddings
    against enrolled workers in DB.
    
    Returns list of matches: [(worker_id, name, section, similarity_score, face_bbox), ...]
    Only returns matches above the MATCH_THRESHOLD.
    """
    MATCH_THRESHOLD = 0.45  # ArcFace cosine similarity threshold (tuned for real-world use)
    
    face_app = get_face_app()
    if face_app is None or not INSIGHTFACE_AVAILABLE:
        return []
    
    if not db_workers:
        return []
    
    # Collect valid enrolled embeddings
    enrolled = []
    for worker in db_workers:
        enc_str = worker.get("face_encoding", "")
        if not enc_str or enc_str in ("[]", "", "null"):
            continue
        try:
            vec = json.loads(enc_str)
            if len(vec) != 512:
                # Old-format (128-d pixel hash) — skip, needs re-enrollment
                logger.debug(f"Skipping worker {worker['worker_id']}: stale 128-d embedding (needs re-enrollment)")
                continue
            arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            enrolled.append({
                "worker_id": worker["worker_id"],
                "name": worker["name"],
                "section": worker["section"],
                "embedding": arr
            })
        except Exception as e:
            logger.debug(f"Failed to parse embedding for worker {worker.get('worker_id')}: {e}")

    if not enrolled:
        logger.debug("No valid ArcFace embeddings in DB — all workers need re-enrollment.")
        return []

    # Run InsightFace on the full frame (it handles face detection internally)
    try:
        faces = face_app.get(img_bgr)
    except Exception as e:
        logger.warning(f"InsightFace inference error: {e}")
        return []

    if not faces:
        return []

    results = []
    for face in faces:
        if face.embedding is None:
            continue

        # Normalize live embedding
        live_emb = face.embedding.astype(np.float32)
        norm = np.linalg.norm(live_emb)
        if norm > 0:
            live_emb = live_emb / norm

        best_id = None
        best_name = None
        best_section = None
        best_score = 0.0

        for enrolled_worker in enrolled:
            score = float(np.dot(live_emb, enrolled_worker["embedding"]))
            # ArcFace cosine similarity: 1.0 = same face, 0.0 = unrelated
            # Normalize from [-1, 1] → [0, 1] for display
            score_normalized = (score + 1.0) / 2.0
            if score_normalized > best_score:
                best_score = score_normalized
                best_id = enrolled_worker["worker_id"]
                best_name = enrolled_worker["name"]
                best_section = enrolled_worker["section"]

        bbox = face.bbox.tolist() if face.bbox is not None else None

        if best_score >= MATCH_THRESHOLD:
            results.append({
                "worker_id": best_id,
                "name": best_name,
                "section": best_section,
                "score": best_score,
                "face_bbox": bbox
            })
            logger.info(f"Face matched: {best_name} (score={best_score:.3f})")
        else:
            # Detected a face but couldn't match it
            results.append({
                "worker_id": None,
                "name": "Неопознанный сотрудник",
                "section": None,
                "score": best_score,
                "face_bbox": bbox
            })
            logger.debug(f"Face detected but unmatched (best score={best_score:.3f}, threshold={MATCH_THRESHOLD})")

    return results


# ── Main inference entry point ───────────────────────────────────────────
def analyze_frame(image_bytes: bytes):
    global FRAME_HISTORY

    # Load enrolled workers from DB
    db_workers = []
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT worker_id, name, section, face_encoding FROM workers")
            db_workers = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.debug(f"Failed to fetch workers: {e}")

    # Decode JPEG frame
    img_decoded = None
    if ML_AVAILABLE:
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img_decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.debug(f"Failed to decode image: {e}")

    if img_decoded is None and ML_AVAILABLE:
        img_decoded = np.zeros((480, 640, 3), dtype=np.uint8)

    h_img = img_decoded.shape[0] if img_decoded is not None else 480
    w_img = img_decoded.shape[1] if img_decoded is not None else 640

    recognized_names = []
    recognized_info = []

    # ── Simulation Fallback (if ML deps not installed) ────────────────────
    if not ML_AVAILABLE:
        is_anomaly = False
        try:
            from app.database import get_db
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT is_anomaly FROM devices WHERE device_id = 'dev_cv_safety'")
                row = cur.fetchone()
                if row:
                    is_anomaly = bool(row["is_anomaly"])
        except Exception:
            pass

        now = time.time()
        out_detections = []
        person_count = 0
        violations_count = 0
        breaches_count = 0

        if is_anomaly and db_workers:
            p_box = [420.0, 160.0, 540.0, 410.0]
            person_count = 1
            violations_count = 1
            w = db_workers[0]
            recognized_info.append({
                "worker_id": w["worker_id"],
                "name": w["name"],
                "section": w["section"],
                "helmet_compliant": False,
                "wrong_section": False,
                "has_violation": True,
                "rule_broken": "no_helmet"
            })
            recognized_names.append(w["name"])
            out_detections.append({
                "box": p_box,
                "label": f"Worker (SIM): NO HELMET (👤 {w['name']})",
                "conf": 0.91,
                "color": "#ec4899",
                "helmet_compliant": False,
                "vest_compliant": True,
                "in_restricted_zone": False
            })

        with history_lock:
            cutoff = now - 60.0
            while FRAME_HISTORY and FRAME_HISTORY[0][0] < cutoff:
                FRAME_HISTORY.popleft()
            if person_count > 0:
                FRAME_HISTORY.append((now, True, violations_count == 0))
            total = sum(1 for f in FRAME_HISTORY if f[1])
            compliant = sum(1 for f in FRAME_HISTORY if f[1] and f[2])
            compliance_pct = round((compliant / total) * 100.0, 1) if total > 0 else 100.0

        return {
            "detections": out_detections,
            "person_count": person_count,
            "active_violations": violations_count,
            "zone_breaches": breaches_count,
            "compliance_pct": compliance_pct,
            "recognized_workers": recognized_names,
            "recognized_info": recognized_info
        }

    # ── Real YOLO inference ──────────────────────────────────────────────
    model = get_model()
    results = model(img_decoded, conf=0.25, verbose=False)
    detections = results[0]
    names = model.names

    people = []
    helmets = []
    no_helmets = []
    vests = []

    for box in detections.boxes:
        cls_id = int(box.cls[0].item())
        cls_name = names[cls_id].lower()
        conf = float(box.conf[0].item())
        xyxy = box.xyxy[0].tolist()

        det_obj = {"box": xyxy, "conf": conf, "cls_id": cls_id, "cls_name": cls_name}

        if "human" in cls_name or "person" in cls_name:
            people.append(det_obj)
        elif "no-helmet" in cls_name or "no_helmet" in cls_name:
            no_helmets.append(det_obj)
        elif "helmet" in cls_name:
            helmets.append(det_obj)
        elif "vest" in cls_name:
            vests.append(det_obj)

    # Fallback: if YOLO didn't find a person body (common for close-up webcam shots),
    # InsightFace will still detect the face on the full frame and run recognition.
    # We create a virtual full-frame person box so PPE checks run on the full image.
    if len(people) == 0:
        # Create a virtual "whole frame" person box — face recognition will still run
        # via InsightFace on the full image. PPE (helmet) check will use YOLO detections
        # against this box, which is the full frame.
        people.append({
            "box": [0.0, 0.0, float(w_img - 1), float(h_img - 1)],
            "conf": 0.6,
            "cls_id": 1,
            "cls_name": "human (full-frame fallback)"
        })
        logger.debug("YOLO found no person — using full-frame virtual box as fallback")

    # ── InsightFace: run on full frame to get all face matches ───────────
    # This runs ONCE per frame (not per person box) for efficiency.
    # We get back a list of (worker_id, name, section, score, face_bbox) for each detected face.
    section_detected = "Участок №3 — Дробление"
    face_matches = match_face_arcface(img_decoded, db_workers)

    # Build a mapping of face_bbox → match info for pairing with person boxes
    # Strategy: for each person box, find the closest face match whose bbox overlaps
    def face_overlaps_person(face_bbox, person_box):
        """Check if the face bounding box center is inside the person bounding box."""
        if face_bbox is None:
            return False
        fx1, fy1, fx2, fy2 = face_bbox[0], face_bbox[1], face_bbox[2], face_bbox[3]
        fcx = (fx1 + fx2) / 2
        fcy = (fy1 + fy2) / 2
        px1, py1, px2, py2 = person_box
        # Also give some margin: face top half of person body
        return px1 <= fcx <= px2 and py1 <= fcy <= (py1 + (py2 - py1) * 0.7)

    out_detections = []
    violations_count = 0
    breaches_count = 0
    person_count = len(people)

    used_face_indices = set()

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

        # Find the face match for this person box
        matched_face = None
        for i, fm in enumerate(face_matches):
            if i in used_face_indices:
                continue
            if face_overlaps_person(fm.get("face_bbox"), p_box):
                matched_face = fm
                used_face_indices.add(i)
                break

        # If no face matched by overlap (close-up shot), use first unmatched face
        if matched_face is None and face_matches:
            for i, fm in enumerate(face_matches):
                if i not in used_face_indices:
                    matched_face = fm
                    used_face_indices.add(i)
                    break

        is_recognized = (matched_face is not None and matched_face["worker_id"] is not None)
        matched_id = matched_face["worker_id"] if matched_face else None
        matched_name = matched_face["name"] if matched_face else "Неопознанный сотрудник"
        matched_section = matched_face["section"] if matched_face else None
        score = matched_face["score"] if matched_face else 0.0

        # Section violation: recognized worker in wrong zone
        wrong_section = False
        if is_recognized and matched_section is not None:
            if matched_section.strip() != section_detected.strip():
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

        info_entry = {
            "worker_id": matched_id,
            "name": matched_name,
            "section": matched_section or "Неизвестно",
            "helmet_compliant": helmet_compliant,
            "wrong_section": wrong_section,
            "has_violation": has_violation,
            "rule_broken": rule_broken
        }
        recognized_info.append(info_entry)
        if matched_name and matched_name != "Неопознанный сотрудник":
            recognized_names.append(matched_name)

        # Draw detection label
        label_parts = []
        if not helmet_compliant:
            label_parts.append("NO HELMET")
        if wrong_section:
            label_parts.append("WRONG SECTION")
        if in_restricted_zone:
            label_parts.append("ZONE BREACH")

        worker_tag = f"👤 {matched_name} ({int(score * 100)}%)" if is_recognized else "👤 Неопознан"
        if has_violation:
            label = f"VIOLATIONS: {', '.join(label_parts)} | {worker_tag}"
            color = "#ec4899"
        else:
            label = f"✓ Compliant | {worker_tag}"
            color = "#10b981"

        out_detections.append({
            "box": p_box,
            "label": label,
            "conf": person["conf"],
            "color": color,
            "helmet_compliant": helmet_compliant,
            "vest_compliant": True,
            "in_restricted_zone": in_restricted_zone
        })

    # Add auxiliary YOLO detections to the output (for visualization)
    for h in helmets:
        out_detections.append({"box": h["box"], "label": "✓ Helmet", "conf": h["conf"], "color": "#3b82f6"})
    for v in vests:
        out_detections.append({"box": v["box"], "label": "✓ Safety Vest", "conf": v["conf"], "color": "#eab308"})
    for nh in no_helmets:
        out_detections.append({"box": nh["box"], "label": "⚠ No Helmet!", "conf": nh["conf"], "color": "#ef4444"})

    # Add face bounding boxes from InsightFace
    for fm in face_matches:
        fbbox = fm.get("face_bbox")
        if fbbox is not None:
            name_label = fm["name"] if fm["worker_id"] else f"? ({int(fm['score'] * 100)}%)"
            out_detections.append({
                "box": fbbox,
                "label": f"👤 {name_label}",
                "conf": fm["score"],
                "color": "#3b82f6" if fm["worker_id"] else "#f59e0b"
            })

    # Update rolling compliance window
    now = time.time()
    with history_lock:
        cutoff = now - 60.0
        while FRAME_HISTORY and FRAME_HISTORY[0][0] < cutoff:
            FRAME_HISTORY.popleft()

        if person_count > 0:
            frame_is_compliant = (violations_count == 0) and (breaches_count == 0)
            FRAME_HISTORY.append((now, True, frame_is_compliant))

        total_frames = sum(1 for f in FRAME_HISTORY if f[1])
        compliant_frames = sum(1 for f in FRAME_HISTORY if f[1] and f[2])
        compliance_pct = round((compliant_frames / total_frames) * 100.0, 1) if total_frames > 0 else 100.0

    return {
        "detections": out_detections,
        "person_count": person_count,
        "active_violations": violations_count,
        "zone_breaches": breaches_count,
        "compliance_pct": compliance_pct,
        "recognized_workers": recognized_names,
        "recognized_info": recognized_info
    }
