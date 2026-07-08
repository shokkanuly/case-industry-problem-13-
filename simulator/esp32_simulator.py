"""
Industrial Nervous System — Edge Telemetry Simulator
Simulates local AI model inference, local buffering, and offline synchronization.
Supports all 15 cases defined in the registry.
"""

import time
import math
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


# ─────────────────────────────────────────────
# DEVICE STATE GENERATION
# ─────────────────────────────────────────────
class EdgeDevice:
    def __init__(self, case_id: int, device_id: str, device_type: str, description: str, underground: bool = False):
        self.case_id = case_id
        self.device_id = device_id
        self.device_type = device_type
        self.description = description
        self.underground = underground
        self.battery_v = 4.15
        self.rssi_dbm = -60
        self.buffer = []
        self.tick_count = 0
        
        # Algorithmic state storage variables
        self.mapping_progress = 0.0
        self.history_detections = []
        self.displacement_history = [0.0]
        self.blink_history = []

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
            "unit": "",
            "timestamp": int(time.time()),
            "battery_v": round(self.battery_v, 2),
            "rssi_dbm": self.rssi_dbm,
            "risk_score": 0.0,
            "metadata": {}
        }

        # ─────────────────────────────────────────────
        # REGISTRY-DRIVEN CASE-SPECIFIC GENERATORS
        # ─────────────────────────────────────────────
        try:
            # 1. Geological Survey Drone (Case 1)
            if self.device_id == "dev_expl_drone":
                payload["event"] = "scan"
                self.mapping_progress = min(100.0, self.mapping_progress + random.uniform(5.0, 10.0))
                payload["value"] = round(self.mapping_progress, 1)

                # Generate synthetic 20x20 terrain grid
                anomalies = []
                grid_size = 20
                for x in range(grid_size):
                    for y in range(grid_size):
                        # Elevation baseline with undulating peaks
                        elevation = 500 + 100 * math.sin(x / 3) * math.cos(y / 3) + random.uniform(-10, 10)
                        spectral = random.uniform(0, 1)
                        fracture = random.uniform(0, 1)
                        # Score combines low elevation (accessible valley) with alteraton signals
                        alteration = 0.4 * spectral + 0.4 * fracture + 0.2 * (1.0 - (elevation - 400) / 300)
                        if alteration > 0.75:
                            anomalies.append({
                                "coord": f"{x},{y}",
                                "score": round(alteration, 2),
                                "elevation_m": round(elevation, 1),
                                "spectral_idx": round(spectral, 2),
                                "fracture_density": round(fracture, 2)
                            })
                
                anomalies.sort(key=lambda a: a["score"], reverse=True)
                top_inspections = anomalies[:5]

                payload["metadata"] = {
                    "area_mapped_pct": payload["value"],
                    "anomalies_flagged": len(anomalies),
                    "top_inspection_zones": top_inspections
                }
                print(f"  {C.DIM}[DRONE SURVEY]{C.RESET} {self.device_id}: Grid processed. Anomalies: {len(anomalies)} | Mapped: {payload['value']}%")
                # Reset mapping progress upon full loop completion
                if self.mapping_progress >= 100.0:
                    self.mapping_progress = 0.0

            # 2. Handheld Spectrometer (Case 2 - Demo Slice)
            elif self.device_id == "dev_spec_analyzer":
                payload["event"] = "scan"
                if anomaly_active or (self.tick_count % 4 == 0):
                    if anomaly_active:
                        payload["value"] = round(random.uniform(4.2, 6.8), 2)
                        payload["metadata"] = {
                            "ore_grade_pct": payload["value"],
                            "mineral_type": "Chalcocite",
                            "copper_pct": payload["value"],
                            "gold_oz_t": round(random.uniform(0.25, 0.45), 2),
                            "classification": "High-Grade Core Sample"
                        }
                        print(f"  {C.GREEN}[PORTABLE SCAN]{C.RESET} {self.device_id}: Core Scan Complete: High-Grade Chalcocite found! Grade: {payload['value']}% Cu")
                    else:
                        payload["value"] = round(random.uniform(0.9, 1.8), 2)
                        payload["metadata"] = {
                            "ore_grade_pct": payload["value"],
                            "mineral_type": "Chalcopyrite",
                            "copper_pct": payload["value"],
                            "classification": "Standard Ore Core"
                        }
                        print(f"  {C.DIM}[PORTABLE SCAN]{C.RESET} {self.device_id}: Core Scan Complete. Copper Grade: {payload['value']}%")
                else:
                    payload["value"] = 0.0
                    payload["event"] = "reading"
                    payload["metadata"] = {"status": "calibrated_idle"}
                    print(f"  {C.DIM}[PORTABLE SCAN]{C.RESET} {self.device_id}: Spectrometer calibrated and idle.")
                payload["unit"] = "%"

            # 3. Flotation Reagent Recommender (Case 3)
            elif self.device_id == "dev_ore_grade_sensor":
                payload["event"] = "reading"
                if anomaly_active:
                    payload["value"] = round(random.uniform(0.4, 0.7), 2)
                else:
                    payload["value"] = round(random.uniform(1.35, 1.65), 2)
                
                # Reagent Xanthate dosage estimate algorithm: dosage = 2.5 - 1.2 * grade
                optimal_dosage = max(0.1, round(2.5 - 1.2 * payload["value"], 2))
                target_dosage = 0.7  # L/ton standard
                deviation = round(optimal_dosage - target_dosage, 2)
                
                # Map risk_score based on deviation limits: Warning = 0.2, Critical = 0.5
                abs_dev = abs(deviation)
                if abs_dev < 0.2:
                    payload["risk_score"] = round(abs_dev / 0.2 * 39, 1)
                elif abs_dev < 0.5:
                    payload["risk_score"] = round(40 + (abs_dev - 0.2) / 0.3 * 34, 1)
                else:
                    payload["risk_score"] = round(75 + min(24.0, (abs_dev - 0.5) * 50), 1)

                payload["metadata"] = {
                    "reagent_type": "Xanthate Collector",
                    "recommended_dosage_l_ton": optimal_dosage,
                    "current_deviation": deviation
                }
                payload["unit"] = "%"
                print(f"  {C.DIM}[REAGENT OPT]{C.RESET} {self.device_id}: Ore grade: {payload['value']}% | Recommended dosage: {optimal_dosage} L/ton (Dev: {deviation:+})")

            # 4. Short-Circuit Thermal Camera (Case 4 - Demo Slice)
            elif self.device_id == "dev_cv_shortcircuit":
                if anomaly_active:
                    payload["value"] = round(random.uniform(98.0, 118.0), 1)
                    payload["risk_score"] = round(random.uniform(85.0, 98.0), 1)
                    payload["metadata"] = {
                        "short_circuit_detected": True,
                        "coordinate": f"Cathode_Grid_{random.choice(['A4', 'B2', 'D1'])}",
                        "temperature_anomaly_c": payload["value"] - 50.0
                    }
                    print(f"  {C.MAGENTA}[EDGE CV-THERMAL]{C.RESET} {self.device_id}: Short-circuit detected at {payload['metadata']['coordinate']}! Temperature: {payload['value']}°C")
                else:
                    payload["value"] = round(random.uniform(45.0, 52.0), 1)
                    payload["risk_score"] = round(random.uniform(5.0, 15.0), 1)
                    payload["metadata"] = {"short_circuit_detected": False}
                    print(f"  {C.DIM}[EDGE CV-THERMAL]{C.RESET} {self.device_id}: Thermal camera scan normal. Mean Temp: {payload['value']}°C")
                payload["unit"] = "°C"

            # 5. Slope Stability Radar (Case 5)
            elif self.device_id == "dev_slope_radar":
                payload["event"] = "reading"
                
                # Displacement calculation: accumulate mm of displacement
                last_disp = self.displacement_history[-1]
                if anomaly_active:
                    # Accelerating displacement: exponential creep model
                    t = len(self.displacement_history)
                    delta = 0.2 + 0.1 * math.exp(t * 0.12)
                else:
                    # Constant slow creep
                    delta = random.uniform(0.05, 0.15)
                    # Limit history window size to prevent memory leaks
                    if len(self.displacement_history) > 20:
                        self.displacement_history.pop(0)

                new_disp = round(last_disp + delta, 2)
                self.displacement_history.append(new_disp)
                
                # Calculate velocity and acceleration
                velocity = delta
                if len(self.displacement_history) >= 3:
                    prev_delta = self.displacement_history[-2] - self.displacement_history[-3]
                    acceleration = round(delta - prev_delta, 3)
                else:
                    acceleration = 0.0
                
                # Risk mapping on acceleration: Warning > 0.5, Critical > 1.5
                if acceleration <= 0.05:
                    payload["risk_score"] = round(random.uniform(1.0, 15.0), 1)
                elif acceleration < 0.15:
                    payload["risk_score"] = round(40.0 + (acceleration - 0.05) / 0.10 * 30.0, 1)
                else:
                    payload["risk_score"] = round(75.0 + min(24.0, (acceleration - 0.15) * 100.0), 1)
                    
                payload["value"] = round(velocity, 2)
                payload["unit"] = "mm/day"
                payload["metadata"] = {
                    "cumulative_displacement_mm": new_disp,
                    "displacement_acceleration": acceleration,
                    "trend_analysis": "Accelerating Slip" if acceleration > 0.05 else "Stable Creep"
                }
                print(f"  {C.DIM}[SLOPE RADAR]{C.RESET} {self.device_id}: Velocity: {payload['value']} mm/day | Accel: {acceleration} mm/day² | Risk: {payload['risk_score']}%")

            # 6. Haul Truck Radar (Case 6)
            elif self.device_id == "dev_truck_collision":
                payload["event"] = "reading"
                
                # Speed & Gear Status simulation
                truck_speed = random.choice([0.0, 15.0, 32.0]) if not anomaly_active else 24.0
                transmission = "Neutral" if truck_speed == 0.0 else "Drive"
                
                if anomaly_active:
                    distance = round(random.uniform(1.5, 4.2), 1)
                else:
                    distance = round(random.uniform(12.0, 45.0), 1)
                    
                # Warning if distance <= 10m AND speed > 0. Critical if distance <= 5m AND speed > 0.
                if distance > 10.0 or truck_speed == 0.0:
                    payload["risk_score"] = round((10.0 / distance) * 20.0, 1) if distance > 0 else 0.0
                elif distance > 5.0:
                    payload["risk_score"] = round(40.0 + (10.0 - distance) / 5.0 * 34.0, 1)
                else:
                    payload["risk_score"] = round(75.0 + (5.0 - distance) / 5.0 * 24.0, 1)
                    
                payload["value"] = 1.0 if (distance <= 5.0 and truck_speed > 0) else 0.0
                payload["unit"] = "violation"
                payload["metadata"] = {
                    "radar_distance_m": distance,
                    "truck_speed_kmh": truck_speed,
                    "transmission_gear": transmission,
                    "object_detected": distance <= 10.0
                }
                print(f"  {C.DIM}[TRUCK RADAR]{C.RESET} {self.device_id}: Distance: {distance}m | Speed: {truck_speed}km/h | Risk: {payload['risk_score']}%")

            # 7. Vanyukov Furnace Blast (Case 7 - Demo Slice)
            elif self.device_id == "dev_furnace_sensor":
                if anomaly_active:
                    if random.random() < 0.5:
                        payload["value"] = round(random.uniform(15.0, 16.5), 1)
                    else:
                        payload["value"] = round(random.uniform(9.5, 10.8), 1)
                    payload["risk_score"] = round(random.uniform(80.0, 94.0), 1)
                    print(f"  {C.CYAN}[EDGE OPTIMIZER]{C.RESET} {self.device_id}: Furnace deviation anomaly! Coke Ratio: {payload['value']}%")
                else:
                    payload["value"] = round(random.uniform(12.2, 13.2), 1)
                    payload["risk_score"] = round(random.uniform(5.0, 18.0), 1)
                    print(f"  {C.DIM}[EDGE OPTIMIZER]{C.RESET} {self.device_id}: Furnace parameters stable. Coke Ratio: {payload['value']}%")
                payload["unit"] = "%"

            # 8. Flotation Machine Diagnostics (Case 8 - Demo Slice)
            elif self.device_id == "dev_vib_flotation":
                if anomaly_active:
                    payload["value"] = round(random.uniform(8.5, 12.0), 2)
                    payload["risk_score"] = round(random.uniform(80.0, 95.0), 1)
                    payload["metadata"] = {
                        "bearing_fault_detected": True,
                        "velocity_rms_mms": payload["value"]
                    }
                    print(f"  {C.YELLOW}[EDGE SPECTRAL-AI]{C.RESET} {self.device_id}: Bearing fault! Vibration: {payload['value']} mm/s.")
                else:
                    payload["value"] = round(random.uniform(1.2, 2.3), 2)
                    payload["risk_score"] = round(random.uniform(2.0, 14.0), 1)
                    payload["metadata"] = {"bearing_fault_detected": False}
                    print(f"  {C.DIM}[EDGE SPECTRAL-AI]{C.RESET} {self.device_id}: Pump health normal. Vibration RMS: {payload['value']} mm/s.")
                payload["unit"] = "mm/s"

            # 9. Balkhash Lake Biodiversity (Case 9)
            elif self.device_id == "dev_lake_biodiversity":
                payload["event"] = "scan"
                
                # Rolling window frequency tracking
                species_pool = ["Carp", "Sturgeon", "Pelican", "Fox", "Gull"]
                detected_species = random.choice(species_pool)
                confidence = round(random.uniform(0.85, 0.99), 2)
                
                self.history_detections.append({
                    "timestamp": int(time.time()),
                    "species": detected_species,
                    "confidence": confidence
                })
                if len(self.history_detections) > 15:
                    self.history_detections.pop(0)
                    
                novelty = "None"
                if anomaly_active or (self.tick_count % 8 == 0):
                    novelty = "Trachemys scripta elegans (Invasive Turtle)"
                    self.history_detections.append({
                        "timestamp": int(time.time()),
                        "species": novelty,
                        "confidence": 0.97
                    })
                    print(f"  {C.YELLOW}[LAKE MONITOR]{C.RESET} {self.device_id}: Invasive Species Sighted: {novelty}")
                    
                counts = {}
                for d_item in self.history_detections:
                    s = d_item["species"]
                    counts[s] = counts.get(s, 0) + 1
                    
                payload["value"] = float(len(counts))
                payload["unit"] = "species"
                payload["metadata"] = {
                    "species_tallied": len(counts),
                    "novel_species_detected": novelty,
                    "detections_summary": counts,
                    "recent_detections": self.history_detections[-5:]
                }
                print(f"  {C.DIM}[LAKE MONITOR]{C.RESET} {self.device_id}: Tallied {payload['value']} unique species in window.")

            # 10. Tunnel Wi-Fi Gateway (Case 10)
            elif self.device_id == "dev_mesh_gateway":
                payload["event"] = "reading"
                
                # Simulates ping response time + packet drop rates.
                if anomaly_active:
                    latency = round(random.uniform(180.0, 420.0), 1)
                    packet_loss = round(random.uniform(18.0, 35.0), 1)
                else:
                    latency = round(random.uniform(15.0, 35.0), 1)
                    packet_loss = round(random.uniform(0.0, 1.2), 2)
                    
                # Model: Warning if latency > 150ms or loss > 5%. Critical if latency > 300ms or loss > 15%.
                if latency <= 150.0 and packet_loss <= 5.0:
                    payload["risk_score"] = round(latency / 150.0 * 39.0, 1)
                elif latency <= 300.0 and packet_loss <= 15.0:
                    payload["risk_score"] = round(40.0 + (latency - 150.0) / 150.0 * 34.0, 1)
                else:
                    payload["risk_score"] = round(75.0 + min(24.0, (latency - 300.0) / 300.0 * 24.0), 1)
                    
                payload["value"] = latency
                payload["unit"] = "ms"
                payload["metadata"] = {
                    "mesh_packet_loss_pct": packet_loss,
                    "redundant_nodes_online": random.randint(3, 5) if not anomaly_active else 1,
                    "signal_quality_dbm": self.rssi_dbm
                }
                print(f"  {C.DIM}[UNDERGROUND COMMS]{C.RESET} {self.device_id}: Latency: {latency}ms | Packet Loss: {packet_loss}% | Risk: {payload['risk_score']}%")

            # 11. Mill energy tariff optimizer (Case 11)
            elif self.device_id == "dev_energy_opt":
                payload["event"] = "reading"
                
                # Local time tariff schedule: peak hours between 18:00 and 22:00
                now_dt = datetime.now()
                hour = now_dt.hour
                is_peak = (18 <= hour < 22) or anomaly_active
                
                target_load = 2200.0
                if is_peak:
                    payload["value"] = round(random.uniform(2650.0, 2950.0), 1)
                    excess_kw = payload["value"] - target_load
                    excess_cost_usd = round(excess_kw * 0.18, 2)
                    payload["risk_score"] = round(80.0 + random.uniform(0.0, 13.0), 1)
                    
                    payload["metadata"] = {
                        "peak_tariff_window": True,
                        "tariff_rate_multiplier": "2.5x (Peak)",
                        "estimated_excess_cost_hr": excess_cost_usd,
                        "peak_shaving_recommendation": f"Reduce mill throughput by {round(excess_kw, 1)} kW to avoid peak tariff surcharges."
                    }
                    print(f"  {C.YELLOW}[ENERGY TARIFF]{C.RESET} {self.device_id}: Peak Load Violation! Load: {payload['value']} kW (Limit: {target_load} kW)")
                else:
                    payload["value"] = round(random.uniform(2050.0, 2350.0), 1)
                    payload["risk_score"] = round(random.uniform(5.0, 15.0), 1)
                    payload["metadata"] = {
                        "peak_tariff_window": False,
                        "tariff_rate_multiplier": "1.0x (Standard)",
                        "estimated_excess_cost_hr": 0.0
                    }
                    print(f"  {C.DIM}[ENERGY TARIFF]{C.RESET} {self.device_id}: Load stable. Load: {payload['value']} kW")
                payload["unit"] = "kW"

            # 12. Fatigue Camera (Case 12)
            elif self.device_id == "dev_driver_fatigue":
                payload["event"] = "reading"
                
                # Blink Duration tracking: Normal (0.1s - 0.3s), Drowsy (0.6s - 2.2s)
                if anomaly_active:
                    blink_duration = round(random.uniform(0.6, 2.2), 2)
                else:
                    blink_duration = round(random.uniform(0.1, 0.3), 2)
                    
                is_closed = 1 if blink_duration > 0.4 else 0
                self.blink_history.append(is_closed)
                if len(self.blink_history) > 10:
                    self.blink_history.pop(0)
                    
                # PERCLOS: percent of time eyes closed in rolling window
                perclos_pct = round(sum(self.blink_history) / len(self.blink_history) * 100.0, 1) if self.blink_history else 0.0
                
                if perclos_pct < 15.0:
                    payload["risk_score"] = round(perclos_pct / 15.0 * 39.0, 1)
                elif perclos_pct <= 30.0:
                    payload["risk_score"] = round(40.0 + (perclos_pct - 15.0) / 15.0 * 34.0, 1)
                else:
                    payload["risk_score"] = round(75.0 + min(24.0, (perclos_pct - 30.0) / 70.0 * 24.0), 1)
                    
                payload["value"] = 1.0 if perclos_pct > 30.0 else 0.0
                payload["unit"] = "violation"
                payload["metadata"] = {
                    "perclos_index_pct": perclos_pct,
                    "latest_blink_duration_s": blink_duration,
                    "eyelid_state": "Drowsy/Closed" if is_closed else "Active/Open"
                }
                print(f"  {C.DIM}[FATIGUE DETECTOR]{C.RESET} {self.device_id}: PERCLOS: {perclos_pct}% | Last Blink: {blink_duration}s | Risk: {payload['risk_score']}%")

            # 13. Safety PPE Compliance (Case 13)
            elif self.device_id == "dev_cv_safety":
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
                    # Clamped strictly between 0 and 100.0% to resolve random overflow bug
                    compliance_pct = max(0.0, min(100.0, round(100.0 - random.uniform(0.0, 2.0), 1)))
                    payload["metadata"] = {
                        "ppe_compliance_pct": compliance_pct,
                        "worker_in_danger_zone": False
                    }
                    print(f"  {C.DIM}[EDGE YOLOv8-PPE]{C.RESET} {self.device_id}: Haul road safety compliant. Compliance: {compliance_pct}%")
                payload["unit"] = "violation"

            # 14. Reversing Wagon Video (Case 14)
            elif self.device_id == "dev_wagon_rear_cam":
                if anomaly_active:
                    distance = round(random.uniform(0.5, 2.8), 1)
                else:
                    distance = round(random.uniform(8.5, 22.0), 1)
                    
                # Warning if distance <= 8m, Critical if distance <= 3m
                if distance > 8.0:
                    payload["risk_score"] = round((8.0 / distance) * 25.0, 1)
                elif distance > 3.0:
                    payload["risk_score"] = round(40.0 + (8.0 - distance) / 5.0 * 34.0, 1)
                else:
                    payload["risk_score"] = round(75.0 + (3.0 - distance) / 3.0 * 24.0, 1)
                    
                payload["value"] = 1.0 if distance <= 3.0 else 0.0
                payload["unit"] = "violation"
                payload["metadata"] = {
                    "rear_sensor_distance_m": distance,
                    "obstruction_warning": distance <= 8.0,
                    "braking_system_engaged": distance <= 3.0
                }
                print(f"  {C.DIM}[RAIL COUPLING]{C.RESET} {self.device_id}: Rear Distance: {distance}m | Risk: {payload['risk_score']}%")

            # 15. Road core concrete analyzer (Case 15)
            elif self.device_id == "dev_concrete_analyzer":
                payload["event"] = "scan"
                
                # Multi-class classification spectrometer analyzer mapping wavelengths to concrete grades
                if anomaly_active:
                    peak_wavelength = 2200
                    peak_intensity = round(random.uniform(0.42, 0.58), 2)
                    compressive_strength = round(random.uniform(15.0, 22.5), 1)
                    composition = "Grade-20 Lower-Strength Concrete Mix"
                    confidence = round(random.uniform(0.72, 0.85), 2)
                else:
                    if random.random() < 0.5:
                        peak_wavelength = 2200
                        peak_intensity = round(random.uniform(0.78, 0.95), 2)
                        compressive_strength = round(random.uniform(32.5, 42.0), 1)
                        composition = "Grade-40 High-Strength Concrete Mix"
                        confidence = round(random.uniform(0.91, 0.98), 2)
                    else:
                        peak_wavelength = 2350
                        peak_intensity = round(random.uniform(0.75, 0.92), 2)
                        compressive_strength = round(random.uniform(28.0, 35.0), 1)
                        composition = "Grade-35 Standard Asphalt Mix"
                        confidence = round(random.uniform(0.89, 0.97), 2)
                        
                payload["value"] = compressive_strength
                payload["unit"] = "%"
                payload["metadata"] = {
                    "compressive_strength_mpa": compressive_strength,
                    "peak_wavelength_nm": peak_wavelength,
                    "peak_intensity": peak_intensity,
                    "curing_days": 28,
                    "composition": composition,
                    "analyzer_confidence": confidence
                }
                print(f"  {C.DIM}[CONCRETE SCANNER]{C.RESET} {self.device_id}: Scanner classification: {composition} | Strength: {compressive_strength} MPa")

        except Exception as e:
            # Fault-isolation fallback to safeguard the main simulation loop
            import traceback
            print(f"  {C.RED}[SIMULATOR ERROR] Fault isolated on device {self.device_id}: {e}{C.RESET}")
            traceback.print_exc()
            payload["value"] = 0.0
            payload["risk_score"] = 0.0
            payload["metadata"] = {"error": str(e)}

        return payload


# ─────────────────────────────────────────────
# MAIN SIMULATOR LOOP
# ─────────────────────────────────────────────
def main():
    print(f"\n{C.BOLD}{'═' * 70}")
    print(f"  INDUSTRIAL NERVOUS SYSTEM — EDGE SIMULATOR WORKER")
    print(f"  Ingest URL: {API_URL}")
    print(f"  Interval:   {INTERVAL}s")
    print(f"{'═' * 70}{C.RESET}\n")

    # Load 15 devices dynamically from Case Registry JSON
    devices = []
    try:
        registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "app", "case_registry.json")
        if not os.path.exists(registry_path):
            registry_path = os.path.join(os.path.dirname(__file__), "case_registry.json")
        
        with open(registry_path, "r") as f:
            registry = json.load(f)
        
        for case in registry.get("cases", []):
            d = EdgeDevice(
                case_id=case["case_id"],
                device_id=case["device_id"],
                device_type=case["input_type"],
                description=case["name"],
                underground=case.get("underground", False)
            )
            devices.append(d)
    except Exception as e:
        print(f"{C.RED}Error seeding dynamic registry devices: {e}{C.RESET}")
        sys.exit(1)

    for d in devices:
        underground_str = f" {C.MAGENTA}[UG]{C.RESET}" if d.underground else ""
        print(f"  📡  {C.CYAN}{d.device_id:<22}{C.RESET} │ {d.description}{underground_str}")

    print(f"\n{C.DIM}Underground Tunnel Connectivity (Case 10) Drop Schedule: 15s drop every 60s.{C.RESET}")
    print(f"{C.DIM}Press Ctrl+C to exit.{C.RESET}\n")

    try:
        start_time = time.time()
        tick_index = 0
        while True:
            current_time = time.time() - start_time
            # Connection drop schedule: offline during seconds 40-55 of every minute
            loop_sec = int(current_time) % 60
            periodic_offline = (40 <= loop_sec < 55)

            tick_index += 1

            for d in devices:
                # Decide if this device runs this tick (Cadence Control)
                is_demo = d.case_id in [2, 4, 7, 8, 13]
                if not is_demo and (tick_index % 6 != 0):
                    continue

                # 1. Fetch overrides from backend API
                override = d.get_override_state()
                anomaly_active = override.get("anomaly_active", False)
                connection_override = override.get("connection_active", True)

                # Underground devices drop connection during periodic drop
                is_connected = connection_override
                if d.underground and periodic_offline:
                    is_connected = False

                # 2. Generate current telemetry
                packet = d.generate_packet(anomaly_active)

                if not is_connected:
                    # 3. Buffer local telemetry during outages
                    d.buffer.append(packet)
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  {C.YELLOW}[OFFLINE BUFF]{C.RESET} [{ts}] {d.device_id:<22} │ "
                          f"Queued packet. Local Flash Buffer size: {len(d.buffer)}")
                else:
                    # 4. Flush buffer first if we just reconnected
                    if len(d.buffer) > 0:
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"  {C.GREEN}[CONNECTED]{C.RESET} [{ts}] {d.device_id:<22} │ "
                              f"Reconnected. Bursting {len(d.buffer)} buffered packets...")
                        
                        # Flush in chronological order
                        while len(d.buffer) > 0:
                            buffered_pkt = d.buffer.pop(0)
                            try:
                                r = requests.post(API_URL, json=buffered_pkt, headers=HEADERS, timeout=2.0)
                                if r.status_code == 200:
                                    print(f"    ↳ {C.GREEN}Synced packet{C.RESET} from timestamp {datetime.fromtimestamp(buffered_pkt['timestamp']).strftime('%H:%M:%S')}")
                                else:
                                    d.buffer.insert(0, buffered_pkt)
                                    print(f"    ↳ {C.RED}Failed to sync{C.RESET}: HTTP {r.status_code}")
                                    break
                            except Exception as e:
                                d.buffer.insert(0, buffered_pkt)
                                print(f"    ↳ {C.RED}Sync error{C.RESET}: {e}")
                                break
                            time.sleep(0.2)

                    # 5. Send current packet
                    try:
                        ts = datetime.now().strftime("%H:%M:%S")
                        r = requests.post(API_URL, json=packet, headers=HEADERS, timeout=2.0)
                        if r.status_code == 200:
                            resp = r.json()
                            alerts = resp.get("alerts_fired", 0)
                            alert_marker = f" {C.RED}{C.BOLD}⚠ ALERT{C.RESET}" if alerts > 0 else ""
                            print(f"  {C.GREEN}[ONLINE SEND]{C.RESET} [{ts}] {d.device_id:<22} │ Ingested OK. Value: {packet['value']}{packet['unit']} | Risk: {packet['risk_score']}%{alert_marker}")
                        else:
                            print(f"  {C.RED}[SEND FAIL]{C.RESET} HTTP {r.status_code}: {r.text[:60]}")
                    except Exception as e:
                        print(f"  {C.RED}[SEND ERROR]{C.RESET} {d.device_id} connection error: {e}")

            print(f"{C.DIM}-{C.RESET}" * 60)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Simulator shutting down.{C.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
