"""Task 20 tests: extended drill systems (network, queues, air/CO2) + sensitivity."""

from __future__ import annotations

from datetime import date

import numpy as np

from backend.app.drill import air as air_mod
from backend.app.drill import twin as twin_mod
from backend.app.drill import verdict as verdict_mod
from backend.app.drill.twin import DrillContext


def _ctx(occ_peak=180, cap=330, n_blocks=48, aps=4, vol=0.0, vent=0.0):
    series = []
    for i in range(n_blocks):
        frac = min(1.0, i / 5) if i < n_blocks * 0.5 else max(0.1, 1 - (i - n_blocks / 2) / (n_blocks / 2))
        series.append(int(occ_peak * frac))
    clocks = [f"{(9 + (i*15)//60) % 24:02d}:00" for i in range(n_blocks)]
    return DrillContext(
        peak_p90=occ_peak, assigned_capacity=cap, assigned_power_circuits=8,
        per_block_occupancy=series, per_block_clock=clocks,
        event_start=date(2026, 10, 24), event_end=date(2026, 10, 25),
        overnight=True, event_type="hackathon",
        assigned_access_points=aps, room_volume_l=vol, ventilation_lps=vent,
    )


# --------------------------------------------------------------------------- #
# CO2 mass balance
# --------------------------------------------------------------------------- #
def test_co2_steady_state_closed_form():
    # Equilibrium = C_out + 1e6 * N*G / Q.
    n, q = 100.0, 50.0
    expected = 420.0 + 1e6 * (n * air_mod.G_PER_PERSON) / q
    # Integrate a long constant-occupancy series; it should converge to expected.
    occ = np.full(400, n)
    ppm = air_mod.co2_series(occ, q_lps=q, volume_l=50000.0, dt_s=900.0)
    assert abs(ppm[-1] - expected) < 0.01 * expected  # within 1%


def test_co2_thresholds():
    assert air_mod.status_for(500) == "ok"
    assert air_mod.status_for(1100) == "strained"
    assert air_mod.status_for(1500) == "failing"


def test_co2_rises_with_occupancy():
    low = air_mod.co2_series(np.full(20, 10.0), q_lps=100.0, volume_l=100000.0)
    high = air_mod.co2_series(np.full(20, 300.0), q_lps=100.0, volume_l=100000.0)
    assert high[-1] > low[-1] > air_mod.C_OUT


# --------------------------------------------------------------------------- #
# Extended systems appear only when requested
# --------------------------------------------------------------------------- #
def test_extended_adds_network_queues_air():
    core = {s.system for s in twin_mod.run(_ctx(), extended=False).systems}
    ext = {s.system for s in twin_mod.run(_ctx(), extended=True).systems}
    assert core == {"occupancy", "power", "getting_home"}
    assert ext == {"occupancy", "power", "getting_home", "network", "queues", "air"}


def test_network_fails_when_aps_insufficient():
    # 180 peak * 2.3 devices = ~414 clients; 1 AP * 40 = 40 -> failing.
    res = twin_mod.run(_ctx(aps=1), extended=True)
    net = next(s for s in res.systems if s.system == "network")
    assert net.status == twin_mod.STATUS_FAILING


def test_air_poor_ventilation_strains():
    # Tiny volume + low ventilation -> CO2 climbs past amber.
    res = twin_mod.run(_ctx(vol=50000.0, vent=20.0), extended=True)
    airsys = next(s for s in res.systems if s.system == "air")
    assert airsys.status in (twin_mod.STATUS_STRAINED, twin_mod.STATUS_FAILING)


# --------------------------------------------------------------------------- #
# Verdict + sensitivity
# --------------------------------------------------------------------------- #
def test_verdict_includes_extended_in_readiness():
    v = verdict_mod.assess(twin_mod.run(_ctx(), extended=True))
    assert 0 <= v.readiness <= 100


def test_sensitivity_tornado_sorted_by_delta():
    rows = twin_mod.sensitivity(_ctx(aps=2))
    assert rows
    deltas = [r["delta"] for r in rows]
    assert deltas == sorted(deltas)
    assert all("driver" in r and "readiness" in r for r in rows)
