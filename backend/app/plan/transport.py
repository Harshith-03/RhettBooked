"""
transport.py

Getting-there plan (P0, task 16) using COMMITTED data only.

Produces:
  - nearest MBTA stops with walk minutes (the dataset's walk_min_ASSUMED) and
    accessibility flags (wheelchair_accessible + accessibility_notes),
  - active/planned disruptions parsed from service_alert, with the Route 57
    shuttle note surfaced when present,
  - parking options with weekend/overnight rate hints from the real parking table.

Live MBTA V3 alerts, Bluebikes GBFS, OSM parking, and the crash-density KDE are
P1 hooks (``_live_alerts_hook`` / ``_gbfs_hook``) that return nothing in P0.

Provenance: stops/bus/parking MEASURED (walk_min ASSUMED); disruptions MEASURED
(parsed from the committed service_alert text).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ..data import loaders
from ..provenance import Label, ProvenanceRow

# How many nearest stops to surface.
NEAREST_N = 6


@dataclass
class StopInfo:
    stop_id: str
    name: str
    lines: list[str]
    walk_min: int | None
    accessible: bool
    accessibility_note: str
    disrupted: bool


@dataclass
class PlannedDisruptionInfo:
    label: str
    lines: list[str]
    start_date: str | None
    end_date: str | None
    shuttle_note: str | None
    fare_free: bool
    overlaps_event: bool


@dataclass
class ParkingInfo:
    lot_id: str
    name: str
    type: str
    public_or_visitor: str
    notes: str


@dataclass
class TransportPlan:
    stops: list[StopInfo]
    bus_routes: list[dict]
    planned_disruptions: list[PlannedDisruptionInfo]
    parking: list[ParkingInfo]
    accessibility_flags: list[str]
    shuttle_note: str | None
    provenance: list[ProvenanceRow] = field(default_factory=list)


def _truthy_access(value: str) -> bool:
    return str(value).strip().lower() in ("yes", "true", "1", "accessible")


def _live_alerts_hook():
    """P1 hook: live MBTA V3 alerts. Empty in P0 (committed data only)."""
    return []


def _gbfs_hook():
    """P1 hook: Bluebikes GBFS docks. Empty in P0."""
    return []


def plan(brief, db_path=None) -> TransportPlan:
    stops_raw, stop_prov = loaders.load_mbta_stops()
    bus_rows, bus_prov = loaders.load_bus_routes()
    parking_rows, parking_label, parking_prov = loaders.load_parking()

    event_start = _parse_date(getattr(brief, "start", None))
    event_end = _parse_date(getattr(brief, "end", None))

    # Build stop list sorted by walk_min (None sorts last).
    stops: list[StopInfo] = []
    for s in stops_raw:
        stops.append(
            StopInfo(
                stop_id=s.stop_id,
                name=s.name,
                lines=s.lines,
                walk_min=s.walk_min,
                accessible=_truthy_access(s.wheelchair_accessible),
                accessibility_note=s.accessibility_notes,
                disrupted=s.disruption is not None,
            )
        )
    stops.sort(key=lambda x: (x.walk_min is None, x.walk_min if x.walk_min is not None else 9999))
    nearest = stops[:NEAREST_N]

    # Accessibility flags: call out inaccessible nearest stops.
    accessibility_flags: list[str] = []
    for s in nearest:
        if not s.accessible:
            note = f" ({s.accessibility_note})" if s.accessibility_note else ""
            accessibility_flags.append(f"{s.name} is not step-free{note}")

    # Planned disruptions (unique) + whether they overlap the event.
    seen: dict[str, PlannedDisruptionInfo] = {}
    shuttle_note = None
    for s in stops_raw:
        d = s.disruption
        if not d:
            continue
        key = f"{d.start_date}|{d.end_date}|{','.join(d.lines)}"
        if key in seen:
            continue
        overlaps = bool(event_start and event_end and d.overlaps(event_start, event_end))
        bits = []
        if d.lines:
            bits.append(", ".join(d.lines) + " closure")
        if d.shuttle_note:
            bits.append(d.shuttle_note + (" (fare-free)" if d.fare_free else ""))
            shuttle_note = d.shuttle_note + (" (fare-free)" if d.fare_free else "")
        seen[key] = PlannedDisruptionInfo(
            label="; ".join(bits) or "planned MBTA disruption",
            lines=d.lines,
            start_date=d.start_date.isoformat() if d.start_date else None,
            end_date=d.end_date.isoformat() if d.end_date else None,
            shuttle_note=d.shuttle_note,
            fare_free=d.fare_free,
            overlaps_event=overlaps,
        )

    parking = [
        ParkingInfo(
            lot_id=(r.get("lot_id") or r.get("parking_id") or "").strip(),
            name=(r.get("name") or "").strip(),
            type=(r.get("type") or "").strip(),
            public_or_visitor=(r.get("public_or_visitor") or "").strip(),
            notes=(r.get("notes") or "").strip(),
        )
        for r in parking_rows
    ]
    # Prefer public/visitor lots first for a short list.
    parking.sort(key=lambda p: p.public_or_visitor.lower() != "yes")

    prov: list[ProvenanceRow] = list(stop_prov) + list(bus_prov) + list(parking_prov)

    return TransportPlan(
        stops=nearest,
        bus_routes=bus_rows[:8],
        planned_disruptions=list(seen.values()),
        parking=parking[:6],
        accessibility_flags=accessibility_flags,
        shuttle_note=shuttle_note,
        provenance=prov,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
