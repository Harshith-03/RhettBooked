"""Task 6 tests: budget Monte Carlo + plan orchestrator."""

from __future__ import annotations

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import attendance as attendance_mod
from backend.app.plan import budget as budget_mod
from backend.app.plan import plan as plan_mod


def _brief_a():
    return EventBrief(
        type=EventType.hackathon,
        description="300-person overnight AI hackathon at BU",
        start="2026-10-24",
        end="2026-10-25",
        overnight=True,
        expected_registrations=300,
        budget_usd=15000,
        meals=["breakfast", "lunch", "snack", "dinner"],
    )


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #
def test_budget_percentiles_ordered():
    brief = _brief_a()
    att = attendance_mod.sample(brief, draws=500)
    b = budget_mod.estimate(brief, att, draws=500)
    assert b.total_p10 <= b.total_p50 <= b.total_p90
    for li in b.line_items:
        assert li.p10 <= li.p50 <= li.p90


def test_budget_has_catering_lines_per_meal():
    brief = _brief_a()
    att = attendance_mod.sample(brief, draws=300)
    b = budget_mod.estimate(brief, att, draws=300)
    names = {li.name for li in b.line_items}
    for meal in ("breakfast", "lunch", "snack", "dinner"):
        assert f"Catering - {meal}" in names


def test_sponsorship_gap_is_p50_minus_budget():
    brief = _brief_a()
    att = attendance_mod.sample(brief, draws=400)
    b = budget_mod.estimate(brief, att, draws=400)
    assert b.sponsorship_gap == b.total_p50 - 15000


def test_cost_per_attendee_positive():
    brief = _brief_a()
    att = attendance_mod.sample(brief, draws=300)
    b = budget_mod.estimate(brief, att, draws=300)
    assert b.cost_per_attendee_p50 > 0


def test_budget_provenance_labels():
    brief = _brief_a()
    att = attendance_mod.sample(brief, draws=200)
    b = budget_mod.estimate(brief, att, draws=200)
    by_key = {p.output_key: p for p in b.provenance}
    assert by_key["budget.total"].label == "SIMULATED"
    assert by_key["budget.sponsorship_gap"].label == "SIMULATED"
    # Rate-card inputs are ASSUMED.
    assert by_key["budget.catering.lunch"].label == "ASSUMED"


def test_budget_scales_with_turnout():
    small = EventBrief(type=EventType.conference, description="small conf",
                       expected_registrations=50, meals=["lunch"], budget_usd=5000,
                       start="2026-05-05", end="2026-05-05")
    big = EventBrief(type=EventType.conference, description="big conf",
                     expected_registrations=800, meals=["lunch"], budget_usd=5000,
                     start="2026-05-05", end="2026-05-05")
    bs = budget_mod.estimate(small, attendance_mod.sample(small, draws=300), draws=300)
    bb = budget_mod.estimate(big, attendance_mod.sample(big, draws=300), draws=300)
    assert bb.total_p50 > bs.total_p50


# --------------------------------------------------------------------------- #
# Plan orchestrator
# --------------------------------------------------------------------------- #
def test_plan_build_assembles_summary_and_tiles():
    plan = plan_mod.build(_brief_a(), draws=400)
    s = plan.summary
    assert s["recommended_building"] is not None
    assert s["cost_p10"] <= s["cost_p50"] <= s["cost_p90"]
    assert s["sponsorship_gap"] == s["cost_p50"] - 15000
    # Readiness + top risks are now filled by the integrated drill (task 7).
    assert isinstance(s["readiness"], int) and 0 <= s["readiness"] <= 100
    assert isinstance(s["top_risks"], list)
    # All seven tiles present.
    tile_names = {t.name for t in plan.tiles}
    assert {"Venue", "Budget", "Tech", "Food & Water", "Getting There",
            "People", "Drill"} <= tile_names


def test_plan_venue_tile_has_confirm_action_items():
    plan = plan_mod.build(_brief_a(), draws=400)
    venue_tile = next(t for t in plan.tiles if t.name == "Venue")
    items = " ".join(venue_tile.action_items).lower()
    # Overnight + AV confirmation items surface under the Venue tile.
    assert "overnight access" in items
    assert "av level" in items


def test_plan_recommended_building_is_measured_for_brief_a():
    plan = plan_mod.build(_brief_a(), draws=400)
    venue_tile = next(t for t in plan.tiles if t.name == "Venue")
    assert venue_tile.details.get("measured_share", 0) >= 0.999


def test_plan_to_dict_is_json_friendly():
    plan = plan_mod.build(_brief_a(), draws=200)
    d = plan.to_dict()
    assert set(d.keys()) >= {"summary", "venue", "budget", "attendance", "tiles", "provenance"}
    # provenance carries labels.
    labels = {row["label"] for row in d["provenance"]}
    assert labels & {"MEASURED", "ASSUMED", "SIMULATED"}
