"""
explainer.py

Template explainer (P0, task 11).

``explain(plan)`` produces a grounded, human-readable summary of a plan dict. It
uses ONLY numbers that appear in the plan (the tool output) and cites the
provenance source ids that back the headline figures. It never introduces a
number that is not already in the plan.

This satisfies the correctness property "explainer grounding": every number in
the output also appears in the plan, and the sources come from plan.provenance.
"""

from __future__ import annotations

from typing import Any


def _money(n: Any) -> str:
    try:
        return f"${int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def _sources_for(plan: dict, prefixes: tuple[str, ...]) -> list[str]:
    """Collect distinct source strings for provenance keys matching prefixes."""
    rows = plan.get("provenance", []) or []
    out: list[str] = []
    seen = set()
    for r in rows:
        key = r.get("output_key", "")
        if key.startswith(prefixes):
            src = r.get("source", "")
            if src and src not in seen:
                seen.add(src)
                out.append(src)
    return out


def explain(plan: dict) -> str:
    """Return a grounded explanation sentence-set for a plan dict."""
    summary = plan.get("summary", {}) or {}
    lines: list[str] = []

    building = summary.get("recommended_building")
    if building:
        venue_src = _sources_for(plan, ("venue.",))
        cite = f" [source: {venue_src[0]}]" if venue_src else ""
        lines.append(f"Recommended venue: {building}{cite}.")

    p10, p50, p90 = summary.get("cost_p10"), summary.get("cost_p50"), summary.get("cost_p90")
    if p10 is not None and p90 is not None:
        budget_src = _sources_for(plan, ("budget.total",))
        cite = f" [source: {budget_src[0]}]" if budget_src else ""
        lines.append(
            f"Estimated cost {_money(p10)} to {_money(p90)} (p50 {_money(p50)}){cite}."
        )

    gap = summary.get("sponsorship_gap")
    if gap:
        lines.append(f"Sponsorship gap: {_money(gap)} (p50 cost minus budget).")

    readiness = summary.get("readiness")
    if readiness is not None:
        drill_src = _sources_for(plan, ("drill.readiness",))
        cite = f" [source: {drill_src[0]}]" if drill_src else ""
        lines.append(f"Drill readiness: {readiness}/100{cite}.")

    risks = summary.get("top_risks") or []
    if risks:
        lines.append("Top risks: " + "; ".join(str(r) for r in risks) + ".")

    turnout_p50 = summary.get("turnout_p50")
    turnout_p90 = summary.get("turnout_p90")
    if turnout_p50 is not None and turnout_p90 is not None:
        att_src = _sources_for(plan, ("attendance.turnout",))
        cite = f" [source: {att_src[0]}]" if att_src else ""
        lines.append(f"Expected turnout {turnout_p50}-{turnout_p90} (p50-p90){cite}.")

    if not lines:
        return "No results available to explain yet."
    return " ".join(lines)


def numbers_in(text: str) -> set[str]:
    """Extract integer-like VALUE tokens from text (used by grounding tests).

    Percentile labels like p10/p50/p90 are names, not data values, so digits
    immediately preceded by 'p' are excluded. The readiness denominator '/100'
    is likewise structural and excluded.
    """
    import re

    cleaned = re.sub(r"p\d{2}", "", text)          # drop p10/p50/p90 labels
    cleaned = cleaned.replace("/100", "")          # drop readiness denominator
    return set(re.findall(r"\d[\d,]*", cleaned))
