"""
arrival_fit.py

Fit an arrival/departure PRESENCE shape from real mobility data (task 13).

Source (committed): data/raw/v3/bluebikes/bu_hourly_nov2024.csv - hourly trip
starts/ends within 600 m of BU buildings, split weekday/weekend. (Numina
pedestrian profiles will be blended in once available; see METHODS.md.)

Model: treat hourly trip STARTS as a proxy for the arrival rate and ENDS as the
departure rate near the venue. The presence profile over the day is the running
balance of arrivals minus departures, floored at 0 and normalized to [0, 1].
That normalized hourly profile is smoothed and resampled to 15-minute blocks and
used as the concurrency SHAPE, replacing the trapezoid. The trapezoid remains the
fallback when the data file is absent.

Fit error is the RMSE between the smoothed fitted curve and the raw normalized
hourly profile (reported in METHODS.md).

The fitted curve is MEASURED-derived (it comes from real Bluebikes counts).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

_V3 = Path(__file__).resolve().parents[3] / "data" / "raw" / "v3"
BLUEBIKES_CSV = _V3 / "bluebikes" / "bu_hourly_nov2024.csv"
NUMINA_CSV = _V3 / "numina" / "data.csv"
NUMINA_LABEL = "Boston Numina sensor zones, 2020-21, not BU-specific"


@dataclass
class FittedShape:
    hourly_presence: np.ndarray    # length 24, normalized [0,1]
    rmse: float                    # fit error vs raw normalized profile
    source: str
    daytype: str
    numina_blended: bool = False


def _read_hourly(daytype: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (starts, ends) arrays of length 24 for the day type, or None."""
    if not BLUEBIKES_CSV.exists():
        return None
    starts = np.zeros(24)
    ends = np.zeros(24)
    import csv

    with BLUEBIKES_CSV.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            break  # consumed header via first non-comment line below
        f.seek(0)
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    # rows[0] is the header.
    header = rows[0]
    try:
        idx = {name: header.index(name) for name in ("daytype", "hour", "starts", "ends")}
    except ValueError:
        return None
    for r in rows[1:]:
        if r[idx["daytype"]] != daytype:
            continue
        h = int(r[idx["hour"]])
        starts[h] = float(r[idx["starts"]])
        ends[h] = float(r[idx["ends"]])
    if starts.sum() == 0:
        return None
    return starts, ends


def _read_numina_pedestrian(daytype: str) -> np.ndarray | None:
    """Hourly pedestrian count profile (length 24, normalized) for the day type.

    Aggregates object=pedestrian rows from the Numina export. Citywide, 2020-21,
    not BU-specific - a weak shape prior blended with Bluebikes.
    """
    if not NUMINA_CSV.exists():
        return None
    import csv
    from datetime import datetime

    hourly = np.zeros(24)
    with NUMINA_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("object") or "").strip().lower() != "pedestrian":
                continue
            try:
                count = float(row.get("count") or 0)
            except ValueError:
                continue
            if count <= 0:
                continue
            ts = (row.get("time") or "").strip()
            try:
                dt = datetime.fromisoformat(ts)
            except ValueError:
                continue
            is_weekend = dt.weekday() >= 5
            if (daytype == "weekend") != is_weekend:
                continue
            hourly[dt.hour] += count
    if hourly.sum() == 0:
        return None
    return hourly / hourly.max()


def _presence_from_flows(starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Running balance of arrivals minus departures, floored at 0, normalized."""
    # Normalize flows to the same scale first (daily totals differ slightly).
    bal = np.cumsum(starts - ends)
    bal = bal - bal.min()          # floor at 0
    peak = bal.max()
    if peak <= 0:
        # Degenerate: fall back to the raw starts profile.
        prof = starts / (starts.max() or 1.0)
        return prof
    return bal / peak


def _smooth(profile: np.ndarray, window: int = 3) -> np.ndarray:
    """Simple centered moving-average smoother (wrap-free, edge-preserving)."""
    kernel = np.ones(window) / window
    padded = np.pad(profile, (window // 2, window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(profile)]


@lru_cache(maxsize=4)
def fit(daytype: str = "weekend") -> FittedShape | None:
    """Fit the hourly presence shape for a day type from Bluebikes data."""
    flows = _read_hourly(daytype)
    if flows is None:
        return None
    starts, ends = flows
    raw = _presence_from_flows(starts, ends)

    # Blend in the Numina pedestrian profile as a weak citywide prior, if present.
    numina = _read_numina_pedestrian(daytype)
    numina_blended = False
    if numina is not None:
        # Numina is a raw hourly intensity; convert to presence by the same
        # running-balance idea is not meaningful (it's a count, not a flow), so
        # use it directly as a shape prior and blend with Bluebikes presence.
        combined = 0.7 * raw + 0.3 * numina
        raw = combined / (combined.max() or 1.0)
        numina_blended = True

    smoothed = _smooth(raw, window=3)
    if smoothed.max() > 0:
        smoothed = smoothed / smoothed.max()
    rmse = float(np.sqrt(np.mean((smoothed - raw) ** 2)))

    source = "Bluebikes 202411 hourly trips within 600 m of BU (MEASURED-derived)"
    if numina_blended:
        source += f"; blended 70/30 with {NUMINA_LABEL}"
    return FittedShape(
        hourly_presence=smoothed,
        rmse=rmse,
        source=source,
        daytype=daytype,
        numina_blended=numina_blended,
    )


def shape_for_blocks(n_blocks: int, daytype: str = "weekend") -> np.ndarray | None:
    """Resample the fitted hourly presence to ``n_blocks`` 15-minute blocks.

    Returns None when no fit data is available (caller falls back to trapezoid).
    The event is assumed to start at ~09:00; the curve is sampled starting there
    and wraps across the day/overnight span the blocks cover.
    """
    fitted = fit(daytype)
    if fitted is None or n_blocks <= 0:
        return None
    hourly = fitted.hourly_presence
    start_hour = 9
    # Each block is 15 min; hour index advances every 4 blocks, wrapping at 24h.
    out = np.empty(n_blocks)
    for i in range(n_blocks):
        hour_pos = (start_hour + i / 4.0) % 24.0
        lo = int(np.floor(hour_pos)) % 24
        hi = (lo + 1) % 24
        frac = hour_pos - np.floor(hour_pos)
        out[i] = (1 - frac) * hourly[lo] + frac * hourly[hi]
    # Normalize so the peak block sits at 1.0 (presence fraction of turnout).
    if out.max() > 0:
        out = out / out.max()
    return out
