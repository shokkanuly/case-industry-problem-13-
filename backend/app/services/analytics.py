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
from app.ts_database import get_telemetry_store

logger = logging.getLogger("edge.analytics")


def get_summary() -> dict:
    """Dashboard summary: total events, active devices, alerts, etc."""
    now = int(time.time())
    today_start = now - (now % 86400)  # Midnight UTC today
    offline_cutoff = now - settings.device_offline_timeout_s

    # Get time-series stats
    ts_stats = get_telemetry_store().get_summary_stats(today_start)

    with get_db() as conn:
        cur = conn.cursor()

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
        "total_events_today": ts_stats["total_events_today"],
        "active_devices": active_devices,
        "total_devices": total_devices,
        "avg_power_w": ts_stats["avg_power_w"],
        "total_energy_wh": ts_stats["total_energy_wh"],
        "motion_events_today": ts_stats["motion_events_today"],
        "active_alerts": active_alerts,
        "uptime_pct": uptime_pct
    }


def get_hourly_trend(device_type: str, hours: int = 24) -> list[dict]:
    """Get hourly aggregated buckets for a device type."""
    return get_telemetry_store().get_hourly_trend(device_type, hours)


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
    return get_telemetry_store().get_latest(limit)


def get_telemetry_history(device_id: str, hours: int = 24) -> list[dict]:
    """Get telemetry history for a specific device."""
    return get_telemetry_store().get_history(device_id, hours)
