# Methods

## Attendance arrival/departure curve (task 13)

The 15-minute concurrency shape used by the attendance Monte Carlo is **fitted
from real mobility data**, replacing the earlier trapezoid (which remains as a
fallback when no fit data is present).

### Data sources
- **Bluebikes November 2024 trip data** — the public monthly file
  `https://s3.amazonaws.com/hubway-data/202411-bluebikes-tripdata.zip`
  (397,406 trips). Downloaded once by `backend/app/data/fetch_bluebikes.py` into
  `data/raw/v3/bluebikes/raw/` (gitignored) and aggregated to the small,
  committed CSV `data/raw/v3/bluebikes/bu_hourly_nov2024.csv`.
  Aggregation keeps trips whose **start or end point is within 600 m** of any
  building in `data/reference/bu_buildings_ref.csv` (**50,106** of 397,406 trips),
  counting hourly **starts** (arrival proxy) and **ends** (departure proxy),
  split **weekday vs weekend**. The acceptance events are on a weekend, so the
  **weekend** profile is used.
- **Numina pedestrian counts** (`data/raw/v3/numina/data.csv`, 245,555 rows,
  nine sensor zones, 2020–21). `object=pedestrian` rows are aggregated to an
  hourly weekday/weekend profile and **blended 70/30** (Bluebikes/Numina) into
  the shape prior. Labelled *"Boston Numina sensor zones, 2020–21, not
  BU-specific"*.

### Fit
- Presence over the day = running balance of (starts − ends), floored at 0 and
  normalized to [0, 1]; blended 70/30 with the Numina pedestrian profile; smoothed
  with a 3-hour centered moving average and resampled to 15-minute blocks from a
  ~09:00 start.
- Chart: `docs/arrival_fit.svg` (fitted vs raw vs trapezoid fallback).
- The fitted curve is labelled **MEASURED-derived** in provenance
  (`attendance.arrival_shape`), since it is computed from real Bluebikes counts.
  When the fit file is absent, the shape falls back to the ASSUMED trapezoid.

### Temporal holdout validation (the real test)
The month is split in two: the shape is **fit on Nov 1–15** and tested against the
**held-out Nov 16–30** presence profile. (An earlier in-sample "RMSE 0.022" number
only measured how much the smoother changed the training curve — it was not a
validation and has been removed.)

| day type | fitted RMSE | fitted Spearman | trapezoid RMSE | trapezoid Spearman |
|----------|-------------|-----------------|----------------|--------------------|
| **weekend** (event case) | **0.107** | **0.974** | 0.499 | 0.006 |
| weekday | 0.125 | 0.832 | 0.644 | 0.470 |

On the weekend profile the fitted curve has ~4.6× lower error than the flat
trapezoid and near-perfect rank correlation (0.97) with the held-out half, versus
~0 for the trapezoid. The fit generalizes across halves of the month; the
trapezoid does not track the real shape. Reproduce with
`arrival_fit.holdout_validation("weekend")`.

### Caveats
- **One month only.** November 2024 is a single month of Bluebikes data; seasonal
  and weather-driven variation is not captured.
- **Bluebikes riders are not all attendees.** Dock activity near BU is a *proxy*
  for pedestrian arrival/departure timing, not a direct attendance measurement;
  it over-weights people who bike.
- **Numina is citywide and older.** The Numina pedestrian profile is from
  2020–21 sensor zones that are **not BU-specific** and predate the event; it is
  used only as a weak 30% shape prior blended onto the BU-specific Bluebikes
  signal.
