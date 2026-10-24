"""
food_water.py

Food & water plan (P0, task 15) using COMMITTED data only.

For each meal in the brief:
  - list BU dining halls (table `dining`, MEASURED) that are OPEN during the
    meal window, using the parsed hours by day-of-week,
  - flag "check hours" for any hall whose hours are unknown (never assumed open),
  - estimate per-meal catering cost from rate_cards.yaml (ASSUMED ranges),
  - recommend a serving-line count from a simple capacity rule.

Water: refill-station vs bottled comparison driven by
``water_litres_per_person_per_hour`` from assumptions.yaml and the bottled/refill
rates from rate_cards.yaml.

Live OSM (restaurants/cafes, drinking_water) is a P1 hook: ``_osm_hook`` is a
placeholder that returns nothing here; task 15's OSM path plugs in later.

Provenance: dining rows MEASURED; costs + water params ASSUMED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from ..config import PLACEHOLDER_DIR, load_assumptions
from ..data import loaders
from ..provenance import Label, ProvenanceRow

# Meal windows (local wall-clock), used to test dining-hall open hours.
MEAL_WINDOWS: dict[str, tuple[time, time]] = {
    "breakfast": (time(7, 0), time(9, 30)),
    "lunch": (time(11, 30), time(13, 30)),
    "snack": (time(23, 30), time(23, 59)),      # "midnight snack" ~ late night
    "dinner": (time(17, 30), time(19, 30)),
}
# Serving-line capacity rule (ASSUMED): one line serves ~this many people within
# a standard meal window.
PEOPLE_PER_LINE = 75
DEFAULT_TIER = "balanced"


@dataclass
class DiningOption:
    dining_id: str
    name: str
    building_code: str
    open: bool
    hours_unknown: bool
    flags: list[str]
    hours_window: str | None     # the day's hours used, e.g. "08:00-22:00"


@dataclass
class MealPlan:
    meal: str
    window: str
    headcount: int
    bu_dining_open: list[DiningOption]
    bu_dining_check_hours: list[DiningOption]
    cost_low: int
    cost_high: int
    serving_lines: int
    note: str = ""
    osm_fallback: list[dict] = field(default_factory=list)   # P1 hook


@dataclass
class WaterPlan:
    litres_per_person_hour: float
    hours: int
    headcount: int
    total_litres: float
    bottled_cost_low: int
    bottled_cost_high: int
    refill_cost_low: int
    refill_cost_high: int
    recommendation: str


@dataclass
class FoodWaterPlan:
    meals: list[MealPlan]
    water: WaterPlan
    provenance: list[ProvenanceRow] = field(default_factory=list)


def _rate_cards() -> dict:
    path = PLACEHOLDER_DIR / "rate_cards.yaml"
    if not path.exists():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _day_key(d: date | None) -> str:
    """Map a date to the dining hours column key (mon_thu / fri / sat_sun)."""
    if d is None:
        return "mon_thu"
    wd = d.weekday()  # Mon=0 .. Sun=6
    if wd <= 3:
        return "mon_thu"
    if wd == 4:
        return "fri"
    return "sat_sun"


def _is_open(hours: tuple[str, str] | None, window: tuple[time, time]) -> bool:
    """True if the dining hours cover the meal window start (thin check)."""
    if not hours:
        return False
    try:
        o = datetime.strptime(hours[0], "%H:%M").time()
        c = datetime.strptime(hours[1], "%H:%M").time()
    except ValueError:
        return False
    start = window[0]
    # Open if the window start falls within [open, close).
    return o <= start < c


def _osm_hook(building_code: str | None):
    """P1 hook for live OSM restaurant/cafe fallback. Intentionally empty in P0."""
    return []


def plan(brief, attendance=None, db_path=None) -> FoodWaterPlan:
    assumptions = load_assumptions()
    cards = _rate_cards()
    dining, dining_prov = loaders.load_dining()

    # Headcount per meal from attendance p90 (fallback to registrations).
    headcount = 0
    if attendance is not None:
        headcount = getattr(attendance, "turnout_p90", 0) or 0
    if not headcount:
        headcount = int(getattr(brief, "expected_registrations", 0) or 0)

    event_day = _parse_date(getattr(brief, "start", None))
    day_key = _day_key(event_day)

    prov: list[ProvenanceRow] = list(dining_prov)
    tier = DEFAULT_TIER
    catering = (cards.get("catering_per_head") or {}).get(tier, {})

    meal_plans: list[MealPlan] = []
    for meal in (getattr(brief, "meals", []) or []):
        window = MEAL_WINDOWS.get(meal, (time(12, 0), time(13, 0)))
        open_halls: list[DiningOption] = []
        check_halls: list[DiningOption] = []
        for d in dining:
            hrs = d.hours.get(day_key)
            opt = DiningOption(
                dining_id=d.dining_id,
                name=d.name,
                building_code=d.building_code,
                open=_is_open(hrs, window),
                hours_unknown=d.hours_unknown,
                flags=list(d.flags),
                hours_window=f"{hrs[0]}-{hrs[1]}" if hrs else None,
            )
            if d.hours_unknown:
                check_halls.append(opt)
            elif opt.open:
                open_halls.append(opt)

        card = catering.get(meal) or catering.get("lunch") or {"low": 10, "high": 20}
        cost_low = int(round(float(card["low"]) * headcount))
        cost_high = int(round(float(card["high"]) * headcount))
        lines = max(1, -(-headcount // PEOPLE_PER_LINE))  # ceil division

        note = ""
        if not open_halls and check_halls:
            note = "No BU hall confirmed open; verify the 'check hours' halls."
        elif not open_halls:
            note = "No BU dining hall open in this window; use OSM restaurants (P1)."

        meal_plans.append(
            MealPlan(
                meal=meal,
                window=f"{window[0].strftime('%H:%M')}-{window[1].strftime('%H:%M')}",
                headcount=headcount,
                bu_dining_open=open_halls,
                bu_dining_check_hours=check_halls,
                cost_low=cost_low,
                cost_high=cost_high,
                serving_lines=lines,
                note=note,
                osm_fallback=_osm_hook(getattr(brief, "preferred_area", None)),
            )
        )
        prov.append(
            ProvenanceRow(
                output_key=f"food.{meal}.cost",
                label=Label.ASSUMED,
                source=f"rate_cards.yaml catering_per_head.{tier}.{meal}",
                value_summary=f"${cost_low}-{cost_high} for {headcount}",
            )
        )

    water = _water_plan(brief, assumptions, cards, headcount)
    prov.append(
        ProvenanceRow(
            output_key="water.demand",
            label=Label.ASSUMED,
            source="assumptions.yaml water_litres_per_person_per_hour",
            value_summary=f"{water.total_litres:.0f} L total",
        )
    )

    return FoodWaterPlan(meals=meal_plans, water=water, provenance=prov)


def _water_plan(brief, assumptions, cards, headcount) -> WaterPlan:
    lpph = float(
        (assumptions.get("water_litres_per_person_per_hour") or {}).get("value", 0.25)
    )
    # Active hours: overnight events run long; default to a day window otherwise.
    hours = 36 if getattr(brief, "overnight", False) else 9
    total_litres = lpph * headcount * hours

    bottled = cards.get("bottled_water_each") or {"low": 0.35, "high": 0.9}
    # ~0.5 L per bottle -> bottles = litres / 0.5.
    bottles = total_litres / 0.5
    b_low = int(round(bottles * float(bottled["low"])))
    b_high = int(round(bottles * float(bottled["high"])))

    refill = cards.get("water_refill_station_rental_per_day") or {"low": 75, "high": 200}
    days = max(1, -(-hours // 24))
    # Assume 1 refill station per ~150 people.
    stations = max(1, -(-headcount // 150))
    r_low = int(round(float(refill["low"]) * stations * days))
    r_high = int(round(float(refill["high"]) * stations * days))

    rec = (
        "Refill stations are cheaper and lower-waste"
        if r_high < b_low
        else "Bottled is cheaper at this scale; refill if sustainability matters"
    )
    return WaterPlan(
        litres_per_person_hour=lpph,
        hours=hours,
        headcount=headcount,
        total_litres=total_litres,
        bottled_cost_low=b_low,
        bottled_cost_high=b_high,
        refill_cost_low=r_low,
        refill_cost_high=r_high,
        recommendation=rec,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
