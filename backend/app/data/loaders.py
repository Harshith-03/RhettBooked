"""
loaders.py

Load the REAL Boston University datasets from ``data/raw/bu/`` (MEASURED) and the
PLACEHOLDER datasets from ``data/placeholder/`` (PLACEHOLDER), applying the
"real data wins" policy:

  - real event spaces, dining, MBTA stops, bus routes and parking load as MEASURED
    (``walk_min`` on stops stays ASSUMED),
  - placeholder rooms are used only for buildings the real event-spaces file does
    not cover, and stay PLACEHOLDER,
  - a reference ``buildings`` table (``data/reference/bu_buildings_ref.csv``) is
    built to back the map and walking distances.

Every loader reads CSVs with ``comment="#"`` so a leading comment row is skipped,
and returns the rows plus a list of :class:`ProvenanceRow`.

Parsing rules implemented here (from the spec):
  - blank layout-capacity column  -> ``None`` (NULL), never 0,
  - blank ``max_capacity``         -> max of the per-layout capacities,
  - air-wall groups parsed from the notes (e.g. GSU-219 -> 219A + 219B),
  - dining hours like "08:00-22:00" parsed; blank -> unknown + "check hours",
  - ``service_alert`` text parsed into a structured PlannedDisruption.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from ..config import PLACEHOLDER_DIR, RAW_BU_DIR, REFERENCE_DIR
from ..provenance import Label, ProvenanceRow

# --------------------------------------------------------------------------- #
# Layout-capacity columns (nullable) in the real event_spaces file.
# --------------------------------------------------------------------------- #
LAYOUT_COLS = [
    "cap_theatre_lecture",
    "cap_classroom",
    "cap_banquet_round",
    "cap_buffet",
    "cap_reception",
    "cap_u_shape",
    "cap_boardroom",
    "cap_fixed_seats",
]


# --------------------------------------------------------------------------- #
# CSV reading with comment="#" support (stdlib only).
# --------------------------------------------------------------------------- #
def read_csv_rows(path: Path, comment: str = "#") -> list[dict[str, str]]:
    """Read a CSV into dict rows, skipping blank lines and lines starting with
    ``comment`` (after optional leading whitespace)."""
    text = path.read_text(encoding="utf-8")
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        if comment and stripped.startswith(comment):
            continue
        kept.append(line)
    if not kept:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(kept)))
    return [dict(row) for row in reader]


def _to_int(value: str | None) -> int | None:
    """Parse an int, returning None for blank/missing (NEVER 0)."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


# --------------------------------------------------------------------------- #
# Raw-file resolution (download names can be messy, e.g. "bu_event_spaces (2).csv")
# --------------------------------------------------------------------------- #
def resolve_raw_file(canonical: str, raw_dir: Path = RAW_BU_DIR) -> Path | None:
    """Return the canonical file if present, else the newest file whose stem
    starts with the canonical stem (handles "bu_event_spaces (2).csv")."""
    exact = raw_dir / canonical
    if exact.exists():
        return exact
    stem = Path(canonical).stem
    candidates = [
        p for p in raw_dir.glob(f"{stem}*{Path(canonical).suffix}")
        if p.is_file()
    ] if raw_dir.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# --------------------------------------------------------------------------- #
# Event spaces -> table `event_spaces` (MEASURED)
# --------------------------------------------------------------------------- #
@dataclass
class EventSpace:
    space_id: str
    building_code: str
    name: str
    room: str
    floor: str
    sqft: int | None
    max_capacity: int | None
    layout_caps: dict[str, int | None]
    notes: str
    source_url: str
    source_note: str
    air_wall_group: str | None = None


def parse_air_wall_group(space_id: str, name: str, notes: str) -> str | None:
    """Return a group id for an air-wall room, else None.

    A room participates in an air-wall relationship if it is a whole room that
    splits into lettered parts (e.g. GSU-219 -> 219A/219B), OR it is itself a
    lettered part (GSU-219A). The group id is the whole-room space_id (GSU-219).
    """
    text = (notes or "").lower()
    # Lettered part: trailing capital letter(s) on the space_id (e.g. GSU-219A).
    m = re.match(r"^(?P<base>.*?\d+)(?P<letter>[A-Z])$", space_id)
    if m and ("air wall" in text or "splits into" in text or True):
        # A lettered sibling is only meaningful if a base room could exist.
        base = m.group("base")
        # Only treat as part when the id clearly ends in a letter after digits.
        if re.search(r"\d[A-Z]$", space_id):
            return base
    # Whole room that announces a split in its notes.
    if "air wall" in text or "splits into" in text:
        return space_id
    return None


def load_event_spaces(path: Path | None = None) -> tuple[list[EventSpace], list[ProvenanceRow]]:
    path = path or resolve_raw_file("bu_event_spaces.csv")
    if path is None:
        return [], []
    rows = read_csv_rows(path)
    spaces: list[EventSpace] = []
    prov: list[ProvenanceRow] = []
    for r in rows:
        layout_caps = {col: _to_int(r.get(col)) for col in LAYOUT_COLS}
        max_cap = _to_int(r.get("max_capacity"))
        if max_cap is None:
            present = [v for v in layout_caps.values() if v is not None]
            max_cap = max(present) if present else None
        space_id = (r.get("space_id") or "").strip()
        building_code = (r.get("building_code") or "").strip()
        notes = (r.get("notes") or "").strip()
        space = EventSpace(
            space_id=space_id,
            building_code=building_code,
            name=(r.get("name") or "").strip(),
            room=(r.get("room") or "").strip(),
            floor=(r.get("floor") or "").strip(),
            sqft=_to_int(r.get("sqft")),
            max_capacity=max_cap,
            layout_caps=layout_caps,
            notes=notes,
            source_url=(r.get("source_url") or "").strip(),
            source_note=(r.get("source_note") or "").strip(),
            air_wall_group=parse_air_wall_group(space_id, r.get("name") or "", notes),
        )
        spaces.append(space)
        src = space.source_url or space.source_note or "bu_event_spaces.csv"
        prov.append(
            ProvenanceRow(
                output_key=f"event_spaces.{space_id}",
                label=Label.MEASURED,
                source=src,
                value_summary=f"max_capacity={max_cap}",
            )
        )
    return spaces, prov


# --------------------------------------------------------------------------- #
# Dining -> table `dining` (MEASURED); parse hours, flag unknowns.
# --------------------------------------------------------------------------- #
@dataclass
class DiningLocation:
    dining_id: str
    name: str
    building_code: str
    address: str
    type: str
    hours: dict[str, tuple[str, str] | None]   # key -> (open, close) or None
    hours_unknown: bool
    flags: list[str]
    notes: str


_HOURS_RE = re.compile(r"^\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*$")


def parse_hours(value: str | None) -> tuple[str, str] | None:
    """Parse "08:00-22:00" -> ("08:00", "22:00"); blank/unparseable -> None."""
    if _blank(value):
        return None
    m = _HOURS_RE.match(str(value))
    if not m:
        return None
    return (m.group(1), m.group(2))


def load_dining(path: Path | None = None) -> tuple[list[DiningLocation], list[ProvenanceRow]]:
    path = path or resolve_raw_file("bu_dining_locations.csv")
    if path is None:
        return [], []
    rows = read_csv_rows(path)
    out: list[DiningLocation] = []
    prov: list[ProvenanceRow] = []
    for r in rows:
        hours = {
            "mon_thu": parse_hours(r.get("hours_mon_thu")),
            "fri": parse_hours(r.get("hours_fri")),
            "sat_sun": parse_hours(r.get("hours_sat_sun")),
        }
        unknown = all(v is None for v in hours.values())
        flags = ["check hours"] if unknown else []
        dining_id = (r.get("dining_id") or "").strip()
        out.append(
            DiningLocation(
                dining_id=dining_id,
                name=(r.get("name") or "").strip(),
                building_code=(r.get("building_code") or "").strip(),
                address=(r.get("address") or "").strip(),
                type=(r.get("type") or "").strip(),
                hours=hours,
                hours_unknown=unknown,
                flags=flags,
                notes=(r.get("notes") or "").strip(),
            )
        )
        prov.append(
            ProvenanceRow(
                output_key=f"dining.{dining_id}",
                label=Label.MEASURED,
                source=(r.get("hours_source") or "bu_dining_locations.csv").strip(),
                value_summary="hours unknown" if unknown else "hours parsed",
            )
        )
    return out, prov


# --------------------------------------------------------------------------- #
# MBTA stops -> table `mbta_stops` (MEASURED; walk_min ASSUMED). Parse alerts.
# --------------------------------------------------------------------------- #
@dataclass
class PlannedDisruption:
    raw: str
    lines: list[str] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    shuttle_note: str | None = None
    fare_free: bool = False

    def overlaps(self, event_start: date, event_end: date) -> bool:
        if self.start_date is None or self.end_date is None:
            return False
        return not (event_end < self.start_date or event_start > self.end_date)


@dataclass
class MbtaStop:
    stop_id: str
    name: str
    mode: str
    lines: list[str]
    lat: float | None
    lon: float | None
    address: str
    wheelchair_accessible: str
    accessibility_notes: str
    walk_min: int | None       # ASSUMED
    disruption: PlannedDisruption | None
    source: str


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# e.g. "Oct 31-Nov 1 2026" or "Oct 31 2026"
_DATE_RANGE_RE = re.compile(
    r"([A-Za-z]{3,9})\s+(\d{1,2})"
    r"(?:\s*-\s*(?:([A-Za-z]{3,9})\s+)?(\d{1,2}))?"
    r"[, ]+\s*(\d{4})"
)
_LINE_RE = re.compile(r"\b(Green|Red|Orange|Blue|Silver)\s*Line\b", re.IGNORECASE)
_ROUTE_RE = re.compile(r"\bRoute\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)


def _month_num(name: str) -> int | None:
    return _MONTHS.get(name[:3].lower())


def parse_service_alert(text: str | None) -> PlannedDisruption | None:
    """Parse a free-text service alert into a structured PlannedDisruption."""
    if _blank(text):
        return None
    raw = str(text).strip()
    disruption = PlannedDisruption(raw=raw)

    m = _DATE_RANGE_RE.search(raw)
    if m:
        start_mon_name, start_day, end_mon_name, end_day, year = m.groups()
        yr = int(year)
        start_mon = _month_num(start_mon_name)
        if start_mon:
            disruption.start_date = date(yr, start_mon, int(start_day))
            end_mon = _month_num(end_mon_name) if end_mon_name else start_mon
            end_d = int(end_day) if end_day else int(start_day)
            if end_mon:
                disruption.end_date = date(yr, end_mon, end_d)

    disruption.lines = sorted({
        f"{m.group(1).title()} Line" for m in _LINE_RE.finditer(raw)
    })

    route = _ROUTE_RE.search(raw)
    if route:
        disruption.shuttle_note = f"Route {route.group(1)} shuttle"
    elif "shuttle" in raw.lower():
        disruption.shuttle_note = "shuttle buses"

    disruption.fare_free = "fare-free" in raw.lower() or "fare free" in raw.lower()
    return disruption


def _to_float(value: str | None) -> float | None:
    if _blank(value):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def load_mbta_stops(path: Path | None = None) -> tuple[list[MbtaStop], list[ProvenanceRow]]:
    path = path or resolve_raw_file("mbta_stations_bu.csv")
    if path is None:
        return [], []
    rows = read_csv_rows(path)
    out: list[MbtaStop] = []
    prov: list[ProvenanceRow] = []
    for r in rows:
        stop_id = (r.get("stop_id") or "").strip()
        lines = [s.strip() for s in (r.get("lines") or "").split(",") if s.strip()]
        disruption = parse_service_alert(r.get("service_alert"))
        walk_min = _to_int(r.get("walk_min_ASSUMED"))
        out.append(
            MbtaStop(
                stop_id=stop_id,
                name=(r.get("name") or "").strip(),
                mode=(r.get("mode") or "").strip(),
                lines=lines,
                lat=_to_float(r.get("lat")),
                lon=_to_float(r.get("lon")),
                address=(r.get("address") or "").strip(),
                wheelchair_accessible=(r.get("wheelchair_accessible") or "").strip(),
                accessibility_notes=(r.get("accessibility_notes") or "").strip(),
                walk_min=walk_min,
                disruption=disruption,
                source=(r.get("source") or "mbta_stations_bu.csv").strip(),
            )
        )
        prov.append(
            ProvenanceRow(
                output_key=f"mbta_stops.{stop_id}",
                label=Label.MEASURED,
                source=(r.get("source") or "mbta_stations_bu.csv").strip(),
                value_summary=f"lines={','.join(lines)}",
            )
        )
        # walk_min is ASSUMED, recorded separately.
        if walk_min is not None:
            prov.append(
                ProvenanceRow(
                    output_key=f"mbta_stops.{stop_id}.walk_min",
                    label=Label.ASSUMED,
                    source="walk_min_ASSUMED column (estimated walking time)",
                    value_summary=f"{walk_min} min",
                )
            )
    return out, prov


# --------------------------------------------------------------------------- #
# Bus routes -> table `bus_routes` (MEASURED)
# --------------------------------------------------------------------------- #
def load_bus_routes(path: Path | None = None) -> tuple[list[dict[str, Any]], list[ProvenanceRow]]:
    path = path or resolve_raw_file("mbta_bus_routes_bu.csv")
    if path is None:
        return [], []
    rows = read_csv_rows(path)
    prov: list[ProvenanceRow] = []
    for r in rows:
        route = (r.get("route") or "").strip()
        prov.append(
            ProvenanceRow(
                output_key=f"bus_routes.{route}",
                label=Label.MEASURED,
                source=(r.get("source_url") or "mbta_bus_routes_bu.csv").strip(),
                value_summary=(r.get("name") or "").strip()[:60],
            )
        )
    return rows, prov


# --------------------------------------------------------------------------- #
# Parking -> table `parking` (MEASURED when real file present, else PLACEHOLDER)
# --------------------------------------------------------------------------- #
def load_parking() -> tuple[list[dict[str, Any]], str, list[ProvenanceRow]]:
    """Return (rows, label, provenance). Real file wins; placeholder is fallback."""
    real = resolve_raw_file("bu_parking.csv")
    prov: list[ProvenanceRow] = []
    if real is not None:
        rows = read_csv_rows(real)
        label = Label.MEASURED
        source_default = "bu_parking.csv (real)"
    else:
        placeholder = PLACEHOLDER_DIR / "bu_parking.csv"
        rows = read_csv_rows(placeholder) if placeholder.exists() else []
        label = Label.PLACEHOLDER
        source_default = "data/placeholder/bu_parking.csv"
    for r in rows:
        pid = (r.get("lot_id") or r.get("parking_id") or "").strip()
        prov.append(
            ProvenanceRow(
                output_key=f"parking.{pid}",
                label=label,
                source=(r.get("source_url") or source_default).strip(),
                value_summary=(r.get("name") or "").strip()[:60],
            )
        )
    return rows, label.value, prov


# --------------------------------------------------------------------------- #
# Placeholder buildings + rooms (for the union + lat/lon matching)
# --------------------------------------------------------------------------- #
def load_placeholder_buildings() -> list[dict[str, str]]:
    path = PLACEHOLDER_DIR / "bu_buildings.csv"
    return read_csv_rows(path) if path.exists() else []


def load_placeholder_rooms() -> list[dict[str, str]]:
    path = PLACEHOLDER_DIR / "bu_rooms.csv"
    return read_csv_rows(path) if path.exists() else []


__all__ = [
    "LAYOUT_COLS",
    "read_csv_rows",
    "resolve_raw_file",
    "EventSpace",
    "load_event_spaces",
    "parse_air_wall_group",
    "DiningLocation",
    "parse_hours",
    "load_dining",
    "PlannedDisruption",
    "MbtaStop",
    "parse_service_alert",
    "load_mbta_stops",
    "load_bus_routes",
    "load_parking",
    "load_placeholder_buildings",
    "load_placeholder_rooms",
    "REFERENCE_DIR",
]
