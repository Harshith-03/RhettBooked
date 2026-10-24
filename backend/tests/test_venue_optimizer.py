"""Task 5 tests: layout-aware CP-SAT venue optimizer + air-wall exclusivity."""

from __future__ import annotations

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import venue_optimizer as vo
from backend.app.plan.venue_optimizer import (
    Room,
    ScheduleBlock,
    optimize,
)


def _room(room_id, building, caps, rate=100, group=None, label="MEASURED", name=None):
    layout_caps = {c: None for c in vo._LAYOUT_COLS}
    layout_caps.update(caps)
    return Room(
        room_id=room_id,
        building_code=building,
        name=name or room_id,
        floor="2",
        layout_caps=layout_caps,
        rate_per_hour=rate,
        air_wall_group=group,
        label=label,
    )


def _brief(overnight=False, accessibility=None):
    return EventBrief(
        type=EventType.hackathon,
        description="test event",
        overnight=overnight,
        expected_registrations=300,
        accessibility_needs=accessibility or [],
    )


# --------------------------------------------------------------------------- #
# Layout sizing: a room with NULL for the needed layout cannot host the block
# --------------------------------------------------------------------------- #
def test_null_layout_room_cannot_host_block():
    # Room offers only reception; the block needs a 'work' (classroom) layout.
    rooms = [_room("R-RECEPTION", "B1", {"cap_reception": 500})]
    blocks = [ScheduleBlock(name="Work", layout="work", headcount=100)]
    res = optimize(_brief(), p90=100, blocks=blocks, rooms=rooms, building_attrs={})
    opt = res.options[0]
    assert opt.feasible is False
    assert "layout 'work'" in (opt.unmet_constraint or "")


def test_block_sized_against_its_layout_column():
    # Room has classroom=120 (enough for 100*1.1=110) but buffet=50 (too small).
    rooms = [_room("R", "B1", {"cap_classroom": 120, "cap_buffet": 50})]
    work_ok = optimize(
        _brief(), 100, [ScheduleBlock("W", "work", 100)], rooms=rooms, building_attrs={}
    )
    meal_bad = optimize(
        _brief(), 100, [ScheduleBlock("M", "meal", 100)], rooms=rooms, building_attrs={}
    )
    assert work_ok.options[0].feasible is True
    assert meal_bad.options[0].feasible is False


# --------------------------------------------------------------------------- #
# Capacity safety margin (p90 * 1.1)
# --------------------------------------------------------------------------- #
def test_capacity_requires_safety_margin():
    # Need 100 -> require >= 110. A 105-cap room must fail; a 110-cap room passes.
    small = [_room("S", "B1", {"cap_classroom": 105})]
    big = [_room("L", "B1", {"cap_classroom": 110})]
    blocks = [ScheduleBlock("W", "work", 100)]
    assert optimize(_brief(), 100, blocks, rooms=small, building_attrs={}).options[0].feasible is False
    assert optimize(_brief(), 100, blocks, rooms=big, building_attrs={}).options[0].feasible is True


# --------------------------------------------------------------------------- #
# Air-wall exclusivity (the required test)
# --------------------------------------------------------------------------- #
def test_air_wall_whole_and_part_never_booked_together():
    # GSU-219 (whole) splits into 219A + 219B. Two blocks both need a large
    # classroom layout; the whole room and a part could each host a block, but
    # the optimizer must not use the whole room AND a part simultaneously.
    rooms = [
        _room("GSU-219", "GSU", {"cap_classroom": 828}, rate=400, group="GSU-219"),
        _room("GSU-219A", "GSU", {"cap_classroom": 275}, rate=150, group="GSU-219"),
        _room("GSU-219B", "GSU", {"cap_classroom": 520}, rate=250, group="GSU-219"),
        _room("GSU-OTHER", "GSU", {"cap_classroom": 300}, rate=100),
    ]
    blocks = [
        ScheduleBlock("Block1", "work", 200),
        ScheduleBlock("Block2", "work", 200),
    ]
    res = optimize(_brief(), 200, blocks, rooms=rooms, building_attrs={})
    opt = res.options[0]
    assert opt.feasible is True
    used = {a.room_id for a in opt.assignments}
    # If the whole room is used, neither part may be used, and vice versa.
    if "GSU-219" in used:
        assert "GSU-219A" not in used and "GSU-219B" not in used
    # And never both a part and the whole.
    assert not ("GSU-219" in used and ({"GSU-219A", "GSU-219B"} & used))


def test_air_wall_conflicts_pairs():
    rooms = [
        _room("W", "B", {"cap_classroom": 100}, group="W"),
        _room("WA", "B", {"cap_classroom": 50}, group="W"),
        _room("WB", "B", {"cap_classroom": 50}, group="W"),
    ]
    conflicts = vo._air_wall_conflicts(rooms)
    assert ("W", "WA") in conflicts
    assert ("W", "WB") in conflicts
    assert len(conflicts) == 2


# --------------------------------------------------------------------------- #
# Hard constraints: accessibility + overnight (building level)
# --------------------------------------------------------------------------- #
def test_accessibility_blocks_restricted_building():
    rooms = [_room("R", "PHO", {"cap_classroom": 500})]
    attrs = {"PHO": {"accessible_entrance": "restricted", "overnight_allowed": "unknown"}}
    blocks = [ScheduleBlock("W", "work", 100)]
    res = optimize(
        _brief(accessibility=["step-free"]), 100, blocks, rooms=rooms, building_attrs=attrs
    )
    assert res.options[0].feasible is False
    assert "accessibility" in (res.options[0].unmet_constraint or "")


def test_overnight_false_building_blocked():
    rooms = [_room("R", "X", {"cap_classroom": 500})]
    attrs = {"X": {"accessible_entrance": "true", "overnight_allowed": "false"}}
    blocks = [ScheduleBlock("W", "work", 100)]
    res = optimize(_brief(overnight=True), 100, blocks, rooms=rooms, building_attrs=attrs)
    assert res.options[0].feasible is False
    assert "overnight" in (res.options[0].unmet_constraint or "")


# --------------------------------------------------------------------------- #
# Ranking + top-3
# --------------------------------------------------------------------------- #
def test_returns_top_3_and_cheapest_feasible_first():
    rooms = [
        _room("A1", "A", {"cap_classroom": 200}, rate=300),
        _room("B1", "B", {"cap_classroom": 200}, rate=100),  # cheapest
        _room("C1", "C", {"cap_classroom": 200}, rate=200),
        _room("D1", "D", {"cap_classroom": 200}, rate=500),
    ]
    blocks = [ScheduleBlock("W", "work", 150)]
    res = optimize(_brief(), 150, blocks, rooms=rooms, building_attrs={})
    assert len(res.options) == 3
    assert res.recommended.building_code == "B"  # cheapest feasible


# --------------------------------------------------------------------------- #
# Real data: optimize against the built DuckDB
# --------------------------------------------------------------------------- #
def test_optimize_against_real_duckdb(tmp_path):
    from backend.app.data import build_db

    db = tmp_path / "real.duckdb"
    build_db.build(db_path=db, write_reference=False)

    brief = EventBrief(
        type=EventType.hackathon,
        description="300-person overnight AI hackathon",
        overnight=True,
        expected_registrations=300,
    )
    blocks = [
        ScheduleBlock("Main hall", "work", 180),
        ScheduleBlock("Keynote", "keynote", 180),
    ]
    res = optimize(brief, 180, blocks, db_path=db)
    assert res.options, "expected at least one building option"
    # At least one real building should be able to host a 180-person work layout.
    assert res.recommended is not None
    if res.recommended.feasible:
        assert all(a.capacity >= int(180 * 1.1) for a in res.recommended.assignments)
        # Provenance records the recommended building (MEASURED) + AV assumption.
        keys = {p.output_key for p in res.provenance}
        assert "venue.recommended_building" in keys


def test_brief_a_top_option_uses_measured_rooms(tmp_path):
    """Data-confidence penalty: on Brief A the top feasible option is real spaces."""
    from backend.app.data import build_db

    db = tmp_path / "real.duckdb"
    build_db.build(db_path=db, write_reference=False)

    brief = EventBrief(
        type=EventType.hackathon,
        description="300-person overnight AI hackathon",
        overnight=True,
        expected_registrations=300,
    )
    blocks = [
        ScheduleBlock("Main hall", "work", 180),
        ScheduleBlock("Keynote", "keynote", 180),
        ScheduleBlock("Meals", "meal", 180),
    ]
    res = optimize(brief, 180, blocks, db_path=db)
    rec = res.recommended
    assert rec is not None and rec.feasible
    # The recommended option is fully MEASURED (real BU event spaces).
    assert rec.measured_share >= 0.999
    assert all(a.room_id for a in rec.assignments)
    assert "100% real BU event-space data" in rec.reason
    # Overnight + AV confirmation action items are surfaced.
    assert any("overnight access" in a.lower() for a in rec.action_items)
    assert any("av level" in a.lower() for a in rec.action_items)


def test_data_confidence_penalty_prefers_measured_when_close_on_cost():
    # A MEASURED room slightly pricier than a PLACEHOLDER room should still win
    # once the ~25% + flat confidence penalty is applied to the placeholder.
    rooms = [
        _room("REAL", "A", {"cap_classroom": 200}, rate=110, label="MEASURED"),
        _room("PLACE", "B", {"cap_classroom": 200}, rate=100, label="PLACEHOLDER"),
    ]
    blocks = [ScheduleBlock("W", "work", 150)]
    res = optimize(_brief(), 150, blocks, rooms=rooms, building_attrs={})
    assert res.recommended.building_code == "A"  # MEASURED wins despite +$10/hr
