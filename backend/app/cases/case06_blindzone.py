"""
Case 06 — Haul truck blind-zone safety.

Software core of the onboard collision-warning unit: given tracked objects
(from CV/radar fusion) in truck-relative coordinates, classifies each into
a blind-zone sector, computes closing speed and time-to-collision, and
grades the warning the same way commercial proximity-detection systems do
(advise -> caution -> stop).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

# Blind-zone sectors around a haul truck, truck-relative metres
# (x: forward+, y: left+). Real geometry varies per truck model.
SECTORS = {
    "front": {"x": (2.0, 18.0), "y": (-5.0, 5.0)},
    "rear": {"x": (-22.0, -4.0), "y": (-6.0, 6.0)},
    "left": {"x": (-4.0, 8.0), "y": (3.0, 12.0)},
    "right": {"x": (-4.0, 8.0), "y": (-12.0, -3.0)},
}
TTC_STOP_S = 4.0
TTC_CAUTION_S = 9.0
PERSON_RANGE_STOP_M = 15.0   # any person this close in a blind zone = stop


class BlindZoneEngine(CaseEngine):
    case_id = 6
    slug = "haul-truck-blindzone"
    name = "Haul Truck Blind-Zone Safety"
    category = "transport-safety"
    stage = "hardware-later"
    algorithm = "Sector classification + closing-speed time-to-collision grading"
    architecture_type = (
        "Vehicle-edge (Jetson-class GPU) with inter-vehicle wireless mesh; integrates with the mine's Fleet Management System"
    )
    why_distinct = (
        "The only case requiring direct vehicle-to-vehicle communication, independent of the central platform — central-server latency is unacceptable in a collision scenario."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "truck_speed_kmh": "own truck speed",
            "objects": "list of {id, kind: person|vehicle, x_m, y_m, vx_ms, vy_ms}",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(21)
        objects = [
            {"id": "LV-104", "kind": "vehicle", "x_m": 45.0, "y_m": 14.0,
             "vx_ms": -0.5, "vy_ms": 0.0},
        ]
        if scenario == "anomaly":
            objects += [
                # Person walking into the rear blind zone
                {"id": "P-01", "kind": "person", "x_m": -12.0, "y_m": 2.0,
                 "vx_ms": 0.0, "vy_ms": -0.8},
                # Light vehicle closing fast from the right
                {"id": "LV-207", "kind": "vehicle", "x_m": 6.0, "y_m": -22.0,
                 "vx_ms": 0.0, "vy_ms": 4.5},
            ]
        return {"truck_speed_kmh": rng.uniform(18, 24), "objects": objects}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        objects: List[Dict[str, Any]] = payload.get("objects", [])
        threats: List[Dict[str, Any]] = []

        for obj in objects:
            x, y = float(obj["x_m"]), float(obj["y_m"])
            vx, vy = float(obj.get("vx_ms", 0)), float(obj.get("vy_ms", 0))
            rng_m = math.hypot(x, y)

            sector = next(
                (name for name, s in SECTORS.items()
                 if s["x"][0] <= x <= s["x"][1] and s["y"][0] <= y <= s["y"][1]),
                None,
            )

            # Closing speed: negative radial velocity means approaching
            closing = -(x * vx + y * vy) / (rng_m or 1e-6)
            ttc = rng_m / closing if closing > 0.1 else None

            level = "advise"
            if sector and obj["kind"] == "person" and rng_m <= PERSON_RANGE_STOP_M:
                level = "stop"
            elif ttc is not None and ttc <= TTC_STOP_S:
                level = "stop"
            elif (sector and closing > 0) or (ttc is not None and ttc <= TTC_CAUTION_S):
                level = "caution"
            elif not sector:
                continue  # outside all monitored zones and no imminent TTC

            threats.append(
                {
                    "id": obj["id"],
                    "kind": obj["kind"],
                    "sector": sector or "approach",
                    "range_m": round(rng_m, 1),
                    "closing_ms": round(closing, 2),
                    "ttc_s": round(ttc, 1) if ttc is not None else None,
                    "level": level,
                }
            )

        order = {"stop": 0, "caution": 1, "advise": 2}
        threats.sort(key=lambda t: (order[t["level"]], t["range_m"]))
        worst = threats[0]["level"] if threats else None
        status = {"stop": "critical", "caution": "warning", "advise": "normal", None: "normal"}[worst]
        headline = (
            f"{threats[0]['kind'].upper()} {threats[0]['id']} in {threats[0]['sector']} zone "
            f"at {threats[0]['range_m']} m — {worst.upper()} warning"
            if threats
            else "All blind-zone sectors clear"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "threats": threats,
                "objects_tracked": len(objects),
                "ttc_stop_s": TTC_STOP_S,
                "ttc_caution_s": TTC_CAUTION_S,
            },
            recommendations=(
                ["Sound in-cab STOP alarm; broadcast V2V proximity warning",
                 "Hold truck until sector confirmed clear"]
                if status == "critical"
                else ["In-cab caution chime; reduce speed"]
                if status == "warning"
                else ["No action — continue haul cycle"]
            ),
        )
