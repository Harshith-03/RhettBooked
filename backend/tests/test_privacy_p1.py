"""Privacy P1 + task 21 tests: tokenizer/vault/audit, suppression, risk report."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.privacy import aggregate_counts, risk_report
from backend.app.privacy.tokenizer import Vault

client = TestClient(app)


# --------------------------------------------------------------------------- #
# HMAC tokenizer + vault + audit
# --------------------------------------------------------------------------- #
def test_tokenizer_deterministic_and_detokenize():
    v = Vault(path=":memory:")
    try:
        t1 = v.tokenize("U12345678", entity="BU_ID")
        t2 = v.tokenize("U12345678", entity="BU_ID")
        assert t1 == t2                      # deterministic
        assert len(t1) == 64                 # HMAC-SHA256 hex
        assert v.detokenize(t1) == "U12345678"
    finally:
        v.close()


def test_distinct_inputs_distinct_tokens():
    v = Vault(path=":memory:")
    try:
        assert v.tokenize("a@bu.edu") != v.tokenize("b@bu.edu")
    finally:
        v.close()


def test_audit_log_records_actions():
    v = Vault(path=":memory:")
    try:
        t = v.tokenize("x")
        v.detokenize(t)
        actions = [e["action"] for e in v.audit_log()]
        assert "tokenize" in actions and "detokenize" in actions
    finally:
        v.close()


def test_detokenize_demo_endpoint():
    r = client.post("/privacy/detokenize-demo", json={"value": "U99999999"})
    assert r.status_code == 200
    body = r.json()
    assert body["deterministic"] is True
    assert body["recovered"] == "U99999999"
    assert body["audit_entries"] >= 2


# --------------------------------------------------------------------------- #
# Aggregate suppression (<5)
# --------------------------------------------------------------------------- #
def test_aggregate_suppresses_small_cells():
    rows = (
        [{"diet": "omnivore"}] * 10
        + [{"diet": "vegan"}] * 3        # under 5 -> suppressed
        + [{"diet": "halal"}] * 7
    )
    agg = aggregate_counts(rows, "diet")
    assert agg["counts"] == {"omnivore": 10, "halal": 7}
    assert "vegan" not in agg["counts"]
    assert agg["suppressed_people"] == 3


# --------------------------------------------------------------------------- #
# Risk report
# --------------------------------------------------------------------------- #
def test_risk_report_entities_and_residual_zero():
    rows = [
        {"name": "Jane", "email": "jane@bu.edu", "bu_id": "U12345678", "diet": "vegan"},
        {"name": "John", "email": "john@bu.edu", "bu_id": "U87654321", "diet": "omnivore"},
    ]
    rep = risk_report(rows)
    assert "email" in rep.entities_per_column
    assert "bu_id" in rep.entities_per_column
    # After scrubbing, no residual PII remains.
    assert rep.residual_pii == 0
    assert rep.n_rows == 2


def test_upload_has_names_note():
    r = client.post(
        "/privacy/upload",
        files={"file": ("x.csv", b"name,email\nJane,j@bu.edu\n", "text/csv")},
    )
    assert "NER via Presidio" in r.json()["names_note"]


# --------------------------------------------------------------------------- #
# Trust endpoint
# --------------------------------------------------------------------------- #
def test_trust_endpoint_label_mix_and_sensitivity():
    r = client.post("/trust", json={"text": (
        "300-person overnight AI hackathon at BU, Oct 24-25, students, budget "
        "$15k, needs lunch, dinner, midnight snack, breakfast"
    ), "draws": 200})
    assert r.status_code == 200
    body = r.json()
    counts = body["label_counts"]
    assert set(counts) == {"MEASURED", "ASSUMED", "PLACEHOLDER", "SIMULATED"}
    assert sum(counts.values()) > 0
    assert isinstance(body["sensitivity"], list)
