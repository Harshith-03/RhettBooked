"""
tools.py

Agent tool layer (P0, task 11).

A small, named set of tools the agent (and the explainer) call. Each tool wraps a
domain service and returns plain dict output plus the provenance rows that back
its numbers, so the explainer can cite source ids and never invent figures.

Tools:
  parse_brief(text)                      -> brief + questions
  build_plan(brief|text)                 -> full plan dict (+ provenance)
  compare_options(brief|text, fixes)     -> drill before/after
  run_drill(brief|text, disruptions)     -> drill verdict
  get_live_alerts()                      -> planned MBTA disruptions
  get_provenance()                       -> provenance label counts + rows
"""

from __future__ import annotations

from typing import Any

from .. import brief as brief_pkg
from ..brief.models import EventBrief
from ..data import loaders
from ..drill import twin as twin_mod
from ..drill import verdict as verdict_mod
from ..plan import plan as plan_mod
from ..provenance import ProvenanceStore


def _resolve_brief(brief: dict | EventBrief | None, text: str | None) -> EventBrief:
    if isinstance(brief, EventBrief):
        return brief
    if isinstance(brief, dict):
        return EventBrief(**brief)
    parsed, _ = brief_pkg.parse(text or "")
    return parsed


def parse_brief(text: str) -> dict[str, Any]:
    parsed, questions = brief_pkg.parse(text)
    return {
        "brief": parsed.model_dump(),
        "questions": [q.model_dump() for q in questions],
    }


def build_plan(brief: dict | None = None, text: str | None = None, draws: int = 500) -> dict[str, Any]:
    b = _resolve_brief(brief, text)
    return plan_mod.build(b, draws=draws).to_dict()


def run_drill(brief: dict | None = None, text: str | None = None,
              disruptions: list[str] | None = None) -> dict[str, Any]:
    b = _resolve_brief(brief, text)
    ctx = plan_mod.drill_context_for(b)
    result = twin_mod.run(ctx, disruptions=disruptions or [])
    v = verdict_mod.assess(result)
    return {
        "readiness": v.readiness,
        "worst_status": v.worst_status,
        "top_risks": v.top_risks,
        "fixes": v.fixes,
        "disruptions": result.disruptions,
        "planned_disruptions": result.planned_disruptions,
    }


def compare_options(brief: dict | None = None, text: str | None = None,
                    applied_fixes: dict | None = None) -> dict[str, Any]:
    b = _resolve_brief(brief, text)
    ctx = plan_mod.drill_context_for(b)
    return verdict_mod.rerun(ctx, applied_fixes or {})


def get_live_alerts() -> dict[str, Any]:
    stops, _ = loaders.load_mbta_stops()
    seen: dict[str, dict[str, Any]] = {}
    for stop in stops:
        d = stop.disruption
        if not d:
            continue
        key = f"{d.start_date}|{d.end_date}|{','.join(d.lines)}"
        seen.setdefault(key, {
            "lines": d.lines,
            "start_date": d.start_date.isoformat() if d.start_date else None,
            "end_date": d.end_date.isoformat() if d.end_date else None,
            "shuttle_note": d.shuttle_note,
            "fare_free": d.fare_free,
        })
    return {"alerts": list(seen.values())}


def get_provenance() -> dict[str, Any]:
    store = ProvenanceStore()
    return {"label_counts": store.label_counts(), "rows": store.all()}


# Registry so callers can look tools up by name.
TOOLS = {
    "parse_brief": parse_brief,
    "build_plan": build_plan,
    "run_drill": run_drill,
    "compare_options": compare_options,
    "get_live_alerts": get_live_alerts,
    "get_provenance": get_provenance,
}
