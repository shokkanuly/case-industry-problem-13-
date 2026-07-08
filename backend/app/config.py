"""
Edge Telemetry — Configuration
Loads settings from .env with pydantic-settings.
"""

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from backend directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Security
    edge_api_key: str = "dev-key-001"

    # Database
    sqlite_path: str = "telemetry.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # WebSocket
    ws_broadcast_interval_ms: int = 500

    # Alert Thresholds (static — no Z-score, just raw limits)
    alert_power_threshold_w: float = 3000.0
    alert_battery_low_v: float = 2.8
    alert_temp_high_c: float = 35.0

    # Device health
    device_offline_timeout_s: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
