"""
CaseEngine contract shared by all 15 industrial case modules.

An engine is a pure algorithmic unit: no I/O, no database, no camera.
The API layer feeds it either real payloads (POST /api/cases/{id}/run)
or the engine's own synthetic scenario (GET /api/cases/{id}/demo), so
every case is exercisable end-to-end before its hardware exists.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CaseResult:
    """Uniform result envelope every engine returns from compute()."""

    case_id: int
    status: str                      # "normal" | "warning" | "critical"
    headline: str                    # one-line human-readable conclusion
    metrics: Dict[str, Any] = field(default_factory=dict)
    series: Dict[str, List[float]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    computed_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "headline": self.headline,
            "metrics": self.metrics,
            "series": self.series,
            "recommendations": self.recommendations,
            "computed_at": self.computed_at,
        }


class CaseEngine(ABC):
    """Base class for a case's algorithmic core."""

    case_id: int
    slug: str
    name: str
    category: str
    stage: str = "software"          # "software" | "hardware-later" | "live"
    algorithm: str = ""              # the real method the engine implements
    architecture_type: str = ""      # the real system pattern this case deploys as
    why_distinct: str = ""           # what makes this case architecturally unique among the 15

    def describe(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "slug": self.slug,
            "name": self.name,
            "category": self.category,
            "stage": self.stage,
            "algorithm": self.algorithm,
            "architecture_type": self.architecture_type,
            "why_distinct": self.why_distinct,
            "input_schema": self.input_schema(),
        }

    def input_schema(self) -> Dict[str, str]:
        """Names and short descriptions of the payload fields compute() accepts."""
        return {}

    @abstractmethod
    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        """Produce a synthetic input payload. Scenarios: 'normal', 'anomaly'."""

    @abstractmethod
    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        """Run the case algorithm over an input payload."""

    def demo(self, scenario: str = "anomaly") -> Dict[str, Any]:
        """Simulate + compute in one call; returns both for display."""
        payload = self.simulate(scenario)
        result = self.compute(payload)
        return {"scenario": scenario, "input": payload, "result": result.to_dict()}


class CaseRegistry:
    """In-memory registry of all case engines, keyed by case_id."""

    def __init__(self) -> None:
        self._engines: Dict[int, CaseEngine] = {}

    def register(self, engine: CaseEngine) -> None:
        if engine.case_id in self._engines:
            raise ValueError(f"Duplicate case_id {engine.case_id}")
        self._engines[engine.case_id] = engine

    def get(self, case_id: int) -> Optional[CaseEngine]:
        return self._engines.get(case_id)

    def all(self) -> List[CaseEngine]:
        return [self._engines[k] for k in sorted(self._engines)]
