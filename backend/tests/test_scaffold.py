"""Task 1 scaffold tests: config, provenance, LLM adapter, and assumptions.yaml."""

from __future__ import annotations

import pytest

from backend.app import config, llm
from backend.app.provenance import (
    ALLOWED_LABELS,
    Label,
    ProvenanceRecorder,
    ProvenanceRow,
    ProvenanceStore,
)


# --------------------------------------------------------------------------- #
# Provenance labels and records
# --------------------------------------------------------------------------- #
def test_allowed_labels_are_the_four_canonical_ones():
    assert ALLOWED_LABELS == {"MEASURED", "ASSUMED", "PLACEHOLDER", "SIMULATED"}


def test_provenance_row_rejects_bad_label():
    with pytest.raises(ValueError):
        ProvenanceRow(output_key="x", label="GUESSED", source="nope")


def test_provenance_row_rejects_empty_key():
    with pytest.raises(ValueError):
        ProvenanceRow(output_key="", label=Label.ASSUMED, source="s")


def test_recorder_collects_rows_and_labels():
    rec = ProvenanceRecorder()
    rec.record("venue.capacity", Label.MEASURED, "bu_event_spaces.csv", "1100")
    rec.record("budget.total_p50", "SIMULATED", "monte_carlo", "$14,200")
    assert len(rec.rows) == 2
    assert rec.labels_present() == {"MEASURED", "SIMULATED"}


# --------------------------------------------------------------------------- #
# Provenance store (in-memory DuckDB)
# --------------------------------------------------------------------------- #
def test_store_roundtrip_and_counts():
    store = ProvenanceStore(db_path=":memory:")
    # NOTE: a :memory: DuckDB connection is per-connection, so exercise add+read
    # against a fresh store seeded in one call path.
    rec = ProvenanceRecorder()
    rec.record("a.b", Label.ASSUMED, "assumptions.yaml", "0.6")
    rec.record("c.d", Label.PLACEHOLDER, "bu_rooms.csv", "42")
    added = store.add(rec.rows)
    assert added == 2


def test_store_label_counts_includes_all_labels():
    store = ProvenanceStore(db_path=":memory:")
    counts = store.label_counts()
    assert set(counts.keys()) == ALLOWED_LABELS
    assert all(v == 0 for v in counts.values())


# --------------------------------------------------------------------------- #
# LLM adapter under LLM_PROVIDER=none
# --------------------------------------------------------------------------- #
def test_parse_json_raises_when_provider_none(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "none")
    with pytest.raises(llm.LLMUnavailable):
        llm.parse_json("300-person hackathon", {"type": "object"})


def test_explain_returns_grounded_template_under_none(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "none")
    text = llm.explain(
        {
            "summary": {
                "recommended_building": "GSU",
                "cost_p10": "$9,000",
                "cost_p90": "$18,000",
                "readiness": 82,
                "top_risks": ["Green Line closure"],
            }
        }
    )
    # Only numbers from the context appear; nothing invented.
    assert "GSU" in text
    assert "$9,000" in text and "$18,000" in text
    assert "82/100" in text
    assert "Green Line closure" in text


def test_explain_handles_empty_context(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "none")
    assert llm.explain({}) == "No results available to explain yet."


# --------------------------------------------------------------------------- #
# Config + assumptions.yaml
# --------------------------------------------------------------------------- #
def test_config_paths_point_into_repo():
    assert config.RAW_BU_DIR.name == "bu"
    assert config.DUCKDB_PATH.name == "eventtwin.duckdb"
    assert config.ASSUMPTIONS_PATH.exists()


def test_assumptions_yaml_has_required_params_with_value_and_source():
    import yaml

    data = yaml.safe_load(config.ASSUMPTIONS_PATH.read_text(encoding="utf-8"))
    # Top-level parameters the task requires.
    assert "show_up_rate" in data
    assert "devices_per_person" in data
    assert "mbps_per_device" in data
    assert data["watts_per_device"]["value"] == 65
    assert data["ap_comfortable_clients"]["value"] == 40
    assert "water_litres_per_person_per_hour" in data
    assert "dietary_shares" in data
    assert data["contingency_percent"]["value"] == 10

    # Spot-check that leaf params carry value + range + source.
    watts = data["watts_per_device"]
    assert "range" in watts and "source" in watts
    assert watts["source"].startswith("ASSUMED")
