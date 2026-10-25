"""Research agent + job API tests (mocked Gemini/search, no network)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.app.agent import research as research_mod
from backend.app.brief.models import EventBrief, EventType
from backend.app.main import app
from backend.app.plan import plan as plan_mod

client = TestClient(app)

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


def _plan_dict():
    brief = EventBrief(
        type=EventType.hackathon, description="AI hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=300, topics=["ai", "machine-learning"],
        meals=["lunch", "dinner"],
    )
    p = plan_mod.build(brief, draws=200).to_dict()
    p["brief"] = brief.model_dump()
    return p


# A fake Gemini generate: returns items + grounded sources.
def _fake_generate(_prompt: str):
    return {
        "text": "Dumpling House\nBoston Catering Co\nFar Away Kitchen",
        "sources": [
            {"url": "https://dumplinghouse.com/catering", "title": "Dumpling House"},
            {"url": "https://bostoncatering.com", "title": "Boston Catering"},
        ],
    }


# A fake OSM fetch for the caterer cross-check.
def _fake_osm_fetch(_query: str):
    return {"elements": [
        {"type": "node", "id": 1, "lat": 42.3506, "lon": -71.1055,
         "tags": {"name": "Dumpling House", "cuisine": "chinese",
                  "website": "https://dumplinghouse.com"}},
        {"type": "node", "id": 2, "lat": 42.3509, "lon": -71.1060,
         "tags": {"name": "Boston Catering Co", "cuisine": "american"}},
    ]}


# --------------------------------------------------------------------------- #
# No-key fallback (default test env forces LLM_PROVIDER=none, GEMINI_API_KEY="")
# --------------------------------------------------------------------------- #
def test_catering_no_key_returns_fallback():
    result = research_mod.research_catering(_plan_dict())
    assert result["fallback_reason"]
    assert "GEMINI_API_KEY" in result["fallback_reason"]
    assert result["label"] == "ASSUMED"   # fallback, not RESEARCHED


def test_people_no_key_still_returns_openalex_judges():
    result = research_mod.research_people(_plan_dict())
    # OpenAlex judges are real and need no key.
    assert len(result["judges"]) >= 1
    assert all(j["research_data"] for j in result["judges"])
    assert result["fallback_reason"]   # speakers/sponsors need a key


# --------------------------------------------------------------------------- #
# With mocked Gemini + OSM: verified caterers, sources required
# --------------------------------------------------------------------------- #
def test_catering_with_mocks_verifies_and_requires_sources():
    result = research_mod.research_catering(
        _plan_dict(), generate=_fake_generate, osm_fetch=_fake_osm_fetch
    )
    assert result["label"] == "RESEARCHED"
    all_caterers = [c for m in result["meals"] for c in m["caterers"]]
    assert all_caterers, "expected caterers from the mocked search"
    # Every caterer carries a source URL (unsourced ones are dropped).
    assert all(c["source_urls"] for c in all_caterers)
    # Dumpling House matches OSM -> VERIFIED.
    assert any(c["verification"] == "VERIFIED" for c in all_caterers)


def test_people_with_mocked_search_scrubs_and_sources():
    def gen_with_pii(_p):
        return {
            "text": "Prof X at x@bu.edu\nDr Y call 617-555-0123",
            "sources": [{"url": "https://bu.edu/x", "title": "BU"}],
        }
    result = research_mod.research_people(_plan_dict(), generate=gen_with_pii)
    web_people = result["speakers"] + result["sponsors"]
    for p in web_people:
        assert "@" not in p["name"]
        assert "617-555-0123" not in p["name"]
        assert "Contact through official channels." in p["note"]


# --------------------------------------------------------------------------- #
# Job API
# --------------------------------------------------------------------------- #
def test_agent_research_job_lifecycle():
    r = client.post("/agent/research", json={"text": BRIEF_A, "task": "catering"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Poll until done (no key -> fallback, finishes fast).
    for _ in range(50):
        job = client.get(f"/agent/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "done"
    assert job["steps"]                       # human-readable progress
    assert job["result"] is not None


def test_agent_research_rejects_bad_task():
    r = client.post("/agent/research", json={"text": BRIEF_A, "task": "hacking"})
    assert r.status_code == 400


def test_agent_job_not_found():
    assert client.get("/agent/jobs/doesnotexist").status_code == 404


# --------------------------------------------------------------------------- #
# A provider error must NEVER leak into the serialized fallback reason
# (operating rule: snapshots/results carry no API error text or secrets).
# --------------------------------------------------------------------------- #
def test_provider_error_text_not_leaked_into_catering_fallback():
    def boom(_prompt):
        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED {'error': {'message': 'quota', 'key': 'SECRET'}}"
        )

    res = research_mod.research_catering(_plan_dict(), generate=boom, osm_fetch=_fake_osm_fetch)
    reason = res["fallback_reason"] or ""
    assert res["label"] == "ASSUMED"
    # Clean, classified reason only - no raw provider dump, no braces/JSON/secret.
    assert "rate-limited" in reason.lower()
    assert "RESOURCE_EXHAUSTED" not in reason
    assert "{" not in reason and "SECRET" not in reason


def test_provider_error_text_not_leaked_into_people_reason():
    def boom(_prompt):
        raise RuntimeError("403 PERMISSION_DENIED api_key=SECRET")

    res = research_mod.research_people(_plan_dict(), generate=boom)
    reason = res["fallback_reason"] or ""
    # Judges (OpenAlex) are still real; the reason is sanitized.
    assert len(res["judges"]) >= 1
    assert "SECRET" not in reason
    assert "api_key" not in reason
    assert "{" not in reason