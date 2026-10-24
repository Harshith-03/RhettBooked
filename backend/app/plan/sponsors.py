"""
sponsors.py

Sponsor recommender (P1, task 19).

Matches the brief's topics to sponsor categories in
`data/placeholder/sponsors_placeholder.csv` (PLACEHOLDER archetypes, not real
companies) using **TF-IDF similarity** over each category's topic tags, ranks by
fit x typical-ask midpoint, and suggests an ask level that would cover the
budget gap.

Provenance: sponsor categories are PLACEHOLDER; the suggested ask is SIMULATED
(derived from the budget gap).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..config import PLACEHOLDER_DIR
from ..provenance import Label, ProvenanceRow
from .people import embed   # reuse the TF-IDF embed seam

SPONSORS_CSV = PLACEHOLDER_DIR / "sponsors_placeholder.csv"
SIMILARITY_NAME = "TF-IDF similarity"


@dataclass
class SponsorCategory:
    label: str
    industry: str
    typical_ask: str
    typical_range_usd: str
    fit: float
    matched_topics: list[str]


@dataclass
class SponsorResult:
    categories: list[SponsorCategory]
    budget_gap: int
    suggested_ask_level: str
    similarity_method: str
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "budget_gap": self.budget_gap,
            "suggested_ask_level": self.suggested_ask_level,
            "similarity_method": self.similarity_method,
            "categories": [
                {"label": c.label, "industry": c.industry,
                 "typical_ask": c.typical_ask, "typical_range_usd": c.typical_range_usd,
                 "fit": round(c.fit, 4), "matched_topics": c.matched_topics}
                for c in self.categories
            ],
        }


def _load_sponsors() -> list[dict]:
    if not SPONSORS_CSV.exists():
        return []
    with SPONSORS_CSV.open(encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    if not rows:
        return []
    header = rows[0]
    idx = {name: header.index(name) for name in header}
    out = []
    for r in rows[1:]:
        out.append({
            "label": r[idx["label"]],
            "industry": r[idx["industry"]],
            "typical_ask": r[idx["typical_ask"]],
            "typical_range_usd": r[idx["typical_range_usd"]],
            "topic_tags": r[idx["topic_tags"]],
        })
    return out


def _range_mid(rng: str) -> float:
    try:
        lo, hi = rng.split("-")
        return (float(lo) + float(hi)) / 2
    except (ValueError, AttributeError):
        return 0.0


def recommend(brief, budget_gap: int = 0, top_n: int = 6) -> SponsorResult:
    sponsors = _load_sponsors()
    topics = list(getattr(brief, "topics", []) or [])
    query = " ".join(topics) or (getattr(brief, "description", "") or "")

    if not sponsors or not query.strip():
        return SponsorResult(
            categories=[], budget_gap=budget_gap,
            suggested_ask_level="n/a", similarity_method=SIMILARITY_NAME,
            provenance=[ProvenanceRow(
                output_key="sponsors.recommend", label=Label.PLACEHOLDER,
                source="sponsors_placeholder.csv", value_summary="no match")],
        )

    corpus = [query] + [s["topic_tags"].replace("|", " ") for s in sponsors]
    vec, matrix = embed(corpus)
    q = matrix[0]
    docs = matrix[1:]
    sims = (docs @ q.T).toarray().ravel()

    scored: list[SponsorCategory] = []
    for s, sim in zip(sponsors, sims):
        if sim <= 0:
            continue
        matched = [t for t in s["topic_tags"].split("|")
                   if any(tok.lower() in t.lower() for tok in query.split())][:4]
        fit = float(sim) * (1 + _range_mid(s["typical_range_usd"]) / 20000.0)
        scored.append(SponsorCategory(
            label=s["label"], industry=s["industry"], typical_ask=s["typical_ask"],
            typical_range_usd=s["typical_range_usd"], fit=fit, matched_topics=matched,
        ))
    scored.sort(key=lambda c: -c.fit)
    top = scored[:top_n]

    # Suggested ask: a per-sponsor level across the top categories that covers the gap.
    suggested = "n/a"
    if budget_gap > 0 and top:
        per_sponsor = budget_gap / max(1, len(top))
        if per_sponsor <= 1000:
            suggested = "$250-1,000 each"
        elif per_sponsor <= 2500:
            suggested = "$1,000-2,500 each"
        elif per_sponsor <= 5000:
            suggested = "$2,500-5,000 each"
        else:
            suggested = "$5,000-10,000+ each"

    prov = [
        ProvenanceRow(
            output_key="sponsors.recommend", label=Label.PLACEHOLDER,
            source=f"sponsors_placeholder.csv ranked by {SIMILARITY_NAME} x typical ask",
            value_summary=f"{len(top)} categories",
        ),
    ]
    if budget_gap > 0:
        prov.append(ProvenanceRow(
            output_key="sponsors.suggested_ask", label=Label.SIMULATED,
            source="budget gap / number of top sponsor categories",
            value_summary=suggested,
        ))

    return SponsorResult(
        categories=top, budget_gap=budget_gap, suggested_ask_level=suggested,
        similarity_method=SIMILARITY_NAME, provenance=prov,
    )
