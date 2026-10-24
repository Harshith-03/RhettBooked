"""
attendance.py

Thin attendance model + Monte Carlo harness (P0, task 4).

``sample(brief)`` turns an EventBrief into an :class:`AttendanceSamples` object:
a 15-minute concurrency curve with p50/p90 per block, driven by Monte Carlo over
a Beta show-up prior selected by event type and free/paid status (read from
``config/assumptions.yaml``).

What is thin here (deepened later in P1 task 13): the per-block arrival/departure
SHAPE is a deterministic trapezoid (with overnight decay for hackathons) rather
than a fit from Bluebikes/Numina live data. The STOCHASTIC part - how many people
show up - is the Monte Carlo over the Beta prior.

Provenance: turnout/concurrency outputs are SIMULATED; the Beta prior is ASSUMED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from ..brief.models import EventBrief, EventType
from ..config import load_assumptions
from ..provenance import Label, ProvenanceRow
from . import arrival_fit

BLOCK_MINUTES = 15
DEFAULT_DRAWS = 500
DEFAULT_SINGLE_DAY_HOURS = 9       # 9:00-18:00 default window when times are absent
DEFAULT_HACKATHON_HOURS = 36       # overnight hackathon default span


@dataclass
class BlockStat:
    """Per-block attendance statistics across the Monte Carlo draws."""

    index: int
    clock: str          # "HH:MM" wall-clock label for the block start
    minute_offset: int  # minutes from event start
    p50: int
    p90: int
    mean: float


@dataclass
class AttendanceSamples:
    """Monte Carlo attendance result for one event."""

    per_block: list[BlockStat]
    draws: int
    turnout_p50: int
    turnout_p90: int
    show_up_alpha: float
    show_up_beta: float
    source: str
    # Raw concurrency draws: shape (draws, n_blocks). Kept for downstream models.
    concurrency: np.ndarray = field(repr=False, default=None)
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def peak_p90(self) -> int:
        return max((b.p90 for b in self.per_block), default=0)


# --------------------------------------------------------------------------- #
# Beta prior selection
# --------------------------------------------------------------------------- #
def _select_beta(brief: EventBrief, assumptions: dict) -> tuple[float, float, str]:
    """Return (alpha, beta, source) for the show-up Beta prior.

    Free/paid is inferred: a positive budget with a paid audience would be 'paid',
    but the thin model treats events as 'free' unless the description says paid or
    ticketed. Hackathons/campus events are free by default.
    """
    table = (assumptions.get("show_up_rate") or {}).get("by_type") or {}
    etype = (brief.type.value if brief.type else "other")
    type_block = table.get(etype) or table.get("other") or {}

    desc = (brief.description or "").lower()
    is_paid = any(w in desc for w in ("paid", "ticketed", "ticket price", "registration fee"))
    price_key = "paid" if (is_paid and "paid" in type_block) else "free"
    if price_key not in type_block:
        price_key = next(iter(type_block), None)

    prior = type_block.get(price_key) if price_key else None
    if not prior:
        # Safe default prior if assumptions are missing.
        return 6.0, 4.0, "ASSUMED - default Beta(6,4) show-up prior"
    alpha = float(prior.get("alpha", 6))
    beta = float(prior.get("beta", 4))
    source = prior.get("source", f"assumptions.yaml show_up_rate.{etype}.{price_key}")
    return alpha, beta, source


# --------------------------------------------------------------------------- #
# Event window -> number of 15-min blocks
# --------------------------------------------------------------------------- #
def _event_window_minutes(brief: EventBrief) -> int:
    """Total event duration in minutes, from dates/times or type-based defaults."""
    # If explicit start/end dates differ, span midday-to-midday across the days.
    start_d = _parse_date(brief.start)
    end_d = _parse_date(brief.end)
    if start_d and end_d and end_d > start_d:
        days = (end_d - start_d).days
        # Overnight multi-day: continuous span. Cap at a reasonable duration.
        hours = min(24 * days + DEFAULT_SINGLE_DAY_HOURS, 24 * (days + 1))
        return int(hours * 60)
    if brief.type == EventType.hackathon and brief.overnight:
        return DEFAULT_HACKATHON_HOURS * 60
    if brief.overnight:
        return 24 * 60
    return DEFAULT_SINGLE_DAY_HOURS * 60


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Concurrency SHAPE (fraction of turnout present per block), in [0, 1]
# --------------------------------------------------------------------------- #
def concurrency_shape(n_blocks: int, overnight: bool, is_hackathon: bool) -> np.ndarray:
    """Deterministic trapezoidal presence fraction per block.

    - ramp up over the first ~10% of blocks (arrivals),
    - plateau near 1.0 during the day,
    - ramp down over the last ~10% (departures).
    For overnight hackathons, apply a dip through the overnight hours so fewer
    people are present while most sleep, recovering the next morning.
    """
    if n_blocks <= 0:
        return np.zeros(0)
    x = np.linspace(0.0, 1.0, n_blocks)
    ramp = max(1, int(round(0.10 * n_blocks)))
    shape = np.ones(n_blocks)
    # Arrival ramp (linear 0 -> 1).
    shape[:ramp] = np.linspace(0.15, 1.0, ramp)
    # Departure ramp (1 -> ~0.1).
    shape[-ramp:] = np.linspace(1.0, 0.10, ramp)

    if overnight and is_hackathon:
        shape = _apply_overnight_decay(shape)
    return np.clip(shape, 0.0, 1.0)


def _apply_overnight_decay(shape: np.ndarray) -> np.ndarray:
    """Dip presence through the overnight hours (~70% through the span)."""
    n = len(shape)
    if n == 0:
        return shape
    x = np.linspace(0.0, 1.0, n)
    night_center = 0.72
    width = 0.16
    dip = 0.55 * np.exp(-((x - night_center) ** 2) / (2 * width ** 2))
    return np.clip(shape * (1.0 - dip), 0.0, 1.0)


def _event_daytype(brief: EventBrief) -> str:
    """weekend when the event starts Sat/Sun, else weekday."""
    d = _parse_date(brief.start)
    if d is None:
        return "weekend"  # the acceptance events are weekend; safe default
    return "weekend" if d.weekday() >= 5 else "weekday"


# --------------------------------------------------------------------------- #
# Monte Carlo
# --------------------------------------------------------------------------- #
def sample(
    brief: EventBrief,
    draws: int = DEFAULT_DRAWS,
    seed: int = 42,
    assumptions: dict | None = None,
) -> AttendanceSamples:
    """Monte Carlo attendance curve for ``brief``."""
    assumptions = assumptions if assumptions is not None else load_assumptions()
    rng = np.random.default_rng(seed)

    alpha, beta, src = _select_beta(brief, assumptions)
    registrations = int(brief.expected_registrations or 0)

    total_minutes = _event_window_minutes(brief)
    n_blocks = max(1, total_minutes // BLOCK_MINUTES)

    is_hack = brief.type == EventType.hackathon

    # Prefer the data-fitted arrival/departure shape (Bluebikes near BU); fall
    # back to the trapezoid when no fit data is available.
    daytype = _event_daytype(brief)
    fitted = arrival_fit.shape_for_blocks(n_blocks, daytype=daytype)
    if fitted is not None:
        shape = fitted
        if brief.overnight and is_hack:
            shape = _apply_overnight_decay(shape)
        shape_source = arrival_fit.fit(daytype)
        shape_label = Label.MEASURED
        shape_desc = (shape_source.source if shape_source else "Bluebikes fit")
    else:
        shape = concurrency_shape(n_blocks, brief.overnight, is_hack)
        shape_label = Label.ASSUMED
        shape_desc = "trapezoidal fallback shape (no fit data)"

    # Draw show-up rates; turnout = registrations * rate.
    rates = rng.beta(alpha, beta, size=draws)
    turnout = rates * registrations  # shape (draws,)

    # Per-block concurrency = turnout[:, None] * shape[None, :], with mild noise.
    noise = rng.normal(1.0, 0.03, size=(draws, n_blocks))
    concurrency = turnout[:, None] * shape[None, :] * noise
    concurrency = np.clip(concurrency, 0.0, None)

    p50 = np.percentile(concurrency, 50, axis=0)
    p90 = np.percentile(concurrency, 90, axis=0)
    mean = concurrency.mean(axis=0)

    per_block: list[BlockStat] = []
    for i in range(n_blocks):
        offset = i * BLOCK_MINUTES
        per_block.append(
            BlockStat(
                index=i,
                clock=_clock_label(offset),
                minute_offset=offset,
                p50=int(round(p50[i])),
                p90=int(round(p90[i])),
                mean=float(mean[i]),
            )
        )

    turnout_p50 = int(round(float(np.percentile(turnout, 50))))
    turnout_p90 = int(round(float(np.percentile(turnout, 90))))

    prov = [
        ProvenanceRow(
            output_key="attendance.show_up_prior",
            label=Label.ASSUMED,
            source=src,
            value_summary=f"Beta(alpha={alpha}, beta={beta})",
        ),
        ProvenanceRow(
            output_key="attendance.turnout",
            label=Label.SIMULATED,
            source=f"Monte Carlo {draws} draws over the Beta show-up prior",
            value_summary=f"p50={turnout_p50}, p90={turnout_p90}",
        ),
        ProvenanceRow(
            output_key="attendance.concurrency_curve",
            label=Label.SIMULATED,
            source=f"Monte Carlo {draws} draws x {shape_desc}"
                   + (" + overnight decay" if (brief.overnight and is_hack) else ""),
            value_summary=f"{n_blocks} blocks of {BLOCK_MINUTES} min; peak p90="
                          f"{int(round(float(p90.max()))) if n_blocks else 0}",
        ),
        ProvenanceRow(
            output_key="attendance.arrival_shape",
            label=shape_label,
            source=shape_desc,
            value_summary=f"daytype={daytype}",
        ),
    ]

    return AttendanceSamples(
        per_block=per_block,
        draws=draws,
        turnout_p50=turnout_p50,
        turnout_p90=turnout_p90,
        show_up_alpha=alpha,
        show_up_beta=beta,
        source=src,
        concurrency=concurrency,
        provenance=prov,
    )


def _clock_label(minute_offset: int, start_hour: int = 9) -> str:
    """Wall-clock "HH:MM" label for a block starting `minute_offset` minutes in.

    Uses a 9:00 nominal start when the brief has no explicit start time.
    """
    total = start_hour * 60 + minute_offset
    hh = (total // 60) % 24
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"
