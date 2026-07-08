"""
Edge Telemetry — SQLite Database
WAL mode for concurrent reads during WebSocket broadcasts.
"""

import sqlite3
import logging
import os
import time
from contextlib import contextmanager
from app.config import settings

logger = logging.getLogger("edge.database")

# Resolve database path relative to backend directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.sqlite_path)


@contextmanager
def get_db():
    """Context manager for database connections with WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Create all tables on startup."""
    with get_db() as conn:
        cur = conn.cursor()

        # Telemetry log — the core time-series table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                device_type TEXT NOT NULL,
                event TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                battery_v REAL DEFAULT 4.2,
                rssi_dbm INTEGER DEFAULT -50,
                server_ts INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Device registry — auto-populated on first ping
        cur.execute("DROP TABLE IF EXISTS devices")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_type TEXT NOT NULL,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                last_value REAL DEFAULT 0.0,
                last_unit TEXT DEFAULT '',
                battery_v REAL DEFAULT 4.2,
                rssi_dbm INTEGER DEFAULT -50,
                total_events INTEGER DEFAULT 0
            )
        """)

        # Digital Twin assets table
        cur.execute("DROP TABLE IF EXISTS assets")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                parent_asset_id TEXT,
                zone_id TEXT,
                output_type TEXT NOT NULL,
                status TEXT,
                risk_score REAL DEFAULT 0.0,
                recommended_value REAL,
                current_deviation REAL,
                report_ref TEXT,
                last_value REAL DEFAULT 0.0,
                last_unit TEXT DEFAULT '',
                last_seen INTEGER NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # Asset-centric alerts history
        # Drop the old device-centric alerts table to ensure schema compatibility
        cur.execute("DROP TABLE IF EXISTS alerts")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        # Indexes for query performance
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_device_ts
            ON telemetry_log (device_id, timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_ts
            ON telemetry_log (timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_ts
            ON alerts (created_at DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_parent
            ON assets (parent_asset_id)
        """)

        # Seed parent assets/zones
        now_ts = int(time.time())
        parents = [
            ("smelting_hall_1", "Smelting Hall #1", "smelting", None, "smelting_hall_1", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, "{}"),
            ("processing_line_2", "Processing Line #2", "processing", None, "processing_line_2", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, "{}"),
            ("haul_road_b", "Haul Road Zone B", "logistics_safety", None, "haul_road_b", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, "{}"),
            ("exploration_sector_gamma", "Exploration Sector Gamma", "exploration", None, "exploration_sector_gamma", "batch_report", None, 0.0, None, None, None, 0.0, "", now_ts, "{}"),
            ("underground_tunnel_alpha", "Underground Tunnel Alpha", "logistics_safety", None, "underground_tunnel_alpha", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, '{"underground": true}'),
            ("surface_rail_terminal", "Surface Rail Yard", "logistics_safety", None, "surface_rail_terminal", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, "{}")
        ]
        for p in parents:
            cur.execute("""
                INSERT OR IGNORE INTO assets 
                (asset_id, asset_name, asset_type, parent_asset_id, zone_id, output_type, status, risk_score, recommended_value, current_deviation, report_ref, last_value, last_unit, last_seen, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

        # Seed child assets from case_registry.json dynamically
        try:
            import json
            registry_path = os.path.join(os.path.dirname(__file__), "case_registry.json")
            if os.path.exists(registry_path):
                with open(registry_path, "r") as f:
                    registry = json.load(f)
                for case in registry.get("cases", []):
                    asset_id = case["asset_id"]
                    asset_name = case["asset_name"]
                    asset_type = case["category"]
                    parent_asset_id = case["zone_id"]
                    zone_id = case["zone_id"]
                    output_type = case["output_type"]
                    
                    status = None
                    risk_score = 0.0
                    recommended_value = None
                    current_deviation = None
                    report_ref = None
                    
                    if output_type == "status":
                        status = "Normal"
                        risk_score = 0.0
                    
                    metadata_dict = {"underground": case.get("underground", False)}
                    cur.execute("""
                        INSERT OR IGNORE INTO assets 
                        (asset_id, asset_name, asset_type, parent_asset_id, zone_id, output_type, status, risk_score, recommended_value, current_deviation, report_ref, last_value, last_unit, last_seen, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (asset_id, asset_name, asset_type, parent_asset_id, zone_id, output_type, status, risk_score, recommended_value, current_deviation, report_ref, 0.0, "", now_ts, json.dumps(metadata_dict)))
            else:
                logger.warning(f"Could not find case_registry.json at {registry_path} to seed child assets")
        except Exception as e:
            logger.error(f"Error seeding dynamically from registry: {e}")

        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
