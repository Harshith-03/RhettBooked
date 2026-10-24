# Implementation Plan

## Overview

Tasks are ordered so a thin end-to-end plan works early, then each section is deepened. Each task is tagged
**[P0]** (working by 7:30 PM today) or **[P1]** (overnight). Loaders must read placeholder CSVs with
comment="#" / skiprows=1 and still record the PLACEHOLDER provenance label. The thin vertical slice
(tasks 1-11) delivers parse -> attendance -> venue -> budget -> drill -> API -> Intake/Plan/Drill UI,
and task 12 is a thin acceptance checkpoint with tech/food/transport stubbed to labelled defaults.

## Task Dependency Graph

Tasks within the same wave have no interdependencies and may run in parallel. Each wave depends on the
prior waves completing.

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2", "3", "8", "10"] },
    { "wave": 3, "tasks": ["4", "9"] },
    { "wave": 4, "tasks": ["5", "11"] },
    { "wave": 5, "tasks": ["6", "13", "16"] },
    { "wave": 6, "tasks": ["7", "15", "17"] },
    { "wave": 7, "tasks": ["12"] },
    { "wave": 8, "tasks": ["14", "18", "19", "21", "22", "23"] },
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
    "9": ["8"],
    "5": ["4"],
    "11": ["8", "9"],
    "6": ["5"],
    "13": ["4"],
    "16": ["5"],
    "7": ["6"],
    "15": ["4", "5"],
    "17": ["6"],
    "12": ["7", "8", "11"],
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

- [ ] 1. [P0] Scaffold backend, config, and provenance
  - Create FastAPI app skeleton (backend/app/main.py), app package layout, and pytest setup.
  - Add llm.py adapter (bedrock|anthropic|ollama|none); `none` raises LLMUnavailable and returns template text.
  - Add config/assumptions.yaml with Beta show-up priors, devices/person, Mbps/device, watts/device,
    AP comfortable limit, water litres/person/hr, dietary shares, contingency - each with value, range, source.
  - Implement the provenance table + a helper that records (output_key, label, source, value_summary).
  - _Requirements: 11, 12.3_

- [ ] 2. [P0] Data loaders and DuckDB build
  - loaders.py reads placeholder CSVs with comment="#"/skiprows=1 and tags every row PLACEHOLDER in provenance.
  - build_db.py loads buildings, rooms, parking, rate_cards into data/processed/eventtwin.duckdb.
  - _Requirements: 3.1, 8.1 (loader rule), provenance_

- [ ] 3. [P0] EventBrief model and rule-based intake
  - Define EventBrief + needs sub-model (pydantic v2).
  - intake.parse: LLM-with-strict-JSON path and regex/keyword fallback producing the same model.
  - questions.missing: at most 3 follow-ups for missing critical fields only.
  - Unit tests incl. the acceptance brief parsing under LLM_PROVIDER=none.
  - _Requirements: 1.1-1.6_

- [ ] 4. [P0] Attendance (thin) and Monte Carlo harness
  - attendance.sample: Beta show-up prior by type/free-paid; 15-min concurrency curve; overnight decay;
    Monte Carlo 500 draws; expose p50/p90. (Fit refinement deferred to task 12.)
  - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_

- [ ] 5. [P0] Venue optimizer (CP-SAT)
  - venue_optimizer.optimize: CP-SAT over one building (default) or <=2 adjacent; hard constraints
    capacity>=p90*1.1, step_free, overnight, AV; objective cost + walking distance + unused capacity.
  - Return top 3 options with assignments, utilization, win/lose reason; report unmet constraint if infeasible.
  - _Requirements: 3.1-3.6_

- [ ] 6. [P0] Budget (thin) and plan orchestrator
  - budget.estimate: Monte Carlo over turnout + rate-card ranges -> line items + total p10/p50/p90,
    cost/attendee, sponsorship gap = p50 - budget.
  - plan.build: orchestrate attendance -> venue -> budget; assemble summary (building, cost band,
    readiness placeholder, top-3-risks placeholder).
  - _Requirements: 8.1, 8.2, 8.4_

- [ ] 7. [P0] Drill core + verdict (thin)
  - twin.run: 15-min steps for occupancy, power, mobility (no air/CO2 in the P0 core).
  - verdict.assess: per-system status, first-failure time, tiered fixes, before/after re-run; readiness 0-100.
  - Wire readiness + top-3 risks back into plan.summary.
  - _Requirements: 9.1, 9.5, 9.6, 9.7_

- [ ] 8. [P0] API endpoints + CORS
  - Implement POST /brief/parse, /plan, /plan/options, /drill/run, /drill/compare, /privacy/upload,
    GET /provenance, /assumptions, /live/alerts; CORS for localhost:5173; works with LLM_PROVIDER=none.
  - _Requirements: 12.1-12.3_

- [ ] 9. [P0] Frontend thin slice: Intake, Plan, Drill
  - Intake: text box + example chip + optional CSV upload + up to 3 inline follow-ups.
  - Plan: summary bar + 7 tiles with one-line status and details drawers + MapLibre base map.
  - Drill: floor/room grid by worst system, time scrubber + play, first-failure timeline, narration,
    Apply fixes & re-run. Status by colour AND text; light/dark.
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.8_

- [ ] 10. [P0] Privacy core + aggregate suppression
  - scrubber (Presidio + BU_ID/MAC/BSSID recognizers), tokenizer (HMAC-SHA256), vault (SQLite + audit),
    redact/mask/generalize operators; CLI python -m app.privacy.scrub.
  - Upload path keeps only aggregates; suppress any cell < 5 people.
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
  - _Requirements: 14.2 (partial), 12.3_

## Phase 1 - Deepen each P0 section

- [ ] 13. [P0] Attendance fit from live data
  - Fit arrival/departure shape from Bluebikes Nov-2024 hourly trips near the building + Numina profiles;
    cache responses; feed samples to all models.
  - _Requirements: 2.4, 2.5_

- [ ] 14. [P0] Tech, network and power sizing
  - Poisson devices/person; clients per room/block; APs needed vs access_points -> rental APs; Mbps peak +
    GB/day; power circuits via load/(0.8*20*120) -> stations.
  - _Requirements: 4.1-4.5_

- [ ] 15. [P0] Food & water
  - Overpass restaurants/cafes <=800 m (cached); cost-tier heuristics + rate_cards (ASSUMED); per-meal 3
    vendor options + BU Dining; SimPy M/M/c line recommendation; water litres/person/hr refill-vs-bottled;
    Overpass drinking_water.
  - _Requirements: 5.1-5.7_

- [ ] 16. [P0] Getting there
  - MBTA stops <=800 m + service window + alerts (elevator closure = accessibility risk) + late-night gaps;
    Bluebikes GBFS docks; parking (placeholder + OSM); crash-density KDE risk band + recommendation + caveats.
  - _Requirements: 6.1-6.6_

- [ ] 17. [P0] Plan options (Lean/Balanced/Premium)
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

- [ ] 24. [P0] End-to-end acceptance test
  - Automated test: the 300-person overnight AI hackathon brief returns within 10 s (cached APIs,
    LLM_PROVIDER=none) a plan with recommended building, room assignments, tech/power/water numbers, 3
    vendor options per meal, transit + parking, p10-p90 budget, and a drill verdict with fixes + re-run.
  - _Requirements: 14.1, 14.2_

## Notes

- P0 = must work by 7:30 PM today; P1 = overnight. The thin slice (tasks 1-11) is the earliest point the
  end-to-end plan renders; task 12 is a thin acceptance checkpoint (tech/food/transport stubbed to labelled
  defaults); tasks 13-17 deepen the remaining P0 detail; task 24 is the full acceptance test.
- Every loader reads placeholder CSVs with comment="#" / skiprows=1 yet records the PLACEHOLDER provenance label.
- All P0 paths must work with LLM_PROVIDER=none and cached external APIs.
- Each numeric output must carry a provenance label (MEASURED/ASSUMED/PLACEHOLDER/SIMULATED).


