"""
Case 01 — Exploration prospectivity scoring.

Fuses three raster layers over a survey grid — spectral alteration anomaly,
elevation-derived slope favourability, and structural lineament density —
into a weighted prospect-likelihood score per cell, then extracts ranked
target zones by connected-component clustering of high-score cells.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

WEIGHTS = {"alteration": 0.5, "lineament": 0.3, "elevation": 0.2}
TARGET_THRESHOLD = 0.65


class ProspectivityEngine(CaseEngine):
    case_id = 1
    slug = "exploration-survey"
    name = "Autonomous Exploration Survey"
    category = "geology"
    stage = "software"
    algorithm = "Weighted multi-layer raster fusion + connected-component target extraction"
    architecture_type = (
        "Batch geospatial pipeline (offline, not real-time); output belongs in a GIS layer (PostGIS) for QGIS/ArcGIS"
    )
    why_distinct = (
        "The only case that is fundamentally a mapping/GIS problem, not a monitoring problem."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "grid_size": "side length N of the NxN survey grid",
            "alteration": "NxN row-major list, spectral alteration index 0..1",
            "lineament": "NxN row-major list, lineament density 0..1",
            "elevation": "NxN row-major list, elevation in metres",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(42 if scenario == "normal" else 7)
        n = 16
        # Base layers: smooth background noise
        alteration = [rng.uniform(0.05, 0.30) for _ in range(n * n)]
        lineament = [rng.uniform(0.05, 0.40) for _ in range(n * n)]
        elevation = [
            400 + 120 * math.sin(i % n / 3.0) + 80 * math.cos(i // n / 2.5) + rng.uniform(-15, 15)
            for i in range(n * n)
        ]
        if scenario == "anomaly":
            # Inject two ore-signature clusters: high alteration + high lineament
            for cx, cy in ((4, 5), (11, 10)):
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        idx = (cy + dy) * n + (cx + dx)
                        alteration[idx] = rng.uniform(0.80, 0.98)
                        lineament[idx] = rng.uniform(0.70, 0.95)
        return {
            "grid_size": n,
            "alteration": alteration,
            "lineament": lineament,
            "elevation": elevation,
        }

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        n = int(payload["grid_size"])
        alteration = payload["alteration"]
        lineament = payload["lineament"]
        elevation = payload["elevation"]

        # Normalise elevation favourability: moderate slopes score highest.
        emin, emax = min(elevation), max(elevation)
        espan = (emax - emin) or 1.0
        elev_norm = [1.0 - abs((e - emin) / espan - 0.5) * 2.0 for e in elevation]

        scores = [
            WEIGHTS["alteration"] * alteration[i]
            + WEIGHTS["lineament"] * lineament[i]
            + WEIGHTS["elevation"] * elev_norm[i]
            for i in range(n * n)
        ]

        targets = self._extract_targets(scores, n)
        status = "warning" if targets else "normal"
        headline = (
            f"{len(targets)} prospect target zone(s) above {TARGET_THRESHOLD:.2f} fusion score"
            if targets
            else "No prospect zones above threshold in surveyed grid"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "grid_size": n,
                "cells_scored": n * n,
                "max_score": round(max(scores), 3),
                "mean_score": round(sum(scores) / len(scores), 3),
                "targets": targets,
                "weights": WEIGHTS,
            },
            series={"score_grid": [round(s, 3) for s in scores]},
            recommendations=[
                f"Priority drill target: cluster #{t['rank']} at grid ({t['centroid'][0]}, {t['centroid'][1]}), "
                f"peak score {t['peak_score']}"
                for t in targets[:3]
            ],
        )

    @staticmethod
    def _extract_targets(scores: List[float], n: int) -> List[Dict[str, Any]]:
        """4-connected component clustering of cells above threshold."""
        seen = [False] * (n * n)
        clusters: List[Dict[str, Any]] = []
        for start in range(n * n):
            if seen[start] or scores[start] < TARGET_THRESHOLD:
                continue
            stack, cells = [start], []
            seen[start] = True
            while stack:
                idx = stack.pop()
                cells.append(idx)
                x, y = idx % n, idx // n
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < n and 0 <= ny < n:
                        nidx = ny * n + nx
                        if not seen[nidx] and scores[nidx] >= TARGET_THRESHOLD:
                            seen[nidx] = True
                            stack.append(nidx)
            peak = max(scores[c] for c in cells)
            cx = round(sum(c % n for c in cells) / len(cells))
            cy = round(sum(c // n for c in cells) / len(cells))
            clusters.append(
                {"cells": len(cells), "peak_score": round(peak, 3), "centroid": [cx, cy]}
            )
        clusters.sort(key=lambda c: c["peak_score"], reverse=True)
        for rank, c in enumerate(clusters, start=1):
            c["rank"] = rank
        return clusters
