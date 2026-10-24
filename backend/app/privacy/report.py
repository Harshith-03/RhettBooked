"""
report.py

Aggregate suppression + privacy risk report (P1, tasks "Privacy P1" + 21).

- ``aggregate_counts(rows, column)`` -> category counts with any cell under 5
  people SUPPRESSED (reported as "<5" / dropped), so personal data survives only
  as safe aggregates.
- ``risk_report(rows)`` -> entities detected per column, a residual-PII scan
  (target 0 after scrubbing), and a simple k-anonymity check on quasi-identifiers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .scrubber import detect, scrub_rows

SUPPRESS_THRESHOLD = 5


@dataclass
class RiskReport:
    entities_per_column: dict[str, dict[str, int]]
    residual_pii: int
    k_anonymity_min: int
    n_rows: int
    note: str = ""


def aggregate_counts(rows: list[dict], column: str) -> dict[str, object]:
    """Counts by category for one column, suppressing cells under 5 people."""
    counts = Counter(str(r.get(column, "")).strip() for r in rows if r.get(column))
    kept: dict[str, int] = {}
    suppressed = 0
    for cat, n in counts.items():
        if n < SUPPRESS_THRESHOLD:
            suppressed += n
        else:
            kept[cat] = n
    return {
        "column": column,
        "counts": kept,
        "suppressed_cells": sum(1 for n in counts.values() if n < SUPPRESS_THRESHOLD),
        "suppressed_people": suppressed,
        "threshold": SUPPRESS_THRESHOLD,
    }


def risk_report(rows: list[dict], quasi_identifiers: list[str] | None = None) -> RiskReport:
    if not rows:
        return RiskReport({}, 0, 0, 0, note="no rows")

    columns = list(rows[0].keys())
    entities_per_column: dict[str, dict[str, int]] = {}
    for col in columns:
        c: Counter = Counter()
        for r in rows:
            v = r.get(col)
            if isinstance(v, str):
                for f in detect(v):
                    c[f.entity] += 1
        if c:
            entities_per_column[col] = dict(c)

    # Residual scan: after scrubbing, no PII should remain.
    scrubbed = scrub_rows(rows)
    residual = 0
    for r in scrubbed:
        for v in r.values():
            if isinstance(v, str):
                residual += len(detect(v))

    # k-anonymity: smallest group size over the quasi-identifier combination.
    qis = quasi_identifiers or [c for c in columns if c not in entities_per_column]
    if qis:
        groups: Counter = Counter(
            tuple(str(r.get(q, "")) for q in qis) for r in rows
        )
        k_min = min(groups.values()) if groups else 0
    else:
        k_min = len(rows)

    return RiskReport(
        entities_per_column=entities_per_column,
        residual_pii=residual,
        k_anonymity_min=k_min,
        n_rows=len(rows),
    )
