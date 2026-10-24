"""
fetch_bluebikes.py

ONE-TIME downloader + aggregator for Bluebikes November 2024 trip data.

Downloads the public monthly trip file:
    https://s3.amazonaws.com/hubway-data/202411-bluebikes-tripdata.zip
into data/raw/v3/bluebikes/raw/ (gitignored), then streams the CSV in chunks and
aggregates it into a small, commit-ready CSV:
    data/raw/v3/bluebikes/bu_hourly_nov2024.csv

Aggregation: for trips whose START or END point is within 600 m of ANY building
in data/reference/bu_buildings_ref.csv, count hourly trip STARTS and ENDS, split
into weekday vs weekend. Output columns:
    daytype (weekday|weekend), hour (0-23), starts, ends

Only the aggregated CSV is meant to be committed; the raw download stays local.

Run:
    python -m backend.app.data.fetch_bluebikes
"""

from __future__ import annotations

import csv
import io
import math
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..config import REFERENCE_DIR

URL = "https://s3.amazonaws.com/hubway-data/202411-bluebikes-tripdata.zip"
BASE = Path(__file__).resolve().parents[3] / "data" / "raw" / "v3" / "bluebikes"
RAW_DIR = BASE / "raw"
OUT_CSV = BASE / "bu_hourly_nov2024.csv"
RADIUS_M = 600.0

# Possible column names across Bluebikes schema versions.
START_TIME_COLS = ("started_at", "starttime", "start_time")
END_TIME_COLS = ("ended_at", "stoptime", "stop_time", "end_time")
START_LAT_COLS = ("start_lat", "start station latitude", "start_station_latitude")
START_LNG_COLS = ("start_lng", "start station longitude", "start_station_longitude")
END_LAT_COLS = ("end_lat", "end station latitude", "end_station_latitude")
END_LNG_COLS = ("end_lng", "end station longitude", "end_station_longitude")


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load_building_points() -> list[tuple[float, float]]:
    ref = REFERENCE_DIR / "bu_buildings_ref.csv"
    pts: list[tuple[float, float]] = []
    if not ref.exists():
        return pts
    with ref.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row.get("lat") or "")
                lon = float(row.get("lon") or "")
            except ValueError:
                continue
            pts.append((lat, lon))
    return pts


def _near_bu(lat: float, lon: float, points: list[tuple[float, float]]) -> bool:
    # Quick bounding-box reject (~0.01 deg lat ~ 1.1 km) before haversine.
    for blat, blon in points:
        if abs(lat - blat) > 0.01 or abs(lon - blon) > 0.013:
            continue
        if _haversine_m(lat, lon, blat, blon) <= RADIUS_M:
            return True
    return False


def _pick(colmap: dict[str, int], names: tuple[str, ...]) -> int | None:
    for n in names:
        if n in colmap:
            return colmap[n]
    return None


def _parse_hour(value: str) -> tuple[str, int] | None:
    """Return (daytype, hour) from a timestamp string, or None."""
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value[:26], fmt)
            daytype = "weekend" if dt.weekday() >= 5 else "weekday"
            return daytype, dt.hour
        except ValueError:
            continue
    return None


def download() -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "202411-bluebikes-tripdata.zip"
    if zip_path.exists() and zip_path.stat().st_size > 0:
        print(f"Using cached download: {zip_path} ({zip_path.stat().st_size:,} bytes)")
        return zip_path
    print(f"Downloading {URL} ...")
    req = urllib.request.Request(URL, headers={"User-Agent": "eventtwin/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp, zip_path.open("wb") as out:
        total = 0
        while True:
            chunk = resp.read(1 << 20)  # 1 MB
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    print(f"Downloaded {total:,} bytes -> {zip_path}")
    return zip_path


def aggregate(zip_path: Path) -> Path:
    points = _load_building_points()
    if not points:
        print("ERROR: no building reference points; run build_db first.", file=sys.stderr)
        raise SystemExit(1)

    # starts[(daytype, hour)] and ends[(daytype, hour)]
    starts: dict[tuple[str, int], int] = defaultdict(int)
    ends: dict[tuple[str, int], int] = defaultdict(int)
    rows_seen = 0
    rows_kept = 0

    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv") and "__MACOSX" not in n]
        if not csv_names:
            print("ERROR: no CSV inside the zip.", file=sys.stderr)
            raise SystemExit(1)
        inner = csv_names[0]
        print(f"Streaming {inner} ...")
        with zf.open(inner) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.reader(text)
            header = next(reader)
            colmap = {h.strip(): i for i, h in enumerate(header)}
            i_st = _pick(colmap, START_TIME_COLS)
            i_et = _pick(colmap, END_TIME_COLS)
            i_slat = _pick(colmap, START_LAT_COLS)
            i_slng = _pick(colmap, START_LNG_COLS)
            i_elat = _pick(colmap, END_LAT_COLS)
            i_elng = _pick(colmap, END_LNG_COLS)
            if None in (i_st, i_slat, i_slng):
                print(f"ERROR: unexpected columns: {header}", file=sys.stderr)
                raise SystemExit(1)

            for row in reader:
                rows_seen += 1
                try:
                    slat = float(row[i_slat]); slng = float(row[i_slng])
                except (ValueError, IndexError):
                    slat = slng = None
                try:
                    elat = float(row[i_elat]) if i_elat is not None else None
                    elng = float(row[i_elng]) if i_elng is not None else None
                except (ValueError, IndexError):
                    elat = elng = None

                start_near = slat is not None and _near_bu(slat, slng, points)
                end_near = elat is not None and _near_bu(elat, elng, points)
                if not (start_near or end_near):
                    continue
                rows_kept += 1

                if start_near and i_st is not None:
                    parsed = _parse_hour(row[i_st])
                    if parsed:
                        starts[parsed] += 1
                if end_near and i_et is not None and i_et < len(row):
                    parsed = _parse_hour(row[i_et])
                    if parsed:
                        ends[parsed] += 1

                if rows_seen % 200000 == 0:
                    print(f"  ...{rows_seen:,} rows scanned, {rows_kept:,} near BU")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Bluebikes 202411 trips within 600 m of BU buildings; hourly starts/ends"])
        w.writerow(["daytype", "hour", "starts", "ends"])
        for daytype in ("weekday", "weekend"):
            for hour in range(24):
                w.writerow([daytype, hour, starts[(daytype, hour)], ends[(daytype, hour)]])

    print(f"Scanned {rows_seen:,} trips; kept {rows_kept:,} near BU.")
    print(f"Wrote {OUT_CSV}")
    return OUT_CSV


def main() -> None:
    zip_path = download()
    aggregate(zip_path)


if __name__ == "__main__":
    main()
