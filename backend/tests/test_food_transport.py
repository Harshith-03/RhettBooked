"""Tasks 15 & 16 tests: food & water + getting there (committed data only)."""

from __future__ import annotations

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import food_water as fw_mod
from backend.app.plan import plan as plan_mod
from backend.app.plan import transport as tr_mod


def _brief(meals=None, start="2026-10-24", end="2026-10-25", overnight=True, regs=300):
    return EventBrief(
        type=EventType.hackathon,
        description="300-person overnight AI hackathon at BU",
        start=start, end=end, overnight=overnight,
        expected_registrations=regs,
        meals=meals if meals is not None else ["breakfast", "lunch", "snack", "dinner"],
    )


# --------------------------------------------------------------------------- #
# Food & water
# --------------------------------------------------------------------------- #
def test_food_plan_has_one_entry_per_meal():
    fw = fw_mod.plan(_brief())
    assert [m.meal for m in fw.meals] == ["breakfast", "lunch", "snack", "dinner"]


def test_food_lunch_lists_open_bu_halls():
    fw = fw_mod.plan(_brief(meals=["lunch"]))
    lunch = fw.meals[0]
    # Residential halls open 08:00-22:00 on a weekday -> open for lunch window.
    assert any(h.name for h in lunch.bu_dining_open)
    names = {h.name for h in lunch.bu_dining_open}
    assert "Warren Towers Dining Hall" in names


def test_gsu_food_court_flagged_check_hours():
    fw = fw_mod.plan(_brief(meals=["lunch"]))
    lunch = fw.meals[0]
    check = {h.name for h in lunch.bu_dining_check_hours}
    # GSU Food Court has blank hours -> "check hours", never assumed open.
    assert "GSU Food Court" in check
    # And it never appears as confirmed-open.
    assert "GSU Food Court" not in {h.name for h in lunch.bu_dining_open}


def test_midnight_snack_window_excludes_daytime_only_halls():
    fw = fw_mod.plan(_brief(meals=["snack"]))
    snack = fw.meals[0]
    # Halls closing at 21:00-22:00 are NOT open at a ~23:30 snack window.
    assert snack.bu_dining_open == []


def test_food_cost_from_rate_cards_scales_with_headcount():
    small = fw_mod.plan(_brief(meals=["lunch"], regs=100))
    big = fw_mod.plan(_brief(meals=["lunch"], regs=1000))
    assert big.meals[0].cost_high > small.meals[0].cost_high


def test_serving_lines_from_capacity_rule():
    fw = fw_mod.plan(_brief(meals=["lunch"], regs=300))
    # ceil(headcount / PEOPLE_PER_LINE); headcount is attendance p90 (< 300).
    assert fw.meals[0].serving_lines >= 1


def test_water_refill_vs_bottled_present():
    fw = fw_mod.plan(_brief())
    w = fw.water
    assert w.total_litres > 0
    assert w.bottled_cost_low <= w.bottled_cost_high
    assert w.refill_cost_low <= w.refill_cost_high
    assert w.recommendation


def test_food_provenance_labels():
    fw = fw_mod.plan(_brief(meals=["lunch"]))
    keys = {p.output_key: p.label for p in fw.provenance}
    assert keys.get("food.lunch.cost") == "ASSUMED"
    assert keys.get("water.demand") == "ASSUMED"
    assert any(k.startswith("dining.") and v == "MEASURED" for k, v in keys.items())


# --------------------------------------------------------------------------- #
# Getting there
# --------------------------------------------------------------------------- #
def test_transport_nearest_stops_sorted_by_walk_min():
    tr = tr_mod.plan(_brief())
    walks = [s.walk_min for s in tr.stops if s.walk_min is not None]
    assert walks == sorted(walks)
    assert len(tr.stops) <= tr_mod.NEAREST_N


def test_transport_accessibility_flags_blandford():
    tr = tr_mod.plan(_brief())
    # Blandford St is not accessible; it should surface in accessibility flags
    # if it is among the nearest stops.
    names_flagged = " ".join(tr.accessibility_flags)
    nearest_names = {s.name for s in tr.stops}
    if "Blandford Street" in nearest_names:
        assert "Blandford Street" in names_flagged


def test_brief_b_disruption_overlaps_and_shuttle_surfaced():
    tr = tr_mod.plan(_brief(start="2026-10-31", end="2026-11-01"))
    overlapping = [d for d in tr.planned_disruptions if d.overlaps_event]
    assert overlapping, "Brief B should overlap the Green Line closure"
    d = overlapping[0]
    assert "Green Line" in " ".join(d.lines)
    assert d.fare_free is True
    assert tr.shuttle_note and "57" in tr.shuttle_note


def test_brief_a_no_overlapping_disruption():
    tr = tr_mod.plan(_brief(start="2026-10-24", end="2026-10-25"))
    assert not any(d.overlaps_event for d in tr.planned_disruptions)


def test_transport_parking_with_rates_or_notes():
    tr = tr_mod.plan(_brief())
    assert tr.parking, "expected parking options from the real table"
    # Public/visitor lots are surfaced first.
    assert tr.parking[0].public_or_visitor.lower() in ("yes", "no", "")


def test_transport_provenance_measured():
    tr = tr_mod.plan(_brief())
    labels = {p.label for p in tr.provenance}
    assert "MEASURED" in labels


# --------------------------------------------------------------------------- #
# Plan integration: both tiles populated
# --------------------------------------------------------------------------- #
def test_plan_food_and_getting_there_tiles_populated():
    plan = plan_mod.build(_brief(), draws=300)
    food = next(t for t in plan.tiles if t.name == "Food & Water")
    gt = next(t for t in plan.tiles if t.name == "Getting There")
    assert food.details["meals"]
    assert "water" in food.details
    assert gt.details["stops"]
    assert "parking" in gt.details


def test_plan_brief_b_getting_there_shows_overlap():
    plan = plan_mod.build(_brief(start="2026-10-31", end="2026-11-01"), draws=300)
    gt = next(t for t in plan.tiles if t.name == "Getting There")
    overlapping = [d for d in gt.details["planned_disruptions"] if d["overlaps_event"]]
    assert overlapping
    assert gt.action_items
