"""
venue_optimizer.py

Layout-aware CP-SAT room assignment (P0, task 5).

``optimize(brief, p90, blocks, rooms=None)`` assigns each schedule block to a
room, searching within a single building by default (or up to 2 adjacent
buildings), and returns the top-3 building options.

Key rules (from the spec / Requirement 3):
  - Each schedule block carries a LAYOUT. The room is sized against THAT layout's
    capacity column:
        hackathon work   -> classroom   (fallback banquet_round)
        ceremony/keynote -> theatre_lecture or fixed_seats
        meals            -> buffet or banquet_round
        networking       -> reception
    A room whose needed layout column is NULL cannot host that block.
  - Hard constraints: layout capacity >= p90 * 1.1; step_free when accessibility
    is needed; overnight_allowed when the event is overnight; AV when required.
  - Air-wall exclusivity: for an air-wall group (e.g. GSU-219 / GSU-219A /
    GSU-219B) the optimizer may book the whole room OR its parts, never both.
  - Objective: minimize room cost + inter-block walking distance + unused capacity.
  - If no feasible assignment exists, report which constraint could not be met.

Data notes (the real event_spaces file has no step_free/overnight/AV columns, so
these come from the building reference, with documented ASSUMED defaults):
  - accessibility: a building passes if accessible_entrance == "true"
    ("restricted" or "false" fails when accessibility is needed),
  - overnight: building overnight_allowed == "false" is a hard fail when the
    event is overnight; "true"/"unknown" pass ("unknown" with a caveat),
  - AV: assumed available (recorded ASSUMED) since the dataset carries no AV level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model

from ..config import active_db_path
from ..provenance import Label, ProvenanceRow

CAP_SAFETY = 1.1  # capacity must be >= p90 * 1.1
# Flat per-room penalty for PLACEHOLDER rooms so even free placeholder rooms are
# dispreferred vs a free MEASURED room (in the same cost-weighted units).
PLACEHOLDER_FLAT_PENALTY = 20

# Block layout -> ordered list of acceptable capacity columns (first = preferred).
LAYOUT_COLUMNS: dict[str, list[str]] = {
    "work": ["cap_classroom", "cap_banquet_round"],
    "ceremony": ["cap_theatre_lecture", "cap_fixed_seats"],
    "keynote": ["cap_theatre_lecture", "cap_fixed_seats"],
    "meal": ["cap_buffet", "cap_banquet_round"],
    "networking": ["cap_reception"],
    "breakout": ["cap_classroom", "cap_u_shape", "cap_boardroom"],
}


@dataclass
class ScheduleBlock:
    """One block of the event's schedule needing a room."""

    name: str                    # e.g. "Main hall", "Lunch"
    layout: str                  # key into LAYOUT_COLUMNS
    headcount: int               # required occupancy (usually attendance p90)


@dataclass
class Room:
    """A candidate room, as loaded from the DuckDB `rooms` table."""

    room_id: str
    building_code: str
    name: str
    floor: str
    layout_caps: dict[str, int | None]
    rate_per_hour: int
    air_wall_group: str | None
    label: str                   # provenance label (MEASURED/PLACEHOLDER)

    def capacity_for(self, layout: str) -> int | None:
        """Best capacity this room offers for the block layout, or None."""
        best = None
        for col in LAYOUT_COLUMNS.get(layout, []):
            cap = self.layout_caps.get(col)
            if cap is not None and (best is None or cap > best):
                best = cap
        return best


@dataclass
class Assignment:
    block: str
    room_id: str
    room_name: str
    layout: str
    capacity: int
    headcount: int
    utilization: float


@dataclass
class BuildingOption:
    building_code: str
    feasible: bool
    assignments: list[Assignment]
    total_cost: int
    avg_utilization: float
    reason: str
    measured_share: float = 0.0           # fraction of assigned rooms that are MEASURED
    action_items: list[str] = field(default_factory=list)  # Venue "Do now" items
    adjusted_cost: int = 0                # cost + data-confidence penalty, for ranking
    unmet_constraint: str | None = None


@dataclass
class VenueResult:
    options: list[BuildingOption]
    provenance: list[ProvenanceRow] = field(default_factory=list)

    @property
    def recommended(self) -> BuildingOption | None:
        feas = [o for o in self.options if o.feasible]
        return feas[0] if feas else (self.options[0] if self.options else None)


# --------------------------------------------------------------------------- #
# Load rooms + building attributes from DuckDB
# --------------------------------------------------------------------------- #
_LAYOUT_COLS = [
    "cap_theatre_lecture", "cap_classroom", "cap_banquet_round", "cap_buffet",
    "cap_reception", "cap_u_shape", "cap_boardroom", "cap_fixed_seats",
]


def load_rooms(db_path: Path | str | None = None) -> tuple[list[Room], dict[str, dict]]:
    """Return (rooms, building_attrs) from DuckDB."""
    import duckdb

    con = duckdb.connect(str(db_path or active_db_path()))
    try:
        cols = ["room_id", "building_code", "name", "floor", *_LAYOUT_COLS,
                "rate_per_hour", "air_wall_group", "label"]
        rows = con.execute(f"SELECT {', '.join(cols)} FROM rooms").fetchall()
        rooms = []
        for r in rows:
            d = dict(zip(cols, r))
            rooms.append(
                Room(
                    room_id=d["room_id"],
                    building_code=d["building_code"],
                    name=d["name"] or d["room_id"],
                    floor=str(d["floor"] or ""),
                    layout_caps={c: d[c] for c in _LAYOUT_COLS},
                    rate_per_hour=int(d["rate_per_hour"] or 0),
                    air_wall_group=d["air_wall_group"],
                    label=d["label"] or "",
                )
            )
        battrs: dict[str, dict] = {}
        try:
            brows = con.execute(
                "SELECT building_code, overnight_allowed, accessible_entrance, name "
                "FROM buildings"
            ).fetchall()
            for code, overnight, accessible, name in brows:
                battrs[code] = {
                    "overnight_allowed": (overnight or "unknown"),
                    "accessible_entrance": (accessible or "true"),
                    "name": name or code,
                }
        except Exception:
            pass
        return rooms, battrs
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Building-level hard constraints (accessibility / overnight)
# --------------------------------------------------------------------------- #
def _building_blocks_reason(
    attrs: dict, needs_accessibility: bool, overnight: bool
) -> str | None:
    """Return a reason string if the building fails a hard constraint, else None."""
    if needs_accessibility:
        acc = str(attrs.get("accessible_entrance", "true")).lower()
        if acc in ("false", "restricted"):
            return f"accessibility: entrance is '{acc}'"
    if overnight:
        ov = str(attrs.get("overnight_allowed", "unknown")).lower()
        if ov == "false":
            return "overnight not allowed in this building"
    return None


# --------------------------------------------------------------------------- #
# Air-wall exclusivity helpers
# --------------------------------------------------------------------------- #
def _air_wall_conflicts(rooms: list[Room]) -> list[tuple[str, str]]:
    """Pairs of room_ids that must not be booked together (whole vs part).

    The whole room has air_wall_group == its own room_id; the parts share that
    group id. The whole-room id conflicts with each part id.
    """
    groups: dict[str, list[Room]] = {}
    for r in rooms:
        if r.air_wall_group:
            groups.setdefault(r.air_wall_group, []).append(r)
    conflicts: list[tuple[str, str]] = []
    for group_id, members in groups.items():
        whole = [m for m in members if m.room_id == group_id]
        parts = [m for m in members if m.room_id != group_id]
        for w in whole:
            for p in parts:
                conflicts.append((w.room_id, p.room_id))
    return conflicts


# --------------------------------------------------------------------------- #
# Per-building CP-SAT solve
# --------------------------------------------------------------------------- #
def _solve_building(
    building_code: str,
    rooms: list[Room],
    blocks: list[ScheduleBlock],
    needs_accessibility: bool,
    overnight: bool,
    attrs: dict,
) -> BuildingOption:
    # Hard building-level gate first.
    blocked = _building_blocks_reason(attrs, needs_accessibility, overnight)
    if blocked:
        return BuildingOption(
            building_code=building_code,
            feasible=False,
            assignments=[],
            total_cost=0,
            avg_utilization=0.0,
            reason=f"infeasible - {blocked}",
            unmet_constraint=blocked,
        )

    model = cp_model.CpModel()

    # x[b, r] = 1 if block b is held in room r.
    x: dict[tuple[int, int], Any] = {}
    feasible_rooms_per_block: list[list[int]] = []
    for bi, block in enumerate(blocks):
        need = int(round(block.headcount * CAP_SAFETY))
        allowed: list[int] = []
        for ri, room in enumerate(rooms):
            cap = room.capacity_for(block.layout)
            if cap is not None and cap >= need:
                x[(bi, ri)] = model.NewBoolVar(f"x_{bi}_{ri}")
                allowed.append(ri)
        feasible_rooms_per_block.append(allowed)
        if not allowed:
            # No room can host this block's layout at the needed capacity.
            reason = (
                f"no room offers layout '{block.layout}' at capacity "
                f">= {need} for block '{block.name}'"
            )
            return BuildingOption(
                building_code=building_code,
                feasible=False,
                assignments=[],
                total_cost=0,
                avg_utilization=0.0,
                reason=f"infeasible - {reason}",
                unmet_constraint=reason,
            )

    # Each block assigned to exactly one allowed room.
    for bi, allowed in enumerate(feasible_rooms_per_block):
        model.AddExactlyOne(x[(bi, ri)] for ri in allowed)

    # A room hosts at most one block (thin model: blocks may be concurrent).
    room_used = {}
    for ri in range(len(rooms)):
        uses = [x[(bi, ri)] for bi in range(len(blocks)) if (bi, ri) in x]
        if uses:
            used = model.NewBoolVar(f"used_{ri}")
            model.AddMaxEquality(used, uses)
            room_used[ri] = used
            model.Add(sum(uses) <= 1)

    # Air-wall exclusivity: whole room and its parts cannot both be used.
    id_to_index = {room.room_id: ri for ri, room in enumerate(rooms)}
    for whole_id, part_id in _air_wall_conflicts(rooms):
        wi, pi = id_to_index.get(whole_id), id_to_index.get(part_id)
        if wi in room_used and pi in room_used:
            model.Add(room_used[wi] + room_used[pi] <= 1)

    # Objective: cost + unused capacity + walking distance (floor spread proxy)
    # + a DATA-CONFIDENCE penalty on PLACEHOLDER rooms. The penalty is ~25% of
    # the room's hourly cost (scaled by the same weight as cost), so real
    # MEASURED spaces win when reasonably close on cost, without excluding
    # placeholders. We add a small flat floor so even free placeholder rooms
    # carry some penalty versus a free real room.
    cost_terms = []
    unused_terms = []
    floor_terms = []
    confidence_terms = []
    for bi, block in enumerate(blocks):
        need = int(round(block.headcount * CAP_SAFETY))
        for ri in feasible_rooms_per_block[bi]:
            room = rooms[ri]
            cap = room.capacity_for(block.layout) or 0
            cost_terms.append(room.rate_per_hour * x[(bi, ri)])
            unused_terms.append(max(0, cap - need) * x[(bi, ri)])
            floor_terms.append(_floor_num(room.floor) * x[(bi, ri)])
            if room.label == Label.PLACEHOLDER.value:
                penalty = int(round(0.25 * room.rate_per_hour)) + PLACEHOLDER_FLAT_PENALTY
                confidence_terms.append(penalty * x[(bi, ri)])

    model.Minimize(
        10 * sum(cost_terms)
        + sum(unused_terms)
        + 5 * sum(floor_terms)   # proxy for inter-block walking distance
        + 10 * sum(confidence_terms)  # data-confidence: prefer real MEASURED rooms
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return BuildingOption(
            building_code=building_code,
            feasible=False,
            assignments=[],
            total_cost=0,
            avg_utilization=0.0,
            reason="infeasible - no assignment satisfied all constraints",
            unmet_constraint="combined capacity/exclusivity constraints",
        )

    assignments: list[Assignment] = []
    total_cost = 0
    adjusted_cost = 0
    utils: list[float] = []
    measured_count = 0
    for bi, block in enumerate(blocks):
        for ri in feasible_rooms_per_block[bi]:
            if solver.Value(x[(bi, ri)]) == 1:
                room = rooms[ri]
                cap = room.capacity_for(block.layout) or 0
                util = block.headcount / cap if cap else 0.0
                adjusted_cost += room.rate_per_hour
                if room.label == Label.PLACEHOLDER.value:
                    adjusted_cost += int(round(0.25 * room.rate_per_hour)) + PLACEHOLDER_FLAT_PENALTY
                assignments.append(
                    Assignment(
                        block=block.name,
                        room_id=room.room_id,
                        room_name=room.name,
                        layout=block.layout,
                        capacity=cap,
                        headcount=block.headcount,
                        utilization=round(util, 3),
                    )
                )
                total_cost += room.rate_per_hour
                utils.append(util)
                if room.label == Label.MEASURED.value:
                    measured_count += 1
                break

    avg_util = round(sum(utils) / len(utils), 3) if utils else 0.0
    measured_share = round(measured_count / len(assignments), 3) if assignments else 0.0

    # Data-confidence phrasing in the reason.
    if measured_share >= 0.999:
        data_phrase = "100% real BU event-space data"
    elif measured_share <= 0.001:
        data_phrase = "placeholder room data, verify with BU Reservations"
    else:
        data_phrase = (
            f"{int(round(measured_share * 100))}% real BU event-space data, "
            f"rest placeholder - verify with BU Reservations"
        )

    reason = (
        f"fits all {len(blocks)} blocks; avg utilization {int(avg_util * 100)}%, "
        f"room cost ${total_cost}/hr; {data_phrase}"
    )

    # Venue "Do now" action items surfaced into the plan (overnight + AV are not
    # in the dataset).
    action_items: list[str] = []
    if overnight and str(attrs.get("overnight_allowed", "unknown")).lower() == "unknown":
        action_items.append(
            "Confirm overnight access for this building with BU Reservations"
        )
    action_items.append(
        "Confirm AV level (projector/sound/mic) with BU Reservations"
    )
    if measured_share < 0.999:
        action_items.append(
            "Verify placeholder room details (capacity, rate, AV) with BU Reservations"
        )

    return BuildingOption(
        building_code=building_code,
        feasible=True,
        assignments=assignments,
        total_cost=total_cost,
        avg_utilization=avg_util,
        reason=reason,
        measured_share=measured_share,
        action_items=action_items,
        adjusted_cost=adjusted_cost,
    )


def _floor_num(floor: str) -> int:
    s = str(floor).strip().upper()
    if not s:
        return 0
    if s.startswith("B"):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def optimize(
    brief,
    p90: int,
    blocks: list[ScheduleBlock],
    rooms: list[Room] | None = None,
    building_attrs: dict[str, dict] | None = None,
    db_path: Path | str | None = None,
    top_n: int = 3,
) -> VenueResult:
    """Assign rooms per block across candidate buildings; return the top-N options."""
    if rooms is None or building_attrs is None:
        loaded_rooms, loaded_attrs = load_rooms(db_path)
        rooms = rooms if rooms is not None else loaded_rooms
        building_attrs = building_attrs if building_attrs is not None else loaded_attrs

    needs_accessibility = bool(getattr(brief, "accessibility_needs", None))
    overnight = bool(getattr(brief, "overnight", False))

    # Group rooms by building.
    by_building: dict[str, list[Room]] = {}
    for r in rooms:
        by_building.setdefault(r.building_code, []).append(r)

    options: list[BuildingOption] = []
    for code, building_rooms in by_building.items():
        attrs = (building_attrs or {}).get(code, {})
        options.append(
            _solve_building(
                code, building_rooms, blocks, needs_accessibility, overnight, attrs
            )
        )

    # Rank: feasible first. Among feasible options, prefer higher real-data
    # confidence (MEASURED share) in coarse tiers, then lowest
    # data-confidence-adjusted cost (PLACEHOLDER rooms carry a ~25% + flat
    # penalty), then higher utilization. Tiering the measured share means a
    # fully-real option wins over a placeholder one, while the adjusted cost
    # still orders options within the same confidence tier.
    def _confidence_tier(share: float) -> int:
        # 0 = fully real, 1 = mostly real, 2 = mixed/placeholder (lower is better)
        if share >= 0.999:
            return 0
        if share >= 0.5:
            return 1
        return 2

    options.sort(
        key=lambda o: (
            not o.feasible,
            _confidence_tier(o.measured_share),
            o.adjusted_cost,
            -o.avg_utilization,
        )
    )
    top = options[:top_n]

    prov: list[ProvenanceRow] = []
    rec = next((o for o in top if o.feasible), None)
    if rec:
        prov.append(
            ProvenanceRow(
                output_key="venue.recommended_building",
                label=Label.MEASURED,
                source="bu_event_spaces.csv via DuckDB rooms (layout capacities)",
                value_summary=f"{rec.building_code}: {len(rec.assignments)} blocks assigned",
            )
        )
        prov.append(
            ProvenanceRow(
                output_key="venue.av_capability",
                label=Label.ASSUMED,
                source="AV level not in dataset; assumed available",
                value_summary="AV assumed available",
            )
        )
    return VenueResult(options=top, provenance=prov)


# Default schedule-block builder for a simple event (used by the orchestrator/tests).
def default_blocks(p90: int, overnight: bool, food: bool) -> list[ScheduleBlock]:
    blocks = [ScheduleBlock(name="Main hall", layout="work", headcount=p90)]
    if food:
        blocks.append(ScheduleBlock(name="Meals", layout="meal", headcount=p90))
    blocks.append(ScheduleBlock(name="Opening keynote", layout="keynote", headcount=p90))
    return blocks
