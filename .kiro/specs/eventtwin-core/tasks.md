# Implementation Plan

## Overview

Tasks are ordered so a thin end-to-end plan works early, then each section is deepened. Each task is tagged
**[P0]** (working by 7:30 PM today, solo) or **[P1]** (overnight). Real data wins: loaders read the real
BU CSVs in data/raw/bu/ as MEASURED, fall back to placeholder CSVs (read with comment="#") only for
entities the real files do not cover, and record the correct provenance label for every row. The thin
vertical slice
delivers parse (rule-based) -> attendance -> venue -> food -> transport -> budget -> drill (occupancy +
power + getting-home) -> API -> ONE combined frontend page (Intake + Plan summary + tiles + Drill). A thin
acceptance checkpoint (task 8a) runs right after the API; task 12 is the broader end-to-end slice checkpoint
with any remaining systems stubbed to labelled defaults.

## Task Dependency Graph

Tasks within the same wave have no interdependencies and may run in parallel. Each wave depends on the
prior waves completing.

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2", "3", "8", "10"] },
    { "wave": 3, "tasks": ["4", "8a"] },
    { "wave": 4, "tasks": ["5", "9"] },
    { "wave": 5, "tasks": ["6", "11", "16"] },
    { "wave": 6, "tasks": ["7", "15"] },
    { "wave": 7, "tasks": ["12"] },
    { "wave": 8, "tasks": ["13", "14", "17", "18", "19", "21", "22", "23"] },
    { "wave": 9, "tasks": ["20"] },
    { "wave": 10, "tasks": ["24"] }
  ],
  "dependencies": {
    "1": [],
    "2": ["1"],
    "3": ["1"],
    "8": ["1"],
    "10": ["1"],
    "4": ["2", "3"],
    "8a": ["8", "4", "5"],
    "9": ["8", "8a"],
    "5": ["4"],
    "11": ["8", "9"],
    "6": ["5"],
    "13": ["4"],
    "16": ["5"],
    "7": ["6"],
    "15": ["4", "5"],
    "17": ["6"],
    "12": ["7", "8", "8a", "11"],
    "14": ["5", "7"],
    "18": ["3", "6"],
    "19": ["3", "6"],
    "21": ["10"],
    "22": ["11"],
    "23": ["9", "17"],
    "20": ["7", "14", "15"],
    "24": ["7", "8", "13", "14", "15", "16", "17"]
  }
}
```
## Tasks

## Phase 0 - Foundation and thin vertical slice

- [x] 1. [P0] Scaffold backend, config, and provenance
  - Create FastAPI app skeleton (backend/app/main.py), app package layout, and pytest setup.
  - Add llm.py adapter (bedrock|anthropic|ollama|none); `none` raises LLMUnavailable and returns template text.
  - Add config/assumptions.yaml with Beta show-up priors, devices/person, Mbps/device, watts/device,
    AP comfortable limit, water litres/person/hr, dietary shares, contingency - each with value, range, source.
  - Implement the provenance table + a helper that records (output_key, label, source, value_summary).
  - _Requirements: 11, 12.3_

- [x] 2. [P0] Data loaders and DuckDB build (real BU data wins)
  - loaders.py loads the REAL CSVs from data/raw/bu/ as MEASURED: bu_event_spaces.csv -> event_spaces,
    bu_dining_locations.csv -> dining, mbta_stations_bu.csv -> mbta_stops (walk_min_ASSUMED stays ASSUMED),
    mbta_bus_routes_bu.csv -> bus_routes, bu_parking.csv -> parking (MEASURED when present in data/raw/bu/,
    else fall back to data/placeholder/bu_parking.csv as PLACEHOLDER). Raw files may arrive with messy
    names (e.g. "bu_event_spaces (2).csv"); normalize to canonical names / resolve newest per table.
    Read every CSV (real and placeholder) with comment="#".
  - event_spaces rules: blank layout-capacity column -> NULL (never 0); blank max_capacity -> max of the
    per-layout capacities; parse air-wall groups from notes (e.g. GSU-219 -> GSU-219A + GSU-219B).
  - dining rules: parse hours like "08:00-22:00"; blank hours -> unknown + "check hours" flag (never open).
  - mbta_stops rules: parse service_alert into structured PlannedDisruption(start, end, lines, shuttle_note,
    fare_free); carry wheelchair_accessible + accessibility_notes.
  - Build data/reference/bu_buildings_ref.csv keyed by building_code covering every code in event_spaces,
    dining, and placeholder buildings (GSU, PHO, CDS, YAW, RES-WTW, RES-RICH, FCC, ...): columns
    building_code, name, address, lat, lon, overnight_allowed, accessible_entrance, label. lat/lon from
    placeholder bu_buildings.csv where name matches (keep its label) else approximate from address + label
    ASSUMED; overnight_allowed/accessible_entrance ASSUMED unless a note says otherwise
    (e.g. "Elevators unlock 1 hr before/after events" -> access restriction).
  - build_db.py assembles rooms = event_spaces (MEASURED) UNION placeholder rooms for buildings not in
    event_spaces (e.g. CDS, PLACEHOLDER); fills+labels ASSUMED: power_circuits=ceil(sqft/400),
    access_points=ceil(max_capacity/40), rate_per_hour from rate_cards.yaml by size, ventilation_cfm=
    7.5*max_capacity. Loads event_spaces, dining, mbta_stops, bus_routes, parking, buildings, rooms,
    rate_cards into data/processed/eventtwin.duckdb; records a provenance label for every row.
  - Tests: blank capacities load as NULL (not 0); every rooms row carries a provenance label.
  - _Requirements: 3.2, 3.3, 8.1 (loader rule), 15.1-15.4, provenance_

- [x] 3. [P0] EventBrief model and rule-based intake (rule-based only)
  - Define EventBrief + needs sub-model (pydantic v2).
  - intake.parse: regex/keyword rule-based parser producing the model. LLM-with-strict-JSON path
    deferred to P1; P0 ships the rule-based path only.
  - questions.missing: at most 3 follow-ups for missing critical fields only.
  - Unit tests incl. the acceptance brief parsing under LLM_PROVIDER=none.
  - _Requirements: 1.1-1.6_

- [x] 4. [P0] Attendance (thin) and Monte Carlo harness
  - attendance.sample: Beta show-up prior by type/free-paid; 15-min concurrency curve; overnight decay;
    Monte Carlo 500 draws; expose p50/p90. (Fit refinement deferred to task 12.)
  - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_

- [x] 5. [P0] Venue optimizer (CP-SAT, layout-aware + air-wall)
  - venue_optimizer.optimize: CP-SAT over one building (default) or <=2 adjacent, over the rooms union
    (MEASURED event_spaces + PLACEHOLDER fills) from task 2.
  - Each schedule block carries a layout and is sized against THAT layout's capacity column: hackathon
    work = classroom (fallback banquet_round), ceremony/keynote = theatre_lecture or fixed_seats,
    meals = buffet or banquet_round, networking = reception. A room with NULL for the needed layout cannot
    host that block.
  - Air-wall exclusivity: for a parsed air-wall group (e.g. GSU-219 / GSU-219A / GSU-219B) book the whole
    room OR its parts, never both at once.
  - Hard constraints capacity(layout)>=p90*1.1, step_free, overnight, AV; objective cost + walking
    distance + unused capacity.
  - Return top 3 options with assignments, utilization, win/lose reason; report unmet constraint if infeasible.
  - Test: air-wall exclusivity holds in every returned assignment.
  - _Requirements: 3.1-3.10_

- [ ] 6. [P0] Budget (thin) and plan orchestrator
  - budget.estimate: Monte Carlo over turnout + rate-card ranges -> line items + total p10/p50/p90,
    cost/attendee, sponsorship gap = p50 - budget.
  - plan.build: orchestrate attendance -> venue -> budget; assemble summary (building, cost band,
    readiness placeholder, top-3-risks placeholder).
  - _Requirements: 8.1, 8.2, 8.4_

- [ ] 7. [P0] Drill core + verdict (limited: occupancy + power + getting-home)
  - twin.run: 15-min steps for occupancy, power, and getting-home/mobility only (no air/CO2, network,
    or food/restroom queues in the P0 core - those move to P1 task 20).
  - Auto-include any planned MBTA disruption whose window overlaps the event dates (from transport.plan,
    e.g. the Oct 31-Nov 1 2026 Green Line closure with Route 57 shuttle), stressing getting-home/mobility.
  - verdict.assess: per-system status, first-failure time, tiered fixes, before/after re-run; readiness 0-100.
  - Wire readiness + top-3 risks back into plan.summary.
  - Test: an Oct 31 2026 event triggers the Green Line risk and the drill auto-includes the closure.
  - _Requirements: 9.1, 9.4, 9.5, 9.6, 9.7, 15.5_

- [ ] 8. [P0] API endpoints + CORS
  - Implement POST /brief/parse, /plan, /plan/options, /drill/run, /drill/compare, /privacy/upload,
    GET /provenance, /assumptions, /live/alerts; CORS for localhost:5173; works with LLM_PROVIDER=none.
  - _Requirements: 12.1-12.3_

- [ ] 8a. [P0] Thin acceptance checkpoint (post-API)
  - Smoke test right after the API lands: app boots, and with LLM_PROVIDER=none the acceptance brief
    flows POST /brief/parse -> POST /plan and returns a 200 with a non-empty plan summary (venue + budget
    present; drill/food/transport may be labelled stubs at this point).
  - Purpose: catch wiring/CORS/serialization breakage before building the frontend on top.
  - _Requirements: 12.1-12.3_

- [ ] 9. [P0] Frontend thin slice: Intake, Plan, Drill
  - Intake: text box + example chip + optional CSV upload + up to 3 inline follow-ups.
  - Plan: summary bar + 7 tiles with one-line status and details drawers + MapLibre base map.
  - Drill: floor/room grid by worst system, time scrubber + play, first-failure timeline, narration,
    Apply fixes & re-run. Status by colour AND text; light/dark.
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.8_

- [ ] 10. [P0 if <30 min, else P1] Privacy scrubber core + tests
  - Scope kept P0 ONLY if deliverable in under 30 minutes: scrubber (Presidio + BU_ID/MAC/BSSID
    recognizers) + unit tests. If it runs over 30 minutes, drop the whole task to P1.
  - Deferred to P1 regardless: tokenizer (HMAC-SHA256), vault (SQLite + audit), redact/mask/generalize
    operators, CLI python -m app.privacy.scrub, aggregate-only upload path, and <5-cell suppression.
  - Privacy upload UI is P1 (see frontend notes).
  - _Requirements: 1.7, 1.8, 1.9, 10.1, 10.2, 10.3, 10.5_

- [ ] 11. [P0] Agent tools + template explainer
  - tools: parse_brief, build_plan, compare_options, run_drill, get_live_alerts, get_provenance.
  - Template explainer uses only tool-output numbers and cites source ids.
  - _Requirements: 11.1, 11.2, 11.4, 11.5_

- [ ] 12. [P0] Thin end-to-end acceptance checkpoint
  - Automated test: the 300-person overnight AI hackathon brief returns an end-to-end plan (recommended
    building + room assignments, budget p10-p90, drill verdict with fixes + re-run) with LLM_PROVIDER=none.
  - tech/food/transport may be stubs that return labelled default values (provenance ASSUMED/PLACEHOLDER);
    the slice must still assemble a complete Plan and render via the API.
  - _Requirements: 14.1 (partial), 12.3_

## Phase 1 - Deepen each P0 section

- [ ] 13. [P1] Attendance fit from live data
  - Fit arrival/departure shape from Bluebikes Nov-2024 hourly trips near the building + Numina profiles;
    cache responses; feed samples to all models.
  - _Requirements: 2.4, 2.5_

- [ ] 14. [P1] Tech, Wi-Fi/network and power sizing (Wi-Fi detail)
  - Poisson devices/person; clients per room/block; APs needed vs access_points -> rental APs; Mbps peak +
    GB/day; power circuits via load/(0.8*20*120) -> stations.
  - Also covers the sensor logger (device/occupancy telemetry ingest) deferred from P0.
  - _Requirements: 4.1-4.5_

- [ ] 15. [P0] Food & water (BU dining first, then OSM)
  - Per meal, prefer BU dining halls (table dining, MEASURED) OPEN during the meal window first, then fall
    back to Overpass restaurants/cafes <=800 m (cached). Dining rows with blank/unknown hours are never
    assumed open and carry a "check hours" flag.
  - cost-tier heuristics + rate_cards (ASSUMED); per-meal 3 vendor options; SimPy M/M/c line
    recommendation; water litres/person/hr refill-vs-bottled; Overpass drinking_water.
  - _Requirements: 5.1-5.7_

- [ ] 16. [P0] Getting there (real stops/bus/parking + planned disruptions)
  - Real mbta_stops <=800 m (MEASURED, walk_min ASSUMED) + nearby bus_routes (MEASURED) + service window.
  - Parse service_alert into PlannedDisruption; when event dates overlap one, add to plan top risks and
    signal the drill to auto-include it (e.g. Green Line Oct 31-Nov 1 2026, Route 57 shuttle, fare-free).
  - Accessibility from wheelchair_accessible + accessibility_notes (e.g. Blandford St not accessible);
    live alerts (elevator closure = accessibility risk) + late-night gaps.
  - Bluebikes GBFS docks; parking from real parking table (MEASURED, else PLACEHOLDER) + OSM;
    crash-density KDE risk band + recommendation + caveats.
  - _Requirements: 6.1-6.8, 15.5_

- [ ] 17. [P1] Plan options (Lean/Balanced/Premium compare)
  - options.build varies catering tier, rental APs, AV, security for the Compare view.
  - _Requirements: 8.3_

## Phase 2 - Overnight depth (P1)

- [ ] 18. [P1] People recommendations
  - Topic embeddings; OpenAlex slice + cached API filtered to BU + nine campuses; aggregate by author;
    rank similarity*log(citations)*recency; public fields only; institution-diversity check; no demographics.
  - _Requirements: 7.1-7.5_

- [ ] 19. [P1] Sponsors
  - topics->O*NET occupations->industries->sponsors_placeholder categories by embedding similarity;
    rank by fit + typical ask; suggested ask level covering the budget gap.
  - _Requirements: 7.6, 7.7_

- [ ] 20. [P1] Drill extended systems
  - Add network load and food/restroom queues to twin.run. Add the air/CO2 mass-balance helper (air.co2, dC/dt = (N*G - Q*(C - C_out))/V, G=0.0052 L/s/person, C_out=420, amber 1000, red 1400) and wire air quality into twin.run; add sensitivity/tornado inputs.
  - _Requirements: 9.2, 9.3, 9.4 (extended), sensitivity_

- [ ] 21. [P1] Privacy risk report + Trust UI
  - risk_report: entities/column, residual scan target 0, k-anonymity on quasi-identifiers, utility check.
  - Trust page: provenance, label counts, privacy report, sensitivity tornado chart.
  - _Requirements: 10.4, 13.6_

- [ ] 22. [P1] RAG explainer
  - Build corpus over METHODS.md, ETHICS.md, dataset caveats, MBTA alert texts, placeholder README;
    MiniLM embeddings + NumPy cosine search; cite source ids; numbers only from tool outputs.
  - _Requirements: 11.3, 11.4, 11.5_

- [ ] 23. [P1] Compare and Export pages + polish
  - Compare: Lean/Balanced/Premium columns (cost, readiness, trade-offs).
  - Export: one-page printable plan + run-of-show + budget CSV. General UI polish.
  - _Requirements: 13.5, 13.7_

## Phase 3 - Acceptance

- [ ] 24. [P0] End-to-end acceptance test (two briefs)
  - Brief A (main demo): the 300-person overnight AI hackathon on Oct 24-25 returns within 10 s (cached
    APIs, LLM_PROVIDER=none) a plan with recommended building, room assignments, tech/power/water numbers,
    3 vendor options per meal, transit + parking, p10-p90 budget, and a drill verdict with fixes + re-run.
    Brief A MUST NOT surface the Oct 31-Nov 1 2026 Green Line closure.
  - Brief B (disruption): the SAME event on Oct 31-Nov 1 2026 MUST list the Green Line closure as a top
    risk with the Route 57 shuttle (fare-free) as the mitigation, and the drill MUST include that closure.
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

## Notes

- P0 = must work by 7:30 PM today (solo); P1 = overnight. Solo P0 scope: scaffold (1), loaders + DuckDB +
  provenance (2), rule-based intake only (3), attendance (4), venue optimizer (5), budget Monte Carlo (6),
  drill limited to occupancy + power + getting-home + verdict + re-run (7), API (8), food - BU dining +
  optional OSM (15), transport - MBTA stops/alerts/bus routes + parking (16), agent tools + explainer (11),
  and ONE combined frontend page (9: Intake + Plan summary + tiles + Drill). Task 8a is a thin acceptance
  checkpoint right after the API; task 12 is the broader end-to-end slice checkpoint.
- Privacy scrubber core + tests (10) is P0 ONLY if it comes in under 30 minutes; otherwise it drops to P1.
- Moved to P1 (overnight): sensor logger + Wi-Fi/tech detail (14), people/judges (18), sponsors (19),
  Lean/Balanced/Premium compare (17 + 23), privacy upload UI + Trust page (21), RAG explainer (22), the
  Export page (23), and attendance live-data fit (13 - today's attendance is covered by the thin task 4).
- task 24 is the full acceptance test.
- Real data wins: real BU CSVs in data/raw/bu/ (event_spaces, dining, mbta_stops, bus_routes, parking)
  load as MEASURED; walk_min stays ASSUMED; placeholder rooms (for buildings the real file omits) and
  derived room fields stay PLACEHOLDER/ASSUMED. Every loader reads CSVs (real and placeholder) with
  comment="#" and records the correct provenance label for every row.
- data/reference/bu_buildings_ref.csv backs the map and walking distances (built in task 2).
- New real-data tests (in tasks 2, 5, 7): blank capacities load as NULL (not 0); air-wall exclusivity;
  an Oct 31 2026 event triggers the Green Line risk + drill auto-include; every rooms row has a label.
- All P0 paths must work with LLM_PROVIDER=none and cached external APIs.
- Each numeric output must carry a provenance label (MEASURED/ASSUMED/PLACEHOLDER/SIMULATED).


