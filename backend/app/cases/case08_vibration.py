"""
Case 08 — Predictive maintenance: vibration diagnostics.

Real pipeline structure: time-domain RMS velocity checked against the
ISO 20816-3 zone boundaries (Group 2 machines, rigid foundation), plus a
radix-2 Cooley-Tukey FFT for spectral fault-band analysis (1x unbalance,
2x misalignment/looseness) to say not just "how bad" but "what kind".
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Any, Dict, List, Tuple

from app.cases.base import CaseEngine, CaseResult

# ISO 20816-3, Group 2 (15 kW < P <= 300 kW), rigid support:
# RMS vibration velocity zone boundaries in mm/s.
ISO_ZONES_MM_S = [(1.4, "A"), (2.8, "B"), (4.5, "C"), (float("inf"), "D")]
ZONE_MEANING = {
    "A": "New-machine condition",
    "B": "Acceptable for unrestricted long-term operation",
    "C": "Unsatisfactory for long-term operation — plan corrective action",
    "D": "Vibration severe enough to cause damage — act now",
}


def fft(signal: List[complex]) -> List[complex]:
    """Radix-2 Cooley-Tukey FFT (input length must be a power of two)."""
    n = len(signal)
    if n == 1:
        return signal
    if n & (n - 1):
        raise ValueError("FFT length must be a power of two")
    even = fft(signal[0::2])
    odd = fft(signal[1::2])
    out = [0j] * n
    for k in range(n // 2):
        tw = cmath.exp(-2j * math.pi * k / n) * odd[k]
        out[k] = even[k] + tw
        out[k + n // 2] = even[k] - tw
    return out


def rms(values: List[float]) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values))


def iso_zone(rms_mm_s: float) -> str:
    for bound, zone in ISO_ZONES_MM_S:
        if rms_mm_s <= bound:
            return zone
    return "D"


class VibrationDiagnosticsEngine(CaseEngine):
    case_id = 8
    slug = "predictive-maintenance"
    name = "Predictive Maintenance (Flotation/Pumps)"
    category = "reliability"
    stage = "software"
    algorithm = "FFT fault-band analysis + ISO 20816-3 zone classification (Group 2, rigid)"
    architecture_type = (
        "Standards-compliant condition monitoring with enterprise CMMS work-order integration"
    )
    why_distinct = (
        "The only case governed by a specific, citable international standard (ISO 20816-3) rather than a custom threshold."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "sample_rate_hz": "vibration sample rate",
            "running_speed_hz": "machine running speed (Hz)",
            "velocity_mm_s": "vibration velocity waveform samples (mm/s), power-of-two length",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(31)
        fs, n = 2048, 2048
        speed_hz = 24.75  # ~1485 rpm pump
        samples = []
        for i in range(n):
            t = i / fs
            v = 0.9 * math.sin(2 * math.pi * speed_hz * t)          # healthy 1x residual
            v += 0.2 * math.sin(2 * math.pi * 2 * speed_hz * t)
            if scenario == "anomaly":
                v += 4.2 * math.sin(2 * math.pi * speed_hz * t + 0.4)      # unbalance blow-up at 1x
                v += 1.6 * math.sin(2 * math.pi * 2 * speed_hz * t + 1.1)  # plus misalignment growth
            v += rng.gauss(0, 0.15)
            samples.append(v)
        return {"sample_rate_hz": fs, "running_speed_hz": speed_hz, "velocity_mm_s": samples}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        fs = float(payload["sample_rate_hz"])
        speed = float(payload["running_speed_hz"])
        wave: List[float] = payload["velocity_mm_s"]

        overall_rms = rms(wave)
        zone = iso_zone(overall_rms)

        spectrum = fft([complex(v, 0) for v in wave])
        n = len(wave)
        # Single-sided amplitude spectrum
        amps = [2.0 * abs(spectrum[k]) / n for k in range(n // 2)]
        freq_res = fs / n

        def band_peak(center_hz: float, half_width_hz: float = 1.5) -> Tuple[float, float]:
            lo = max(0, int((center_hz - half_width_hz) / freq_res))
            hi = min(len(amps) - 1, int((center_hz + half_width_hz) / freq_res))
            k = max(range(lo, hi + 1), key=lambda i: amps[i])
            return amps[k], k * freq_res

        amp_1x, f_1x = band_peak(speed)
        amp_2x, f_2x = band_peak(2 * speed)

        faults: List[str] = []
        if zone in ("C", "D"):
            if amp_1x > 2.0 and amp_1x > 2.0 * amp_2x:
                faults.append("unbalance (dominant 1x)")
            if amp_2x > 1.0 and amp_2x > 0.5 * amp_1x:
                faults.append("misalignment/looseness (elevated 2x)")
            if not faults:
                faults.append("broadband severity increase — inspect bearings")

        status = {"A": "normal", "B": "normal", "C": "warning", "D": "critical"}[zone]
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=(
                f"ISO 20816-3 Zone {zone} — RMS {overall_rms:.2f} mm/s"
                + (f"; suspected {', '.join(faults)}" if faults else "")
            ),
            metrics={
                "overall_rms_mm_s": round(overall_rms, 3),
                "iso_zone": zone,
                "zone_meaning": ZONE_MEANING[zone],
                "peak_1x_mm_s": round(amp_1x, 3),
                "peak_1x_freq_hz": round(f_1x, 2),
                "peak_2x_mm_s": round(amp_2x, 3),
                "peak_2x_freq_hz": round(f_2x, 2),
                "suspected_faults": faults,
                "running_speed_hz": speed,
            },
            series={"spectrum_mm_s": [round(a, 4) for a in amps[: int(6 * speed / freq_res)]]},
            recommendations=(
                ["Auto-generate CMMS work order: corrective maintenance within 24h",
                 "Confirm with second measurement point before stopping machine"]
                if zone == "D"
                else ["Schedule balancing/alignment check at next planned stop"]
                if zone == "C"
                else ["No action — trend RMS weekly"]
            ),
        )
