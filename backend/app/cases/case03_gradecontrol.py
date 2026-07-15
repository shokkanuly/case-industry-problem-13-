"""
Case 03 — Ore grade control.

A PI-style dosing controller: given a grade time series from a cross-belt
analyzer, computes the reagent dosing setpoint proportional to deviation
from target grade with an integral term, subject to a dead-band and a
per-step slew-rate limit — the same structure a plant DCS loop would run.
Advisory output is a new setpoint, not an actuation.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

TARGET_GRADE = 4.7          # % Cu feed target the circuit is tuned for
BASE_DOSE = 12.0            # mL/t collector at target grade
KP = 2.4                    # mL/t per % grade deviation
KI = 0.35
DEAD_BAND = 0.15            # % grade deviation ignored (avoids dosing chatter)
MAX_STEP = 1.5              # mL/t max change per control interval
DOSE_LIMITS = (4.0, 28.0)


class GradeControlEngine(CaseEngine):
    case_id = 3
    slug = "ore-grade-control"
    name = "Ore Grade Control"
    category = "processing"
    stage = "hardware-later"
    algorithm = "PI dosing control with dead-band and slew-rate limiting (OPC UA setpoint output)"

    def input_schema(self) -> Dict[str, str]:
        return {
            "grades": "recent grade readings (% Cu), oldest first",
            "current_dose": "current reagent dose setpoint (mL/t)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(5)
        grades = [TARGET_GRADE + rng.gauss(0, 0.08) for _ in range(20)]
        if scenario == "anomaly":
            # Feed grade ramps down: harder ore band hits the belt
            for i in range(8):
                grades.append(TARGET_GRADE - 0.25 * (i + 1) + rng.gauss(0, 0.06))
        return {"grades": grades, "current_dose": BASE_DOSE}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        grades: List[float] = payload["grades"]
        current_dose = float(payload.get("current_dose", BASE_DOSE))
        if not grades:
            raise ValueError("grades series is empty")

        latest = grades[-1]
        error = TARGET_GRADE - latest
        # Integral over the recent window (grade-minutes of accumulated error)
        integral = sum(TARGET_GRADE - g for g in grades[-10:]) / max(1, min(10, len(grades)))

        if abs(error) <= DEAD_BAND:
            new_dose = current_dose
            action = "hold"
        else:
            raw = BASE_DOSE + KP * error + KI * integral
            step = max(-MAX_STEP, min(MAX_STEP, raw - current_dose))
            new_dose = max(DOSE_LIMITS[0], min(DOSE_LIMITS[1], current_dose + step))
            action = "increase" if new_dose > current_dose else "decrease"

        deviation_pct = abs(error) / TARGET_GRADE * 100
        status = "critical" if deviation_pct > 15 else "warning" if deviation_pct > 5 else "normal"
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=(
                f"Feed grade {latest:.2f}% vs target {TARGET_GRADE}% — "
                f"{action} dose to {new_dose:.1f} mL/t"
            ),
            metrics={
                "latest_grade_pct": round(latest, 3),
                "target_grade_pct": TARGET_GRADE,
                "grade_error": round(error, 3),
                "integral_term": round(integral, 3),
                "current_dose_ml_t": round(current_dose, 2),
                "recommended_dose_ml_t": round(new_dose, 2),
                "action": action,
                "dead_band": DEAD_BAND,
                "slew_limit_ml_t": MAX_STEP,
            },
            series={"grades": [round(g, 3) for g in grades]},
            recommendations=[
                f"Write setpoint {new_dose:.1f} mL/t to DCS register via OPC UA"
                if action != "hold"
                else "Grade within dead-band — no setpoint change"
            ],
        )
