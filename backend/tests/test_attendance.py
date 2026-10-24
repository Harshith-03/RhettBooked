"""Task 4 tests: thin attendance model + Monte Carlo harness."""

from __future__ import annotations

import numpy as np

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import attendance
from backend.app.plan.attendance import BLOCK_MINUTES, concurrency_shape, sample


def _hackathon_brief(regs=300, overnight=True, start="2026-10-24", end="2026-10-25"):
    return EventBrief(
        type=EventType.hackathon,
        description="300-person overnight AI hackathon",
        start=start,
        end=end,
        overnight=overnight,
        expected_registrations=regs,
    )


# --------------------------------------------------------------------------- #
# Core shape and structure
# --------------------------------------------------------------------------- #
def test_sample_runs_and_has_blocks():
    s = sample(_hackathon_brief(), draws=500, seed=1)
    assert s.draws == 500
    assert len(s.per_block) > 0
    # 15-minute blocks.
    assert s.per_block[1].minute_offset - s.per_block[0].minute_offset == BLOCK_MINUTES


def test_p90_ge_p50_every_block():
    s = sample(_hackathon_brief(), draws=500, seed=2)
    assert all(b.p90 >= b.p50 for b in s.per_block)


def test_turnout_below_registrations_and_percentiles_ordered():
    s = sample(_hackathon_brief(regs=300), draws=500, seed=3)
    # Show-up rate < 1, so turnout well under registrations.
    assert 0 < s.turnout_p50 <= 300
    assert s.turnout_p90 >= s.turnout_p50
    # Peak concurrency never exceeds registrations by much (noise aside).
    assert s.peak_p90() <= 300 * 1.1


def test_turnout_scales_with_registrations():
    small = sample(_hackathon_brief(regs=100), draws=500, seed=4)
    big = sample(_hackathon_brief(regs=1000), draws=500, seed=4)
    assert big.turnout_p50 > small.turnout_p50 * 5


def test_zero_registrations_yields_zero():
    s = sample(_hackathon_brief(regs=0), draws=200, seed=5)
    assert s.turnout_p50 == 0
    assert s.peak_p90() == 0


# --------------------------------------------------------------------------- #
# Beta prior selection from assumptions.yaml
# --------------------------------------------------------------------------- #
def test_beta_prior_matches_hackathon_free_assumption():
    s = sample(_hackathon_brief(), draws=100, seed=6)
    # assumptions.yaml: hackathon.free -> Beta(6, 4), mean 0.6.
    assert s.show_up_alpha == 6.0
    assert s.show_up_beta == 4.0


def test_conference_prior_differs_from_hackathon():
    conf = EventBrief(
        type=EventType.conference,
        description="free professional conference",
        start="2026-05-05",
        end="2026-05-05",
        expected_registrations=200,
    )
    s = sample(conf, draws=100, seed=7)
    # conference.free -> Beta(7, 3).
    assert (s.show_up_alpha, s.show_up_beta) == (7.0, 3.0)


# --------------------------------------------------------------------------- #
# Overnight decay
# --------------------------------------------------------------------------- #
def test_overnight_hackathon_has_overnight_dip():
    shape = concurrency_shape(n_blocks=144, overnight=True, is_hackathon=True)
    # The dip is centred around 72% through the span; presence there should be
    # clearly lower than the daytime plateau around the 40% mark.
    plateau = shape[int(0.40 * 144)]
    night = shape[int(0.72 * 144)]
    assert night < plateau * 0.8


def test_non_overnight_has_no_overnight_dip():
    shape = concurrency_shape(n_blocks=36, overnight=False, is_hackathon=False)
    # Plateau in the middle should be ~1.0 (no night dip).
    assert shape[len(shape) // 2] > 0.95


# --------------------------------------------------------------------------- #
# Provenance labelling
# --------------------------------------------------------------------------- #
def test_provenance_labels_prior_assumed_and_turnout_simulated():
    s = sample(_hackathon_brief(), draws=100, seed=8)
    by_key = {p.output_key: p for p in s.provenance}
    assert by_key["attendance.show_up_prior"].label == "ASSUMED"
    assert by_key["attendance.turnout"].label == "SIMULATED"
    assert by_key["attendance.concurrency_curve"].label == "SIMULATED"


def test_determinism_with_seed():
    a = sample(_hackathon_brief(), draws=300, seed=99)
    b = sample(_hackathon_brief(), draws=300, seed=99)
    assert a.turnout_p50 == b.turnout_p50
    assert [x.p90 for x in a.per_block] == [x.p90 for x in b.per_block]
