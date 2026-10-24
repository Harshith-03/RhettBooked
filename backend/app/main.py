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

from collections import Counter

from fastapi import UploadFile

from . import brief as brief_pkg
from .agent import explainer as explainer_mod
from .brief.models import EventBrief
from .config import load_assumptions, settings
from .data import loaders
from .drill import twin as twin_mod
from .drill import verdict as verdict_mod
from .plan import plan as plan_mod
from .privacy import detect as privacy_detect
from .privacy import scrub as privacy_scrub
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


@app.post("/explain")
def post_explain(req: PlanRequest) -> dict[str, Any]:
    """Return a grounded, source-cited narrative for a brief's plan (task 11)."""
    brief = _resolve_brief(req.text, req.brief)
    plan = plan_mod.build(brief, draws=req.draws).to_dict()
    return {"explanation": explainer_mod.explain(plan)}


@app.post("/plan/options")
def post_plan_options(req: PlanRequest) -> dict[str, Any]:
    """Lean/Balanced/Premium compare (task 17)."""
    brief = _resolve_brief(req.text, req.brief)
    att = plan_mod.attendance_mod.sample(brief, draws=req.draws)
    result = plan_mod.options_mod.build(brief, att, draws=req.draws)
    return result.as_dict()


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
async def post_privacy_upload(file: UploadFile) -> dict[str, Any]:
    """Scrub PII from an uploaded CSV and return per-entity counts + a preview.

    The scrubber core (task 10) redacts emails, BU IDs, MAC/BSSID, and phones.
    The aggregate-only retention + <5-cell suppression path is P1 (task 10 notes).
    """
    raw = (await file.read()).decode("utf-8", errors="replace")
    counts: Counter[str] = Counter()
    scrubbed_lines: list[str] = []
    for line in raw.splitlines():
        for f in privacy_detect(line):
            counts[f.entity] += 1
        scrubbed_lines.append(privacy_scrub(line).scrubbed)
    scrubbed_text = "\n".join(scrubbed_lines)
    # Residual check: scrubbing again should find nothing.
    residual = len(privacy_detect(scrubbed_text))
    return {
        "status": "scrubbed",
        "filename": file.filename,
        "findings": dict(counts),
        "residual_pii": residual,
        "preview": scrubbed_text[:2000],
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
