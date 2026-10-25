"""
budget.py

Probabilistic budget (P0, task 6).

``estimate(brief, attendance, venue)`` runs Monte Carlo over turnout and the
rate-card ranges (from ``data/placeholder/rate_cards.yaml``) to produce per
line-item and total p10/p50/p90 costs, cost per attendee, and the sponsorship
gap (p50 total minus the stated budget).

Provenance: budget outputs are SIMULATED; rate-card inputs are ASSUMED (the rate
cards are placeholder/assumed market ranges, not quotes).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import PLACEHOLDER_DIR
from ..provenance import Label, ProvenanceRow

DEFAULT_DRAWS = 500

# Default meal tier when the brief does not specify one.
DEFAULT_TIER = "balanced"


@dataclass
class LineItem:
    name: str
    p10: int
    p50: int
    p90: int


@dataclass
class BudgetResult:
    line_items: list[LineItem]
    total_p10: int
    total_p50: int
    total_p90: int
    cost_per_attendee_p50: float
    sponsorship_gap: int           # p50 total - budget (positive = shortfall)
    budget_usd: int | None
    draws: int
    tier: str = DEFAULT_TIER
    provenance: list[ProvenanceRow] = field(default_factory=list)


def _load_rate_cards() -> dict:
    path = PLACEHOLDER_DIR / "rate_cards.yaml"
    if not path.exists():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _tri(rng: np.ndarray, low: float, high: float, draws: int) -> np.ndarray:
    """Draws from a triangular distribution over [low, high] (mode at midpoint)."""
    if high <= low:
        return np.full(draws, low)
    mode = (low + high) / 2.0
    return rng.triangular(low, mode, high, size=draws)


def estimate(
    brief,
    attendance,
    venue=None,
    draws: int = DEFAULT_DRAWS,
    seed: int = 7,
    rate_cards: dict | None = None,
    tier: str = DEFAULT_TIER,
    service_scale: float = 1.0,
) -> BudgetResult:
    """Monte Carlo budget over turnout + rate-card ranges.

    tier selects the catering_per_head tier (lean/balanced/premium);
    service_scale scales staffing hours (AV/security/custodial) for the plan tier.
    """
    cards = rate_cards if rate_cards is not None else _load_rate_cards()
    rng = np.random.default_rng(seed)

    # Resources BU provides at no cash charge for recognised student events.
    # Any line whose in-kind token is listed is zeroed in the cash budget and
    # labelled "ASSUMED - BU resource (no charge)". Maps budget keys -> token.
    bu_in_kind = set(cards.get("bu_in_kind") or [])
    _IN_KIND_TOKEN = {
        "wifi": "wifi", "power": "power",
        "av_tech_per_hour": "av_tech",
        "security_police_detail_per_hour": "security",
        "custodial_per_hour": "custodial",
    }

    def _is_in_kind(budget_key: str) -> bool:
        return _IN_KIND_TOKEN.get(budget_key, budget_key) in bu_in_kind

    # Turnout draws: reuse the attendance Monte Carlo turnout percentiles to form
    # a per-draw turnout vector (lognormal-ish around p50 with p90 spread).
    t_p50 = max(1, getattr(attendance, "turnout_p50", 0) or 1)
    t_p90 = max(t_p50, getattr(attendance, "turnout_p90", t_p50))
    # Approximate per-draw turnout as a clipped normal with p90 ~ mean + 1.28 sd.
    sd = max(1.0, (t_p90 - t_p50) / 1.2816)
    turnout = np.clip(rng.normal(t_p50, sd, size=draws), 0, None)

    meals = list(getattr(brief, "meals", []) or [])
    line_cols: dict[str, np.ndarray] = {}
    prov: list[ProvenanceRow] = []

    # --- Catering per meal (per-head range from the rate card tier) ---
    catering = (cards.get("catering_per_head") or {}).get(tier, {})
    for meal in meals:
        rng_card = catering.get(meal) or catering.get("lunch") or {"low": 10, "high": 20}
        per_head = _tri(rng, float(rng_card["low"]), float(rng_card["high"]), draws)
        line_cols[f"Catering - {meal}"] = per_head * turnout
        prov.append(
            ProvenanceRow(
                output_key=f"budget.catering.{meal}",
                label=Label.ASSUMED,
                source=f"rate_cards.yaml catering_per_head.{tier}.{meal} (placeholder range)",
                value_summary=f"${rng_card['low']}-{rng_card['high']}/head",
            )
        )

    # --- Water (bottled as a simple baseline) ---
    water = cards.get("bottled_water_each") or {"low": 0.35, "high": 0.9}
    per_head_water = _tri(rng, float(water["low"]), float(water["high"]), draws) * 3
    line_cols["Water"] = per_head_water * turnout
    prov.append(_assumed("budget.water", "rate_cards.yaml bottled_water_each", "~3 bottles/head"))

    # --- Wi-Fi AP rental (scaled by venue rooms if available, else a default) ---
    ap = cards.get("temporary_wifi_ap_rental_per_ap_per_day") or {"low": 45, "high": 120}
    n_aps = 6  # thin default; tech sizing (task 14) refines this
    if _is_in_kind("wifi"):
        line_cols["Wi-Fi AP rental"] = np.zeros(draws)
        prov.append(_in_kind("budget.wifi", "campus Wi-Fi / temporary APs via IS&T"))
    else:
        line_cols["Wi-Fi AP rental"] = _tri(rng, float(ap["low"]), float(ap["high"]), draws) * n_aps
        prov.append(_assumed("budget.wifi", "rate_cards.yaml temporary_wifi_ap_rental_per_ap_per_day", f"{n_aps} APs"))

    # --- Power stations ---
    power = cards.get("power_strip_station_rental_each") or {"low": 8, "high": 25}
    n_power = 20
    if _is_in_kind("power"):
        line_cols["Power stations"] = np.zeros(draws)
        prov.append(_in_kind("budget.power", "existing building circuits"))
    else:
        line_cols["Power stations"] = _tri(rng, float(power["low"]), float(power["high"]), draws) * n_power
        prov.append(_assumed("budget.power", "rate_cards.yaml power_strip_station_rental_each", f"{n_power} stations"))

    # --- AV tech + security + custodial (hourly; tier scales staffing hours) ---
    hours = int(round(12 * service_scale))
    for key, label_name, default in (
        ("av_tech_per_hour", "AV tech", {"low": 45, "high": 110}),
        ("security_police_detail_per_hour", "Security", {"low": 55, "high": 95}),
        ("custodial_per_hour", "Custodial", {"low": 30, "high": 60}),
    ):
        if _is_in_kind(key):
            line_cols[label_name] = np.zeros(draws)
            prov.append(_in_kind(f"budget.{key}", f"{label_name} provided by BU for registered events"))
            continue
        card = cards.get(key) or default
        line_cols[label_name] = _tri(rng, float(card["low"]), float(card["high"]), draws) * hours
        prov.append(_assumed(f"budget.{key}", f"rate_cards.yaml {key}", f"{hours} hrs"))

    # --- Flat items: insurance, prizes, printing, swag per head ---
    for key, label_name in (("event_insurance_flat", "Insurance"),
                            ("prizes_total", "Prizes"),
                            ("printing_flat", "Printing")):
        card = cards.get(key) or {"low": 100, "high": 500}
        line_cols[label_name] = _tri(rng, float(card["low"]), float(card["high"]), draws)
        prov.append(_assumed(f"budget.{key}", f"rate_cards.yaml {key}", "flat"))

    swag = cards.get("swag_per_head") or {"low": 5, "high": 20}
    line_cols["Swag"] = _tri(rng, float(swag["low"]), float(swag["high"]), draws) * turnout
    prov.append(_assumed("budget.swag", "rate_cards.yaml swag_per_head", "per head"))

    # --- Contingency (percent of subtotal) ---
    subtotal = np.sum(np.stack(list(line_cols.values()), axis=0), axis=0)
    cont = cards.get("contingency_percent") or {"low": 5, "high": 15}
    cont_frac = _tri(rng, float(cont["low"]), float(cont["high"]), draws) / 100.0
    line_cols["Contingency"] = subtotal * cont_frac
    prov.append(_assumed("budget.contingency", "rate_cards.yaml contingency_percent", "% of subtotal"))

    # Assemble line items with percentiles.
    line_items: list[LineItem] = []
    for name, col in line_cols.items():
        line_items.append(
            LineItem(
                name=name,
                p10=int(round(float(np.percentile(col, 10)))),
                p50=int(round(float(np.percentile(col, 50)))),
                p90=int(round(float(np.percentile(col, 90)))),
            )
        )

    total = np.sum(np.stack(list(line_cols.values()), axis=0), axis=0)
    total_p10 = int(round(float(np.percentile(total, 10))))
    total_p50 = int(round(float(np.percentile(total, 50))))
    total_p90 = int(round(float(np.percentile(total, 90))))

    cost_per_attendee = round(total_p50 / t_p50, 2) if t_p50 else 0.0
    budget_usd = getattr(brief, "budget_usd", None)
    gap = int(total_p50 - budget_usd) if budget_usd else 0

    prov.append(
        ProvenanceRow(
            output_key="budget.total",
            label=Label.SIMULATED,
            source=f"Monte Carlo {draws} draws over turnout + rate-card ranges",
            value_summary=f"p10={total_p10}, p50={total_p50}, p90={total_p90}",
        )
    )
    if budget_usd:
        prov.append(
            ProvenanceRow(
                output_key="budget.sponsorship_gap",
                label=Label.SIMULATED,
                source="p50 total minus stated budget",
                value_summary=f"gap={gap}",
            )
        )

    return BudgetResult(
        line_items=line_items,
        total_p10=total_p10,
        total_p50=total_p50,
        total_p90=total_p90,
        cost_per_attendee_p50=cost_per_attendee,
        sponsorship_gap=gap,
        budget_usd=budget_usd,
        draws=draws,
        tier=tier,
        provenance=prov,
    )


def _assumed(key: str, source: str, summary: str) -> ProvenanceRow:
    return ProvenanceRow(output_key=key, label=Label.ASSUMED, source=source, value_summary=summary)


def _in_kind(key: str, what: str) -> ProvenanceRow:
    """A $0 line that BU provides in-kind for recognised student events."""
    return ProvenanceRow(
        output_key=key,
        label=Label.ASSUMED,
        source=f"ASSUMED - BU resource (no charge): {what}",
        value_summary="$0 (in-kind)",
    )
