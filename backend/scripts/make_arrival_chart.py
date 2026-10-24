"""
make_arrival_chart.py

Render the fitted arrival/departure presence curve to docs/arrival_fit.svg
(dependency-free SVG) and print the fit RMSE. Compares, for the weekend profile:
  - raw normalized presence from Bluebikes flows,
  - the smoothed fitted curve,
  - the trapezoid fallback (same block count).

Run:
    python -m backend.scripts.make_arrival_chart
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.app.plan import arrival_fit
from backend.app.plan.attendance import concurrency_shape

DOCS = Path(__file__).resolve().parents[2] / "docs"
OUT = DOCS / "arrival_fit.svg"

W, H = 720, 320
PAD = 40


def _poly(points: list[tuple[float, float]], color: str, width: float = 2.0) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline fill="none" stroke="{color}" stroke-width="{width}" points="{pts}" />'


def _curve_to_points(values: np.ndarray) -> list[tuple[float, float]]:
    n = len(values)
    out = []
    for i, v in enumerate(values):
        x = PAD + (W - 2 * PAD) * (i / max(1, n - 1))
        y = (H - PAD) - (H - 2 * PAD) * float(v)
        out.append((x, y))
    return out


def main() -> None:
    fitted = arrival_fit.fit("weekend")
    if fitted is None:
        print("No Bluebikes fit data available; chart not generated.")
        return

    hourly = fitted.hourly_presence                      # length 24
    flows = arrival_fit._read_hourly("weekend")
    raw = arrival_fit._presence_from_flows(*flows)       # raw normalized

    # Trapezoid fallback on the same 24 "blocks" for visual comparison.
    trap = concurrency_shape(24, overnight=False, is_hackathon=False)

    DOCS.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<line x1="{PAD}" y1="{H-PAD}" x2="{W-PAD}" y2="{H-PAD}" stroke="#999"/>',
        f'<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H-PAD}" stroke="#999"/>',
        f'<text x="{PAD}" y="{PAD-12}" fill="#333">Weekend presence shape (0-1) by hour of day</text>',
        _poly(_curve_to_points(raw), "#bbb", 1.5),       # raw
        _poly(_curve_to_points(hourly), "#1d4ed8", 2.5), # fitted
        _poly(_curve_to_points(trap), "#dc2626", 1.5),   # trapezoid fallback
        # Legend
        f'<rect x="{W-200}" y="{PAD}" width="10" height="10" fill="#1d4ed8"/>'
        f'<text x="{W-185}" y="{PAD+9}" fill="#333">fitted (BB+Numina)</text>',
        f'<rect x="{W-200}" y="{PAD+16}" width="10" height="10" fill="#bbb"/>'
        f'<text x="{W-185}" y="{PAD+25}" fill="#333">raw normalized</text>',
        f'<rect x="{W-200}" y="{PAD+32}" width="10" height="10" fill="#dc2626"/>'
        f'<text x="{W-185}" y="{PAD+41}" fill="#333">trapezoid fallback</text>',
        f'<text x="{PAD}" y="{H-PAD+16}" fill="#666">0h</text>',
        f'<text x="{W-PAD-16}" y="{H-PAD+16}" fill="#666">23h</text>',
        f'<text x="{PAD+(W-2*PAD)*9//24}" y="{H-PAD+16}" fill="#2563eb">~9h start</text>',
        "</svg>",
    ]
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Weekend fit RMSE (smoothed vs raw): {fitted.rmse:.4f}")


if __name__ == "__main__":
    main()
