"""Task 19 tests: sponsor recommender."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.brief.models import EventBrief, EventType
from backend.app.main import app
from backend.app.plan import sponsors as sp_mod

client = TestClient(app)


def _brief(topics=("ai", "machine-learning", "data")):
    return EventBrief(
        type=EventType.hackathon, description="AI hackathon",
        expected_registrations=300, budget_usd=15000, topics=list(topics),
    )


def test_recommend_returns_categories():
    res = sp_mod.recommend(_brief(), budget_gap=10000)
    assert res.categories
    assert res.similarity_method == "TF-IDF similarity"


def test_categories_ranked_by_fit():
    res = sp_mod.recommend(_brief(), budget_gap=10000)
    fits = [c.fit for c in res.categories]
    assert fits == sorted(fits, reverse=True)


def test_suggested_ask_scales_with_gap():
    small = sp_mod.recommend(_brief(), budget_gap=2000)
    big = sp_mod.recommend(_brief(), budget_gap=60000)
    assert small.suggested_ask_level != "n/a"
    assert big.suggested_ask_level != "n/a"
    # A bigger gap implies a higher per-sponsor ask tier.
    assert "5,000" in big.suggested_ask_level or "10,000" in big.suggested_ask_level


def test_zero_gap_gives_na_ask():
    res = sp_mod.recommend(_brief(), budget_gap=0)
    assert res.suggested_ask_level == "n/a"


def test_categories_are_placeholder_labelled():
    res = sp_mod.recommend(_brief(), budget_gap=5000)
    labels = {p.label for p in res.provenance}
    assert "PLACEHOLDER" in labels


def test_sponsors_endpoint():
    r = client.post("/sponsors", json={"text": (
        "300-person AI hackathon at BU, budget $15k, needs lunch"
    ), "draws": 200})
    assert r.status_code == 200
    body = r.json()
    assert "categories" in body
    assert body["budget_gap"] >= 0
