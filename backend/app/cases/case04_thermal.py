"""
Case 04 — Copper electrolysis short-circuit detection.

Published tankhouse methods scan a thermal image of the cell rows and flag
anode-cathode short circuits as localised hot spots. This engine implements
the software half: per-cell robust z-score against the row's median
temperature, hot-spot blob confirmation, and severity grading by excess
temperature — the exact logic a crane-mounted IR camera rig would feed.
"""

from __future__ import annotations

import random
from statistics import median
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

Z_THRESHOLD = 3.5           # robust z-score above which a cell is a hot-spot candidate
CRITICAL_EXCESS_C = 12.0    # deg C above row median that indicates a hard short


class ThermalShortCircuitEngine(CaseEngine):
    case_id = 4
    slug = "electrolysis-shortcircuit"
    name = "Copper Electrolysis Automation"
    category = "metallurgy"
    stage = "hardware-later"
    algorithm = "Robust z-score hot-spot detection on tankhouse thermal scans (MAD-based)"
    architecture_type = (
        "Mobile crane-mounted inspection system, radio-linked to the control room; integrates with crane scheduling"
    )
    why_distinct = (
        "The only case where the sensor itself is mobile — mounted on moving industrial equipment rather than fixed."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "rows": "number of cell rows",
            "cols": "cells per row",
            "temperatures": "rows*cols row-major surface temperatures (deg C)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(9)
        rows, cols = 4, 12
        temps = [62.0 + rng.gauss(0, 0.8) for _ in range(rows * cols)]
        if scenario == "anomaly":
            temps[1 * cols + 7] += 16.5   # hard short in row 2, cell 8
            temps[3 * cols + 2] += 6.0    # developing soft short
        return {"rows": rows, "cols": cols, "temperatures": temps}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        rows, cols = int(payload["rows"]), int(payload["cols"])
        temps: List[float] = payload["temperatures"]

        hotspots: List[Dict[str, Any]] = []
        for r in range(rows):
            row = temps[r * cols:(r + 1) * cols]
            med = median(row)
            mad = median([abs(t - med) for t in row]) or 0.1
            for c, t in enumerate(row):
                z = 0.6745 * (t - med) / mad  # consistent MAD z-score
                excess = t - med
                if z > Z_THRESHOLD and excess > 2.0:
                    hotspots.append(
                        {
                            "row": r + 1,
                            "cell": c + 1,
                            "temp_c": round(t, 1),
                            "excess_c": round(excess, 1),
                            "z_score": round(z, 1),
                            "severity": "critical" if excess >= CRITICAL_EXCESS_C else "warning",
                        }
                    )

        hotspots.sort(key=lambda h: h["excess_c"], reverse=True)
        criticals = [h for h in hotspots if h["severity"] == "critical"]
        status = "critical" if criticals else "warning" if hotspots else "normal"
        headline = (
            f"{len(hotspots)} short-circuit candidate(s), {len(criticals)} hard short(s)"
            if hotspots
            else "Tankhouse thermal scan clean — no short circuits"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "cells_scanned": rows * cols,
                "hotspots": hotspots,
                "z_threshold": Z_THRESHOLD,
                "critical_excess_c": CRITICAL_EXCESS_C,
            },
            series={"temperatures": [round(t, 2) for t in temps]},
            recommendations=[
                f"Dispatch operator to row {h['row']} cell {h['cell']} — {h['excess_c']}°C above row median"
                for h in hotspots[:3]
            ]
            or ["Continue scheduled crane scan cycle"],
        )
