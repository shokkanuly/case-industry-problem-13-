"""
Case 11 — Energy consumption optimization.

Load-shifting optimizer over a time-of-use tariff. Given per-hour baseline
demand and a set of shiftable loads (each with energy, duration, and an
allowed window), it greedily schedules each shiftable block into the
cheapest feasible contiguous window that respects a site peak-demand cap —
a transparent, deterministic stand-in for the MILP a full EMS would solve.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult


class EnergyOptimizerEngine(CaseEngine):
    case_id = 11
    slug = "energy-optimization"
    name = "Energy Consumption Optimization"
    category = "energy"
    stage = "software"
    algorithm = "Greedy tariff-aware load-shift scheduling under a peak-demand cap"

    def input_schema(self) -> Dict[str, str]:
        return {
            "tariff": "24 hourly prices ($/MWh)",
            "baseline_kwh": "24 hourly fixed baseline demand (kWh)",
            "shiftable_loads": "list of {id, kwh, duration_h, window:[start,end]}",
            "peak_cap_kwh": "max total demand allowed in any hour (kWh)",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(41)
        # Off-peak nights cheap, day peak expensive, evening shoulder
        tariff = [
            (35 if 0 <= h < 6 else 120 if 8 <= h < 11 or 18 <= h < 21 else 75)
            + rng.uniform(-3, 3)
            for h in range(24)
        ]
        baseline = [300 + 60 * (1 if 8 <= h < 20 else 0) + rng.uniform(-10, 10) for h in range(24)]
        # current_start = where the load runs today (business-as-usual, in the day peak)
        shiftable = [
            {"id": "mill-regrind", "kwh": 900, "duration_h": 3, "window": [0, 23], "current_start": 9},
            {"id": "dewater-pumps", "kwh": 400, "duration_h": 2, "window": [0, 23], "current_start": 18},
        ]
        if scenario == "anomaly":
            # A big flexible batch load currently parked in the expensive peak
            shiftable.append(
                {"id": "leach-heaters", "kwh": 1500, "duration_h": 4, "window": [0, 23], "current_start": 8}
            )
        return {
            "tariff": [round(t, 2) for t in tariff],
            "baseline_kwh": [round(b, 1) for b in baseline],
            "shiftable_loads": shiftable,
            "peak_cap_kwh": 900.0,
        }

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        tariff: List[float] = payload["tariff"]
        baseline: List[float] = list(payload["baseline_kwh"])
        loads: List[Dict[str, Any]] = payload["shiftable_loads"]
        cap: float = float(payload["peak_cap_kwh"])
        H = len(tariff)

        demand = list(baseline)  # running scheduled demand per hour
        schedule: List[Dict[str, Any]] = []

        # Status-quo cost: each shiftable block runs at its current (peak-hour)
        # placement. Falls back to window start only if no current_start given.
        naive_cost = self._fixed_cost(baseline, tariff)
        for load in loads:
            start_naive = load.get("current_start", load["window"][0])
            per_hour = load["kwh"] / load["duration_h"]
            for h in range(start_naive, start_naive + load["duration_h"]):
                naive_cost += per_hour / 1000.0 * tariff[h % H]

        # Greedy: schedule biggest loads first into cheapest feasible window
        for load in sorted(loads, key=lambda l: -l["kwh"]):
            dur = load["duration_h"]
            per_hour = load["kwh"] / dur
            lo, hi = load["window"]
            best_start, best_cost = None, float("inf")
            for start in range(lo, hi - dur + 2):
                hours = [(start + k) % H for k in range(dur)]
                if any(demand[h] + per_hour > cap for h in hours):
                    continue
                cost = sum(per_hour / 1000.0 * tariff[h] for h in hours)
                if cost < best_cost:
                    best_cost, best_start = cost, start
            if best_start is None:
                # No cap-feasible window: place at cheapest window ignoring cap
                best_start = min(
                    range(lo, hi - dur + 2),
                    key=lambda s: sum(tariff[(s + k) % H] for k in range(dur)),
                )
                best_cost = sum(
                    per_hour / 1000.0 * tariff[(best_start + k) % H] for k in range(dur)
                )
            for k in range(dur):
                demand[(best_start + k) % H] += per_hour
            schedule.append(
                {
                    "id": load["id"],
                    "start_hour": best_start,
                    "duration_h": dur,
                    "kwh": load["kwh"],
                    "block_cost": round(best_cost, 2),
                }
            )

        optimized_cost = self._fixed_cost(baseline, tariff) + sum(s["block_cost"] for s in schedule)
        savings = naive_cost - optimized_cost
        savings_pct = savings / naive_cost * 100 if naive_cost else 0.0
        peak = max(demand)

        status = "warning" if savings_pct > 5 else "normal"
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=(
                f"Load-shift saves ${savings:,.0f}/day ({savings_pct:.1f}%); "
                f"peak {peak:.0f} kWh vs cap {cap:.0f}"
            ),
            metrics={
                "naive_cost_usd": round(naive_cost, 2),
                "optimized_cost_usd": round(optimized_cost, 2),
                "savings_usd": round(savings, 2),
                "savings_pct": round(savings_pct, 2),
                "peak_demand_kwh": round(peak, 1),
                "peak_cap_kwh": cap,
                "schedule": schedule,
            },
            series={"optimized_demand_kwh": [round(d, 1) for d in demand], "tariff": tariff},
            recommendations=[
                f"Shift '{s['id']}' to start {s['start_hour']:02d}:00 (off-peak window)"
                for s in sorted(schedule, key=lambda s: s["start_hour"])
            ],
        )

    @staticmethod
    def _fixed_cost(baseline: List[float], tariff: List[float]) -> float:
        return sum(b / 1000.0 * t for b, t in zip(baseline, tariff))
