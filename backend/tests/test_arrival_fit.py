"""Task 13 tests: Bluebikes-fitted arrival/departure shape."""

from __future__ import annotations

import numpy as np

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import arrival_fit
from backend.app.plan import attendance as att_mod


def test_bluebikes_fit_available_and_bounded():
    fitted = arrival_fit.fit("weekend")
    assert fitted is not None, "expected committed Bluebikes CSV to be present"
    p = fitted.hourly_presence
    assert len(p) == 24
    assert p.min() >= 0.0 and p.max() <= 1.0 + 1e-9
    assert fitted.rmse < 0.1               # tight smoothing fit
    assert "Bluebikes" in fitted.source


def test_weekend_and_weekday_profiles_differ():
    wk = arrival_fit.fit("weekday")
    we = arrival_fit.fit("weekend")
    assert wk is not None and we is not None
    # Commuter weekday has a stronger morning peak than the weekend.
    assert not np.allclose(wk.hourly_presence, we.hourly_presence)


def test_shape_for_blocks_resamples():
    shape = arrival_fit.shape_for_blocks(48, daytype="weekend")
    assert shape is not None
    assert len(shape) == 48
    assert abs(shape.max() - 1.0) < 1e-6   # normalized to peak 1.0


def test_attendance_uses_measured_shape_for_dated_event():
    brief = EventBrief(
        type=EventType.hackathon, description="weekend hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=300,
    )
    s = att_mod.sample(brief, draws=200)
    by_key = {p.output_key: p for p in s.provenance}
    assert by_key["attendance.arrival_shape"].label == "MEASURED"
    assert "Bluebikes" in by_key["attendance.arrival_shape"].source


def test_attendance_still_produces_ordered_percentiles_with_fit():
    brief = EventBrief(
        type=EventType.hackathon, description="weekend hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=300,
    )
    s = att_mod.sample(brief, draws=300)
    assert all(b.p90 >= b.p50 for b in s.per_block)
    assert s.peak_p90() > 0
