"""
Checkpoint 8a: thin post-API acceptance.

Confirms the app boots and, under LLM_PROVIDER=none, the acceptance brief flows
POST /brief/parse -> POST /plan and returns a 200 with a non-empty plan summary
(venue + budget present). Catches wiring/CORS/serialization breakage before the
frontend is built on top.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


def test_app_boots_under_llm_none():
    assert os.environ.get("LLM_PROVIDER", "none") == "none"
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["llm_provider"] == "none"


def test_parse_then_plan_returns_nonempty_summary():
    # 1. Parse the acceptance brief.
    parse_resp = client.post("/brief/parse", json={"text": BRIEF_A})
    assert parse_resp.status_code == 200
    parsed = parse_resp.json()
    assert parsed["brief"]["type"] == "hackathon"
    assert parsed["brief"]["budget_usd"] == 15000
    # Acceptance brief has every critical field -> no follow-up questions.
    assert parsed["questions"] == []

    # 2. Feed the parsed brief into /plan.
    plan_resp = client.post("/plan", json={"brief": parsed["brief"], "draws": 300})
    assert plan_resp.status_code == 200
    plan = plan_resp.json()

    # Non-empty summary with venue + budget present.
    summary = plan["summary"]
    assert summary["recommended_building"], "expected a recommended building"
    assert summary["cost_p50"] > 0
    assert summary["cost_p10"] <= summary["cost_p50"] <= summary["cost_p90"]
    assert isinstance(summary["readiness"], int)

    # Venue + budget sections are populated.
    assert plan["venue"]["recommended"]
    assert plan["budget"]["line_items"]

    # Provenance carries real labels (serialization intact end-to-end).
    labels = {row["label"] for row in plan["provenance"]}
    assert {"MEASURED", "ASSUMED", "SIMULATED"} <= labels


def test_text_only_plan_path_also_works():
    # The one-shot path (raw text straight to /plan) must also assemble a plan.
    r = client.post("/plan", json={"text": BRIEF_A, "draws": 200})
    assert r.status_code == 200
    assert r.json()["summary"]["recommended_building"]
