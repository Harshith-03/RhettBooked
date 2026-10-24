"""
main.py

FastAPI application skeleton for EventTwin.

Task 1 wires up the app, CORS for the Vite dev server, and three read endpoints
that already work under ``LLM_PROVIDER=none``:
  - GET /health        liveness + current LLM provider
  - GET /assumptions   the ASSUMED parameter table from config/assumptions.yaml
  - GET /provenance    the provenance table (label counts + rows)

The plan/drill/privacy endpoints from Requirement 12 are added in later tasks.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import brief as brief_pkg
from .config import load_assumptions, settings
from .provenance import ProvenanceStore

app = FastAPI(title="EventTwin", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BriefParseRequest(BaseModel):
    text: str


@app.post("/brief/parse")
def post_brief_parse(req: BriefParseRequest) -> dict[str, Any]:
    """Parse free text into an EventBrief plus any follow-up questions.

    Works under LLM_PROVIDER=none via the rule-based parser (task 3).
    """
    parsed, questions = brief_pkg.parse(req.text)
    return {
        "brief": parsed.model_dump(),
        "questions": [q.model_dump() for q in questions],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_enabled": settings.llm_enabled,
    }


@app.get("/assumptions")
def get_assumptions() -> dict[str, Any]:
    """Return the ASSUMED parameter table (value/range/source per parameter)."""
    return {"assumptions": load_assumptions()}


@app.get("/provenance")
def get_provenance() -> dict[str, Any]:
    """Return provenance label counts and rows from the DuckDB table."""
    store = ProvenanceStore()
    return {
        "label_counts": store.label_counts(),
        "rows": store.all(),
    }
