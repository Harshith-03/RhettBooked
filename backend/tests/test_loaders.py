"""Task 2 tests: real-data loaders, parsing rules, rooms union, and DuckDB build."""

from __future__ import annotations

from datetime import date

from backend.app.data import build_db, loaders
from backend.app.provenance import ALLOWED_LABELS, Label


# --------------------------------------------------------------------------- #
# Event spaces: blank capacities -> NULL (not 0); derived max_capacity
# --------------------------------------------------------------------------- #
def test_event_spaces_load_and_blank_caps_are_null():
    spaces, prov = loaders.load_event_spaces()
    assert spaces, "expected real event_spaces rows"
    by_id = {s.space_id: s for s in spaces}

    # GSU-219A: cap_theatre_lecture=400, cap_classroom=275, but cap_reception and
    # the u_shape/boardroom/fixed_seats columns are blank -> None, never 0.
    a = by_id["GSU-219A"]
    assert a.layout_caps["cap_theatre_lecture"] == 400
    assert a.layout_caps["cap_classroom"] == 275
    assert a.layout_caps["cap_reception"] is None
    assert a.layout_caps["cap_u_shape"] is None
    # No capacity column is ever the integer 0 from a blank.
    for s in spaces:
        for v in s.layout_caps.values():
            assert v != 0

    # OSW-918 has a blank max_capacity and all blank layouts -> max_capacity None.
    assert by_id["OSW-918"].max_capacity is None

    # GSU-228 (auditorium) has only fixed_seats=260 and blank max_capacity ->
    # derived max_capacity = 260.
    assert by_id["GSU-228"].max_capacity == 260
    assert by_id["GSU-228"].layout_caps["cap_fixed_seats"] == 260

    assert all(p.label == Label.MEASURED.value for p in prov)


def test_air_wall_groups_parsed():
    spaces, _ = loaders.load_event_spaces()
    by_id = {s.space_id: s for s in spaces}
    # Whole room announces the split in its notes.
    assert by_id["GSU-219"].air_wall_group == "GSU-219"
    # The lettered parts belong to the same base group.
    assert by_id["GSU-219A"].air_wall_group == "GSU-219"
    assert by_id["GSU-219B"].air_wall_group == "GSU-219"
    # A normal room is not in any air-wall group.
    assert by_id["GSU-228"].air_wall_group is None


# --------------------------------------------------------------------------- #
# Dining hours parsing + unknown flag
# --------------------------------------------------------------------------- #
def test_dining_hours_parsed_and_unknown_flagged():
    dining, prov = loaders.load_dining()
    by_id = {d.dining_id: d for d in dining}
    assert by_id["DIN-WTW"].hours["mon_thu"] == ("08:00", "22:00")
    assert by_id["DIN-WTW"].hours_unknown is False
    # GSU food court has blank hours -> unknown + "check hours".
    assert by_id["DIN-GSU"].hours_unknown is True
    assert "check hours" in by_id["DIN-GSU"].flags
    assert all(p.label == Label.MEASURED.value for p in prov)


def test_parse_hours_edge_cases():
    assert loaders.parse_hours("08:00-22:00") == ("08:00", "22:00")
    assert loaders.parse_hours("") is None
    assert loaders.parse_hours(None) is None
    assert loaders.parse_hours("all day") is None


# --------------------------------------------------------------------------- #
# MBTA service-alert parsing -> structured PlannedDisruption
# --------------------------------------------------------------------------- #
def test_service_alert_parsed_green_line_closure():
    stops, prov = loaders.load_mbta_stops()
    by_id = {s.stop_id: s for s in stops}
    kenmore = by_id["place-kencl"]
    d = kenmore.disruption
    assert d is not None
    assert d.start_date == date(2026, 10, 31)
    assert d.end_date == date(2026, 11, 1)
    assert "Green Line" in d.lines
    assert d.shuttle_note == "Route 57 shuttle"
    assert d.fare_free is True

    # Overlap logic: the acceptance Brief B dates overlap; Brief A does not.
    assert d.overlaps(date(2026, 10, 31), date(2026, 11, 1)) is True
    assert d.overlaps(date(2026, 10, 24), date(2026, 10, 25)) is False

    # walk_min is recorded ASSUMED, stop itself MEASURED.
    labels = {p.label for p in prov}
    assert Label.MEASURED.value in labels
    assert Label.ASSUMED.value in labels


def test_stop_accessibility_fields_present():
    stops, _ = loaders.load_mbta_stops()
    by_id = {s.stop_id: s for s in stops}
    # Blandford Street is not accessible.
    assert by_id["place-bland"].wheelchair_accessible.lower() == "no"


# --------------------------------------------------------------------------- #
# Parking is MEASURED (real file present)
# --------------------------------------------------------------------------- #
def test_parking_is_measured_when_real_file_present():
    rows, label, prov = loaders.load_parking()
    assert rows, "expected real parking rows"
    assert label == Label.MEASURED.value
    assert all(p.label == Label.MEASURED.value for p in prov)


# --------------------------------------------------------------------------- #
# Full build: rooms union, every row labelled, blank caps still NULL in DuckDB
# --------------------------------------------------------------------------- #
def test_build_in_memory_counts_and_tables():
    import duckdb  # noqa: F401  (ensures dependency present)

    result = build_db.build(db_path=":memory:", write_reference=False)
    # :memory: build is per-connection, so we re-run against a temp file to query.


def test_build_to_tempfile_rooms_all_labelled_and_null_caps(tmp_path):
    db = tmp_path / "test.duckdb"
    result = build_db.build(db_path=db, write_reference=False)
    assert result.counts["rooms"] > 0
    assert result.counts["event_spaces"] > 0
    assert result.counts["parking"] > 0

    import duckdb

    con = duckdb.connect(str(db))
    try:
        # Every rooms row carries a provenance label from the allowed set.
        labels = [r[0] for r in con.execute("SELECT label FROM rooms").fetchall()]
        assert labels, "rooms table is empty"
        assert all(lbl in ALLOWED_LABELS for lbl in labels)
        assert all(lbl is not None and lbl != "" for lbl in labels)

        # Blank layout capacities are NULL, never 0.
        zero_caps = con.execute(
            "SELECT COUNT(*) FROM rooms WHERE cap_theatre_lecture = 0 "
            "OR cap_classroom = 0 OR cap_banquet_round = 0 OR cap_buffet = 0 "
            "OR cap_reception = 0 OR cap_u_shape = 0 OR cap_boardroom = 0 "
            "OR cap_fixed_seats = 0"
        ).fetchone()[0]
        assert zero_caps == 0

        # GSU-219A: real theatre/classroom columns, but a NULL reception column.
        row = con.execute(
            "SELECT cap_theatre_lecture, cap_classroom, cap_reception "
            "FROM rooms WHERE room_id = 'GSU-219A'"
        ).fetchone()
        assert row == (400, 275, None)

        # The union includes a PLACEHOLDER room for a building with no event_spaces
        # (CDS rooms come from the placeholder set).
        ph = con.execute(
            "SELECT COUNT(*) FROM rooms WHERE label = 'PLACEHOLDER'"
        ).fetchone()[0]
        assert ph > 0

        # MEASURED rooms exist too (real event_spaces).
        measured = con.execute(
            "SELECT COUNT(*) FROM rooms WHERE label = 'MEASURED'"
        ).fetchone()[0]
        assert measured > 0
    finally:
        con.close()


def test_buildings_ref_covers_codes_and_labels(tmp_path):
    db = tmp_path / "t.duckdb"
    build_db.build(db_path=db, write_reference=False)
    import duckdb

    con = duckdb.connect(str(db))
    try:
        codes = {r[0] for r in con.execute("SELECT building_code FROM buildings").fetchall()}
        # Codes from event_spaces, dining, and placeholder buildings are all present.
        for code in ("GSU", "PHO", "CDS", "YAW", "RES-WTW", "RES-RICH", "FCC"):
            assert code in codes, f"missing building_code {code}"
        labels = {r[0] for r in con.execute("SELECT label FROM buildings").fetchall()}
        assert labels <= ALLOWED_LABELS
    finally:
        con.close()
