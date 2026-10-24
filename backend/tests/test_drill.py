"""Task 7 tests: drill core (occupancy/power/getting-home) + verdict + re-run."""

from __future__ import annotations

from datetime import date

from backend.app.brief.models import EventBrief, EventType
from backend.app.drill import twin as twin_mod
from backend.app.drill import verdict as verdict_mod
from backend.app.drill.twin import DrillContext
from backend.app.plan import plan as plan_mod


def _ctx(occ_peak=180, cap=330, circuits=8, start="2026-10-24", end="2026-10-25",
         n_blocks=48):
    # A simple ramp-up/plateau/ramp-down occupancy curve.
    series = []
    for i in range(n_blocks):
        frac = min(1.0, i / 5) if i < n_blocks * 0.5 else max(0.1, 1 - (i - n_blocks/2) / (n_blocks/2))
        series.append(int(occ_peak * frac))
    clocks = [f"{(9 + (i*15)//60) % 24:02d}:{(i*15) % 60:02d}" for i in range(n_blocks)]
    return DrillContext(
        peak_p90=occ_peak, assigned_capacity=cap, assigned_power_circuits=circuits,
        per_block_occupancy=series, per_block_clock=clocks,
        event_start=date.fromisoformat(start), event_end=date.fromisoformat(end),
        overnight=True, event_type="hackathon",
    )


# --------------------------------------------------------------------------- #
# Core systems
# --------------------------------------------------------------------------- #
def test_drill_runs_p0_systems_only():
    res = twin_mod.run(_ctx())
    names = {s.system for s in res.systems}
    assert names == {"occupancy", "power", "getting_home"}
    # No air/network/queues in the P0 core.
    assert "air" not in names and "network" not in names


def test_occupancy_fails_when_over_capacity():
    # Occupancy peak 400 vs capacity 200 -> ratio 2.0 -> failing.
    res = twin_mod.run(_ctx(occ_peak=400, cap=200))
    occ = next(s for s in res.systems if s.system == "occupancy")
    assert occ.status == twin_mod.STATUS_FAILING
    assert occ.first_failure_clock is not None


def test_occupancy_ok_when_within_capacity():
    res = twin_mod.run(_ctx(occ_peak=100, cap=500))
    occ = next(s for s in res.systems if s.system == "occupancy")
    assert occ.status == twin_mod.STATUS_OK


# --------------------------------------------------------------------------- #
# Oct 31 2026 event triggers Green Line risk + drill auto-include (the required test)
# --------------------------------------------------------------------------- #
def test_oct_31_event_triggers_green_line_and_drill_includes_it():
    res = twin_mod.run(_ctx(start="2026-10-31", end="2026-11-01"))
    # The planned closure is auto-included.
    assert res.planned_disruptions, "expected the Green Line closure to be included"
    pd = res.planned_disruptions[0]
    assert "Green Line" in " ".join(pd["lines"])
    assert pd["start_date"] == "2026-10-31"
    assert pd["end_date"] == "2026-11-01"
    assert pd["fare_free"] is True
    assert "57" in (pd["shuttle_note"] or "")
    # It appears as a drill disruption string too.
    assert any("Green Line" in d for d in res.disruptions)

    # And the verdict lists it as a top risk with a shuttle "do now" fix.
    v = verdict_mod.assess(res)
    assert any("Green Line" in r for r in v.top_risks)
    assert any("57" in f for f in v.fixes["do_now"])


def test_brief_a_oct_24_does_not_include_green_line():
    res = twin_mod.run(_ctx(start="2026-10-24", end="2026-10-25"))
    assert res.planned_disruptions == []
    assert not any("Green Line" in d for d in res.disruptions)


# --------------------------------------------------------------------------- #
# Verdict + readiness + re-run
# --------------------------------------------------------------------------- #
def test_readiness_range_and_worst_status():
    v = verdict_mod.assess(twin_mod.run(_ctx(occ_peak=100, cap=500)))
    assert 0 <= v.readiness <= 100
    assert v.worst_status in (twin_mod.STATUS_OK, twin_mod.STATUS_STRAINED,
                              twin_mod.STATUS_FAILING)


def test_rerun_before_after_improves_with_fixes():
    ctx = _ctx(occ_peak=400, cap=200, circuits=2)  # overloaded
    cmp = verdict_mod.rerun(ctx, {"add_room_capacity": 400, "add_power_circuits": 10})
    assert cmp["after"]["readiness"] >= cmp["before"]["readiness"]


def test_fixes_are_tiered():
    v = verdict_mod.assess(twin_mod.run(_ctx(occ_peak=400, cap=200)))
    assert set(v.fixes.keys()) == {"do_now", "plan_for", "improve_later"}
    assert v.fixes["do_now"]  # at least one immediate fix when failing


# --------------------------------------------------------------------------- #
# Plan integration: readiness + top risks flow into the summary
# --------------------------------------------------------------------------- #
def test_plan_summary_gets_readiness_and_risks_from_drill():
    brief = EventBrief(
        type=EventType.hackathon, description="300-person overnight AI hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=300, budget_usd=15000,
        meals=["breakfast", "lunch", "snack", "dinner"],
    )
    plan = plan_mod.build(brief, draws=300)
    assert isinstance(plan.summary["readiness"], int)
    assert 0 <= plan.summary["readiness"] <= 100
    drill_tile = next(t for t in plan.tiles if t.name == "Drill")
    assert "readiness" in drill_tile.details


def test_plan_brief_b_surfaces_green_line_in_summary_risks():
    brief = EventBrief(
        type=EventType.hackathon, description="300-person overnight AI hackathon",
        start="2026-10-31", end="2026-11-01", overnight=True,
        expected_registrations=300, budget_usd=15000,
        meals=["breakfast", "lunch", "snack", "dinner"],
    )
    plan = plan_mod.build(brief, draws=300)
    assert any("Green Line" in r for r in plan.summary["top_risks"])
    # Getting There tile reflects the closure.
    gt = next(t for t in plan.tiles if t.name == "Getting There")
    assert gt.details["planned_disruptions"]
