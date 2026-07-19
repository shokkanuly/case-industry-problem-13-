"""
Case 14 — Reversing wagon rear camera (standalone fail-safe).

The design constraint IS the software: a proximity/motion-dwell detector
that must reach a stop decision purely from local sensor data with zero
network dependency. This engine fuses a rear rangefinder track with an
optical-flow "motion in path" flag and applies a dwell filter (an obstacle
must persist N frames before it trips a stop) to reject sensor flicker.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

STOP_DISTANCE_M = 5.0
SLOW_DISTANCE_M = 15.0
DWELL_FRAMES = 3        # obstacle must persist this many frames to trip
NETWORK_REQUIRED = False


class WagonCameraEngine(CaseEngine):
    case_id = 14
    slug = "wagon-rear-camera"
    name = "Reversing Wagon Rear Camera"
    category = "rail-safety"
    stage = "hardware-later"
    algorithm = "Proximity + motion-dwell fusion with flicker-reject filter (offline fail-safe)"
    architecture_type = (
        "Standalone fail-safe device wired directly to the in-cab display — deliberately NOT cloud-dependent"
    )
    why_distinct = (
        "The only case explicitly designed to keep working if the rest of the platform is completely down; the central link is for logging only."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "distances_m": "per-frame nearest-obstacle range from rear rangefinder",
            "motion_in_path": "per-frame boolean, optical-flow motion within track corridor",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(67)
        n = 30
        distances = [40.0 - 0.8 * i + rng.gauss(0, 0.3) for i in range(n)]  # closing on a clear buffer
        motion = [False] * n
        if scenario == "anomaly":
            # A person steps into the corridor at frame 12 and stays
            for i in range(12, n):
                distances[i] = min(distances[i], 6.0 - 0.2 * (i - 12))
                motion[i] = True
            # One-frame sensor glitch earlier that must NOT trip a stop
            distances[5] = 3.0
        return {"distances_m": distances, "motion_in_path": motion}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        distances: List[float] = payload["distances_m"]
        motion: List[bool] = payload.get("motion_in_path", [False] * len(distances))

        decisions: List[str] = []
        stop_run = 0
        first_stop_frame = None
        first_glitch_rejected = False

        for i, d in enumerate(distances):
            in_stop = d <= STOP_DISTANCE_M or (motion[i] and d <= SLOW_DISTANCE_M)
            if in_stop:
                stop_run += 1
            else:
                if 0 < stop_run < DWELL_FRAMES:
                    first_glitch_rejected = True   # a short burst got filtered out
                stop_run = 0

            if stop_run >= DWELL_FRAMES:
                decisions.append("STOP")
                if first_stop_frame is None:
                    first_stop_frame = i
            elif d <= SLOW_DISTANCE_M:
                decisions.append("SLOW")
            else:
                decisions.append("CLEAR")

        tripped = first_stop_frame is not None
        min_dist = min(distances)
        status = "critical" if tripped else "warning" if min_dist <= SLOW_DISTANCE_M else "normal"
        headline = (
            f"STOP asserted at frame {first_stop_frame} (obstacle held {DWELL_FRAMES}+ frames)"
            if tripped
            else f"No stop condition — nearest obstacle {min_dist:.1f} m"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "stop_asserted": tripped,
                "first_stop_frame": first_stop_frame,
                "min_distance_m": round(min_dist, 2),
                "glitch_rejected_by_dwell": first_glitch_rejected,
                "dwell_frames": DWELL_FRAMES,
                "network_required": NETWORK_REQUIRED,
                "final_decision": decisions[-1] if decisions else "CLEAR",
            },
            series={"distances_m": [round(d, 2) for d in distances]},
            recommendations=(
                ["Assert in-cab STOP relay locally (no network round-trip)",
                 "Hold movement until corridor clears for 3+ frames"]
                if tripped
                else ["Continue reverse move at restricted speed"]
                if status == "warning"
                else ["Corridor clear"]
            ),
        )
