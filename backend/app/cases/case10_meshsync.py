"""
Case 10 — Underground safety mesh: store-and-forward resilience.

The capital radio network is out of scope; the software core is the
buffering/burst-sync logic. This engine replays an event log through a
link that drops and recovers, buffering locally during outages and
replaying in monotonic order on reconnect, and verifies exactly-once,
in-order delivery plus gas-threshold alarm latency across the outage.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.cases.base import CaseEngine, CaseResult

CH4_ALARM_PCT = 1.25    # methane alarm threshold (% volume), typical statutory trigger
BUFFER_CAPACITY = 500


class MeshSyncEngine(CaseEngine):
    case_id = 10
    slug = "underground-mesh"
    name = "Underground Communications & Safety Mesh"
    category = "underground-safety"
    stage = "hardware-later"
    algorithm = "Store-and-forward buffering with in-order burst replay + delivery verification"
    architecture_type = (
        "Hybrid multi-radio network: leaky feeder (voice) + private LTE/5G (data/video) + LoRaWAN (low-power sensors)"
    )
    why_distinct = (
        "The only case that is fundamentally a telecom/network-engineering problem, not a sensing/ML problem."
    )

    def input_schema(self) -> Dict[str, str]:
        return {
            "events": "list of {seq, t, sensor, metric, value}",
            "link_up": "list of booleans, link state per time step",
        }

    def simulate(self, scenario: str = "normal") -> Dict[str, Any]:
        rng = random.Random(37)
        events, link_up = [], []
        for t in range(40):
            events.append(
                {
                    "seq": t,
                    "t": t,
                    "sensor": f"gas_{t % 3}",
                    "metric": "ch4_pct",
                    "value": round(0.6 + rng.uniform(-0.1, 0.1), 3),
                }
            )
            link_up.append(True)
        if scenario == "anomaly":
            # Roof fall severs the link for steps 12..25 (14-step outage)
            for t in range(12, 26):
                link_up[t] = False
            # And a methane spike happens *during* the outage at t=18
            events[18]["value"] = 1.9
        return {"events": events, "link_up": link_up}

    def compute(self, payload: Dict[str, Any]) -> CaseResult:
        events: List[Dict[str, Any]] = payload["events"]
        link_up: List[bool] = payload["link_up"]

        buffer: List[Dict[str, Any]] = []
        delivered: List[Dict[str, Any]] = []
        delivery_time: Dict[int, int] = {}    # seq -> time step delivered
        max_buffer_depth = 0
        dropped_overflow = 0

        for t, ev in enumerate(events):
            up = link_up[t] if t < len(link_up) else True
            # New event always lands in the local buffer first
            if len(buffer) < BUFFER_CAPACITY:
                buffer.append(ev)
            else:
                dropped_overflow += 1
            max_buffer_depth = max(max_buffer_depth, len(buffer))
            # On an up link, flush the buffer in seq order (burst replay)
            if up:
                for b in sorted(buffer, key=lambda e: e["seq"]):
                    delivered.append(b)
                    delivery_time[b["seq"]] = t
                buffer.clear()

        # Anything still buffered at the end is undelivered
        undelivered = sorted(buffer, key=lambda e: e["seq"])

        # Verification: in-order + exactly-once
        seqs = [d["seq"] for d in delivered]
        in_order = all(seqs[i] <= seqs[i + 1] for i in range(len(seqs) - 1))
        exactly_once = len(seqs) == len(set(seqs))

        # Gas-alarm latency: when did the first over-threshold reading get delivered
        alarm_events = [e for e in events if e["value"] >= CH4_ALARM_PCT]
        alarm_latency = None
        if alarm_events:
            first = min(alarm_events, key=lambda e: e["seq"])
            if first["seq"] in delivery_time:
                alarm_latency = delivery_time[first["seq"]] - first["t"]

        outage_steps = sum(1 for u in link_up if not u)
        status = "normal"
        if not in_order or not exactly_once or undelivered:
            status = "critical"
        elif alarm_latency and alarm_latency > 0:
            status = "warning"

        headline = (
            f"{len(delivered)}/{len(events)} events delivered in order after "
            f"{outage_steps}-step outage"
            + (f"; gas alarm surfaced {alarm_latency} steps late" if alarm_latency else "")
        )
        return CaseResult(
            case_id=self.case_id,
            status=status,
            headline=headline,
            metrics={
                "events_total": len(events),
                "events_delivered": len(delivered),
                "events_undelivered": len(undelivered),
                "in_order": in_order,
                "exactly_once": exactly_once,
                "max_buffer_depth": max_buffer_depth,
                "buffer_overflow_dropped": dropped_overflow,
                "outage_steps": outage_steps,
                "gas_alarm_latency_steps": alarm_latency,
                "ch4_alarm_pct": CH4_ALARM_PCT,
            },
            recommendations=(
                ["Data integrity preserved across outage — no message loss"]
                if status != "critical"
                else ["Buffer overflow or ordering violation — increase local buffer capacity"]
            ),
        )
