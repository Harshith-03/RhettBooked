"""
placeholder_gen.py

Generate the EventTwin PLACEHOLDER dataset under data/placeholder/.

IMPORTANT: Every value in these files is ILLUSTRATIVE. Building names are real
Boston University Charles River Campus buildings, but all floors, rooms,
capacities, rates, coordinates, parking figures and sponsor entries are made up
for demonstration. These are NOT official BU data.

Run:
    python backend/app/data/placeholder_gen.py

Output is reproducible because a fixed random seed is used.
"""

from __future__ import annotations

import csv
import os
import random
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

SEED = 42
HEADER_COMMENT = "# PLACEHOLDER - illustrative values, not official BU data"

# Resolve data/placeholder/ relative to the repo root (three levels up from this file:
# backend/app/data/placeholder_gen.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "data" / "placeholder"


# --------------------------------------------------------------------------- #
# CSV helper: writes the placeholder comment row, then the header, then rows.
# --------------------------------------------------------------------------- #
def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write(HEADER_COMMENT + "\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def bool_str(value: bool) -> str:
    return "true" if value else "false"


# --------------------------------------------------------------------------- #
# 1. Buildings
# --------------------------------------------------------------------------- #
# Real BU Charles River Campus buildings. Coordinates are APPROXIMATE points
# along/near Commonwealth Ave and are illustrative only.
BUILDINGS = [
    # name, address, lat, lon, floors, accessible, elevators, dock, overnight, mbta, wifi
    ("Center for Computing & Data Sciences", "665 Commonwealth Ave", 42.3499, -71.1030, 19, True, 6, True, True, "BU Central", "high"),
    ("George Sherman Union", "775 Commonwealth Ave", 42.3505, -71.1066, 4, True, 3, True, False, "BU Central", "high"),
    ("Photonics Center", "8 Saint Mary's St", 42.3490, -71.1041, 9, True, 3, True, False, "BU Central", "high"),
    ("College of Arts & Sciences", "725 Commonwealth Ave", 42.3503, -71.1050, 6, True, 4, False, False, "BU Central", "standard"),
    ("Questrom School of Business", "595 Commonwealth Ave", 42.3496, -71.0995, 6, True, 5, True, False, "BU East", "high"),
    ("Metcalf Science Center", "590 Commonwealth Ave", 42.3492, -71.0993, 5, True, 3, True, False, "BU East", "standard"),
    ("Agganis Arena", "925 Commonwealth Ave", 42.3524, -71.1177, 3, True, 4, True, True, "Saint Paul St", "high"),
    ("Fitness & Recreation Center", "915 Commonwealth Ave", 42.3519, -71.1162, 4, True, 4, True, False, "Saint Paul St", "standard"),
    ("Kilachand Hall", "91 Bay State Rd", 42.3497, -71.0978, 9, True, 2, False, True, "BU East", "standard"),
    ("Law Tower", "765 Commonwealth Ave", 42.3505, -71.1058, 18, True, 5, False, False, "BU Central", "high"),
    ("Mugar Memorial Library", "771 Commonwealth Ave", 42.3505, -71.1063, 6, True, 3, True, False, "BU Central", "standard"),
    ("Engineering Product Innovation Center", "750 Commonwealth Ave", 42.3496, -71.1055, 3, True, 2, True, True, "BU Central", "high"),
    ("Rajen Kilachand Center", "610 Commonwealth Ave", 42.3494, -71.1006, 9, True, 4, True, False, "BU East", "high"),
    ("Booth Theatre", "855 Commonwealth Ave", 42.3513, -71.1125, 3, True, 2, False, False, "Pleasant St", "standard"),
    ("1 Silber Way", "1 Silber Way", 42.3498, -71.1016, 10, True, 4, False, False, "BU East", "standard"),
]


def gen_buildings(rng: random.Random) -> list[dict]:
    rows = []
    for i, b in enumerate(BUILDINGS, start=1):
        (name, address, lat, lon, floors, accessible, elevators,
         dock, overnight, mbta, wifi) = b
        rows.append({
            "building_id": f"BLD{i:02d}",
            "name": name,
            "address": address,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "floors": floors,
            "accessible_entrance": bool_str(accessible),
            "elevators": elevators,
            "loading_dock": bool_str(dock),
            "overnight_allowed": bool_str(overnight),
            "nearest_mbta_stop": mbta,
            "building_wifi_tier": wifi,
        })
    return rows


BUILDING_FIELDS = [
    "building_id", "name", "address", "lat", "lon", "floors",
    "accessible_entrance", "elevators", "loading_dock", "overnight_allowed",
    "nearest_mbta_stop", "building_wifi_tier",
]


# --------------------------------------------------------------------------- #
# 2. Rooms
# --------------------------------------------------------------------------- #
ROOM_TYPES = ["lecture", "classroom", "seminar", "ballroom", "lab", "atrium", "lounge"]

# Plausible per-type ranges: (seated_min, seated_max, standing_factor, sqft_per_seat,
# tables_likely, av_choices, power_range, ap_per_100cap)
ROOM_TYPE_SPEC = {
    "lecture":   (60, 300, 1.2, 10, False, ["basic", "full"], (4, 10), 1.0),
    "classroom": (20, 60, 1.3, 18, True, ["basic", "full"], (2, 6), 1.2),
    "seminar":   (8, 30, 1.4, 22, True, ["basic", "full"], (2, 4), 1.5),
    "ballroom":  (120, 600, 1.6, 12, True, ["full"], (8, 16), 1.0),
    "lab":       (12, 40, 1.1, 30, True, ["basic", "full"], (6, 14), 1.4),
    "atrium":    (40, 250, 2.0, 15, False, ["none", "basic"], (2, 6), 0.8),
    "lounge":    (10, 60, 1.8, 20, True, ["none", "basic"], (1, 4), 1.2),
}

# CDS (BLD01) must include these specific rooms to match the real event.
CDS_REQUIRED_ROOMS = ["164", "262", "263", "264", "265", "B62", "B63", "B64"]


def floor_from_room_number(room_number: str) -> int:
    """Infer a floor from a room number like '164', '262', 'B62'."""
    rn = room_number.strip()
    if rn[0].upper() == "B":
        return 0  # basement level
    return int(rn[0])


def make_room(rng: random.Random, room_id: str, building_id: str,
              floor: int, room_number: str, room_type: str,
              overnight_allowed: bool) -> dict:
    spec = ROOM_TYPE_SPEC[room_type]
    (s_min, s_max, stand_factor, sqft_per_seat,
     tables_likely, av_choices, power_range, ap_factor) = spec

    capacity_seated = rng.randint(s_min, s_max)
    capacity_standing = int(capacity_seated * stand_factor)
    area_sqft = int(capacity_seated * sqft_per_seat * rng.uniform(0.9, 1.25))
    tables = tables_likely if rng.random() > 0.2 else (not tables_likely)
    av = rng.choice(av_choices)
    power_circuits = rng.randint(*power_range)
    access_points = max(1, round(capacity_seated / 100.0 * ap_factor) + rng.randint(0, 1))
    step_free = rng.random() > 0.15

    # Rates: many internal student-org rooms are free; others 50-400.
    if room_type in ("classroom", "seminar", "lab") and rng.random() < 0.6:
        rate = 0
    elif room_type in ("atrium", "lounge") and rng.random() < 0.4:
        rate = 0
    else:
        rate = rng.choice([50, 75, 100, 125, 150, 200, 250, 300, 350, 400])
        if room_type == "ballroom":
            rate = rng.choice([250, 300, 350, 400])

    # Ventilation plausible with capacity (ASHRAE-ish illustrative: ~15-25 cfm/person).
    ventilation_cfm = int(capacity_seated * rng.uniform(15, 25))

    return {
        "room_id": room_id,
        "building_id": building_id,
        "floor": floor,
        "room_number": room_number,
        "room_type": room_type,
        "capacity_seated": capacity_seated,
        "capacity_standing": capacity_standing,
        "area_sqft": area_sqft,
        "tables": bool_str(tables),
        "av": av,
        "power_circuits": power_circuits,
        "access_points": access_points,
        "step_free": bool_str(step_free),
        "rate_per_hour_usd": rate,
        "ventilation_cfm": ventilation_cfm,
    }


def gen_rooms(rng: random.Random, buildings: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seq = 1

    for b in buildings:
        bid = b["building_id"]
        floors = int(b["floors"])
        overnight = b["overnight_allowed"] == "true"

        required = CDS_REQUIRED_ROOMS if bid == "BLD01" else []

        # Emit required rooms first (CDS).
        for rn in required:
            floor = floor_from_room_number(rn)
            rtype = rng.choice(["lecture", "classroom", "seminar", "lab"])
            rows.append(make_room(rng, f"RM{seq:04d}", bid, floor, rn, rtype, overnight))
            seq += 1

        # Fill remaining rooms up to a 6-12 total for the building.
        target = rng.randint(6, 12)
        remaining = max(0, target - len(required))
        for _ in range(remaining):
            floor = rng.randint(1, max(1, floors))
            rtype = rng.choice(ROOM_TYPES)
            room_number = f"{floor}{rng.randint(1, 89):02d}"
            rows.append(make_room(rng, f"RM{seq:04d}", bid, floor, room_number, rtype, overnight))
            seq += 1

    return rows


ROOM_FIELDS = [
    "room_id", "building_id", "floor", "room_number", "room_type",
    "capacity_seated", "capacity_standing", "area_sqft", "tables", "av",
    "power_circuits", "access_points", "step_free", "rate_per_hour_usd",
    "ventilation_cfm",
]


# --------------------------------------------------------------------------- #
# 3. Parking
# --------------------------------------------------------------------------- #
PARKING = [
    ("Agganis Arena Garage", 42.3522, -71.1170),
    ("Granby Lot", 42.3490, -71.0989),
    ("Warren Towers Service Lot", 42.3500, -71.1030),
    ("CDS Underground Garage", 42.3499, -71.1032),
    ("Buick Street Garage", 42.3515, -71.1150),
    ("Essex Street Lot", 42.3488, -71.0960),
    ("St. Mary's Street Lot", 42.3491, -71.1045),
    ("Babcock Street Lot", 42.3520, -71.1200),
]


def gen_parking(rng: random.Random) -> list[dict]:
    rows = []
    for i, (name, lat, lon) in enumerate(PARKING, start=1):
        spaces = rng.choice([60, 90, 120, 180, 240, 320, 450])
        rows.append({
            "parking_id": f"PRK{i:02d}",
            "name": name,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "spaces": spaces,
            "weekend_rate_usd": rng.choice([8, 10, 12, 15, 18, 20, 25]),
            "overnight": bool_str(rng.random() > 0.5),
            "accessible_spaces": max(2, round(spaces * rng.uniform(0.02, 0.05))),
        })
    return rows


PARKING_FIELDS = [
    "parking_id", "name", "lat", "lon", "spaces", "weekend_rate_usd",
    "overnight", "accessible_spaces",
]


# --------------------------------------------------------------------------- #
# 5. Sponsors
# --------------------------------------------------------------------------- #
SPONSOR_LABELS = [
    ("Boston AI startup", "AI/ML"),
    ("Biotech company - Kendall Sq", "Biotech"),
    ("Wearables/health-tech company", "Health-tech"),
    ("Cloud provider", "Cloud"),
    ("Local bank", "Finance"),
    ("Design tool company", "Design"),
    ("Robotics startup", "Robotics"),
    ("Fintech company", "Finance"),
    ("Edtech company", "Edtech"),
    ("Climate-tech startup", "Climate"),
    ("Cybersecurity firm", "Security"),
    ("Data analytics company", "Data"),
    ("Semiconductor company", "Hardware"),
    ("Electric vehicle startup", "Mobility"),
    ("Pharma company", "Pharma"),
    ("Developer tools company", "DevTools"),
    ("Consumer app startup", "Consumer"),
    ("Logistics/supply-chain company", "Logistics"),
    ("Aerospace company", "Aerospace"),
    ("Gaming studio", "Gaming"),
]

ASK_TYPES = ["cash", "credits", "food", "swag", "mentors"]
RANGES = ["250-1000", "500-2500", "1000-5000", "2500-10000", "5000-20000"]
TOPIC_POOL = [
    "machine-learning", "nlp", "computer-vision", "cloud", "data-engineering",
    "health", "fintech", "sustainability", "security", "robotics", "hardware",
    "mobility", "design", "product", "analytics", "genomics", "iot",
]


def gen_sponsors(rng: random.Random) -> list[dict]:
    rows = []
    # 40 entries built from the generic labels (cycle through labels twice).
    for i in range(1, 41):
        label, industry = SPONSOR_LABELS[(i - 1) % len(SPONSOR_LABELS)]
        n_tags = rng.randint(2, 3)
        tags = rng.sample(TOPIC_POOL, n_tags)
        rows.append({
            "sponsor_id": f"SPN{i:02d}",
            "label": label,
            "industry": industry,
            "typical_ask": rng.choice(ASK_TYPES),
            "typical_range_usd": rng.choice(RANGES),
            "topic_tags": "|".join(tags),
        })
    return rows


SPONSOR_FIELDS = [
    "sponsor_id", "label", "industry", "typical_ask", "typical_range_usd",
    "topic_tags",
]


# --------------------------------------------------------------------------- #
# 4. Rate cards (YAML)
# --------------------------------------------------------------------------- #
def write_rate_cards(path: Path) -> None:
    data = {
        "_note": "PLACEHOLDER - illustrative ASSUMED unit costs, not official BU or vendor data.",
        "currency": "USD",
        "catering_per_head": {
            "lean": {
                "breakfast": {"low": 6, "high": 10},
                "lunch": {"low": 10, "high": 16},
                "dinner": {"low": 14, "high": 22},
                "snack": {"low": 3, "high": 6},
            },
            "balanced": {
                "breakfast": {"low": 9, "high": 14},
                "lunch": {"low": 15, "high": 24},
                "dinner": {"low": 22, "high": 35},
                "snack": {"low": 5, "high": 9},
            },
            "premium": {
                "breakfast": {"low": 14, "high": 22},
                "lunch": {"low": 24, "high": 40},
                "dinner": {"low": 38, "high": 65},
                "snack": {"low": 8, "high": 14},
            },
        },
        "bottled_water_each": {"low": 0.35, "high": 0.90},
        "water_refill_station_rental_per_day": {"low": 75, "high": 200},
        "temporary_wifi_ap_rental_per_ap_per_day": {"low": 45, "high": 120},
        "power_strip_station_rental_each": {"low": 8, "high": 25},
        "av_tech_per_hour": {"low": 45, "high": 110},
        "security_police_detail_per_hour": {"low": 55, "high": 95},
        "custodial_per_hour": {"low": 30, "high": 60},
        "event_insurance_flat": {"low": 150, "high": 600},
        "swag_per_head": {"low": 5, "high": 20},
        "prizes_total": {"low": 500, "high": 10000},
        "printing_flat": {"low": 50, "high": 400},
        "contingency_percent": {"low": 5, "high": 15},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(HEADER_COMMENT + "\n")
        if yaml is not None:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
        else:  # pragma: no cover - fallback if pyyaml missing
            _dump_simple_yaml(f, data, 0)


def _dump_simple_yaml(f, obj, indent):  # pragma: no cover
    pad = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict,)):
                f.write(f"{pad}{k}:\n")
                _dump_simple_yaml(f, v, indent + 1)
            else:
                f.write(f"{pad}{k}: {v}\n")
    else:
        f.write(f"{pad}{obj}\n")


# --------------------------------------------------------------------------- #
# README
# --------------------------------------------------------------------------- #
README = """# EventTwin placeholder dataset

**PLACEHOLDER - illustrative values, not official BU data.**

Every file in this folder is generated by
`backend/app/data/placeholder_gen.py` with a fixed random seed, so the output is
reproducible. Regenerate at any time:

```bash
python backend/app/data/placeholder_gen.py
```

The building **names** are real Boston University Charles River Campus buildings,
but all other values (floors, rooms, capacities, rates, coordinates, parking
figures, sponsor entries, and unit costs) are **illustrative and invented** for
demonstration. Nothing here should be treated as official BU, MBTA, or vendor
data. Each file starts with the comment line
`# PLACEHOLDER - illustrative values, not official BU data`.

## Files

### `bu_buildings.csv`
15 real BU Charles River Campus buildings with approximate coordinates along
Commonwealth Ave. Columns: `building_id`, `name`, `address`, `lat`, `lon`,
`floors`, `accessible_entrance`, `elevators`, `loading_dock`,
`overnight_allowed`, `nearest_mbta_stop`, `building_wifi_tier`.
*Placeholder because* floors, access details, docks, overnight policy and wifi
tier are guessed, and coordinates are approximate.

### `bu_rooms.csv`
About 130 rooms (6-12 per building). Columns: `room_id`, `building_id`, `floor`,
`room_number`, `room_type`, `capacity_seated`, `capacity_standing`, `area_sqft`,
`tables`, `av`, `power_circuits`, `access_points`, `step_free`,
`rate_per_hour_usd`, `ventilation_cfm`. Capacities are kept plausible per room
type. The Center for Computing & Data Sciences (`BLD01`) includes rooms 164,
262, 263, 264, 265, B62, B63, B64 to match the real event layout.
*Placeholder because* every capacity, rate, power, AP count and ventilation
figure is invented.

### `bu_parking.csv`
8 BU-area garages/lots. Columns: `parking_id`, `name`, `lat`, `lon`, `spaces`,
`weekend_rate_usd`, `overnight`, `accessible_spaces`.
*Placeholder because* space counts, rates and accessibility figures are invented
and coordinates are approximate.

### `rate_cards.yaml`
ASSUMED unit costs with low/high ranges: catering per head by tier and meal,
bottled water, refill station rental, temporary Wi-Fi AP rental, power station
rental, AV tech, security/police detail, custodial, event insurance, swag,
prizes, printing, and a contingency percentage.
*Placeholder because* these are assumed market-style ranges, not quotes.

### `sponsors_placeholder.csv`
40 sponsor-*type* entries using generic labels only (no real company names).
Columns: `sponsor_id`, `label`, `industry`, `typical_ask`, `typical_range_usd`,
`topic_tags`.
*Placeholder because* these are archetypes for matching logic, not real
sponsors or real commitments.

## Labelling

In EventTwin, values sourced from this folder are surfaced in the UI as
`PLACEHOLDER` so users always know the numbers are illustrative.
"""


def write_readme(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(README, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    buildings = gen_buildings(rng)
    rooms = gen_rooms(rng, buildings)
    parking = gen_parking(rng)
    sponsors = gen_sponsors(rng)

    write_csv(OUT_DIR / "bu_buildings.csv", BUILDING_FIELDS, buildings)
    write_csv(OUT_DIR / "bu_rooms.csv", ROOM_FIELDS, rooms)
    write_csv(OUT_DIR / "bu_parking.csv", PARKING_FIELDS, parking)
    write_csv(OUT_DIR / "sponsors_placeholder.csv", SPONSOR_FIELDS, sponsors)
    write_rate_cards(OUT_DIR / "rate_cards.yaml")
    write_readme(OUT_DIR / "README.md")

    print(f"Wrote placeholder dataset to {OUT_DIR}")
    print(f"  bu_buildings.csv        {len(buildings)} buildings")
    print(f"  bu_rooms.csv            {len(rooms)} rooms")
    print(f"  bu_parking.csv          {len(parking)} parking lots")
    print(f"  sponsors_placeholder.csv {len(sponsors)} sponsors")
    print(f"  rate_cards.yaml")
    print(f"  README.md")


if __name__ == "__main__":
    main()
