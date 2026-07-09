"""
Edge Telemetry — Analytics Service
SQL aggregation queries: hourly buckets, device uptime, energy totals.
Static threshold alerts only — no Z-score / statistical anomaly detection for the MVP.
"""

import time
import logging
import json
import os
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.config import settings

logger = logging.getLogger("edge.analytics")


def get_summary() -> dict:
    """Dashboard summary: total events, active devices, alerts, etc."""
    now = int(time.time())
    today_start = now - (now % 86400)  # Midnight UTC today
    offline_cutoff = now - settings.device_offline_timeout_s

    with get_db() as conn:
        cur = conn.cursor()

        # Total events today
        cur.execute(
            "SELECT COUNT(*) FROM telemetry_log WHERE server_ts >= ?",
            (today_start,)
        )
        total_events_today = cur.fetchone()[0]

        # Total devices configured in case registry
        try:
            registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "case_registry.json")
            if not os.path.exists(registry_path):
                registry_path = os.path.join(os.path.dirname(__file__), "case_registry.json")
            with open(registry_path, "r") as f:
                registry = json.load(f)
            cases = registry.get("cases", [])
            total_devices = len(cases)
            registry_device_ids = [c["device_id"] for c in cases]
        except Exception:
            total_devices = 15
            registry_device_ids = []

        if registry_device_ids:
            placeholders = ",".join("?" for _ in registry_device_ids)
            cur.execute(
                f"SELECT COUNT(*) FROM devices WHERE device_id IN ({placeholders}) AND last_seen >= ?",
                (*registry_device_ids, offline_cutoff)
            )
            active_devices = cur.fetchone()[0]
        else:
            cur.execute(
                "SELECT COUNT(*) FROM devices WHERE last_seen >= ?",
                (offline_cutoff,)
            )
            active_devices = cur.fetchone()[0]

        # Average power (from power-type devices today)
        cur.execute(
            "SELECT AVG(value) FROM telemetry_log WHERE device_type = 'power' AND server_ts >= ?",
            (today_start,)
        )
        row = cur.fetchone()
        avg_power_w = round(row[0], 1) if row[0] else None

        # Total energy estimate (Wh) — sum of power readings × interval in hours
        # Each reading is ~2s apart, so each reading represents ~2/3600 hours
        cur.execute(
            "SELECT SUM(value) FROM telemetry_log WHERE device_type = 'power' AND server_ts >= ?",
            (today_start,)
        )
        row = cur.fetchone()
        total_energy_wh = round(row[0] * 2.0 / 3600.0, 1) if row[0] else None

        # Motion events today
        cur.execute(
            "SELECT COUNT(*) FROM telemetry_log WHERE device_type = 'motion' AND event = 'trigger' AND server_ts >= ?",
            (today_start,)
        )
        motion_events_today = cur.fetchone()[0]

        # Active alerts count
        cur.execute(
            "SELECT COUNT(*) FROM alerts WHERE severity IN ('Warning', 'Critical')"
        )
        active_alerts = cur.fetchone()[0]

        # Uptime percentage (devices seen in last hour / total devices)
        hour_ago = now - 3600
        if registry_device_ids:
            placeholders = ",".join("?" for _ in registry_device_ids)
            cur.execute(
                f"SELECT COUNT(*) FROM devices WHERE device_id IN ({placeholders}) AND last_seen >= ?",
                (*registry_device_ids, hour_ago)
            )
            seen_last_hour = cur.fetchone()[0]
        else:
            cur.execute(
                "SELECT COUNT(*) FROM devices WHERE last_seen >= ?",
                (hour_ago,)
            )
            seen_last_hour = cur.fetchone()[0]
        uptime_pct = round((seen_last_hour / total_devices * 100), 1) if total_devices > 0 else 100.0

    return {
        "total_events_today": total_events_today,
        "active_devices": active_devices,
        "total_devices": total_devices,
        "avg_power_w": avg_power_w,
        "total_energy_wh": total_energy_wh,
        "motion_events_today": motion_events_today,
        "active_alerts": active_alerts,
        "uptime_pct": uptime_pct
    }


def get_hourly_trend(device_type: str, hours: int = 24) -> list[dict]:
    """Get hourly aggregated buckets for a device type."""
    now = int(time.time())
    start = now - (hours * 3600)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                (timestamp / 3600) * 3600 AS hour_bucket,
                AVG(value) AS avg_value,
                MAX(value) AS max_value,
                MIN(value) AS min_value,
                COUNT(*) AS count
            FROM telemetry_log
            WHERE device_type = ? AND timestamp >= ?
            GROUP BY hour_bucket
            ORDER BY hour_bucket ASC
        """, (device_type, start))

        rows = cur.fetchall()

    return [{
        "hour": datetime.fromtimestamp(row[0], tz=timezone.utc).isoformat(),
        "avg_value": round(row[1], 2),
        "max_value": round(row[2], 2),
        "min_value": round(row[3], 2),
        "count": row[4]
    } for row in rows]


def get_devices() -> list[dict]:
    """Get all registered devices with their current status."""
    now = int(time.time())
    offline_cutoff = now - settings.device_offline_timeout_s

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices ORDER BY last_seen DESC")
        rows = cur.fetchall()

    devices = []
    for row in rows:
        last_seen = row["last_seen"]

        # Check if device has active alerts
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM alerts WHERE device_id = ? AND acknowledged = 0",
                (row["device_id"],)
            )
            has_alerts = cur.fetchone()[0] > 0

        if has_alerts:
            status = "alert"
        elif last_seen >= offline_cutoff:
            status = "online"
        else:
            status = "offline"

        devices.append({
            "device_id": row["device_id"],
            "device_type": row["device_type"],
            "last_value": row["last_value"],
            "last_unit": row["last_unit"],
            "last_seen": last_seen,
            "battery_v": row["battery_v"],
            "rssi_dbm": row["rssi_dbm"],
            "status": status,
            "total_events": row["total_events"]
        })

    return devices


def get_assets() -> list[dict]:
    """Get all assets and dynamically compute parent rollups on read."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM assets")
        rows = cur.fetchall()

    # Parse assets
    assets_list = []
    for r in rows:
        meta = {}
        try:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
        except Exception:
            pass

        assets_list.append({
            "asset_id": r["asset_id"],
            "asset_name": r["asset_name"],
            "asset_type": r["asset_type"],
            "parent_asset_id": r["parent_asset_id"],
            "zone_id": r["zone_id"],
            "output_type": r["output_type"],
            "status": r["status"],
            "risk_score": r["risk_score"],
            "recommended_value": r["recommended_value"],
            "current_deviation": r["current_deviation"],
            "report_ref": r["report_ref"],
            "last_value": r["last_value"],
            "last_unit": r["last_unit"],
            "last_seen": r["last_seen"],
            "metadata": meta
        })

    # Group child assets by parent_asset_id
    from collections import defaultdict
    children_by_parent = defaultdict(list)
    for asset in assets_list:
        if asset["parent_asset_id"]:
            children_by_parent[asset["parent_asset_id"]].append(asset)

    # Compute parent status, risk_score, and metadata count on read
    for asset in assets_list:
        # If it's a parent zone (no parent_asset_id but has children)
        if not asset["parent_asset_id"] and asset["asset_id"] in children_by_parent:
            children = children_by_parent[asset["asset_id"]]
            if children:
                # Worst-case status mapping
                status_severity = {"Normal": 0, "Warning": 1, "Critical": 2}
                worst_status_val = 0
                worst_status = "Normal"
                max_risk = 0.0
                warning_count = 0
                critical_count = 0
                last_seen_max = asset["last_seen"]

                for child in children:
                    c_status = child["status"]
                    c_status_val = status_severity.get(c_status, 0)
                    if c_status_val > worst_status_val:
                        worst_status_val = c_status_val
                        worst_status = c_status
                    if child["risk_score"] > max_risk:
                        max_risk = child["risk_score"]
                    if c_status == "Warning":
                        warning_count += 1
                    elif c_status == "Critical":
                        critical_count += 1
                    if child["last_seen"] > last_seen_max:
                        last_seen_max = child["last_seen"]

                asset["status"] = worst_status
                asset["risk_score"] = max_risk
                asset["last_seen"] = last_seen_max
                asset["metadata"]["warning_count"] = warning_count
                asset["metadata"]["critical_count"] = critical_count
                asset["metadata"]["total_children"] = len(children)

    return assets_list


def get_alerts(limit: int = 50) -> list[dict]:
    """Get recent alerts, newest first."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT alert_id, asset_id, severity, message, created_at, frame_image
            FROM alerts
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()

    return [{
        "alert_id": row[0],
        "asset_id": row[1],
        "severity": row[2],
        "message": row[3],
        "created_at": row[4],
        "frame_image": row[5]
    } for row in rows]


def get_telemetry_latest(limit: int = 20) -> list[dict]:
    """Get the most recent telemetry readings across all devices."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts
            FROM telemetry_log
            ORDER BY server_ts DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()

    return [{
        "device_id": row[0],
        "device_type": row[1],
        "event": row[2],
        "value": row[3],
        "unit": row[4],
        "timestamp": row[5],
        "battery_v": row[6],
        "rssi_dbm": row[7],
        "server_ts": row[8]
    } for row in rows]


def get_telemetry_history(device_id: str, hours: int = 24) -> list[dict]:
    """Get telemetry history for a specific device."""
    now = int(time.time())
    start = now - (hours * 3600)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts
            FROM telemetry_log
            WHERE device_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (device_id, start))
        rows = cur.fetchall()

    return [{
        "device_id": row[0],
        "device_type": row[1],
        "event": row[2],
        "value": row[3],
        "unit": row[4],
        "timestamp": row[5],
        "battery_v": row[6],
        "rssi_dbm": row[7],
        "server_ts": row[8]
    } for row in rows]
