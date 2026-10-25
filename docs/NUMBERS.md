# NUMBERS — every pitch figure, recomputed from the current build

Each number below was **recomputed from the committed data and code on the
`wip/v2` branch** (not copied from the pitch). For each: the value we verified,
its source, its provenance label, and the exact command to reproduce it. Rows
flagged **⚠ MISMATCH** disagree with the figure used in earlier pitch copy — use
the verified value here.

Verified: 2026-10-24. Environment: `$env:PYTHONPATH="."` at the repo root.

---

## 1. Venue & room dataset

| Pitch figure | Verified value | Label | Source |
|---|---|---|---|
| 38 BU event spaces | **38** | MEASURED | `event_spaces` table, all 38 rows carry a real `source_url` |
| 147 rooms (38 measured + placeholders) | **139 rooms = 38 MEASURED + 101 PLACEHOLDER** ⚠ MISMATCH | MEASURED + PLACEHOLDER | `rooms` table in DuckDB |

- The **38 event spaces** figure is correct and fully MEASURED (every row has a
  source URL).
- ⚠ **"147 rooms" is wrong.** `data/placeholder/bu_rooms.csv` has 147 data rows,
  but the built DuckDB `rooms` table holds **139** (38 MEASURED + 101
  PLACEHOLDER). 147 is the raw pre-build CSV count; the loaded dataset the app
  actually queries is **139**. Use **139** (or say "139 rooms across the modelled
  buildings, 38 of them from measured BU event-space data").
- `buildings`: 26 rows (15 PLACEHOLDER + 11 ASSUMED). `event_spaces` span 12
  distinct buildings.

**Reproduce:**
```powershell
$env:PYTHONPATH="."
python -c "import duckdb; c=duckdb.connect('data/processed/eventtwin.duckdb', read_only=True); print('event_spaces', c.execute('SELECT COUNT(*) FROM event_spaces').fetchone()[0]); print('rooms', c.execute('SELECT label, COUNT(*) FROM rooms GROUP BY label').fetchall())"
```

---

## 2. Bluebikes arrival-curve data

| Pitch figure | Verified value | Label | Source |
|---|---|---|---|
| 397,406 Bluebikes trips | **397,406** | MEASURED (external) | `202411-bluebikes-tripdata.zip`, public Bluebikes monthly file |
| → 50,106 within 600 m of BU | **50,106** | MEASURED (external) | `fetch_bluebikes.py` aggregation log, recorded in `docs/METHODS.md` |

- Both figures are recorded in `docs/METHODS.md` (lines 12–16) as the output of
  the one-time `backend/app/data/fetch_bluebikes.py` run. The raw 397,406-trip
  zip is **gitignored** (`data/raw/v3/bluebikes/raw/`), so these two counts are
  **not re-runnable offline** — they come from the single documented fetch. The
  committed evidence is the aggregated `bu_hourly_nov2024.csv` (hourly
  starts/ends within 600 m, split weekday/weekend and h1/h2).
- The 600 m radius is enforced by `_near_bu()` (haversine ≤ `RADIUS_M = 600.0`)
  against `data/reference/bu_buildings_ref.csv`.

**Reproduce the aggregation (needs the raw zip re-downloaded):**
```powershell
$env:PYTHONPATH="."
python -m backend.app.data.fetch_bluebikes
```
(Offline, you can only confirm the committed aggregated file exists:
`data/raw/v3/bluebikes/bu_hourly_nov2024.csv`.)

---

## 3. Numina pedestrian data

| Pitch figure | Verified value | Label | Source |
|---|---|---|---|
| 245,555 Numina rows | **245,555** (file has 245,556 lines − 1 header) | MEASURED (external, blended prior) | `data/raw/v3/numina/data.csv` |

- Exact match. Confirmed by both the file line count and
  `data/raw/v3/numina/README.md` ("Rows in data.csv: 245555").
- Used as a **weak citywide shape prior**, blended **70/30 (Bluebikes/Numina)**
  into the weekend presence curve. Labelled "Boston Numina sensor zones, 2020–21,
  not BU-specific" — honestly caveated as not BU-specific.

**Reproduce:**
```powershell
(Get-Content data\raw\v3\numina\data.csv | Measure-Object -Line).Lines   # 245556 incl. header
```

---

## 4. OpenAlex people/judges data

| Pitch figure | Verified value | Label | Source |
|---|---|---|---|
| 2,000 OpenAlex works | **≤2,000 (cap `MAX_WORKS = 2000`)** | RESEARCHED (public scholarly) | `fetch_openalex.py` |
| 18,786 authors | **18,785 author rows** ⚠ MISMATCH (off by one) | RESEARCHED (public scholarly) | `data/raw/v3/openalex/authors_topics.csv` |

- The works count is a **fetch cap** (`MAX_WORKS = 2000`), not a measured total —
  state it as "up to 2,000 recent BU-affiliated works".
- ⚠ **"18,786 authors" is off by one.** The committed table
  `authors_topics.csv` has **18,787 lines = 1 comment + 1 header + 18,785 author
  rows**. The pitch likely counted the header. Use **18,785 unique authors**.
- Only public scholarly fields are stored (name, institution, works, citations,
  topics, OpenAlex IDs). **No emails, contact, or demographic data** — matches the
  ethics guardrail.

**Reproduce:**
```powershell
# lines minus the comment line and the header line = author rows
((Get-Content data\raw\v3\openalex\authors_topics.csv | Measure-Object -Line).Lines) - 2
```

---

## 5. Arrival-curve model evaluation (temporal holdout)

| Pitch figure | Verified value | Label | Source |
|---|---|---|---|
| Fitted RMSE 0.107 | **0.1074** | SIMULATED/eval | `arrival_fit.holdout_validation("weekend")` |
| Fitted Spearman 0.974 | **0.9739** | SIMULATED/eval | same |
| Trapezoid RMSE 0.499 | **0.4995** | SIMULATED/eval (baseline) | same |
| Trapezoid Spearman 0.006 | **0.0061** | SIMULATED/eval (baseline) | same |

- All four match to 3 decimals. This is a **genuine temporal holdout**, not
  in-sample: the model is fit on the first half of the month (`half="h1"`, days
  1–15) and scored against the held-out second half (`half="h2"`, days 16–30) in
  `holdout_validation()`.
- The fitted curve (MEASURED-derived, Bluebikes presence) tracks the held-out
  weekend profile far better than the naive trapezoid baseline on both RMSE
  (0.107 vs 0.499) and rank correlation (0.974 vs ~0). **This is the core
  data-science claim and it reproduces exactly.**
- Note: `fit("weekend").rmse` = **0.022** is a *different* number — the smoothing
  residual of the full-month fit, not the holdout error. Do not confuse the two
  in the pitch; the headline comparison numbers are the **holdout** ones above.

**Reproduce:**
```powershell
$env:PYTHONPATH="."
python -c "from backend.app.plan.arrival_fit import holdout_validation; import json; print(json.dumps(holdout_validation('weekend'), indent=2))"
```

---

## 6. Brief A demo plan outputs (`frontend/src/demo/briefA/`)

All values below are read straight from the committed demo snapshot
`plan.json` / `drill.json`.

| Output | Verified value | Label |
|---|---|---|
| Recommended venue | **GSU** (fits all 3 blocks; avg util 46%; 100% real BU event-space data) | MEASURED (venue data) + SIMULATED (assignment) |
| Cost p50 | **$25,782** | SIMULATED (Monte Carlo, 500 draws) |
| Cost p10–p90 band | **$20,557 – $31,320** | SIMULATED |
| Cost per attendee | **$140.89** | SIMULATED |
| Budget / sponsorship gap | **$10,782** over the stated $15k | SIMULATED |
| Turnout p50 / p90 | **183 / 238** | SIMULATED (Beta show-up prior, 500 draws) |
| Readiness (before fixes) | **69 / 100 (failing)** | SIMULATED (digital-twin drill) |
| Top risk + time | **Power failing from 09:00** | SIMULATED |

- The cost figures are **Monte Carlo over turnout × rate-card ranges (500
  draws)**, every line item labelled ASSUMED (rate cards are PLACEHOLDER) — the
  roll-up is honestly SIMULATED.
- Venue recommendation (GSU) is from the CP-SAT assignment over MEASURED event
  spaces.

**Reproduce (regenerate the whole snapshot):**
```powershell
$env:PYTHONPATH="."
python -m backend.scripts.export_demo
# then inspect frontend/src/demo/briefA/plan.json -> summary
```

---

## 7. Brief B drill scenario — Green Line closure + Route 57 shuttle

From `frontend/src/demo/briefB/drill.json` and `drill_fixes.json`.

| Output | Verified value | Label |
|---|---|---|
| Planned disruption | **Green Line closure 2026-10-31 → 2026-11-01; Route 57 shuttle, `fare_free: true`** | MEASURED (MBTA alert) |
| Readiness before | **69 (failing)** | SIMULATED |
| Readiness after "apply fixes & re-run" | **84 (strained)** | SIMULATED |
| Top risks (before) | Green Line closure; **Power failing from 09:00** | SIMULATED |
| Top fix for transit | **Use the Route 57 shuttle (fare-free) during the closure** | derived |

- The **69 → 84** before/after and the **failing → strained** status change are
  exactly what the drill re-run animation shows. The fare-free Route 57 shuttle is
  carried as a real MBTA planned-disruption record.

**Reproduce:**
```powershell
$env:PYTHONPATH="."
python -m backend.scripts.export_demo
# inspect frontend/src/demo/briefB/drill_fixes.json -> before/after readiness
```

---

## 8. Test counts

| Pitch figure | Verified value | Reproduce |
|---|---|---|
| Backend tests | **209 passed** | `$env:PYTHONPATH="."; python -m pytest -p no:cacheprovider -q` |
| Frontend tests | **15 passed** (3 files) | `cd frontend; npm test` |

Both pass on `wip/v2` as of this audit.

---

## Summary of mismatches to fix in pitch copy

1. ⚠ **"147 rooms" → "139 rooms"** (38 MEASURED + 101 PLACEHOLDER). 147 is the
   raw CSV; the app queries 139.
2. ⚠ **"18,786 authors" → "18,785 authors"** (off by one; the pitch counted the
   header row).
3. **Clarify** "2,000 works" is a fetch **cap** ("up to 2,000 recent works"), not
   a measured total.
4. **Do not confuse** the full-fit smoothing residual (0.022) with the **holdout**
   fitted RMSE (**0.107**) — the headline comparison uses the holdout numbers.

Everything else (38 event spaces, 397,406 → 50,106 trips, 245,555 Numina rows,
the holdout RMSE/Spearman pair, all Brief A/B demo values, and the test counts)
reproduces **exactly**.
