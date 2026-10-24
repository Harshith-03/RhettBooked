"""Task 14 tests: Wi-Fi + power sizing as consumption (p10/p50/p90, no cost)."""

from __future__ import annotations

from backend.app.brief.models import EventBrief, EventType
from backend.app.plan import attendance as att_mod
from backend.app.plan import plan as plan_mod
from backend.app.plan import tech as tech_mod


def _brief(regs=300):
    return EventBrief(
        type=EventType.hackathon, description="overnight AI hackathon",
        start="2026-10-24", end="2026-10-25", overnight=True,
        expected_registrations=regs,
    )


def test_consumption_bands_ordered():
    att = att_mod.sample(_brief(), draws=500)
    t = tech_mod.size(_brief(), att)
    for band in (t.peak_devices, t.peak_mbps, t.total_gb, t.peak_circuits, t.total_kwh):
        assert band.p10 <= band.p50 <= band.p90


def test_has_all_five_metrics_with_units():
    att = att_mod.sample(_brief(), draws=300)
    d = tech_mod.size(_brief(), att).as_dict()
    assert d["peak_devices"]["unit"] == "devices"
    assert d["peak_mbps"]["unit"] == "Mbps"
    assert d["total_gb"]["unit"] == "GB"
    assert d["peak_circuits"]["unit"] == "circuits"
    assert d["total_kwh"]["unit"] == "kWh"
    # No dollar cost anywhere in the tech payload.
    assert "cost" not in d
    assert "no dollar cost" in d["note"].lower()


def test_scales_with_headcount():
    small = tech_mod.size(_brief(100), att_mod.sample(_brief(100), draws=300))
    big = tech_mod.size(_brief(1000), att_mod.sample(_brief(1000), draws=300))
    assert big.peak_devices.p50 > small.peak_devices.p50
    assert big.total_kwh.p50 > small.total_kwh.p50


def test_devices_reflect_devices_per_person():
    att = att_mod.sample(_brief(), draws=500)
    t = tech_mod.size(_brief(), att)
    # Hackathon devices/person is 2.3; peak devices should exceed peak occupancy.
    assert t.peak_devices.p50 > att.peak_p90() * 1.5


def test_provenance_labels():
    att = att_mod.sample(_brief(), draws=200)
    t = tech_mod.size(_brief(), att)
    by_key = {p.output_key: p.label for p in t.provenance}
    assert by_key["tech.consumption"] == "SIMULATED"
    assert by_key["tech.per_device_params"] == "ASSUMED"


def test_plan_tech_and_venue_tiles_show_consumption():
    plan = plan_mod.build(_brief(), draws=300)
    tech_tile = next(t for t in plan.tiles if t.name == "Tech")
    venue_tile = next(t for t in plan.tiles if t.name == "Venue")
    assert tech_tile.details["peak_devices"]["p50"] > 0
    # Consumption is surfaced in the Venue tile too.
    assert venue_tile.details["consumption"]["peak_mbps"]["p50"] > 0
