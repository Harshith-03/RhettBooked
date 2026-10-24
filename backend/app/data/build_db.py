"""
build_db.py

Assemble the EventTwin DuckDB from the real BU datasets (MEASURED) plus
placeholder fills (PLACEHOLDER / ASSUMED), following "real data wins":

  1. Load real event_spaces, dining, mbta_stops, bus_routes, parking.
  2. Build data/reference/bu_buildings_ref.csv keyed by building_code, covering
     every code used by event_spaces, dining, and the placeholder buildings.
     lat/lon come from placeholder bu_buildings.csv where the name matches
     (keeping that label), else approximated and labelled ASSUMED;
     overnight_allowed/accessible_entrance are ASSUMED unless a note indicates a
     restriction.
  3. Build the `rooms` union: event_spaces (MEASURED) UNION placeholder rooms for
     buildings NOT present in event_spaces (PLACEHOLDER). Missing room fields are
     filled and labelled ASSUMED:
        power_circuits = ceil(sqft / 400)
        access_points  = ceil(max_capacity / 40)
        rate_per_hour  = from rate_cards.yaml by room size
        ventilation_cfm = 7.5 * max_capacity
  4. Load event_spaces, dining, mbta_stops, bus_routes, parking, buildings, rooms,
     rate_cards into data/processed/eventtwin.duckdb and record a provenance label
     for every row.

Run:
    python -m backend.app.data.build_db
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import (
    DUCKDB_PATH,
    PLACEHOLDER_DIR,
    REFERENCE_DIR,
)
from ..provenance import Label, ProvenanceRow, ProvenanceStore
from . import loaders

# Map the REAL building_code -> the placeholder building NAME used for lat/lon.
# Only codes with a confident placeholder match are listed; others are ASSUMED.
CODE_TO_PLACEHOLDER_NAME = {
    "GSU": "George Sherman Union",
    "PHO": "Photonics Center",
    "CAS": "College of Arts & Sciences",
    "AGG": "Agganis Arena",
    "SCI": "Metcalf Science Center",
    "CDS": "Center for Computing & Data Sciences",
}

# Give placeholder buildings (keyed by BLD id) a stable building_code so their
# rooms can join the union. CDS is the important one (it has the real event rooms
# in the placeholder set but no entry in the real event_spaces file).
PLACEHOLDER_BLD_TO_CODE = {
    "BLD01": "CDS",
    "BLD02": "GSU",
    "BLD03": "PHO",
    "BLD04": "CAS",
    "BLD05": "QST",
    "BLD06": "SCI",
    "BLD07": "AGG",
    "BLD08": "FRC",
    "BLD09": "KHC",
    "BLD10": "LAW",
    "BLD11": "MUG",
    "BLD12": "EPIC",
    "BLD13": "RKC",
    "BLD14": "BTH",
    "BLD15": "SLB",
}

# Approximate addresses for codes with no placeholder match (ASSUMED coordinates).
# lat/lon left as None here means "approximate later / unknown"; we still emit a row.
CODE_APPROX_ADDRESS = {
    "OSW": "One Silber Way, Boston MA",
    "CASTLE": "225 Bay State Rd, Boston MA",
    "RES-SV1": "10 Buick Street, Boston MA",
    "RES-SV2": "33 Harry Agganis Way, Boston MA",
    "HAW": "43 Hawes Street, Brookline MA",
    "MCH": "735 Commonwealth Ave, Boston MA",
    "COM": "640 Commonwealth Ave, Boston MA",
    "RES-WTW": "700 Commonwealth Ave, Boston MA",
    "YAW": "100 Bay State Rd, Boston MA",
    "RES-RICH": "Babcock Street, Boston MA",
    "FCC": "150 The Riverway, Boston MA",
}


# --------------------------------------------------------------------------- #
# rate_cards.yaml -> rate_per_hour by room size
# --------------------------------------------------------------------------- #
def _load_rate_cards() -> dict[str, Any]:
    path = PLACEHOLDER_DIR / "rate_cards.yaml"
    if not path.exists():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rate_per_hour_by_size(max_capacity: int | None) -> int:
    """ASSUMED hourly room rate by size band (derived from rate_cards tiers)."""
    cap = max_capacity or 0
    if cap >= 500:
        return 400
    if cap >= 200:
        return 300
    if cap >= 75:
        return 150
    if cap >= 30:
        return 75
    return 50


# --------------------------------------------------------------------------- #
# Reference buildings
# --------------------------------------------------------------------------- #
BUILDINGS_REF_FIELDS = [
    "building_code", "name", "address", "lat", "lon",
    "overnight_allowed", "accessible_entrance", "label",
]


@dataclass
class BuildingRef:
    building_code: str
    name: str
    address: str
    lat: float | None
    lon: float | None
    overnight_allowed: str      # "true"/"false"/"unknown"
    accessible_entrance: str    # "true"/"false"/"restricted"
    label: str                  # provenance label for lat/lon


def build_buildings_ref(
    event_spaces: list[loaders.EventSpace],
    dining: list[loaders.DiningLocation],
    placeholder_buildings: list[dict[str, str]],
) -> tuple[list[BuildingRef], list[ProvenanceRow]]:
    # name -> (lat, lon) from placeholder buildings for matching.
    name_to_coords = {
        (b.get("name") or "").strip(): (
            _f(b.get("lat")), _f(b.get("lon"))
        )
        for b in placeholder_buildings
    }

    # Gather every building_code that appears anywhere, plus placeholder codes.
    codes: dict[str, dict[str, Any]] = {}

    def note_for(code: str) -> str:
        for s in event_spaces:
            if s.building_code == code and s.notes:
                return s.notes
        return ""

    for s in event_spaces:
        if s.building_code:
            codes.setdefault(s.building_code, {})["name"] = codes.get(
                s.building_code, {}
            ).get("name") or s.name
    for d in dining:
        if d.building_code:
            codes.setdefault(d.building_code, {}).setdefault("name", d.name)
            codes[d.building_code].setdefault("address", d.address)
    for b in placeholder_buildings:
        bld = (b.get("building_id") or "").strip()
        code = PLACEHOLDER_BLD_TO_CODE.get(bld)
        if code:
            codes.setdefault(code, {}).setdefault("name", (b.get("name") or "").strip())
            codes[code].setdefault("address", (b.get("address") or "").strip())

    refs: list[BuildingRef] = []
    prov: list[ProvenanceRow] = []
    for code in sorted(codes):
        info = codes[code]
        # Prefer a known building name over the first event-space's name, which
        # is a room name (e.g. GSU's first space is "Metcalf Hall Grand Ballroom").
        name = CODE_TO_PLACEHOLDER_NAME.get(code) or info.get("name") or code

        # lat/lon: match placeholder by name; else by the code->name map; else approx.
        lat = lon = None
        label = Label.ASSUMED
        match_name = None
        if name in name_to_coords:
            match_name = name
        elif code in CODE_TO_PLACEHOLDER_NAME and CODE_TO_PLACEHOLDER_NAME[code] in name_to_coords:
            match_name = CODE_TO_PLACEHOLDER_NAME[code]
        if match_name:
            lat, lon = name_to_coords[match_name]
            # Placeholder coordinates keep the PLACEHOLDER label.
            label = Label.PLACEHOLDER

        address = info.get("address") or CODE_APPROX_ADDRESS.get(code, "")

        # overnight / accessibility are ASSUMED unless a note restricts them.
        note = note_for(code).lower()
        overnight = "unknown"
        accessible = "true"
        if "elevators unlock" in note or "1 hr before" in note:
            accessible = "restricted"  # time-gated access restriction

        refs.append(
            BuildingRef(
                building_code=code,
                name=name,
                address=address,
                lat=lat,
                lon=lon,
                overnight_allowed=overnight,
                accessible_entrance=accessible,
                label=label.value,
            )
        )
        prov.append(
            ProvenanceRow(
                output_key=f"buildings.{code}",
                label=label,
                source=(
                    "placeholder bu_buildings.csv (name match)"
                    if match_name else "approximated from address"
                ),
                value_summary=f"lat={lat},lon={lon}",
            )
        )
    return refs, prov


def write_buildings_ref_csv(refs: list[BuildingRef]) -> Path:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = REFERENCE_DIR / "bu_buildings_ref.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BUILDINGS_REF_FIELDS)
        w.writeheader()
        for r in refs:
            w.writerow({
                "building_code": r.building_code,
                "name": r.name,
                "address": r.address,
                "lat": "" if r.lat is None else r.lat,
                "lon": "" if r.lon is None else r.lon,
                "overnight_allowed": r.overnight_allowed,
                "accessible_entrance": r.accessible_entrance,
                "label": r.label,
            })
    return out


# --------------------------------------------------------------------------- #
# Rooms union
# --------------------------------------------------------------------------- #
ROOM_FIELDS = [
    "room_id", "building_code", "name", "room", "floor", "sqft",
    "max_capacity",
    "cap_theatre_lecture", "cap_classroom", "cap_banquet_round", "cap_buffet",
    "cap_reception", "cap_u_shape", "cap_boardroom", "cap_fixed_seats",
    "power_circuits", "access_points", "rate_per_hour", "ventilation_cfm",
    "air_wall_group", "notes", "label",
]


def _ceil_div(numerator: float, denom: float) -> int:
    return int(math.ceil(numerator / denom)) if denom else 0


def build_rooms(
    event_spaces: list[loaders.EventSpace],
    placeholder_rooms: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[ProvenanceRow]]:
    rows: list[dict[str, Any]] = []
    prov: list[ProvenanceRow] = []

    covered_codes = {s.building_code for s in event_spaces if s.building_code}

    # 1. Real event_spaces -> MEASURED rooms, with ASSUMED fills for missing fields.
    for s in event_spaces:
        power = _ceil_div(s.sqft, 400) if s.sqft else None
        aps = _ceil_div(s.max_capacity, 40) if s.max_capacity else None
        rate = rate_per_hour_by_size(s.max_capacity)
        vent = round(7.5 * s.max_capacity) if s.max_capacity else None
        row = {
            "room_id": s.space_id,
            "building_code": s.building_code,
            "name": s.name,
            "room": s.room,
            "floor": s.floor,
            "sqft": s.sqft,
            "max_capacity": s.max_capacity,
            **{col: s.layout_caps.get(col) for col in loaders.LAYOUT_COLS},
            "power_circuits": power,
            "access_points": aps,
            "rate_per_hour": rate,
            "ventilation_cfm": vent,
            "air_wall_group": s.air_wall_group,
            "notes": s.notes,
            "label": Label.MEASURED.value,
        }
        rows.append(row)
        prov.append(
            ProvenanceRow(
                output_key=f"rooms.{s.space_id}",
                label=Label.MEASURED,
                source=s.source_url or s.source_note or "bu_event_spaces.csv",
                value_summary=f"max_capacity={s.max_capacity}",
            )
        )
        # Derived fields are ASSUMED.
        for key, val in (("power_circuits", power), ("access_points", aps),
                         ("rate_per_hour", rate), ("ventilation_cfm", vent)):
            if val is not None:
                prov.append(
                    ProvenanceRow(
                        output_key=f"rooms.{s.space_id}.{key}",
                        label=Label.ASSUMED,
                        source="derived (sqft/capacity formula + rate_cards.yaml)",
                        value_summary=str(val),
                    )
                )

    # 2. Placeholder rooms for buildings NOT in event_spaces -> PLACEHOLDER rooms.
    for r in placeholder_rooms:
        bld = (r.get("building_id") or "").strip()
        code = PLACEHOLDER_BLD_TO_CODE.get(bld, bld)
        if code in covered_codes:
            continue  # real event_spaces wins for this building
        cap = loaders._to_int(r.get("capacity_seated"))
        rtype = (r.get("room_type") or "").strip()
        # Place the single capacity into the layout column matching room_type;
        # leave other layouts NULL.
        layout_caps = {col: None for col in loaders.LAYOUT_COLS}
        layout_map = {
            "lecture": "cap_theatre_lecture",
            "classroom": "cap_classroom",
            "ballroom": "cap_banquet_round",
            "seminar": "cap_u_shape",
            "lab": "cap_classroom",
            "atrium": "cap_reception",
            "lounge": "cap_reception",
        }
        target = layout_map.get(rtype)
        if target:
            layout_caps[target] = cap
        room_id = (r.get("room_id") or "").strip()
        row = {
            "room_id": room_id,
            "building_code": code,
            "name": (r.get("room_number") or "").strip(),
            "room": (r.get("room_number") or "").strip(),
            "floor": (r.get("floor") or "").strip(),
            "sqft": loaders._to_int(r.get("area_sqft")),
            "max_capacity": cap,
            **layout_caps,
            "power_circuits": loaders._to_int(r.get("power_circuits")),
            "access_points": loaders._to_int(r.get("access_points")),
            "rate_per_hour": loaders._to_int(r.get("rate_per_hour_usd")),
            "ventilation_cfm": loaders._to_int(r.get("ventilation_cfm")),
            "air_wall_group": None,
            "notes": "",
            "label": Label.PLACEHOLDER.value,
        }
        rows.append(row)
        prov.append(
            ProvenanceRow(
                output_key=f"rooms.{room_id}",
                label=Label.PLACEHOLDER,
                source="data/placeholder/bu_rooms.csv",
                value_summary=f"max_capacity={cap}",
            )
        )
    return rows, prov


def _f(value: str | None) -> float | None:
    return loaders._to_float(value)


# --------------------------------------------------------------------------- #
# DuckDB load
# --------------------------------------------------------------------------- #
@dataclass
class BuildResult:
    db_path: Path
    counts: dict[str, int]
    provenance_rows: int


def build(db_path: Path | str | None = None, write_reference: bool = True) -> BuildResult:
    db_target = ":memory:" if db_path == ":memory:" else Path(db_path or DUCKDB_PATH)

    event_spaces, prov_es = loaders.load_event_spaces()
    dining, prov_din = loaders.load_dining()
    stops, prov_stops = loaders.load_mbta_stops()
    bus_rows, prov_bus = loaders.load_bus_routes()
    parking_rows, parking_label, prov_park = loaders.load_parking()
    ph_buildings = loaders.load_placeholder_buildings()
    ph_rooms = loaders.load_placeholder_rooms()

    refs, prov_bref = build_buildings_ref(event_spaces, dining, ph_buildings)
    rooms, prov_rooms = build_rooms(event_spaces, ph_rooms)

    if write_reference:
        write_buildings_ref_csv(refs)

    import duckdb

    target = ":memory:" if db_target == ":memory:" else str(db_target)
    if db_target != ":memory:":
        Path(db_target).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(target)
    counts: dict[str, int] = {}
    try:
        # rooms table (the optimizer's input)
        con.execute(f"CREATE OR REPLACE TABLE rooms ({_rooms_ddl()})")
        if rooms:
            con.executemany(
                f"INSERT INTO rooms VALUES ({','.join(['?'] * len(ROOM_FIELDS))})",
                [[r.get(c) for c in ROOM_FIELDS] for r in rooms],
            )
        counts["rooms"] = len(rooms)

        # buildings reference
        con.execute(
            "CREATE OR REPLACE TABLE buildings ("
            "building_code VARCHAR, name VARCHAR, address VARCHAR, lat DOUBLE, "
            "lon DOUBLE, overnight_allowed VARCHAR, accessible_entrance VARCHAR, label VARCHAR)"
        )
        if refs:
            con.executemany(
                "INSERT INTO buildings VALUES (?,?,?,?,?,?,?,?)",
                [
                    [r.building_code, r.name, r.address, r.lat, r.lon,
                     r.overnight_allowed, r.accessible_entrance, r.label]
                    for r in refs
                ],
            )
        counts["buildings"] = len(refs)

        # Raw-ish tables loaded directly from the resolved CSVs for querying.
        counts["event_spaces"] = _load_raw_table(
            con, "event_spaces", loaders.resolve_raw_file("bu_event_spaces.csv")
        )
        counts["dining"] = _load_raw_table(
            con, "dining", loaders.resolve_raw_file("bu_dining_locations.csv")
        )
        counts["mbta_stops"] = _load_raw_table(
            con, "mbta_stops", loaders.resolve_raw_file("mbta_stations_bu.csv")
        )
        counts["bus_routes"] = _load_raw_table(
            con, "bus_routes", loaders.resolve_raw_file("mbta_bus_routes_bu.csv")
        )
        # parking: real file wins, else placeholder
        parking_file = loaders.resolve_raw_file("bu_parking.csv") or (
            PLACEHOLDER_DIR / "bu_parking.csv"
        )
        counts["parking"] = _load_raw_table(con, "parking", parking_file)

        # provenance table
        all_prov = (
            prov_es + prov_din + prov_stops + prov_bus + prov_park
            + prov_bref + prov_rooms
        )
        con.execute(
            "CREATE OR REPLACE TABLE provenance ("
            "output_key VARCHAR, label VARCHAR, source VARCHAR, "
            "value_summary VARCHAR, recorded_at TIMESTAMP)"
        )
        if all_prov:
            con.executemany(
                "INSERT INTO provenance VALUES (?,?,?,?,?)",
                [
                    [p.output_key, p.label, p.source, p.value_summary, p.recorded_at]
                    for p in all_prov
                ],
            )
    finally:
        con.close()

    return BuildResult(
        db_path=db_target if db_target == ":memory:" else Path(db_target),
        counts=counts,
        provenance_rows=len(
            prov_es + prov_din + prov_stops + prov_bus + prov_park + prov_bref + prov_rooms
        ),
    )


def _rooms_ddl() -> str:
    int_cols = {
        "sqft", "max_capacity", "power_circuits", "access_points",
        "rate_per_hour", "ventilation_cfm", *loaders.LAYOUT_COLS,
    }
    parts = []
    for c in ROOM_FIELDS:
        parts.append(f"{c} {'INTEGER' if c in int_cols else 'VARCHAR'}")
    return ", ".join(parts)


def _load_raw_table(con, name: str, path: Path | None) -> int:
    """Load a CSV into DuckDB using read_csv (comment='#'), returning row count."""
    if path is None or not Path(path).exists():
        con.execute(f"CREATE OR REPLACE TABLE {name} (dummy VARCHAR)")
        return 0
    con.execute(
        f"CREATE OR REPLACE TABLE {name} AS "
        f"SELECT * FROM read_csv(?, header=true, comment='#', all_varchar=true)",
        [str(path)],
    )
    return con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]


def main() -> None:
    result = build()
    print(f"Built DuckDB at {result.db_path}")
    for table, n in result.counts.items():
        print(f"  {table:14s} {n}")
    print(f"  provenance     {result.provenance_rows}")


if __name__ == "__main__":
    main()
