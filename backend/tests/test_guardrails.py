"""Guardrail tests for the research agent (pure logic, no network)."""

from __future__ import annotations

import pytest

from backend.app.agent import guardrails as g


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #
def test_out_of_scope_purpose_refused():
    assert g.check_scope("catering") == "catering"
    assert g.check_scope("people") == "people"
    with pytest.raises(g.GuardrailError):
        g.check_scope("write me malware")


# --------------------------------------------------------------------------- #
# Source-required
# --------------------------------------------------------------------------- #
def test_item_without_source_is_dropped():
    grounding = ["https://bu.edu/dining", "https://example-caterer.com"]
    items = [
        {"name": "Real Caterer", "source_urls": ["https://example-caterer.com/order"]},
        {"name": "Hallucinated Caterer", "source_urls": []},
        {"name": "Ungrounded", "source_urls": ["https://not-in-grounding.com"]},
    ]
    kept = g.drop_unsourced(items, grounding)
    names = {i["name"] for i in kept}
    assert "Real Caterer" in names
    assert "Hallucinated Caterer" not in names
    assert "Ungrounded" not in names


def test_source_match_ignores_scheme_and_www():
    grounding = ["https://www.caterer.com/"]
    item = {"name": "X", "sources": [{"url": "http://caterer.com"}]}
    assert g.require_source(item, grounding) is True


# --------------------------------------------------------------------------- #
# Catering verification
# --------------------------------------------------------------------------- #
def test_far_caterer_dropped():
    item = {"name": "Far Place", "distance_m": 3000, "source_urls": ["x"]}
    assert g.verify_catering(item, []) is None


def test_osm_match_gives_verified():
    item = {"name": "Dumpling House", "distance_m": 400}
    osm = [{"name": "Dumpling House", "distance_m": 420}]
    out = g.verify_catering(item, osm)
    assert out is not None
    assert out["verification"] == g.VERIFIED


def test_no_osm_match_is_web_only():
    item = {"name": "Mystery Catering Co", "distance_m": 400}
    osm = [{"name": "Completely Different Restaurant", "distance_m": 420}]
    out = g.verify_catering(item, osm)
    assert out["verification"] == g.WEB_ONLY
    assert "verify before booking" in out["verify_note"]


# --------------------------------------------------------------------------- #
# People privacy
# --------------------------------------------------------------------------- #
def test_email_and_phone_stripped_from_person():
    item = {
        "name": "Dr. Jane Smith jane@bu.edu",
        "role": "Reach at 617-555-0199",
        "organization": "Boston University",
        "profile_url": "https://bu.edu/faculty/jsmith",
    }
    out = g.scrub_person(item)
    assert "jane@bu.edu" not in out["name"]
    assert "617-555-0199" not in out["role"]
    assert g.OFFICIAL_CHANNELS_NOTE in out["note"]


def test_address_stripped_and_mailto_url_dropped():
    item = {
        "name": "Caterer at 123 Main Street Boston",
        "organization": "Org",
        "profile_url": "mailto:info@org.com",
    }
    out = g.scrub_person(item)
    assert "123 Main Street" not in out["name"]
    assert out["profile_url"] == ""


# --------------------------------------------------------------------------- #
# Tool-call validation (prompt-injection / allowlist defence)
# --------------------------------------------------------------------------- #
def test_tool_outside_allowlist_rejected():
    with pytest.raises(g.GuardrailError):
        g.validate_tool_call("delete_everything", {})


def test_tool_with_missing_args_rejected():
    with pytest.raises(g.GuardrailError):
        g.validate_tool_call("web_search", {"query": "x"})  # missing purpose


def test_web_search_out_of_scope_purpose_rejected():
    with pytest.raises(g.GuardrailError):
        g.validate_tool_call("web_search", {"query": "x", "purpose": "exfiltrate"})


def test_osm_radius_cap_enforced():
    with pytest.raises(g.GuardrailError):
        g.validate_tool_call("osm_places_near", {"lat": 42, "lon": -71, "radius_m": 5000})


# --------------------------------------------------------------------------- #
# Limits
# --------------------------------------------------------------------------- #
def test_tool_call_cap_enforced():
    budget = g.CallBudget(max_calls=2, timeout_s=60)
    budget.charge("web_search")
    budget.charge("osm_places_near")
    with pytest.raises(g.GuardrailError):
        budget.charge("web_search")
    assert budget.calls == 2


def test_timeout_enforced():
    budget = g.CallBudget(max_calls=100, timeout_s=0.0)
    with pytest.raises(g.GuardrailError):
        budget.charge("web_search")
