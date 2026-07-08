"""
Industrial Nervous System — Edge Telemetry Simulator
Simulates Case 13 PPE & behavior compliance edge camera telemetry logs.
"""

import time
import random
import sys
import os
import requests
import json
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
API_URL = "http://localhost:8000/api/telemetry"
OVERRIDE_URL_TEMPLATE = "http://localhost:8000/api/analytics/simulator/override/{}"
API_KEY = "dev-key-001"
INTERVAL = 3.0  # seconds between ticks

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# ─────────────────────────────────────────────
# COLORS (ANSI Terminal Output)
# ─────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"
    BOLD = "\033[1m"


class EdgeDevice:
    def __init__(self, case_id: int, device_id: str, device_type: str, description: str):
        self.case_id = case_id
        self.device_id = device_id
        self.device_type = device_type
        self.description = description
        self.battery_v = 4.15
        self.rssi_dbm = -60
        self.buffer = []
        self.tick_count = 0

    def get_override_state(self) -> dict:
        """Poll backend for interactive override triggers."""
        try:
            r = requests.get(OVERRIDE_URL_TEMPLATE.format(self.device_id), headers=HEADERS, timeout=1.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {"anomaly_active": False, "connection_active": True}

    def generate_packet(self, anomaly_active: bool) -> dict:
        self.tick_count += 1
        self.battery_v = max(2.5, self.battery_v - random.uniform(0.0001, 0.0003))
        self.rssi_dbm = max(-95, min(-30, self.rssi_dbm + random.randint(-2, 2)))

        payload = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "event": "reading",
            "value": 0.0,
            "unit": "violation",
            "timestamp": int(time.time()),
            "battery_v": round(self.battery_v, 2),
            "rssi_dbm": self.rssi_dbm,
            "risk_score": 0.0,
            "metadata": {}
        }

        if anomaly_active:
            payload["value"] = 1.0
            payload["risk_score"] = round(random.uniform(75.0, 92.0), 1)
            payload["metadata"] = {
                "ppe_compliance_pct": 0.0,
                "worker_in_danger_zone": True,
                "details": "Worker detected near haul road without protective vest"
            }
            print(f"  {C.RED}[EDGE YOLOv8-PPE]{C.RESET} {self.device_id}: Safety Violation! No protective gear in restricted zone.")
        else:
            payload["value"] = 0.0
            payload["risk_score"] = round(random.uniform(0.0, 10.0), 1)
            compliance_pct = max(0.0, min(100.0, round(100.0 - random.uniform(0.0, 2.0), 1)))
            payload["metadata"] = {
                "ppe_compliance_pct": compliance_pct,
                "worker_in_danger_zone": False
            }
            print(f"  {C.DIM}[EDGE YOLOv8-PPE]{C.RESET} {self.device_id}: Haul road safety compliant. Compliance: {compliance_pct}%")

        return payload


def main():
    print(f"\n{C.BOLD}{'═' * 70}")
    print(f"  CASE 13 SAFETY COMPLIANCE CAMERA — SIMULATOR")
    print(f"  Ingest URL: {API_URL}")
    print(f"  Interval:   {INTERVAL}s")
    print(f"{'═' * 70}{C.RESET}\n")

    # Only load Case 13 device
    device = EdgeDevice(
        case_id=13,
        device_id="dev_cv_safety",
        device_type="video_stream",
        description="PPE & Behavior Compliance Camera"
    )

    print(f"  📡  {C.CYAN}{device.device_id:<22}{C.RESET} │ {device.description}")
    print(f"{C.DIM}Press Ctrl+C to exit.{C.RESET}\n")

    try:
        while True:
            # 1. Fetch overrides from backend API
            override = device.get_override_state()
            anomaly_active = override.get("anomaly_active", False)
            is_connected = override.get("connection_active", True)

            # 2. Generate current telemetry
            packet = device.generate_packet(anomaly_active)

            if not is_connected:
                device.buffer.append(packet)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"  {C.YELLOW}[OFFLINE BUFF]{C.RESET} [{ts}] {device.device_id:<22} │ "
                      f"Queued packet. Buffer size: {len(device.buffer)}")
            else:
                # Flush buffer if we reconnected
                if len(device.buffer) > 0:
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  {C.GREEN}[CONNECTED]{C.RESET} [{ts}] {device.device_id:<22} │ "
                          f"Reconnected. Bursting {len(device.buffer)} buffered packets...")
                    
                    while len(device.buffer) > 0:
                        buffered_pkt = device.buffer.pop(0)
                        try:
                            r = requests.post(API_URL, json=buffered_pkt, headers=HEADERS, timeout=2.0)
                            if r.status_code == 200:
                                print(f"    ↳ {C.GREEN}Synced packet{C.RESET}")
                            else:
                                device.buffer.insert(0, buffered_pkt)
                                break
                        except Exception:
                            device.buffer.insert(0, buffered_pkt)
                            break
                        time.sleep(0.2)

                # Send current packet
                try:
                    ts = datetime.now().strftime("%H:%M:%S")
                    r = requests.post(API_URL, json=packet, headers=HEADERS, timeout=2.0)
                    if r.status_code == 200:
                        resp = r.json()
                        alerts = resp.get("alerts_fired", 0)
                        alert_marker = f" {C.RED}{C.BOLD}⚠ ALERT{C.RESET}" if alerts > 0 else ""
                        print(f"  {C.GREEN}[ONLINE SEND]{C.RESET} [{ts}] {device.device_id:<22} │ Ingested OK. Value: {packet['value']} | Risk: {packet['risk_score']}%{alert_marker}")
                    else:
                        print(f"  {C.RED}[SEND FAIL]{C.RESET} HTTP {r.status_code}")
                except Exception as e:
                    print(f"  {C.RED}[SEND ERROR]{C.RESET} Connection error: {e}")

            print(f"{C.DIM}-{C.RESET}" * 60)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Simulator shutting down.{C.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
