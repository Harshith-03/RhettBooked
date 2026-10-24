"""
Tasks 12 & 24: end-to-end acceptance tests (Requirement 14), LLM_PROVIDER=none.

Task 12 - thin slice checkpoint: the acceptance brief returns an end-to-end plan
  (recommended building + room assignments, budget p10-p90, drill verdict with
  fixes + re-run).

Task 24 - full two-brief acceptance:
  Brief A (Oct 24-25): returns within 10 s a plan with recommended building, room
    assignments, water numbers, 3 vendor-style options per meal (BU halls),
    transit + parking, p10-p90 budget, and a drill verdict with fixes + re-run.
    MUST NOT surface the Green Line closure.
  Brief B (Oct 31-Nov 1 2026): same event MUST list the Green Line closure as a
    top risk with the Route 57 fare-free shuttle, and the drill MUST include it.
"""

from __future__ import annotations

import os
import time

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")
BRIEF_B = ("300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


def _plan(text: str) -> dict:
    r = client.post("/plan", json={"text": text, "draws": 500})
    assert r.status_code == 200
    return r.json()


# --------------------------------------------------------------------------- #
# Task 12 - thin end-to-end checkpoint
# --------------------------------------------------------------------------- #
def test_runs_under_llm_none():
    assert os.environ.get("LLM_PROVIDER", "none") == "none"


def test_task12_thin_slice_assembles_end_to_end():
    plan = _plan(BRIEF_A)
    s = plan["summary"]
    # Recommended building + room assignments.
    assert s["recommended_building"]
    venue_opt = next(o for o in plan["venue"]["options"] if o["feasible"])
    assert venue_opt["assignments"]
    # Budget p10-p90.
    assert plan["budget"]["total_p10"] <= plan["budget"]["total_p50"] <= plan["budget"]["total_p90"]
    # Drill verdict with fixes.
    drill_tile = next(t for t in plan["tiles"] if t["name"] == "Drill")
    assert "readiness" in drill_tile["details"]
    assert drill_tile["details"]["fixes"]["do_now"] is not None
    # Drill re-run (before/after).
    cmp = client.post("/drill/compare", json={
        "text": BRIEF_A, "applied_fixes": {"add_room_capacity": 300, "add_power_circuits": 12}
    }).json()
    assert "before" in cmp and "after" in cmp


# --------------------------------------------------------------------------- #
# Task 24 - full acceptance, Brief A
# --------------------------------------------------------------------------- #
def test_task24_brief_a_full_plan_within_10s_no_green_line():
    start = time.perf_counter()
    plan = _plan(BRIEF_A)
    elapsed = time.perf_counter() - start
    assert elapsed < 10.0, f"plan took {elapsed:.1f}s (budget 10s)"

    s = plan["summary"]
    assert s["recommended_building"]
    # Room assignments.
    venue_opt = next(o for o in plan["venue"]["options"] if o["feasible"])
    assert venue_opt["assignments"]
    # Water numbers + per-meal BU hall options.
    food = next(t for t in plan["tiles"] if t["name"] == "Food & Water")["details"]
    assert food["water"]["total_litres"] > 0
    assert len(food["meals"]) == 4
    assert all("open_halls" in m for m in food["meals"])
    # Transit + parking.
    gt = next(t for t in plan["tiles"] if t["name"] == "Getting There")["details"]
    assert gt["stops"] and gt["parking"]
    # Budget p10-p90.
    assert plan["budget"]["total_p10"] <= plan["budget"]["total_p90"]
    # Drill verdict.
    assert isinstance(s["readiness"], int)

    # MUST NOT surface the Green Line closure for Oct 24-25.
    assert not any("Green Line" in r for r in s["top_risks"])
    overlapping = [d for d in gt["planned_disruptions"] if d["overlaps_event"]]
    assert overlapping == []


# --------------------------------------------------------------------------- #
# Task 24 - full acceptance, Brief B (disruption)
# --------------------------------------------------------------------------- #
def test_task24_brief_b_surfaces_green_line_shuttle_and_drill():
    plan = _plan(BRIEF_B)
    s = plan["summary"]
    # Green Line closure is a top risk.
    assert any("Green Line" in r for r in s["top_risks"])
    # Route 57 fare-free shuttle is the mitigation.
    gt = next(t for t in plan["tiles"] if t["name"] == "Getting There")["details"]
    assert gt["shuttle_note"] and "57" in gt["shuttle_note"]
    overlapping = [d for d in gt["planned_disruptions"] if d["overlaps_event"]]
    assert overlapping and overlapping[0]["fare_free"] is True

    # The drill includes the closure.
    drill = client.post("/drill/run", json={"text": BRIEF_B}).json()
    assert drill["planned_disruptions"]
    assert any("Green Line" in d for d in drill["disruptions"])
    assert any("Green Line" in r for r in drill["top_risks"])


def test_task24_both_briefs_recommend_a_building():
    assert _plan(BRIEF_A)["summary"]["recommended_building"]
    assert _plan(BRIEF_B)["summary"]["recommended_building"]
