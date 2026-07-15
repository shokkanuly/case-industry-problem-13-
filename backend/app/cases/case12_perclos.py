"""
Case 12 — Driver fatigue / microsleep detection.

Computes PERCLOS (the fraction of time eyes are closed beyond 70-80%,
the validated drowsiness metric) from a per-frame eye-aspect-ratio (EAR)
stream, plus blink and microsleep-event detection, gated by vehicle speed
so an alert only fires when the truck is actually moving.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

EAR_CLOSED = 0.20           # eye-aspect-ratio below this = eye closed (P80 convention)
PERCLOS_WARN = 0.15         # 15% eyes-closed time = drowsy
PERCLOS_CRITICAL = 0.30
MICROSLEEP_MIN_S = 0.5      # eyes closed continuously this long = microsleep
MOVING_SPEED_KMH = 5.0


class PerclosEngine(CaseEngine):
    case_id = 12
    slug = "driver-fatigue"
    name = "Driver Fatigue / Microsleep Detection"
    category = "transport-safety"
    stage = "software"
    algorithm = "PERCLOS (P80) + microsleep run-length detection, speed-gated"

    def input_schema(self) -> Dict[str, str]:
        return {
            "fps": "frame rate of the EAR stream",
            "ear": "per-frame eye-aspect-ratio values",
            "speed_kmh": "vehicle speed (scalar or per-frame list)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(53)
        fps, seconds = 30, 60
        n = fps * seconds
        ear: List[float] = []
        for i in range(n):
            base = 0.32 + rng.gauss(0, 0.01)
            # Normal spontaneous blinks: brief dips every ~4 s
            if i % (fps * 4) < 4:
                base = 0.12
            ear.append(base)
        if scenario == "anomaly":
            # Two microsleep episodes: eyes closed ~1.2 s and ~1.8 s
            for start, dur_s in ((fps * 20, 1.2), (fps * 42, 1.8)):
                for k in range(int(dur_s * fps)):
                    ear[start + k] = 0.10 + rng.gauss(0, 0.005)
            # Plus generally heavier lids in the last third
            for i in range(fps * 40, n):
                ear[i] -= 0.05
        return {"fps": fps, "ear": ear, "speed_kmh": 28.0}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        fps = float(payload["fps"])
        ear: List[float] = payload["ear"]
        speed = payload.get("speed_kmh", 30.0)
        speeds = speed if isinstance(speed, list) else [speed] * len(ear)
        if not ear:
            raise ValueError("empty EAR stream")

        closed = [e < EAR_CLOSED for e in ear]
        perclos = sum(closed) / len(closed)

        # Blink + microsleep run-length analysis
        blinks = 0
        microsleeps: List[Dict[str, Any]] = []
        run = 0
        for i, c in enumerate(closed + [False]):
            if c:
                run += 1
            else:
                if run > 0:
                    dur_s = run / fps
                    if dur_s >= MICROSLEEP_MIN_S:
                        microsleeps.append(
                            {"start_s": round((i - run) / fps, 2), "duration_s": round(dur_s, 2)}
                        )
                    else:
                        blinks += 1
                run = 0

        duration_min = len(ear) / fps / 60.0
        blink_rate = blinks / duration_min if duration_min else 0.0
        moving = (sum(speeds) / len(speeds)) >= MOVING_SPEED_KMH

        if not moving:
            status = "normal"
        elif perclos >= PERCLOS_CRITICAL or len(microsleeps) >= 2:
            status = "critical"
        elif perclos >= PERCLOS_WARN or microsleeps:
            status = "warning"
        else:
            status = "normal"

        headline = (
            f"PERCLOS {perclos * 100:.1f}%, {len(microsleeps)} microsleep event(s)"
            + ("" if moving else " (vehicle stationary — alerts suppressed)")
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "perclos": round(perclos, 4),
                "perclos_pct": round(perclos * 100, 2),
                "blink_count": blinks,
                "blink_rate_per_min": round(blink_rate, 1),
                "microsleep_events": microsleeps,
                "vehicle_moving": moving,
                "warn_threshold": PERCLOS_WARN,
                "critical_threshold": PERCLOS_CRITICAL,
            },
            series={"ear": [round(e, 3) for e in ear[:: max(1, len(ear) // 200)]]},
            recommendations=(
                ["Trigger in-cab audible + haptic fatigue alarm", "Notify dispatch; advise rest stop"]
                if status == "critical"
                else ["Escalating drowsiness — issue driver caution prompt"]
                if status == "warning"
                else ["Driver alert — no action"]
            ),
        )
