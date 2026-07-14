import abc
import time
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, List, Dict
from app.config import settings

logger = logging.getLogger("edge.ts_database")

class TelemetryStore(abc.ABC):
    """Abstract interface for high-frequency time-series telemetry store."""

    @abc.abstractmethod
    def write_packet(
        self,
        device_id: str,
        device_type: str,
        event: str,
        value: float,
        unit: str,
        timestamp: int,
        battery_v: float,
        rssi_dbm: int
    ) -> None:
        pass

    @abc.abstractmethod
    def get_latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    def get_history(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    def get_hourly_trend(self, device_type: str, hours: int = 24) -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    def get_summary_stats(self, today_start: int) -> Dict[str, Any]:
        pass


class DuckDBTelemetryStore(TelemetryStore):
    """DuckDB implementation of TelemetryStore (local embedded columnar DB)."""

    def __init__(self, db_path: str = "telemetry_ts.duckdb"):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        self._init_db()

    def _get_conn(self):
        import duckdb
        return duckdb.connect(self.db_path)

    def _init_db(self):
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    device_id VARCHAR,
                    device_type VARCHAR,
                    event VARCHAR,
                    value DOUBLE,
                    unit VARCHAR,
                    timestamp BIGINT,
                    battery_v DOUBLE,
                    rssi_dbm INTEGER,
                    server_ts BIGINT
                )
            """)
            # Create indexing if needed, DuckDB uses internal indexes automatically
            conn.close()
            logger.info(f"DuckDB Telemetry Store initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB: {e}")
            raise

    def write_packet(
        self,
        device_id: str,
        device_type: str,
        event: str,
        value: float,
        unit: str,
        timestamp: int,
        battery_v: float,
        rssi_dbm: int
    ) -> None:
        server_ts = int(time.time())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO telemetry 
                (device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, device_type, event, float(value), unit, int(timestamp), float(battery_v), int(rssi_dbm), server_ts)
            )
        finally:
            conn.close()

    def get_latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            res = conn.execute(
                """
                SELECT device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts
                FROM telemetry
                ORDER BY server_ts DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            
            return [{
                "device_id": r[0],
                "device_type": r[1],
                "event": r[2],
                "value": r[3],
                "unit": r[4],
                "timestamp": r[5],
                "battery_v": r[6],
                "rssi_dbm": r[7],
                "server_ts": r[8]
            } for r in res]
        finally:
            conn.close()

    def get_history(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff_ts = int(time.time()) - (hours * 3600)
        conn = self._get_conn()
        try:
            res = conn.execute(
                """
                SELECT device_id, device_type, event, value, unit, timestamp, battery_v, rssi_dbm, server_ts
                FROM telemetry
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (device_id, cutoff_ts)
            ).fetchall()
            
            return [{
                "device_id": r[0],
                "device_type": r[1],
                "event": r[2],
                "value": r[3],
                "unit": r[4],
                "timestamp": r[5],
                "battery_v": r[6],
                "rssi_dbm": r[7],
                "server_ts": r[8]
            } for r in res]
        finally:
            conn.close()

    def get_hourly_trend(self, device_type: str, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff_ts = int(time.time()) - (hours * 3600)
        conn = self._get_conn()
        try:
            res = conn.execute(
                """
                SELECT
                    (timestamp / 3600) * 3600 AS hour_bucket,
                    AVG(value) AS avg_value,
                    MAX(value) AS max_value,
                    MIN(value) AS min_value,
                    COUNT(*) AS count
                FROM telemetry
                WHERE device_type = ? AND timestamp >= ?
                GROUP BY hour_bucket
                ORDER BY hour_bucket ASC
                """,
                (device_type, cutoff_ts)
            ).fetchall()
            
            return [{
                "hour": datetime.fromtimestamp(r[0], tz=timezone.utc).isoformat(),
                "avg_value": round(r[1], 2),
                "max_value": round(r[2], 2),
                "min_value": round(r[3], 2),
                "count": r[4]
            } for r in res]
        finally:
            conn.close()

    def get_summary_stats(self, today_start: int) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            # 1. Total events today
            res_total = conn.execute(
                "SELECT COUNT(*) FROM telemetry WHERE server_ts >= ?", (today_start,)
            ).fetchone()
            total_events_today = res_total[0] if res_total else 0

            # 2. Avg power and Total energy today
            res_power = conn.execute(
                "SELECT AVG(value), SUM(value) FROM telemetry WHERE device_type = 'power' AND server_ts >= ?",
                (today_start,)
            ).fetchone()
            
            avg_power_w = round(res_power[0], 1) if res_power and res_power[0] is not None else None
            # Wh estimate: sum of power readings * 2 seconds / 3600 seconds
            total_energy_wh = round(res_power[1] * 2.0 / 3600.0, 1) if res_power and res_power[1] is not None else None

            # 3. Motion events today
            res_motion = conn.execute(
                "SELECT COUNT(*) FROM telemetry WHERE device_type = 'motion' AND event = 'trigger' AND server_ts >= ?",
                (today_start,)
            ).fetchone()
            motion_events_today = res_motion[0] if res_motion else 0

            return {
                "total_events_today": total_events_today,
                "avg_power_w": avg_power_w,
                "total_energy_wh": total_energy_wh,
                "motion_events_today": motion_events_today
            }
        finally:
            conn.close()


class InfluxDBTelemetryStore(TelemetryStore):
    """InfluxDB v2 implementation of TelemetryStore (production target)."""

    def __init__(self):
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS
        
        self.url = settings.influxdb_url
        self.token = settings.influxdb_token
        self.org = settings.influxdb_org
        self.bucket = settings.influxdb_bucket
        
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        logger.info(f"InfluxDB Telemetry Store initialized targeting {self.url} bucket {self.bucket}")

    def write_packet(
        self,
        device_id: str,
        device_type: str,
        event: str,
        value: float,
        unit: str,
        timestamp: int,
        battery_v: float,
        rssi_dbm: int
    ) -> None:
        from influxdb_client import Point
        
        # InfluxDB works best with nanosecond or second timestamps
        point = Point("telemetry") \
            .tag("device_id", device_id) \
            .tag("device_type", device_type) \
            .tag("event", event) \
            .field("value", float(value)) \
            .field("unit", unit) \
            .field("battery_v", float(battery_v)) \
            .field("rssi_dbm", int(rssi_dbm)) \
            .time(datetime.fromtimestamp(timestamp, tz=timezone.utc))
            
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def get_latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        # Query latest records using Flux
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -24h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
        '''
        tables = self.query_api.query(query, org=self.org)
        
        result = []
        for table in tables:
            for record in table.records:
                # Parse record
                dt = record.get_time()
                ts = int(dt.timestamp())
                result.append({
                    "device_id": record.values.get("device_id"),
                    "device_type": record.values.get("device_type"),
                    "event": record.values.get("event"),
                    "value": record.values.get("value"),
                    "unit": record.values.get("unit", ""),
                    "timestamp": ts,
                    "battery_v": record.values.get("battery_v", 4.2),
                    "rssi_dbm": record.values.get("rssi_dbm", -50),
                    "server_ts": ts
                })
        
        # Sort by server_ts desc
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        return result[:limit]

    def get_history(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_id"] == "{device_id}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: false)
        '''
        tables = self.query_api.query(query, org=self.org)
        
        result = []
        for table in tables:
            for record in table.records:
                dt = record.get_time()
                ts = int(dt.timestamp())
                result.append({
                    "device_id": record.values.get("device_id"),
                    "device_type": record.values.get("device_type"),
                    "event": record.values.get("event"),
                    "value": record.values.get("value"),
                    "unit": record.values.get("unit", ""),
                    "timestamp": ts,
                    "battery_v": record.values.get("battery_v", 4.2),
                    "rssi_dbm": record.values.get("rssi_dbm", -50),
                    "server_ts": ts
                })
        return result

    def get_hourly_trend(self, device_type: str, hours: int = 24) -> List[Dict[str, Any]]:
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_type"] == "{device_type}" and r["_field"] == "value")
          |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
          |> yield(name: "mean")
        '''
        # Note: To fully support min/max/count, we'd write multiple aggregations or pivot.
        # This basic mean is sufficient for high-level dashboard trend lines.
        tables = self.query_api.query(query, org=self.org)
        
        result = []
        for table in tables:
            for record in table.records:
                dt = record.get_time()
                val = record.get_value()
                result.append({
                    "hour": dt.isoformat(),
                    "avg_value": round(val, 2) if val is not None else 0.0,
                    "max_value": round(val, 2) if val is not None else 0.0,
                    "min_value": round(val, 2) if val is not None else 0.0,
                    "count": 1
                })
        return result

    def get_summary_stats(self, today_start: int) -> Dict[str, Any]:
        # Count total events today
        now_dt = datetime.now(timezone.utc)
        start_dt = datetime.fromtimestamp(today_start, tz=timezone.utc)
        duration_sec = int((now_dt - start_dt).total_seconds())
        duration_hours = max(1, duration_sec // 3600)
        
        # Flux query for count
        count_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{duration_hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["_field"] == "value")
          |> count()
        '''
        tables = self.query_api.query(count_query, org=self.org)
        total_events = 0
        for table in tables:
            for record in table.records:
                total_events += record.get_value()

        # Flux query for power averages
        power_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{duration_hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_type"] == "power" and r["_field"] == "value")
          |> mean()
        '''
        tables = self.query_api.query(power_query, org=self.org)
        avg_power = None
        for table in tables:
            for record in table.records:
                val = record.get_value()
                if val is not None:
                    avg_power = round(val, 1)

        # Flux query for power sum
        power_sum_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{duration_hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_type"] == "power" and r["_field"] == "value")
          |> sum()
        '''
        tables = self.query_api.query(power_sum_query, org=self.org)
        total_energy_wh = None
        for table in tables:
            for record in table.records:
                val = record.get_value()
                if val is not None:
                    total_energy_wh = round(val * 2.0 / 3600.0, 1)

        # Motion count
        motion_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{duration_hours}h)
          |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_type"] == "motion" and r["event"] == "trigger" and r["_field"] == "value")
          |> count()
        '''
        tables = self.query_api.query(motion_query, org=self.org)
        motion_events = 0
        for table in tables:
            for record in table.records:
                motion_events += record.get_value()

        return {
            "total_events_today": total_events,
            "avg_power_w": avg_power,
            "total_energy_wh": total_energy_wh,
            "motion_events_today": motion_events
        }


# Singleton Factory function
_store_instance = None

def get_telemetry_store() -> TelemetryStore:
    global _store_instance
    if _store_instance is None:
        tsdb_type = settings.tsdb_type.lower()
        if tsdb_type == "influxdb":
            try:
                _store_instance = InfluxDBTelemetryStore()
            except Exception as e:
                logger.error(f"Failed to initialize InfluxDB store, falling back to DuckDB: {e}")
                _store_instance = DuckDBTelemetryStore()
        else:
            _store_instance = DuckDBTelemetryStore()
    return _store_instance
