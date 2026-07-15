"""
Case 05 — Pit slope stability: inverse-velocity time-of-failure forecast.

Implements the Fukuzono (1985) inverse-velocity method used across open-pit
geotechnical monitoring: during progressive failure, 1/velocity of wall
displacement trends linearly toward zero; extrapolating the least-squares
line to 1/v = 0 gives the predicted failure time. Alert levels follow the
industry-standard velocity + trend gating.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from app.cases.base import CaseEngine, CaseResult

ONSET_VELOCITY_MM_DAY = 0.5      # velocity above which regression window opens
ALARM_VELOCITY_MM_DAY = 10.0     # immediate evacuation-level velocity
MIN_POINTS = 4


def linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    """Least squares fit y = a*x + b. Returns (a, b, r2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, my, 0.0
    a = sxy / sxx
    b = my - a * mx
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys) or 1e-12
    r2 = 1.0 - ss_res / ss_tot
    return a, b, r2


class SlopeStabilityEngine(CaseEngine):
    case_id = 5
    slug = "pit-slope-stability"
    name = "Pit Slope Stability"
    category = "geotech-safety"
    stage = "software"
    algorithm = "Fukuzono inverse-velocity linear extrapolation to 1/v = 0"

    def input_schema(self) -> Dict[str, str]:
        return {
            "timestamps_days": "observation times in days (monotonic)",
            "displacements_mm": "cumulative wall displacement per observation (mm)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(13)
        ts = [i * 0.25 for i in range(60)]  # 15 days, 6-hourly radar epochs
        if scenario == "normal":
            disp = [0.1 * t + rng.gauss(0, 0.05) for t in ts]
        else:
            # Fukuzono alpha=2 creep: velocity ∝ 1/(t_f - t), so displacement is
            # logarithmic and 1/velocity falls linearly toward zero at failure.
            t_f, c = 16.5, 5.0
            disp = [c * math.log(t_f / (t_f - t)) + rng.gauss(0, 0.01) for t in ts]
        return {"timestamps_days": ts, "displacements_mm": disp}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        ts: List[float] = payload["timestamps_days"]
        disp: List[float] = payload["displacements_mm"]
        if len(ts) < MIN_POINTS + 1:
            raise ValueError(f"Need at least {MIN_POINTS + 1} observations")

        # Central-difference velocities (mm/day)
        vels: List[float] = []
        vts: List[float] = []
        for i in range(1, len(ts)):
            dt = ts[i] - ts[i - 1]
            if dt <= 0:
                continue
            vels.append((disp[i] - disp[i - 1]) / dt)
            vts.append((ts[i] + ts[i - 1]) / 2)

        current_v = vels[-1] if vels else 0.0

        # Open the inverse-velocity regression window where v exceeds onset
        window = [(t, v) for t, v in zip(vts, vels) if v > ONSET_VELOCITY_MM_DAY]
        ttf_days: Optional[float] = None
        r2 = 0.0
        slope = 0.0
        if len(window) >= MIN_POINTS:
            xs = [t for t, _ in window]
            ys = [1.0 / v for _, v in window]
            slope, intercept, r2 = linear_regression(xs, ys)
            if slope < 0 and r2 > 0.5:
                t_fail = -intercept / slope
                remaining = t_fail - ts[-1]
                if remaining > 0:
                    ttf_days = round(remaining, 2)

        if current_v >= ALARM_VELOCITY_MM_DAY or (ttf_days is not None and ttf_days < 2):
            status = "critical"
        elif ttf_days is not None or current_v > ONSET_VELOCITY_MM_DAY:
            status = "warning"
        else:
            status = "normal"

        if ttf_days is not None:
            headline = (
                f"Accelerating deformation: projected failure in {ttf_days} days "
                f"(inverse-velocity fit R²={r2:.2f})"
            )
        elif current_v > ONSET_VELOCITY_MM_DAY:
            headline = f"Elevated wall velocity {current_v:.1f} mm/day — regression window open"
        else:
            headline = f"Wall stable: velocity {current_v:.2f} mm/day below onset threshold"

        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "current_velocity_mm_day": round(current_v, 3),
                "time_to_failure_days": ttf_days,
                "regression_r2": round(r2, 3),
                "regression_slope": round(slope, 5),
                "onset_threshold_mm_day": ONSET_VELOCITY_MM_DAY,
                "alarm_threshold_mm_day": ALARM_VELOCITY_MM_DAY,
                "points_in_window": len(window),
            },
            series={
                "velocity_mm_day": [round(v, 3) for v in vels],
                "inverse_velocity": [round(1.0 / v, 4) if v > 0.01 else 100.0 for v in vels],
            },
            recommendations=(
                ["EVACUATE bench below monitored sector; restrict haul road access",
                 "Increase radar epoch rate to continuous scan"]
                if status == "critical"
                else ["Notify geotechnical engineer; raise monitoring frequency"]
                if status == "warning"
                else ["Continue routine radar epochs"]
            ),
        )
