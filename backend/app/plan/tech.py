"""
tech.py

Wi-Fi / network and power sizing as CONSUMPTION (P1, task 14).

Reports resource USE, not dollar cost (Wi-Fi and power carry no price here):
  - peak concurrent devices          (p10/p50/p90)
  - peak Mbps                         (p10/p50/p90)
  - total GB over the event           (p10/p50/p90)
  - peak circuits in use              (p10/p50/p90)
  - total kWh over the event          (p10/p50/p90)

Driven by the attendance Monte Carlo concurrency draws (shape (draws, blocks))
and the ASSUMED per-device parameters from assumptions.yaml. Percentiles are
taken across the Monte Carlo draws.

Provenance: consumption outputs SIMULATED; per-device parameters ASSUMED.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import load_assumptions
from ..provenance import Label, ProvenanceRow

BLOCK_MINUTES = 15
BLOCK_HOURS = BLOCK_MINUTES / 60.0


@dataclass
class Band:
    p10: float
    p50: float
    p90: float
    unit: str

    def as_dict(self) -> dict:
        return {"p10": round(self.p10, 2), "p50": round(self.p50, 2),
                "p90": round(self.p90, 2), "unit": self.unit}


@dataclass
class TechPlan:
    peak_devices: Band
    peak_mbps: Band
    total_gb: Band
    peak_circuits: Band
    total_kwh: Band
    assumptions_used: dict
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "peak_devices": self.peak_devices.as_dict(),
            "peak_mbps": self.peak_mbps.as_dict(),
            "total_gb": self.total_gb.as_dict(),
            "peak_circuits": self.peak_circuits.as_dict(),
            "total_kwh": self.total_kwh.as_dict(),
            "assumptions_used": self.assumptions_used,
            "note": "Wi-Fi and power are consumption figures; no dollar cost.",
        }


def _assume(a: dict, path: list[str], default: float) -> float:
    cur = a
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def _band(values: np.ndarray, unit: str) -> Band:
    return Band(
        p10=float(np.percentile(values, 10)),
        p50=float(np.percentile(values, 50)),
        p90=float(np.percentile(values, 90)),
        unit=unit,
    )


def size(brief, attendance, seed: int = 11) -> TechPlan:
    """Compute consumption bands from the attendance concurrency draws."""
    a = load_assumptions()
    etype = (brief.type.value if brief.type else "other")
    dpp = _assume(a, ["devices_per_person", "by_type", etype, "value"], 1.6)
    mbps_pd = _assume(a, ["mbps_per_device", "by_type", etype, "value"], 3.0)
    watts_pd = _assume(a, ["watts_per_device", "value"], 65.0)
    amps = _assume(a, ["power_circuit", "amps", "value"], 20.0)
    volts = _assume(a, ["power_circuit", "volts", "value"], 120.0)
    sf = _assume(a, ["power_circuit", "safety_factor", "value"], 0.8)
    circuit_watts = sf * amps * volts

    conc = getattr(attendance, "concurrency", None)   # (draws, blocks)
    if conc is None or conc.size == 0:
        # Degenerate fallback from the p90 peak only.
        peak = float(getattr(attendance, "turnout_p90", 0) or 0)
        conc = np.array([[peak]])

    # Per draw: devices per block = occupancy * devices/person.
    devices = conc * dpp                                # (draws, blocks)
    peak_devices = devices.max(axis=1)                  # per draw peak

    peak_mbps = peak_devices * mbps_pd
    # Total GB: sum over blocks of (mbps * block_seconds / 8) -> megabytes -> GB.
    block_seconds = BLOCK_MINUTES * 60
    gb_per_draw = (devices * mbps_pd * block_seconds / 8.0 / 1024.0).sum(axis=1) / 1024.0

    peak_watts = peak_devices * watts_pd
    peak_circuits = np.ceil(peak_watts / circuit_watts)
    # Total kWh: sum over blocks of (watts * block_hours) / 1000.
    kwh_per_draw = (devices * watts_pd * BLOCK_HOURS).sum(axis=1) / 1000.0

    tech = TechPlan(
        peak_devices=_band(peak_devices, "devices"),
        peak_mbps=_band(peak_mbps, "Mbps"),
        total_gb=_band(gb_per_draw, "GB"),
        peak_circuits=_band(peak_circuits, "circuits"),
        total_kwh=_band(kwh_per_draw, "kWh"),
        assumptions_used={
            "devices_per_person": dpp,
            "mbps_per_device": mbps_pd,
            "watts_per_device": watts_pd,
            "circuit_watts": circuit_watts,
        },
    )
    tech.provenance = [
        ProvenanceRow(
            output_key="tech.consumption",
            label=Label.SIMULATED,
            source="attendance Monte Carlo draws x per-device assumptions",
            value_summary=(
                f"peak devices p50={tech.peak_devices.p50:.0f}, "
                f"peak Mbps p50={tech.peak_mbps.p50:.0f}, "
                f"total kWh p50={tech.total_kwh.p50:.0f}"
            ),
        ),
        ProvenanceRow(
            output_key="tech.per_device_params",
            label=Label.ASSUMED,
            source="assumptions.yaml devices_per_person / mbps_per_device / watts_per_device",
            value_summary=f"dpp={dpp}, mbps={mbps_pd}, watts={watts_pd}",
        ),
    ]
    return tech
