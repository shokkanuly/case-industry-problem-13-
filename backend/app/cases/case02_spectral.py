"""
Case 02 — Portable core/rock/ore analyzer.

Classifies a sample's spectral signature against a mineral reference
library and estimates copper grade from the matched mineral's stoichiometric
copper fraction scaled by relative peak intensity.
"""

from __future__ import annotations

import random
from typing import Any, Dict

from app.cases.base import CaseEngine, CaseResult
from app.cases.spectral_core import SpectralClassifier, gaussian_spectrum

N_CHANNELS = 128

# Synthetic reference peak models (center, width, amplitude) per mineral,
# with each mineral's theoretical copper mass fraction.
MINERAL_LIBRARY = {
    "Chalcopyrite (CuFeS2)": {"peaks": [(0.22, 0.03, 1.0), (0.55, 0.02, 0.7), (0.78, 0.04, 0.4)], "cu_fraction": 0.346},
    "Bornite (Cu5FeS4)": {"peaks": [(0.25, 0.03, 0.9), (0.48, 0.03, 0.8), (0.70, 0.02, 0.5)], "cu_fraction": 0.634},
    "Chalcocite (Cu2S)": {"peaks": [(0.30, 0.02, 1.0), (0.62, 0.03, 0.6)], "cu_fraction": 0.798},
    "Malachite (Cu2CO3(OH)2)": {"peaks": [(0.18, 0.04, 0.8), (0.40, 0.02, 1.0), (0.85, 0.03, 0.3)], "cu_fraction": 0.575},
    "Pyrite (FeS2, gangue)": {"peaks": [(0.35, 0.02, 1.0), (0.66, 0.02, 0.9)], "cu_fraction": 0.0},
    "Quartz (SiO2, gangue)": {"peaks": [(0.50, 0.05, 1.0)], "cu_fraction": 0.0},
}


def _build_classifier() -> SpectralClassifier:
    return SpectralClassifier(
        {
            name: gaussian_spectrum(N_CHANNELS, spec["peaks"])
            for name, spec in MINERAL_LIBRARY.items()
        }
    )


class SpectralAnalyzerEngine(CaseEngine):
    case_id = 2
    slug = "portable-ore-analyzer"
    name = "Portable Core/Rock/Ore Analyzer"
    category = "geology"
    stage = "hardware-later"
    algorithm = "Baseline-removed cosine-similarity spectral matching vs. mineral reference library"

    def __init__(self) -> None:
        self.classifier = _build_classifier()

    def input_schema(self) -> Dict[str, str]:
        return {"spectrum": f"list of {N_CHANNELS} intensity values from the spectrometer"}

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        # normal -> gangue sample; anomaly -> high-grade chalcocite ore
        target = "Quartz (SiO2, gangue)" if scenario == "normal" else "Chalcocite (Cu2S)"
        spec = MINERAL_LIBRARY[target]
        rng = random.Random(3)
        intensity_scale = rng.uniform(0.85, 1.0)
        spectrum = [
            v * intensity_scale
            for v in gaussian_spectrum(N_CHANNELS, spec["peaks"], noise=0.03, seed=11)
        ]
        return {"spectrum": spectrum, "_ground_truth": target}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        spectrum = payload["spectrum"]
        matches = self.classifier.classify(spectrum)
        best = matches[0]
        mineral = best["label"]
        cu_fraction = MINERAL_LIBRARY.get(mineral, {}).get("cu_fraction", 0.0)
        # Grade estimate: stoichiometric Cu of matched phase scaled by
        # how much of the reference signal intensity the sample expresses.
        peak_ratio = min(1.0, max(spectrum) / 1.0) if spectrum else 0.0
        grade_pct = round(cu_fraction * peak_ratio * 100 * 0.12, 2)  # 12% phase abundance assumption

        is_ore = cu_fraction > 0
        status = "warning" if is_ore else "normal"
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=f"Sample matched {mineral} (confidence {best['confidence']:.0%}), est. grade {grade_pct}% Cu",
            metrics={
                "matched_mineral": mineral,
                "confidence": best["confidence"],
                "estimated_grade_pct_cu": grade_pct,
                "is_ore_mineral": is_ore,
                "alternatives": matches[1:],
            },
            series={"spectrum": [round(v, 4) for v in spectrum]},
            recommendations=(
                [f"Log assay ticket and dispatch confirmation sample for {mineral} zone"]
                if is_ore
                else ["Gangue signature — no follow-up assay required"]
            ),
        )
