"""
main.py

FastAPI application for EventTwin (task 8).

Endpoints (Requirement 12), all working under ``LLM_PROVIDER=none``:
  POST /brief/parse     free text -> EventBrief + follow-up questions
  POST /plan            brief -> full Plan (attendance, venue, budget, drill)
  POST /plan/options    Lean/Balanced/Premium compare (P1 stub, labelled)
  POST /drill/run       re-run the drill for a brief (optionally with disruptions)
  POST /drill/compare   before/after a set of applied fixes
  POST /privacy/upload  scrub + aggregate an uploaded CSV (task 10 stub, labelled)
  GET  /provenance      provenance label counts + rows
  GET  /assumptions     the ASSUMED parameter table
  GET  /live/alerts     planned MBTA disruptions from the real stops dataset
  GET  /health          liveness + current LLM provider

CORS is enabled for the Vite dev server (http://localhost:5173).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import brief as brief_pkg
from .brief.models import EventBrief
from .config import load_assumptions, settings
from .data import loaders
from .drill import twin as twin_mod
from .drill import verdict as verdict_mod
from .plan import plan as plan_mod
from .provenance import ProvenanceStore

app = FastAPI(title="EventTwin", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class BriefParseRequest(BaseModel):
    text: str


class PlanRequest(BaseModel):
    """Accept either raw text or an already-parsed brief."""

    text: str | None = None
    brief: dict[str, Any] | None = None
    draws: int = 500


class DrillRunRequest(BaseModel):
    text: str | None = None
    brief: dict[str, Any] | None = None
    disruptions: list[str] = Field(default_factory=list)


class DrillCompareRequest(BaseModel):
    text: str | None = None
    brief: dict[str, Any] | None = None
    applied_fixes: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_brief(text: str | None, brief_dict: dict[str, Any] | None) -> EventBrief:
    if brief_dict:
        return EventBrief(**brief_dict)
    parsed, _ = brief_pkg.parse(text or "")
    return parsed


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #
@app.post("/brief/parse")
def post_brief_parse(req: BriefParseRequest) -> dict[str, Any]:
    parsed, questions = brief_pkg.parse(req.text)
    return {
        "brief": parsed.model_dump(),
        "questions": [q.model_dump() for q in questions],
    }


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #
@app.post("/plan")
def post_plan(req: PlanRequest) -> dict[str, Any]:
    brief = _resolve_brief(req.text, req.brief)
    plan = plan_mod.build(brief, draws=req.draws)
    return plan.to_dict()


@app.post("/plan/options")
def post_plan_options(req: PlanRequest) -> dict[str, Any]:
    """Lean/Balanced/Premium compare - deepened in P1 (task 17).

    Returns the base plan plus a labelled placeholder note so the frontend has a
    stable shape to render.
    """
    brief = _resolve_brief(req.text, req.brief)
    plan = plan_mod.build(brief, draws=req.draws)
    return {
        "base": plan.to_dict(),
        "options": {"lean": None, "balanced": None, "premium": None},
        "note": "Lean/Balanced/Premium compare is P1 (task 17); base plan shown.",
    }


# --------------------------------------------------------------------------- #
# Drill
# --------------------------------------------------------------------------- #
@app.post("/drill/run")
def post_drill_run(req: DrillRunRequest) -> dict[str, Any]:
    brief = _resolve_brief(req.text, req.brief)
    ctx = plan_mod.drill_context_for(brief)
    result = twin_mod.run(ctx, disruptions=req.disruptions)
    v = verdict_mod.assess(result)
    return {
        "readiness": v.readiness,
        "worst_status": v.worst_status,
        "systems": [
            {"system": sv.system, "status": sv.status,
             "first_failure_clock": sv.first_failure_clock, "note": sv.note,
             "fixes": sv.fixes}
            for sv in v.systems
        ],
        "top_risks": v.top_risks,
        "fixes": v.fixes,
        "disruptions": result.disruptions,
        "planned_disruptions": result.planned_disruptions,
    }


@app.post("/drill/compare")
def post_drill_compare(req: DrillCompareRequest) -> dict[str, Any]:
    brief = _resolve_brief(req.text, req.brief)
    ctx = plan_mod.drill_context_for(brief)
    return verdict_mod.rerun(ctx, req.applied_fixes)


# --------------------------------------------------------------------------- #
# Privacy (task 10 - stub that preserves the response shape)
# --------------------------------------------------------------------------- #
@app.post("/privacy/upload")
def post_privacy_upload() -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "note": "Privacy scrubber + aggregate suppression is task 10.",
        "aggregates": {},
    }


# --------------------------------------------------------------------------- #
# Live alerts (real planned disruptions from the stops dataset)
# --------------------------------------------------------------------------- #
@app.get("/live/alerts")
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
            "raw": d.raw,
        })
    return {"alerts": list(seen.values()), "source": "mbta_stations_bu.csv (MEASURED)"}


# --------------------------------------------------------------------------- #
# Read endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_enabled": settings.llm_enabled,
    }


@app.get("/assumptions")
def get_assumptions() -> dict[str, Any]:
    return {"assumptions": load_assumptions()}


@app.get("/provenance")
def get_provenance() -> dict[str, Any]:
    store = ProvenanceStore()
    return {
        "label_counts": store.label_counts(),
        "rows": store.all(),
    }
