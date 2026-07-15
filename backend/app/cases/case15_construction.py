"""
Case 15 — Concrete/asphalt core analyzer.

Reuses the Case 02 spectral-classification core with a construction-material
reference library, and adds a strength estimate from non-destructive test
inputs — rebound-hammer number and ultrasonic pulse velocity (UPV) — via
the standard combined SonReb-style correlation, linked to a project/lot id.
"""

from __future__ import annotations

import random
from typing import Any, Dict

from app.cases.base import CaseEngine, CaseResult
from app.cases.spectral_core import SpectralClassifier, gaussian_spectrum

N_CHANNELS = 128

MATERIAL_LIBRARY = {
    "Portland concrete (sound)": {"peaks": [(0.20, 0.04, 1.0), (0.52, 0.03, 0.6)], "grade": "structural"},
    "Concrete (carbonated)": {"peaks": [(0.22, 0.04, 0.9), (0.45, 0.02, 0.9), (0.80, 0.03, 0.4)], "grade": "review"},
    "Asphalt (dense-graded)": {"peaks": [(0.30, 0.05, 1.0), (0.68, 0.04, 0.7)], "grade": "structural"},
    "Aggregate (limestone)": {"peaks": [(0.40, 0.03, 1.0), (0.60, 0.02, 0.5)], "grade": "aggregate"},
}


def _classifier() -> SpectralClassifier:
    return SpectralClassifier(
        {name: gaussian_spectrum(N_CHANNELS, spec["peaks"]) for name, spec in MATERIAL_LIBRARY.items()}
    )


def sonreb_strength_mpa(rebound_no: float, upv_km_s: float) -> float:
    """
    Combined rebound + UPV strength estimate (SonReb-family power law).
    fc = a * R^b * V^c ; coefficients are representative literature values.
    """
    a, b, c = 0.0286, 1.246, 1.85
    return round(a * (rebound_no ** b) * (upv_km_s ** c), 1)


class ConstructionCoreEngine(CaseEngine):
    case_id = 15
    slug = "construction-core"
    name = "Concrete/Asphalt Core Analyzer"
    category = "construction"
    stage = "hardware-later"
    algorithm = "Spectral material match (shared Case 02 core) + SonReb NDT strength estimate"

    def __init__(self) -> None:
        self.classifier = _classifier()

    def input_schema(self) -> Dict[str, str]:
        return {
            "lot_id": "project/lot identifier the sample links to",
            "spectrum": f"{N_CHANNELS} spectral intensity values",
            "rebound_number": "Schmidt rebound hammer number R",
            "upv_km_s": "ultrasonic pulse velocity (km/s)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(71)
        if scenario == "normal":
            target, rebound, upv = "Portland concrete (sound)", 42.0, 4.5
        else:
            target, rebound, upv = "Concrete (carbonated)", 28.0, 3.4  # weak/degraded core
        spec = MATERIAL_LIBRARY[target]
        spectrum = gaussian_spectrum(N_CHANNELS, spec["peaks"], noise=0.03, seed=13)
        return {
            "lot_id": "LOT-A19-Deck-North",
            "spectrum": spectrum,
            "rebound_number": rebound + rng.uniform(-1, 1),
            "upv_km_s": upv + rng.uniform(-0.05, 0.05),
        }

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        matches = self.classifier.classify(payload["spectrum"])
        best = matches[0]
        material = best["label"]
        rebound = float(payload["rebound_number"])
        upv = float(payload["upv_km_s"])
        strength = sonreb_strength_mpa(rebound, upv)

        # Simple acceptance: structural concrete/asphalt should exceed 25 MPa
        material_grade = MATERIAL_LIBRARY.get(material, {}).get("grade", "review")
        if material_grade == "structural" and strength >= 25:
            status, verdict = "normal", "PASS"
        elif strength >= 20:
            status, verdict = "warning", "MARGINAL"
        else:
            status, verdict = "critical", "FAIL"

        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=(
                f"{payload.get('lot_id', 'sample')}: {material} "
                f"({best['confidence']:.0%}), est. strength {strength} MPa — {verdict}"
            ),
            metrics={
                "lot_id": payload.get("lot_id"),
                "matched_material": material,
                "match_confidence": best["confidence"],
                "rebound_number": round(rebound, 1),
                "upv_km_s": round(upv, 2),
                "estimated_strength_mpa": strength,
                "verdict": verdict,
                "alternatives": matches[1:],
            },
            series={"spectrum": [round(v, 4) for v in payload["spectrum"]]},
            recommendations=(
                [f"Attach result to digital twin record for {payload.get('lot_id')}"]
                if verdict == "PASS"
                else [f"Flag {payload.get('lot_id')} for lab confirmation core ({verdict})"]
            ),
        )
