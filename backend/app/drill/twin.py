"""
twin.py

Digital-twin drill core (P0, task 7).

``run(plan_ctx, disruptions=None, db_path=...)`` steps the chosen plan through
15-minute blocks and evaluates the P0 systems only:
  - occupancy  (concurrent people vs assigned room capacity),
  - power      (device charging load vs circuits in the assigned rooms),
  - getting_home / mobility (late-night departures vs transit, stressed by any
    planned MBTA disruption that overlaps the event dates).

Network, air/CO2, and food/restroom queues are P1 (task 20) and are NOT in the
P0 core.

Planned MBTA disruptions whose window overlaps the event dates are auto-included
as a drill disruption (e.g. the Oct 31-Nov 1 2026 Green Line closure), loaded
from the real mbta_stops dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..config import load_assumptions
from ..data import loaders
from ..provenance import Label, ProvenanceRow

STATUS_OK = "ok"
STATUS_STRAINED = "strained"
STATUS_FAILING = "failing"


@dataclass
class SystemTimeline:
    system: str
    status: str                       # worst status across the run
    first_failure_block: int | None   # block index of first strained/failing
    first_failure_clock: str | None
    series: list[float] = field(default_factory=list)   # load ratio per block
    note: str = ""


@dataclass
class DrillContext:
    """Thin inputs the drill needs, extracted from a Plan."""

    peak_p90: int
    assigned_capacity: int
    assigned_power_circuits: int
    per_block_occupancy: list[int]
    per_block_clock: list[str]
    event_start: date | None
    event_end: date | None
    overnight: bool
    event_type: str = "hackathon"


@dataclass
class DrillResult:
    systems: list[SystemTimeline]
    disruptions: list[str]
    planned_disruptions: list[dict[str, Any]]
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def worst_status(self) -> str:
        order = {STATUS_OK: 0, STATUS_STRAINED: 1, STATUS_FAILING: 2}
        return max((s.status for s in self.systems), key=lambda s: order[s], default=STATUS_OK)


# --------------------------------------------------------------------------- #
# Planned disruptions overlapping the event
# --------------------------------------------------------------------------- #
def planned_disruptions_for(
    event_start: date | None, event_end: date | None, db_path=None
) -> list[loaders.PlannedDisruption]:
    """Return unique planned MBTA disruptions whose window overlaps the event."""
    if not event_start or not event_end:
        return []
    stops, _ = loaders.load_mbta_stops()
    seen: dict[str, loaders.PlannedDisruption] = {}
    for stop in stops:
        d = stop.disruption
        if d and d.overlaps(event_start, event_end):
            key = f"{d.start_date}|{d.end_date}|{','.join(d.lines)}"
            seen.setdefault(key, d)
    return list(seen.values())


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def run(ctx: DrillContext, disruptions: list[str] | None = None, db_path=None) -> DrillResult:
    assumptions = load_assumptions()
    disruptions = list(disruptions or [])
    prov: list[ProvenanceRow] = []

    # Auto-include planned MBTA disruptions overlapping the event dates.
    planned = planned_disruptions_for(ctx.event_start, ctx.event_end, db_path)
    planned_dicts: list[dict[str, Any]] = []
    mobility_stress = 1.0
    for d in planned:
        label_bits = []
        if d.lines:
            label_bits.append(", ".join(d.lines) + " closure")
        if d.shuttle_note:
            label_bits.append(d.shuttle_note + (" (fare-free)" if d.fare_free else ""))
        tag = "; ".join(label_bits) or "planned MBTA disruption"
        disruptions.append(tag)
        planned_dicts.append({
            "lines": d.lines,
            "start_date": d.start_date.isoformat() if d.start_date else None,
            "end_date": d.end_date.isoformat() if d.end_date else None,
            "shuttle_note": d.shuttle_note,
            "fare_free": d.fare_free,
            "label": tag,
        })
        # A rail closure materially slows the late-night getting-home system.
        mobility_stress = max(mobility_stress, 1.6)
        prov.append(
            ProvenanceRow(
                output_key="drill.disruption.planned",
                label=Label.MEASURED,
                source="mbta_stations_bu.csv service_alert",
                value_summary=tag,
            )
        )

    # +30% turnout disruption support (optional).
    turnout_mult = 1.3 if "turnout+30" in disruptions else 1.0

    systems = [
        _occupancy_timeline(ctx, turnout_mult),
        _power_timeline(ctx, assumptions, turnout_mult),
        _mobility_timeline(ctx, mobility_stress, turnout_mult),
    ]

    prov.append(
        ProvenanceRow(
            output_key="drill.run",
            label=Label.SIMULATED,
            source="15-min twin stepping (occupancy, power, getting-home)",
            value_summary=f"worst={_worst(systems)}; disruptions={len(disruptions)}",
        )
    )

    return DrillResult(
        systems=systems,
        disruptions=disruptions,
        planned_disruptions=planned_dicts,
        provenance=prov,
    )


def _status_from_ratio(ratio: float) -> str:
    if ratio <= 0.85:
        return STATUS_OK
    if ratio <= 1.0:
        return STATUS_STRAINED
    return STATUS_FAILING


def _summarize(system: str, series: list[float], clocks: list[str], note: str = "") -> SystemTimeline:
    worst = STATUS_OK
    first_block = None
    first_clock = None
    order = {STATUS_OK: 0, STATUS_STRAINED: 1, STATUS_FAILING: 2}
    for i, ratio in enumerate(series):
        st = _status_from_ratio(ratio)
        if order[st] > order[worst]:
            worst = st
        if st != STATUS_OK and first_block is None:
            first_block = i
            first_clock = clocks[i] if i < len(clocks) else None
    return SystemTimeline(
        system=system, status=worst, first_failure_block=first_block,
        first_failure_clock=first_clock, series=series, note=note,
    )


def _occupancy_timeline(ctx: DrillContext, turnout_mult: float) -> SystemTimeline:
    cap = max(1, ctx.assigned_capacity)
    series = [(occ * turnout_mult) / cap for occ in ctx.per_block_occupancy]
    return _summarize(
        "occupancy", series, ctx.per_block_clock,
        note=f"peak occupancy vs assigned capacity {cap}",
    )


def _power_timeline(ctx: DrillContext, assumptions: dict, turnout_mult: float) -> SystemTimeline:
    # Load per block: devices = occupancy * devices/person; watts = devices * watts/device.
    dpp = _assume(assumptions, ["devices_per_person", "by_type", ctx.event_type, "value"], 2.0)
    wpd = _assume(assumptions, ["watts_per_device", "value"], 65.0)
    amps = _assume(assumptions, ["power_circuit", "amps", "value"], 20.0)
    volts = _assume(assumptions, ["power_circuit", "volts", "value"], 120.0)
    sf = _assume(assumptions, ["power_circuit", "safety_factor", "value"], 0.8)
    circuits = max(1, ctx.assigned_power_circuits)
    circuit_watts = sf * amps * volts * circuits
    series = []
    for occ in ctx.per_block_occupancy:
        load_watts = occ * turnout_mult * dpp * wpd
        series.append(load_watts / circuit_watts if circuit_watts else 0.0)
    return _summarize(
        "power", series, ctx.per_block_clock,
        note=f"charging load vs {circuits} circuits",
    )


def _mobility_timeline(ctx: DrillContext, stress: float, turnout_mult: float) -> SystemTimeline:
    # Getting-home pressure peaks on the departure ramp and late-night blocks.
    # Approximate departures as the block-to-block drop in occupancy, scaled by
    # the disruption stress multiplier. A late-night departure under a rail
    # closure is the risky case.
    occ = [o * turnout_mult for o in ctx.per_block_occupancy]
    n = len(occ)
    series = []
    # Transit "capacity" to clear people in a block; a closure lowers it (stress).
    base_clear = max(1.0, (max(occ) if occ else 1) * 0.25)
    clear = base_clear / stress
    for i in range(n):
        prev = occ[i - 1] if i > 0 else occ[i]
        departures = max(0.0, prev - occ[i])
        series.append(departures / clear if clear else 0.0)
    note = "late-night departures vs transit"
    if stress > 1.0:
        note += " (planned rail closure in effect)"
    return _summarize("getting_home", series, ctx.per_block_clock, note=note)


def _assume(assumptions: dict, path: list[str], default: float) -> float:
    cur: Any = assumptions
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def _worst(systems: list[SystemTimeline]) -> str:
    order = {STATUS_OK: 0, STATUS_STRAINED: 1, STATUS_FAILING: 2}
    return max((s.status for s in systems), key=lambda s: order[s], default=STATUS_OK)
