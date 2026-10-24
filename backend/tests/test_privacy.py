"""Task 10 tests: privacy scrubber core + recognizers."""

from __future__ import annotations

from backend.app.privacy import detect, scrub, scrub_rows


def test_detects_bu_id():
    f = detect("Student U12345678 checked in")
    assert any(x.entity == "BU_ID" and x.text == "U12345678" for x in f)


def test_detects_email():
    f = detect("contact jane.doe@bu.edu please")
    assert any(x.entity == "EMAIL" and x.text == "jane.doe@bu.edu" for x in f)


def test_detects_mac_address():
    f = detect("device 00:1A:2B:3C:4D:5E joined")
    assert any(x.entity == "MAC_ADDRESS" for x in f)


def test_detects_phone():
    f = detect("call 617-555-0199 for info")
    assert any(x.entity == "PHONE" for x in f)


def test_scrub_redacts_all_entities():
    text = "U12345678, jane@bu.edu, 00:1A:2B:3C:4D:5E, 617-555-0199"
    r = scrub(text)
    assert "U12345678" not in r.scrubbed
    assert "jane@bu.edu" not in r.scrubbed
    assert "00:1A:2B:3C:4D:5E" not in r.scrubbed
    assert "617-555-0199" not in r.scrubbed
    assert "[BU_ID]" in r.scrubbed
    assert "[EMAIL]" in r.scrubbed


def test_residual_pii_is_zero_after_scrub():
    text = "U87654321 at aa:bb:cc:dd:ee:ff, email x@y.edu, 1-617-555-0100"
    r = scrub(text)
    assert r.residual_count == 0


def test_mask_mode_keeps_length():
    r = scrub("U12345678", mode="mask")
    assert r.scrubbed == "*" * len("U12345678")


def test_remove_mode_drops_span():
    r = scrub("id U12345678 end", mode="remove")
    assert "U12345678" not in r.scrubbed
    assert "id  end" == r.scrubbed


def test_no_false_positive_on_plain_text():
    r = scrub("300-person overnight hackathon, budget 15000")
    assert r.findings == []
    assert r.scrubbed == r.original


def test_scrub_rows_cleans_cells():
    rows = [{"name": "Jane", "email": "jane@bu.edu", "note": "ok"}]
    out = scrub_rows(rows)
    assert out[0]["email"] == "[EMAIL]"
    assert out[0]["name"] == "Jane"


def test_overlapping_matches_resolved():
    # An email that contains digits shouldn't be split into a phone/BU_ID.
    r = scrub("reach user12345678@bu.edu now")
    assert r.scrubbed == "reach [EMAIL] now"
