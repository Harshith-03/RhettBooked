"""
options.py

Lean / Balanced / Premium plan options for the Compare view (P1, task 17).

``build(brief, attendance)`` runs the budget three times, varying the catering
tier and the staffing/service level (AV, security, custodial hours scale), and
returns a comparable summary per tier: total p10/p50/p90, cost per attendee, and
the sponsorship gap. Wi-Fi/power are consumption (no cost) so they do not vary by
tier here.

Provenance: each tier's budget is SIMULATED (it reuses budget.estimate).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..provenance import ProvenanceRow
from . import budget as budget_mod

# Catering tier + service staffing scale per plan option.
TIERS = {
    "lean": {"tier": "lean", "service_scale": 0.75,
             "tradeoffs": "Cheapest catering; minimal AV/security/custodial hours"},
    "balanced": {"tier": "balanced", "service_scale": 1.0,
                 "tradeoffs": "Mid catering; standard staffing"},
    "premium": {"tier": "premium", "service_scale": 1.5,
                "tradeoffs": "Top catering; extended AV/security/custodial"},
}


@dataclass
class Option:
    name: str
    tier: str
    total_p10: int
    total_p50: int
    total_p90: int
    cost_per_attendee: float
    sponsorship_gap: int
    tradeoffs: str


@dataclass
class OptionsResult:
    options: list[Option]
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "options": [
                {
                    "name": o.name, "tier": o.tier,
                    "total_p10": o.total_p10, "total_p50": o.total_p50,
                    "total_p90": o.total_p90,
                    "cost_per_attendee": o.cost_per_attendee,
                    "sponsorship_gap": o.sponsorship_gap,
                    "tradeoffs": o.tradeoffs,
                }
                for o in self.options
            ]
        }


def build(brief, attendance, venue=None, draws: int = 500) -> OptionsResult:
    options: list[Option] = []
    prov: list[ProvenanceRow] = []
    for name, cfg in TIERS.items():
        b = budget_mod.estimate(
            brief, attendance, venue, draws=draws,
            tier=cfg["tier"], service_scale=cfg["service_scale"],
        )
        options.append(
            Option(
                name=name.capitalize(),
                tier=cfg["tier"],
                total_p10=b.total_p10,
                total_p50=b.total_p50,
                total_p90=b.total_p90,
                cost_per_attendee=b.cost_per_attendee_p50,
                sponsorship_gap=b.sponsorship_gap,
                tradeoffs=cfg["tradeoffs"],
            )
        )
        # One representative provenance row per tier.
        prov.append(
            ProvenanceRow(
                output_key=f"options.{name}.total",
                label="SIMULATED",
                source=f"budget Monte Carlo, tier={cfg['tier']}, service_scale={cfg['service_scale']}",
                value_summary=f"p50={b.total_p50}",
            )
        )
    return OptionsResult(options=options, provenance=prov)
