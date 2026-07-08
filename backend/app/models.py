"""
Edge Telemetry — Pydantic Models
The data contract between hardware and software.
"""

import time
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# INBOUND: Telemetry from ESP32 devices
# ─────────────────────────────────────────────

class TelemetryPacket(BaseModel):
    """
    The universal telemetry payload.
    Every edge device — real or simulated — speaks this format.
    """
    device_id: str = Field(..., min_length=1, max_length=64, description="Unique device identifier")
    device_type: str = Field(..., description="Sensor category")
    event: str = Field(..., description="Event type")
    value: float = Field(..., description="Sensor reading value")
    unit: str = Field(..., max_length=16, description="Unit of measurement")
    timestamp: Optional[int] = Field(default=None, description="Unix epoch seconds. 0 or None = server will assign.")
    battery_v: float = Field(default=4.2, ge=0.0, le=5.0, description="Battery voltage")
    rssi_dbm: int = Field(default=-50, ge=-120, le=0, description="Wi-Fi signal strength")
    risk_score: Optional[float] = Field(default=None, description="Edge AI calculated risk score")
    metadata: Optional[dict] = Field(default=None, description="Device-specific metadata dictionary")

    @field_validator("battery_v")
    @classmethod
    def clamp_battery(cls, v: float) -> float:
        return max(0.0, min(4.2, v))

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        # Broad sanity check
        if abs(v) > 100000:
            raise ValueError(f"Value {v} is out of sane range")
        return v

    @field_validator("timestamp")
    @classmethod
    def fix_timestamp(cls, v: Optional[int]) -> Optional[int]:
        """
        Edge Time-Sync Fix:
        ESP32 devices without RTC battery will send timestamp=0 or impossibly old
        values after boot before NTP sync. We accept these and let the ingestion
        service overwrite with server time. Never reject data over clock issues.
        """
        if v is None or v == 0:
            return None  # Signal to ingestion service: use server time
        # If timestamp is before 2020 (clearly wrong), null it out
        if v < 1577836800:  # 2020-01-01 00:00:00 UTC
            return None
        return v


# ─────────────────────────────────────────────
# OUTBOUND: API Responses
# ─────────────────────────────────────────────

from typing import Dict, Any, List

class TelemetryResponse(BaseModel):
    """Response after successful telemetry ingestion."""
    status: str = "ok"
    device_id: str
    server_ts: int
    alerts_fired: int = 0


class DigitalTwinAsset(BaseModel):
    """A Digital Twin representing an asset in the value chain."""
    asset_id: str
    asset_name: str
    asset_type: str
    parent_asset_id: Optional[str] = None
    zone_id: Optional[str] = None
    output_type: str
    status: str
    risk_score: float
    recommended_value: Optional[float] = None
    current_deviation: Optional[float] = None
    report_ref: Optional[str] = None
    last_value: float
    last_unit: str
    last_seen: int
    metadata: Dict[str, Any]


class DeviceStatus(BaseModel):
    """Status of a registered edge device."""
    device_id: str
    device_type: str
    last_value: float
    last_unit: str
    last_seen: int
    battery_v: float
    rssi_dbm: int
    status: Literal["online", "offline", "alert"]
    total_events: int


class AssetAlertRecord(BaseModel):
    """An asset-centric status transition alert."""
    alert_id: str
    asset_id: str
    severity: str
    message: str
    created_at: int


class SimulatorOverride(BaseModel):
    """Model to override simulation state (inject anomalies, toggle online)."""
    device_id: str
    anomaly_active: bool
    connection_active: bool = True


class AnalyticsSummary(BaseModel):
    """Dashboard summary metrics."""
    total_events_today: int
    active_devices: int
    total_devices: int
    avg_power_w: Optional[float]
    total_energy_wh: Optional[float]
    motion_events_today: int
    active_alerts: int
    uptime_pct: float


class HourlyBucket(BaseModel):
    """One hour of aggregated data."""
    hour: str  # ISO format: "2024-07-03T14:00:00"
    avg_value: float
    max_value: float
    min_value: float
    count: int

