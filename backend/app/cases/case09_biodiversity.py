"""
Case 09 — Lake Balkhash biodiversity monitoring.

Detection is assumed done on-device (MegaDetector-style "animal present" +
species classifier); this engine is the analytics core over the resulting
detection log: per-species registration-frequency trend, Shannon diversity
index, and flags for declining, newly-appearing, or invasive species.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

INVASIVE = {"Prussian carp", "Zander (invasive stock)"}
DECLINE_FLAG = -0.4      # >40% drop in recent window vs baseline


class BiodiversityEngine(CaseEngine):
    case_id = 9
    slug = "balkhash-biodiversity"
    name = "Lake Balkhash Biodiversity Monitoring"
    category = "environment"
    stage = "hardware-later"
    algorithm = "Registration-frequency trend + Shannon diversity index + species-change flags"
    architecture_type = (
        "Remote, intermittent-connectivity camera network: solar camera traps + on-device MegaDetector, satellite/cellular sync"
    )
    why_distinct = (
        "The only case designed around solar power and store-and-forward sync from the start — and the only one where 'critical' means an ecologically significant finding, not danger."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "detections": "list of {species, week} camera-trap detection records",
            "baseline_weeks": "number of leading weeks treated as baseline",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(29)
        species_rates = {
            "Balkhash perch": 8,
            "Common carp": 6,
            "Great cormorant": 4,
            "Grey heron": 3,
        }
        detections: List[Dict[str, Any]] = []
        for week in range(12):
            rates = dict(species_rates)
            if scenario == "anomaly":
                # Native perch declines sharply in recent weeks
                if week >= 8:
                    rates["Balkhash perch"] = 2
                # Invasive species appears mid-series
                if week >= 6:
                    rates["Prussian carp"] = 5 + week - 6
            for sp, rate in rates.items():
                for _ in range(max(0, int(rng.gauss(rate, 1)))):
                    detections.append({"species": sp, "week": week})
        return {"detections": detections, "baseline_weeks": 4}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        detections: List[Dict[str, Any]] = payload["detections"]
        baseline_weeks = int(payload.get("baseline_weeks", 4))
        if not detections:
            raise ValueError("no detections provided")

        weeks = sorted({d["week"] for d in detections})
        recent_cut = weeks[-baseline_weeks:] if len(weeks) > baseline_weeks else weeks
        baseline_cut = weeks[:baseline_weeks]

        species = sorted({d["species"] for d in detections})

        def count(sp: str, wk: List[int]) -> int:
            return sum(1 for d in detections if d["species"] == sp and d["week"] in wk)

        # Shannon diversity over the whole log
        total = len(detections)
        counts = {sp: count(sp, weeks) for sp in species}
        shannon = -sum(
            (c / total) * math.log(c / total) for c in counts.values() if c > 0
        )

        flags: List[Dict[str, Any]] = []
        for sp in species:
            base_n = count(sp, baseline_cut)
            rec_n = count(sp, recent_cut)
            base_rate = base_n / max(1, len(baseline_cut))
            rec_rate = rec_n / max(1, len(recent_cut))
            if base_n == 0 and rec_n > 0:
                kind = "invasive-appearance" if sp in INVASIVE else "new-species"
                flags.append({"species": sp, "flag": kind, "recent_rate": round(rec_rate, 2)})
            elif base_rate > 0:
                change = (rec_rate - base_rate) / base_rate
                if change <= DECLINE_FLAG:
                    flags.append(
                        {"species": sp, "flag": "declining",
                         "change_pct": round(change * 100, 1),
                         "recent_rate": round(rec_rate, 2)}
                    )

        has_invasive = any(f["flag"] == "invasive-appearance" for f in flags)
        has_decline = any(f["flag"] == "declining" for f in flags)
        status = "critical" if has_invasive else "warning" if has_decline or flags else "normal"
        headline = (
            f"{len(flags)} biodiversity change flag(s); Shannon index {shannon:.2f}"
            if flags
            else f"Stable community — Shannon index {shannon:.2f}, {len(species)} species"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "species_richness": len(species),
                "total_detections": total,
                "shannon_index": round(shannon, 3),
                "flags": flags,
                "per_species_counts": counts,
            },
            recommendations=(
                [f"Alert ecology team: {f['species']} ({f['flag']})" for f in flags[:3]]
                if flags
                else ["No intervention — continue automated monitoring"]
            ),
        )
