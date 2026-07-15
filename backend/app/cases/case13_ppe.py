"""
Case 13 — PPE & behavior compliance (the completed proof-of-concept).

The live CV pipeline (YOLO11 + InsightFace + geofencing) lives in
app.services.safety_inference and runs on real camera frames. This engine
is a registry adapter so Case 13 exposes the same describe()/demo()
contract as the other 14 — its compute() scores a structured per-frame
detection summary into the shared compliance status vocabulary.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

REQUIRED_PPE = {"helmet", "vest"}


class PPEComplianceEngine(CaseEngine):
    case_id = 13
    slug = "ppe-compliance"
    name = "PPE & Behavior Compliance"
    category = "logistics_safety"
    stage = "live"
    algorithm = "YOLO11 PPE detection + InsightFace ID + geofence (live camera pipeline)"

    def input_schema(self) -> Dict[str, str]:
        return {
            "persons": "list of {id, ppe:[..present..], in_restricted_zone: bool}",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(61)
        persons = [
            {"id": "W-Alikhan", "ppe": ["helmet", "vest"], "in_restricted_zone": False},
            {"id": "W-Dana", "ppe": ["helmet", "vest"], "in_restricted_zone": False},
        ]
        if scenario == "anomaly":
            persons.append({"id": "W-Ruslan", "ppe": ["vest"], "in_restricted_zone": False})  # no helmet
            persons.append({"id": "UNKNOWN", "ppe": ["helmet", "vest"], "in_restricted_zone": True})  # zone breach
        _ = rng
        return {"persons": persons}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        persons: List[Dict[str, Any]] = payload.get("persons", [])
        violations: List[Dict[str, Any]] = []
        breaches = 0

        for p in persons:
            present = set(p.get("ppe", []))
            missing = REQUIRED_PPE - present
            if missing:
                violations.append({"id": p["id"], "missing_ppe": sorted(missing)})
            if p.get("in_restricted_zone"):
                breaches += 1
                violations.append({"id": p["id"], "violation": "restricted-zone breach"})

        n = len(persons)
        compliant = n - len({v["id"] for v in violations})
        compliance_pct = round(compliant / n * 100, 1) if n else 100.0

        status = "critical" if breaches else "warning" if violations else "normal"
        headline = (
            f"{len(violations)} compliance violation(s) across {n} persons "
            f"({compliance_pct}% compliant)"
            if violations
            else f"All {n} personnel compliant"
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "person_count": n,
                "compliance_pct": compliance_pct,
                "zone_breaches": breaches,
                "violations": violations,
                "required_ppe": sorted(REQUIRED_PPE),
                "live_pipeline": "app.services.safety_inference.analyze_frame",
            },
            recommendations=(
                [f"Log violation for {v['id']}" for v in violations[:3]]
                if violations
                else ["No action — zone compliant"]
            ),
        )
