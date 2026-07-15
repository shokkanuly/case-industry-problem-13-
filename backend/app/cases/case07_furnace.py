"""
Case 07 — Vanyukov furnace regime advisory.

Hybrid model: a first-principles mass/oxygen balance predicts expected
matte grade from charge composition and blast parameters, then a residual
correction layer (exponentially weighted average of recent model errors,
the simplest honest 'ML correction') adjusts the prediction toward plant
reality. Output is advisory only — the engine never actuates.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

TARGET_MATTE_GRADE = 55.0    # % Cu in matte the smelter aims for
GRADE_TOLERANCE = 2.5
EWMA_ALPHA = 0.3


def physics_matte_grade(charge_cu_pct: float, charge_s_pct: float,
                        o2_nm3_per_t: float, o2_enrichment_pct: float) -> float:
    """
    Simplified oxygen balance: more oxygen per tonne burns more Fe/S out of
    the melt, concentrating Cu in the matte. Calibrated around a nominal
    operating point (3.8% Cu charge, 180 Nm3/t, 65% O2 -> ~55% matte).
    """
    o2_effective = o2_nm3_per_t * (o2_enrichment_pct / 65.0)
    desulf_factor = min(0.95, o2_effective / 380.0)          # fraction of S oxidised
    s_remaining = charge_s_pct * (1.0 - desulf_factor)
    # Matte is essentially Cu2S-FeS; less residual S -> higher Cu fraction
    grade = 100.0 * charge_cu_pct / (charge_cu_pct + s_remaining * 1.9)
    return max(20.0, min(78.0, grade))


class VanyukovFurnaceEngine(CaseEngine):
    case_id = 7
    slug = "vanyukov-furnace"
    name = "Vanyukov Furnace Optimization"
    category = "metallurgy"
    stage = "software"
    algorithm = "First-principles oxygen/mass balance + EWMA residual correction (advisory-only)"

    def input_schema(self) -> Dict[str, str]:
        return {
            "charge_cu_pct": "copper content of charge (%)",
            "charge_s_pct": "sulfur content of charge (%)",
            "o2_nm3_per_t": "oxygen blast per tonne of charge (Nm3/t)",
            "o2_enrichment_pct": "blast oxygen enrichment (%)",
            "measured_matte_grades": "recent lab matte grades (%) for residual correction",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(17)
        base = {
            "charge_cu_pct": 3.8,
            "charge_s_pct": 32.0,
            "o2_nm3_per_t": 180.0,
            "o2_enrichment_pct": 65.0,
        }
        history = [55.0 + rng.gauss(0, 0.6) for _ in range(6)]
        if scenario == "anomaly":
            # Charge got richer in S and blast wasn't adjusted: grade drifts low
            base["charge_s_pct"] = 36.5
            base["o2_nm3_per_t"] = 168.0
            history = [54.0, 53.2, 52.5, 51.8, 51.1, 50.3]
        return {**base, "measured_matte_grades": history}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        cu = float(payload["charge_cu_pct"])
        s = float(payload["charge_s_pct"])
        o2 = float(payload["o2_nm3_per_t"])
        enrich = float(payload["o2_enrichment_pct"])
        measured: List[float] = payload.get("measured_matte_grades", [])

        predicted_physics = physics_matte_grade(cu, s, o2, enrich)

        # Residual correction: EWMA of (measured - physics) over history,
        # assuming similar charge conditions across the window.
        residual = 0.0
        if measured:
            r = measured[0] - predicted_physics
            for m in measured[1:]:
                r = EWMA_ALPHA * (m - predicted_physics) + (1 - EWMA_ALPHA) * r
            residual = r
        predicted = predicted_physics + residual

        deviation = predicted - TARGET_MATTE_GRADE

        # Advisory: how much extra O2 per tonne closes the gap (local sensitivity)
        sensitivity = (
            physics_matte_grade(cu, s, o2 + 10, enrich) - predicted_physics
        ) / 10.0 or 0.05
        o2_adjust = round(-deviation / sensitivity, 1) if abs(deviation) > GRADE_TOLERANCE else 0.0
        o2_adjust = max(-30.0, min(30.0, o2_adjust))

        status = (
            "critical" if abs(deviation) > 2 * GRADE_TOLERANCE
            else "warning" if abs(deviation) > GRADE_TOLERANCE
            else "normal"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=(
                f"Predicted matte grade {predicted:.1f}% vs target {TARGET_MATTE_GRADE}% "
                f"({'+' if deviation >= 0 else ''}{deviation:.1f})"
            ),
            metrics={
                "predicted_matte_grade_pct": round(predicted, 2),
                "physics_model_grade_pct": round(predicted_physics, 2),
                "residual_correction": round(residual, 2),
                "target_grade_pct": TARGET_MATTE_GRADE,
                "deviation": round(deviation, 2),
                "recommended_o2_adjust_nm3_t": o2_adjust,
                "advisory_only": True,
            },
            series={"measured_matte_grades": [round(m, 2) for m in measured]},
            recommendations=(
                [
                    f"ADVISORY: adjust oxygen blast by {'+' if o2_adjust > 0 else ''}{o2_adjust} Nm³/t "
                    "(operator confirmation required — model never actuates)",
                    "Re-sample charge S content to confirm drift",
                ]
                if o2_adjust
                else ["Regime within tolerance — no blast change advised"]
            ),
        )
