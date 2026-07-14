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
                created_at INTEGER NOT NULL,
                frame_image TEXT
            )
        """)

        # Workers / Personnel table — preserve data across restarts!
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                section TEXT NOT NULL,
                face_encoding TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Normal',
                compliance_score REAL NOT NULL DEFAULT 100.0,
                photo TEXT
            )
        """)
        
        # Violations table (description filled in async by Gemini after violation is logged)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                violation_id TEXT PRIMARY KEY,
                worker_id TEXT,
                rule_broken TEXT NOT NULL,
                section_detected TEXT NOT NULL,
                frame_path TEXT NOT NULL,
                description TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        # Add description column if upgrading from older schema
        try:
            cur.execute("ALTER TABLE violations ADD COLUMN description TEXT")
        except Exception:
            pass  # Column already exists
        
        # Backwards compatibility alerts table
        cur.execute("DROP TABLE IF EXISTS alerts")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                frame_image TEXT
            )
        """)
        
        # NOTE: No seed workers are added. Workers must be enrolled via the dashboard
        # with a real photo so InsightFace can compute their 512-d ArcFace embedding.
        # Seed workers with empty face_encoding=[] cannot be matched by face recognition.

        # Indexes for query performance

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
            ("haul_road_b", "Haul Road Zone B", "logistics_safety", None, "haul_road_b", "status", "Normal", 0.0, None, None, None, 0.0, "", now_ts, "{}")
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
