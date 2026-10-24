"""
verdict.py

Drill verdict + fixes + readiness + before/after re-run (P0, task 7).

``assess(result)`` turns a DrillResult into a verdict: per-system status,
first-failure time, tiered fixes (Do now / Plan for / Improve later), a readiness
score 0-100, and the top-3 risks that feed back into plan.summary.

``rerun(ctx, applied_fixes)`` re-runs the twin with the chosen fixes applied
(more rooms, more circuits, a shuttle) and returns a before/after comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..provenance import Label, ProvenanceRow
from . import twin as twin_mod

# Weight each P0 system in the readiness score.
SYSTEM_WEIGHTS = {"occupancy": 0.4, "power": 0.3, "getting_home": 0.3}
_STATUS_SCORE = {twin_mod.STATUS_OK: 1.0, twin_mod.STATUS_STRAINED: 0.5,
                 twin_mod.STATUS_FAILING: 0.0}

# Tiered fix templates per system.
_FIXES = {
    "occupancy": {
        "do_now": "Split the main block across a second room or add overflow seating",
        "plan_for": "Stagger arrivals / add a second session to flatten the peak",
        "improve_later": "Book a larger primary room next time",
    },
    "power": {
        "do_now": "Rent additional power stations / distribute charging across rooms",
        "plan_for": "Pre-position power strips and label circuits before doors open",
        "improve_later": "Choose rooms with more branch circuits",
    },
    "getting_home": {
        "do_now": "Publish the shuttle plan and stagger the late-night departure",
        "plan_for": "Arrange a buddy-walk and extra rideshare pickup window",
        "improve_later": "Schedule the end time before the last reliable train",
    },
}


@dataclass
class SystemVerdict:
    system: str
    status: str
    first_failure_clock: str | None
    fixes: dict[str, str]
    note: str


@dataclass
class Verdict:
    readiness: int
    worst_status: str
    systems: list[SystemVerdict]
    top_risks: list[str]
    fixes: dict[str, list[str]]       # do_now / plan_for / improve_later
    provenance: list[ProvenanceRow] = field(default_factory=list)


def assess(result: twin_mod.DrillResult) -> Verdict:
    systems: list[SystemVerdict] = []
    do_now: list[str] = []
    plan_for: list[str] = []
    improve_later: list[str] = []
    risks: list[str] = []

    readiness_num = 0.0
    readiness_den = 0.0
    order = {twin_mod.STATUS_OK: 0, twin_mod.STATUS_STRAINED: 1, twin_mod.STATUS_FAILING: 2}

    for s in result.systems:
        weight = SYSTEM_WEIGHTS.get(s.system, 0.2)
        readiness_num += _STATUS_SCORE[s.status] * weight
        readiness_den += weight

        fixes = _FIXES.get(s.system, {})
        systems.append(
            SystemVerdict(
                system=s.system,
                status=s.status,
                first_failure_clock=s.first_failure_clock,
                fixes=fixes,
                note=s.note,
            )
        )
        if s.status != twin_mod.STATUS_OK:
            if fixes.get("do_now"):
                do_now.append(fixes["do_now"])
            if fixes.get("plan_for"):
                plan_for.append(fixes["plan_for"])
            if fixes.get("improve_later"):
                improve_later.append(fixes["improve_later"])
            when = f" from {s.first_failure_clock}" if s.first_failure_clock else ""
            risks.append(f"{_label(s.system)} {s.status}{when}")

    # Planned MBTA disruptions are always a top risk (getting-home).
    for pd in result.planned_disruptions:
        risks.insert(0, pd["label"])
        shuttle = pd.get("shuttle_note")
        if shuttle:
            fare = " (fare-free)" if pd.get("fare_free") else ""
            do_now.insert(0, f"Use the {shuttle}{fare} during the closure")

    readiness = int(round(100 * (readiness_num / readiness_den))) if readiness_den else 100
    worst = result.worst_status()

    prov = [
        ProvenanceRow(
            output_key="drill.readiness",
            label=Label.SIMULATED,
            source="weighted share of P0 systems ok (occupancy/power/getting-home)",
            value_summary=f"{readiness}/100",
        )
    ]

    return Verdict(
        readiness=readiness,
        worst_status=worst,
        systems=systems,
        top_risks=risks[:3],
        fixes={
            "do_now": _dedup(do_now),
            "plan_for": _dedup(plan_for),
            "improve_later": _dedup(improve_later),
        },
        provenance=prov,
    )


def rerun(ctx: twin_mod.DrillContext, applied_fixes: dict[str, Any], db_path=None) -> dict[str, Any]:
    """Re-run the twin with fixes applied; return before/after readiness + status."""
    before = assess(twin_mod.run(ctx, db_path=db_path))

    # Apply fixes to a copy of the context.
    import copy

    ctx2 = copy.deepcopy(ctx)
    if applied_fixes.get("add_room_capacity"):
        ctx2.assigned_capacity += int(applied_fixes["add_room_capacity"])
    if applied_fixes.get("add_power_circuits"):
        ctx2.assigned_power_circuits += int(applied_fixes["add_power_circuits"])
    extra_disruptions = []
    # A shuttle mitigation relieves the getting-home system; model it by NOT
    # re-stressing mobility (handled below via a flag on the rerun disruptions).
    after_result = twin_mod.run(ctx2, db_path=db_path)
    if applied_fixes.get("shuttle"):
        # Relax mobility series by the shuttle relief factor.
        for s in after_result.systems:
            if s.system == "getting_home":
                s.series = [r / 1.6 for r in s.series]
                s.status = twin_mod.STATUS_OK if all(r <= 0.85 for r in s.series) else s.status
    after = assess(after_result)

    return {
        "before": {"readiness": before.readiness, "worst_status": before.worst_status,
                   "top_risks": before.top_risks},
        "after": {"readiness": after.readiness, "worst_status": after.worst_status,
                  "top_risks": after.top_risks},
        "improved": after.readiness >= before.readiness,
    }


def _label(system: str) -> str:
    return {"occupancy": "Occupancy", "power": "Power",
            "getting_home": "Getting home"}.get(system, system)


def _dedup(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
