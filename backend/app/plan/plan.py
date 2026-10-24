"""
plan.py

Plan orchestrator (P0, task 6).

``build(brief)`` runs the thin vertical slice:
    attendance -> venue -> budget
and assembles a :class:`Plan` with a summary (recommended building, cost band,
readiness placeholder, top-3 risks placeholder) plus per-section tiles.

The drill (task 7) fills in readiness + the real top-3 risks; transport/food/tech
tiles are stubs here and deepened in later tasks. Every section carries its
provenance rows so the Trust page / GET /provenance can aggregate labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from datetime import datetime

from ..drill import twin as twin_mod
from ..drill import verdict as verdict_mod
from ..provenance import ProvenanceRow
from . import attendance as attendance_mod
from . import budget as budget_mod
from . import food_water as food_mod
from . import transport as transport_mod
from . import venue_optimizer as venue_mod


@dataclass
class Tile:
    """One section tile with a one-line status and a details payload."""

    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    action_items: list[str] = field(default_factory=list)


@dataclass
class Plan:
    summary: dict[str, Any]
    venue: dict[str, Any]
    budget: dict[str, Any]
    attendance: dict[str, Any]
    tiles: list[Tile]
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "venue": self.venue,
            "budget": self.budget,
            "attendance": self.attendance,
            "tiles": [
                {
                    "name": t.name,
                    "status": t.status,
                    "details": t.details,
                    "action_items": t.action_items,
                }
                for t in self.tiles
            ],
            "provenance": [
                {"output_key": p.output_key, "label": p.label, "source": p.source,
                 "value_summary": p.value_summary}
                for p in self.provenance
            ],
        }


def build(brief, db_path: Path | str | None = None, draws: int = 500) -> Plan:
    prov: list[ProvenanceRow] = []

    # 1. Attendance
    att = attendance_mod.sample(brief, draws=draws)
    prov.extend(att.provenance)
    p90 = att.peak_p90()

    # 2. Venue
    food = brief.food_implied()
    blocks = venue_mod.default_blocks(p90=p90, overnight=brief.overnight, food=food)
    venue_res = venue_mod.optimize(brief, p90=p90, blocks=blocks, db_path=db_path)
    prov.extend(venue_res.provenance)
    rec = venue_res.recommended

    # 3. Budget
    bud = budget_mod.estimate(brief, att, venue_res, draws=draws)
    prov.extend(bud.provenance)

    # 3b. Food & water + transport (committed data only)
    fw = food_mod.plan(brief, attendance=att, db_path=db_path)
    prov.extend(fw.provenance)
    trans = transport_mod.plan(brief, db_path=db_path)
    prov.extend(trans.provenance)

    # 4. Drill (occupancy + power + getting-home) -> readiness + top-3 risks
    drill_ctx = _build_drill_context(brief, att, rec)
    drill_result = twin_mod.run(drill_ctx, db_path=db_path)
    prov.extend(drill_result.provenance)
    verdict = verdict_mod.assess(drill_result)
    prov.extend(verdict.provenance)

    # --- Summary (readiness + top risks now come from the drill) ---
    summary = {
        "recommended_building": rec.building_code if rec else None,
        "cost_p10": bud.total_p10,
        "cost_p50": bud.total_p50,
        "cost_p90": bud.total_p90,
        "cost_per_attendee": bud.cost_per_attendee_p50,
        "sponsorship_gap": bud.sponsorship_gap,
        "turnout_p50": att.turnout_p50,
        "turnout_p90": att.turnout_p90,
        "readiness": verdict.readiness,
        "top_risks": verdict.top_risks,
    }

    venue_tile = _venue_tile(venue_res)
    tiles = [
        venue_tile,
        Tile(name="Budget",
             status=f"p50 ${bud.total_p50:,} (p10 ${bud.total_p10:,} - p90 ${bud.total_p90:,})",
             details={
                 "total_p10": bud.total_p10,
                 "total_p50": bud.total_p50,
                 "total_p90": bud.total_p90,
                 "cost_per_attendee": bud.cost_per_attendee_p50,
                 "sponsorship_gap": bud.sponsorship_gap,
                 "line_items": [
                     {"name": li.name, "p10": li.p10, "p50": li.p50, "p90": li.p90}
                     for li in bud.line_items
                 ],
             }),
        # Stubs deepened later; present so the Plan assembles completely (task 12).
        Tile(name="Tech", status="sized in task 14", details={}),
        _food_tile(fw),
        _getting_there_tile(trans, drill_result),
        Tile(name="People", status="P1 (task 18)", details={}),
        Tile(name="Drill",
             status=f"readiness {verdict.readiness}/100 ({verdict.worst_status})",
             details={
                 "readiness": verdict.readiness,
                 "worst_status": verdict.worst_status,
                 "systems": [
                     {"system": sv.system, "status": sv.status,
                      "first_failure_clock": sv.first_failure_clock, "note": sv.note}
                     for sv in verdict.systems
                 ],
                 "top_risks": verdict.top_risks,
                 "fixes": verdict.fixes,
                 "disruptions": drill_result.disruptions,
             },
             action_items=verdict.fixes.get("do_now", [])),
    ]

    attendance_summary = {
        "turnout_p50": att.turnout_p50,
        "turnout_p90": att.turnout_p90,
        "peak_p90": p90,
        "blocks": len(att.per_block),
    }

    venue_dict = {
        "recommended": rec.building_code if rec else None,
        "options": [
            {
                "building_code": o.building_code,
                "feasible": o.feasible,
                "reason": o.reason,
                "measured_share": o.measured_share,
                "total_cost": o.total_cost,
                "avg_utilization": o.avg_utilization,
                "assignments": [
                    {"block": a.block, "room_id": a.room_id, "room_name": a.room_name,
                     "layout": a.layout, "capacity": a.capacity,
                     "utilization": a.utilization}
                    for a in o.assignments
                ],
                "action_items": o.action_items,
                "unmet_constraint": o.unmet_constraint,
            }
            for o in venue_res.options
        ],
    }

    budget_dict = {
        "total_p10": bud.total_p10,
        "total_p50": bud.total_p50,
        "total_p90": bud.total_p90,
        "cost_per_attendee": bud.cost_per_attendee_p50,
        "sponsorship_gap": bud.sponsorship_gap,
        "line_items": [
            {"name": li.name, "p10": li.p10, "p50": li.p50, "p90": li.p90}
            for li in bud.line_items
        ],
    }

    return Plan(
        summary=summary,
        venue=venue_dict,
        budget=budget_dict,
        attendance=attendance_summary,
        tiles=tiles,
        provenance=prov,
    )


def drill_context_for(brief, db_path=None) -> twin_mod.DrillContext:
    """Public helper: build a DrillContext for a brief (attendance + venue).

    Used by the /drill/run and /drill/compare endpoints so they don't rebuild a
    whole plan just to get the drill inputs.
    """
    att = attendance_mod.sample(brief)
    p90 = att.peak_p90()
    blocks = venue_mod.default_blocks(p90=p90, overnight=brief.overnight,
                                      food=brief.food_implied())
    rec = venue_mod.optimize(brief, p90=p90, blocks=blocks, db_path=db_path).recommended
    return _build_drill_context(brief, att, rec)


def _build_drill_context(brief, att, rec) -> twin_mod.DrillContext:
    """Assemble the thin DrillContext from attendance + the recommended venue."""
    per_block_occ = [b.p90 for b in att.per_block]
    per_block_clock = [b.clock for b in att.per_block]

    # Assigned capacity = the smallest 'work'/main-hall room capacity assigned
    # (the binding constraint for occupancy). Fall back to peak if none.
    assigned_cap = 0
    assigned_circuits = 0
    if rec and rec.feasible and rec.assignments:
        caps = [a.capacity for a in rec.assignments]
        assigned_cap = min(caps) if caps else 0
        # Power circuits aren't on the Assignment; approximate from capacity
        # using the same ceil(sqft/400) spirit -> here ceil(cap/40) circuits as a
        # thin proxy until tech sizing (task 14) provides the real figure.
        assigned_circuits = max(1, int(round(assigned_cap / 40)))
    if assigned_cap <= 0:
        assigned_cap = max(per_block_occ) if per_block_occ else 1
        assigned_circuits = max(1, int(round(assigned_cap / 40)))

    return twin_mod.DrillContext(
        peak_p90=max(per_block_occ) if per_block_occ else 0,
        assigned_capacity=assigned_cap,
        assigned_power_circuits=assigned_circuits,
        per_block_occupancy=per_block_occ,
        per_block_clock=per_block_clock,
        event_start=_as_date(brief.start),
        event_end=_as_date(brief.end),
        overnight=bool(brief.overnight),
        event_type=(brief.type.value if brief.type else "hackathon"),
    )


def _as_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _food_tile(fw) -> Tile:
    n_open = sum(len(m.bu_dining_open) for m in fw.meals)
    total_low = sum(m.cost_low for m in fw.meals)
    total_high = sum(m.cost_high for m in fw.meals)
    status = (
        f"{len(fw.meals)} meals; est ${total_low:,}-${total_high:,}; "
        f"{n_open} BU hall openings matched"
    )
    return Tile(
        name="Food & Water",
        status=status,
        details={
            "meals": [
                {
                    "meal": m.meal,
                    "window": m.window,
                    "headcount": m.headcount,
                    "cost_low": m.cost_low,
                    "cost_high": m.cost_high,
                    "serving_lines": m.serving_lines,
                    "note": m.note,
                    "open_halls": [
                        {"name": o.name, "building_code": o.building_code,
                         "hours": o.hours_window}
                        for o in m.bu_dining_open
                    ],
                    "check_hours_halls": [
                        {"name": o.name, "building_code": o.building_code,
                         "flags": o.flags}
                        for o in m.bu_dining_check_hours
                    ],
                }
                for m in fw.meals
            ],
            "water": {
                "total_litres": round(fw.water.total_litres),
                "bottled_cost": [fw.water.bottled_cost_low, fw.water.bottled_cost_high],
                "refill_cost": [fw.water.refill_cost_low, fw.water.refill_cost_high],
                "recommendation": fw.water.recommendation,
            },
        },
    )


def _getting_there_tile(trans, drill_result) -> Tile:
    overlapping = [d for d in trans.planned_disruptions if d.overlaps_event]
    if overlapping:
        status = overlapping[0].label
    else:
        status = f"{len(trans.stops)} stops within walking distance; no planned disruption"
    return Tile(
        name="Getting There",
        status=status,
        details={
            "stops": [
                {"name": s.name, "lines": s.lines, "walk_min": s.walk_min,
                 "accessible": s.accessible, "accessibility_note": s.accessibility_note,
                 "disrupted": s.disrupted}
                for s in trans.stops
            ],
            "bus_routes": [
                {"route": r.get("route"), "name": r.get("name")}
                for r in trans.bus_routes
            ],
            "planned_disruptions": [
                {"label": d.label, "lines": d.lines, "start_date": d.start_date,
                 "end_date": d.end_date, "shuttle_note": d.shuttle_note,
                 "fare_free": d.fare_free, "overlaps_event": d.overlaps_event}
                for d in trans.planned_disruptions
            ],
            "shuttle_note": trans.shuttle_note,
            "accessibility_flags": trans.accessibility_flags,
            "parking": [
                {"name": p.name, "type": p.type,
                 "public_or_visitor": p.public_or_visitor, "notes": p.notes}
                for p in trans.parking
            ],
        },
        action_items=(
            [f"Plan around: {overlapping[0].label}"] if overlapping else []
        ),
    )


def _venue_tile(venue_res) -> Tile:
    rec = venue_res.recommended
    if rec and rec.feasible:
        status = f"{rec.building_code} - {rec.reason}"
        return Tile(
            name="Venue",
            status=status,
            details={
                "recommended": rec.building_code,
                "measured_share": rec.measured_share,
                "assignments": [
                    {"block": a.block, "room_id": a.room_id, "room_name": a.room_name,
                     "capacity": a.capacity, "utilization": a.utilization}
                    for a in rec.assignments
                ],
            },
            action_items=rec.action_items,   # overnight + AV "Confirm with BU Reservations"
        )
    reason = rec.reason if rec else "no feasible building found"
    return Tile(name="Venue", status=f"no feasible venue - {reason}", details={})
