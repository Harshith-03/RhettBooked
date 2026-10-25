"""MCP tool implementation tests (offline; injected fetch/generate)."""

from __future__ import annotations

from backend.app.mcp_server import tools_impl
from backend.app.mcp_server.schemas import OpenAlexIn, OsmIn, WebSearchIn


def test_build_query_uses_purpose_template():
    q = tools_impl.build_query("catering", {"headcount": 300, "building": "GSU", "meal": "lunch"})
    assert "300" in q and "GSU" in q and "lunch" in q
    # Free-form is not possible: an unknown purpose raises.
    import pytest
    with pytest.raises(ValueError):
        tools_impl.build_query("exfiltrate", {})


def test_osm_places_parses_and_sorts_by_distance():
    def fake_fetch(_q):
        return {"elements": [
            {"type": "node", "id": 2, "lat": 42.36, "lon": -71.10,
             "tags": {"name": "Far Cafe"}},
            {"type": "node", "id": 1, "lat": 42.3505, "lon": -71.1054,
             "tags": {"name": "Near Caterer", "cuisine": "american",
                      "website": "https://near.com"}},
        ]}
    res = tools_impl.osm_places_near(
        OsmIn(lat=42.3505, lon=-71.1054, radius_m=1500), fetch=fake_fetch
    )
    assert [p.name for p in res.places][0] == "Near Caterer"  # closest first
    assert res.places[0].website == "https://near.com"


def test_web_search_returns_items_and_grounded_sources():
    def fake_gen(_prompt):
        return {"text": "Caterer A\nCaterer B",
                "sources": [{"url": "https://a.com", "title": "A"}]}
    res = tools_impl.web_search(WebSearchIn(query="x", purpose="catering"), generate=fake_gen)
    assert res.answer_items == ["Caterer A", "Caterer B"]
    assert res.sources[0].url == "https://a.com"


def test_openalex_people_returns_real_ranking():
    res = tools_impl.openalex_people(OpenAlexIn(topics=["artificial intelligence"], k=5))
    assert len(res.people) >= 1
    assert res.people[0].name
