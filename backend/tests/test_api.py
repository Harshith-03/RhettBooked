"""Task 8 tests: API endpoints + CORS, all under LLM_PROVIDER=none."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")
BRIEF_B = ("300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


def test_runs_under_llm_none():
    assert os.environ.get("LLM_PROVIDER", "none") == "none"
    assert client.get("/health").json()["llm_provider"] == "none"


def test_cors_header_for_vite_origin():
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_brief_parse_endpoint():
    r = client.post("/brief/parse", json={"text": BRIEF_A})
    assert r.status_code == 200
    b = r.json()["brief"]
    assert b["type"] == "hackathon"
    assert b["budget_usd"] == 15000


def test_all_endpoints_exist_and_respond():
    for path in ("/assumptions", "/provenance", "/live/alerts", "/health"):
        assert client.get(path).status_code == 200
    # /privacy/upload requires a file upload (multipart).
    r = client.post(
        "/privacy/upload",
        files={"file": ("x.csv", b"name,email\nJane,j@bu.edu\n", "text/csv")},
    )
    assert r.status_code == 200


def test_plan_endpoint_returns_full_plan():
    r = client.post("/plan", json={"text": BRIEF_A, "draws": 200})
    assert r.status_code == 200
    plan = r.json()
    assert set(plan.keys()) >= {"summary", "venue", "budget", "attendance", "tiles", "provenance"}
    s = plan["summary"]
    assert s["recommended_building"] is not None
    assert s["cost_p10"] <= s["cost_p50"] <= s["cost_p90"]
    assert isinstance(s["readiness"], int)


def test_plan_options_endpoint_shape():
    r = client.post("/plan/options", json={"text": BRIEF_A, "draws": 150})
    assert r.status_code == 200
    body = r.json()
    assert "options" in body and len(body["options"]) == 3
    assert {o["name"] for o in body["options"]} == {"Lean", "Balanced", "Premium"}


def test_drill_run_endpoint_brief_b_includes_green_line():
    r = client.post("/drill/run", json={"text": BRIEF_B})
    assert r.status_code == 200
    body = r.json()
    assert any("Green Line" in d for d in body["disruptions"])
    assert body["planned_disruptions"]
    assert any("Green Line" in risk for risk in body["top_risks"])


def test_drill_run_brief_a_no_green_line():
    r = client.post("/drill/run", json={"text": BRIEF_A})
    body = r.json()
    assert not any("Green Line" in d for d in body["disruptions"])


def test_drill_compare_before_after():
    r = client.post("/drill/compare", json={
        "text": BRIEF_A,
        "applied_fixes": {"add_room_capacity": 200, "add_power_circuits": 5},
    })
    assert r.status_code == 200
    body = r.json()
    assert "before" in body and "after" in body
    assert body["after"]["readiness"] >= body["before"]["readiness"]


def test_live_alerts_has_green_line_closure():
    r = client.get("/live/alerts")
    alerts = r.json()["alerts"]
    assert any("Green Line" in " ".join(a["lines"]) for a in alerts)
    gl = next(a for a in alerts if "Green Line" in " ".join(a["lines"]))
    assert gl["start_date"] == "2026-10-31"
    assert gl["fare_free"] is True


def test_privacy_upload_scrubs_csv():
    csv_bytes = (
        "name,email,bu_id,device\n"
        "Jane,jane@bu.edu,U12345678,00:1A:2B:3C:4D:5E\n"
    ).encode("utf-8")
    r = client.post(
        "/privacy/upload",
        files={"file": ("reg.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "scrubbed"
    assert body["residual_pii"] == 0
    assert body["findings"].get("EMAIL", 0) >= 1
    assert body["findings"].get("BU_ID", 0) >= 1
    assert "jane@bu.edu" not in body["preview"]
    assert "U12345678" not in body["preview"]
