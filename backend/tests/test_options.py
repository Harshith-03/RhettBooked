"""Task 17 tests: Lean/Balanced/Premium plan options."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.brief.models import EventBrief, EventType
from backend.app.main import app
from backend.app.plan import attendance as att_mod
from backend.app.plan import options as opt_mod

client = TestClient(app)


def _brief():
    return EventBrief(
        type=EventType.hackathon, description="overnight AI hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=300, budget_usd=15000,
        meals=["breakfast", "lunch", "snack", "dinner"],
    )


def test_three_options_returned():
    att = att_mod.sample(_brief(), draws=400)
    res = opt_mod.build(_brief(), att, draws=400)
    names = [o.name for o in res.options]
    assert names == ["Lean", "Balanced", "Premium"]


def test_premium_costs_more_than_lean():
    att = att_mod.sample(_brief(), draws=400)
    res = opt_mod.build(_brief(), att, draws=400)
    by = {o.name: o for o in res.options}
    assert by["Lean"].total_p50 < by["Balanced"].total_p50 < by["Premium"].total_p50


def test_each_option_has_tradeoffs_and_gap():
    att = att_mod.sample(_brief(), draws=300)
    res = opt_mod.build(_brief(), att, draws=300)
    for o in res.options:
        assert o.tradeoffs
        assert o.total_p10 <= o.total_p50 <= o.total_p90
        assert o.sponsorship_gap == o.total_p50 - 15000


def test_options_endpoint():
    r = client.post("/plan/options", json={"text": (
        "300-person overnight AI hackathon at BU, Oct 24-25, students, budget "
        "$15k, needs lunch, dinner, midnight snack, breakfast"
    ), "draws": 300})
    assert r.status_code == 200
    opts = r.json()["options"]
    assert len(opts) == 3
    assert {o["name"] for o in opts} == {"Lean", "Balanced", "Premium"}
