"""Task 18 tests: OpenAlex people recommender with TF-IDF ranking."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.brief.models import EventBrief, EventType
from backend.app.main import app
from backend.app.plan import people as people_mod

client = TestClient(app)


def _brief(topics):
    return EventBrief(
        type=EventType.hackathon, description="AI hackathon",
        expected_registrations=300, topics=topics,
    )


def test_recommend_returns_people_for_ai_topics():
    res = people_mod.recommend(_brief(["ai", "machine-learning", "data"]))
    assert res.people, "expected matching authors"
    assert res.similarity_method == "TF-IDF similarity"


def test_people_scored_descending():
    res = people_mod.recommend(_brief(["machine-learning", "health"]))
    scores = [p.score for p in res.people]
    assert scores == sorted(scores, reverse=True)


def test_only_public_fields_no_contact_or_demographics():
    res = people_mod.recommend(_brief(["ai"]))
    d = res.as_dict()
    for p in d["people"]:
        assert set(p.keys()) == {
            "name", "institution", "matching_topics", "citations",
            "latest_year", "openalex_url", "score",
        }
        # No email/contact/gender fields leak through.
        assert "@" not in p["name"]


def test_institution_diversity_cap():
    res = people_mod.recommend(_brief(["machine-learning", "data", "health"]))
    # No institution exceeds the diversity cap in the returned list.
    for inst, n in res.institution_diversity.items():
        assert n <= people_mod.MAX_PER_INSTITUTION


def test_empty_topics_returns_empty():
    res = people_mod.recommend(_brief([]))
    # Falls back to description text; may be empty but must not error.
    assert res.similarity_method == "TF-IDF similarity"


def test_people_endpoint():
    r = client.post("/people", json={"text": (
        "300-person AI and machine-learning hackathon at BU"
    )})
    assert r.status_code == 200
    body = r.json()
    assert body["similarity_method"] == "TF-IDF similarity"
    assert "people" in body
