"""
air.py

CO2 mass-balance helper for the drill's air-quality system (P1, task 20).

Model (as specified):
    dC/dt = (N*G - Q*(C - C_out)) / V
where
    N     = number of people in the room
    G     = CO2 generation per person = 0.0052 L/s/person
    Q     = ventilation flow (L/s)
    C     = indoor CO2 concentration (ppm)
    C_out = outdoor CO2 = 420 ppm
    V     = room volume (L)
Thresholds: amber at 1000 ppm, red at 1400 ppm.

``co2_series`` integrates the ODE across occupancy over time (Euler steps), and
``steady_state`` gives the closed-form equilibrium C_out + N*G/Q*1e6-scaled, used
by tests to check convergence.
"""

from __future__ import annotations

import numpy as np

G_PER_PERSON = 0.0052   # L/s/person
C_OUT = 420.0           # ppm
AMBER = 1000.0          # ppm
RED = 1400.0            # ppm

# CO2 generation and ventilation are volumetric L/s; converting a volumetric CO2
# generation rate into a ppm change uses parts-per-million = (vol CO2 / vol air).
# With G in L/s and V in L, the fractional rate is G/V (per second); *1e6 -> ppm.


def steady_state(n_people: float, q_lps: float) -> float:
    """Closed-form equilibrium CO2 (ppm): C_out + 1e6 * N*G / Q."""
    if q_lps <= 0:
        return float("inf")
    return C_OUT + 1e6 * (n_people * G_PER_PERSON) / q_lps


def co2_series(
    occupancy: np.ndarray,
    q_lps: float,
    volume_l: float,
    dt_s: float = 900.0,
    c0: float = C_OUT,
) -> np.ndarray:
    """Integrate CO2 (ppm) over the occupancy series with Euler steps.

    occupancy: people per block; dt_s: seconds per block (900 = 15 min).
    Returns the CO2 ppm at the end of each block.
    """
    if volume_l <= 0:
        return np.full(len(occupancy), C_OUT)
    c = c0
    out = np.empty(len(occupancy))
    # Sub-step for numerical stability within each 15-min block.
    substeps = 60
    h = dt_s / substeps
    for i, n in enumerate(occupancy):
        for _ in range(substeps):
            # dC/dt in ppm/s: generation raises C, ventilation pulls C toward C_out.
            gen_ppm_per_s = 1e6 * (n * G_PER_PERSON) / volume_l
            vent_ppm_per_s = (q_lps / volume_l) * (c - C_OUT)
            c += h * (gen_ppm_per_s - vent_ppm_per_s)
            c = max(c, C_OUT)
        out[i] = c
    return out


def status_for(ppm: float) -> str:
    if ppm >= RED:
        return "failing"
    if ppm >= AMBER:
        return "strained"
    return "ok"
