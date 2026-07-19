"""
Shared spectral-classification core used by Case 02 (minerals) and
Case 15 (construction materials).

Pipeline: baseline removal (rolling minimum) -> vector normalisation ->
cosine similarity against a reference library -> ranked matches with a
confidence margin. Reference spectra are synthetic Gaussian-peak models
standing in for a real XRF/Raman/LIBS library; the classifier itself is
the production algorithm.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple


def gaussian_spectrum(
    n_channels: int, peaks: List[Tuple[float, float, float]], noise: float = 0.0, seed: int = 0
) -> List[float]:
    """Build a spectrum from (center_frac, width_frac, amplitude) peaks."""
    rng = random.Random(seed)
    out = []
    for i in range(n_channels):
        x = i / (n_channels - 1)
        v = sum(a * math.exp(-((x - c) ** 2) / (2 * (w ** 2))) for c, w, a in peaks)
        if noise:
            v += rng.gauss(0, noise)
        out.append(max(0.0, v))
    return out


def remove_baseline(spectrum: List[float], window: int = 15) -> List[float]:
    """Subtract a rolling-minimum baseline (simple continuum removal)."""
    n = len(spectrum)
    half = window // 2
    baseline = [
        min(spectrum[max(0, i - half): min(n, i + half + 1)]) for i in range(n)
    ]
    return [s - b for s, b in zip(spectrum, baseline)]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class SpectralClassifier:
    """Matches an observed spectrum against a named reference library."""

    def __init__(self, library: Dict[str, List[float]]):
        self.library = {
            name: remove_baseline(ref) for name, ref in library.items()
        }

    def classify(self, spectrum: List[float], top_k: int = 3) -> List[Dict[str, float]]:
        processed = remove_baseline(spectrum)
        scored = [
            {"label": name, "similarity": round(cosine_similarity(processed, ref), 4)}
            for name, ref in self.library.items()
        ]
        scored.sort(key=lambda s: s["similarity"], reverse=True)
        top = scored[:top_k]
        # Confidence: winner similarity scaled by margin over runner-up
        if len(top) >= 2:
            margin = top[0]["similarity"] - top[1]["similarity"]
            confidence = top[0]["similarity"] * min(1.0, 0.5 + margin * 5)
        else:
            confidence = top[0]["similarity"] if top else 0.0
        for entry in top:
            entry["similarity"] = float(entry["similarity"])
        return [{**top[0], "confidence": round(max(0.0, confidence), 4)}] + top[1:]
