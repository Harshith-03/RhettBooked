# Design Document

## Overview

EventTwin turns a plain-language brief into one organized, non-overwhelming plan across seven sections plus
three plan tiers, backed by a digital-twin stress test. This design follows the steering decisions: FastAPI
+ pydantic v2 backend, DuckDB for data, OR-Tools/SimPy/NumPy/SciPy/scikit-learn for the models,
sentence-transformers for embeddings, Presidio for privacy, and a React + Vite + Tailwind frontend. The LLM
only parses the brief and explains results; every number is produced by a model and carries a provenance
label. The whole system runs with `LLM_PROVIDER=none`.

The build order is deliberately thin-first: a vertical slice (parse -> attendance -> venue -> budget ->
drill verdict -> plan JSON -> Intake/Plan/Drill UI) must work end to end early (P0), then each section is
deepened (remaining P0 detail, then P1).

## Architecture

```
Frontend (React/Vite/TS/Tailwind, MapLibre, Recharts)
  Intake -> Plan -> Drill -> Compare -> Trust -> Export
        |  HTTP (CORS localhost:5173)
        v
FastAPI (backend/app/main.py)
  /brief/parse  /plan  /plan/options  /drill/run  /drill/compare
  /privacy/upload  /provenance  /assumptions  /live/alerts
        |
        v
Agent layer (agent/tools.py, explainer.py, rag.py)
        |
        v
Domain services
  brief/      -> EventBrief, intake, questions
  plan/       -> attendance, venue_optimizer, tech, food_water, transport,
                 people, sponsors, budget, options, plan (orchestrator)
  drill/      -> twin, power, network, air, queues, mobility, montecarlo,
                 sensitivity, verdict
  privacy/    -> scrubber, tokenizer, vault, risk_report
        |
        v
Data layer (data/)
  loaders.py (comment="#", provenance=PLACEHOLDER), build_db.py -> DuckDB
  osm.py / mbta.py / openalex.py (httpx + cache to data/raw/live/)
  placeholder_gen.py (already built)
config/assumptions.yaml  (ASSUMED params with value, range, source)
```

### Cross-cutting: provenance
A single `provenance` table (DuckDB) records `(output_key, label, source, value_summary)` where label is
MEASURED / ASSUMED / PLACEHOLDER / SIMULATED. Every service appends provenance rows as it computes. Loaders
tag placeholder CSV rows PLACEHOLDER. `GET /provenance` returns the table; the Trust page renders label counts.

### Cross-cutting: LLM adapter
`llm.py` exposes `parse_json(prompt, schema)` and `explain(context)` over providers bedrock|anthropic|
ollama|none. With `none`, `parse_json` raises `LLMUnavailable` so callers use the rule-based path, and
`explain` returns the template explainer output.

### Cross-cutting: external APIs and caching
`osm.py`, `mbta.py`, `openalex.py` use httpx. Every response is written to `data/raw/live/<source>/<key>.json`;
on network failure the cached file is used. This is what makes the <10 s cached acceptance run deterministic.

## Components and Interfaces

### brief/
- `EventBrief` (pydantic v2) with the fields from Requirement 1 and a `needs` sub-model.
- `intake.parse(text) -> (EventBrief, list[Question])`: tries `llm.parse_json` under a strict JSON schema,
  falls back to regex/keyword extraction; both paths produce the same model.
- `questions.missing(brief) -> list[Question]` (<= 3), covering only critical fields
  (type, dates, expected_registrations, budget_usd, meals when food is implied).

### plan/
- `attendance.sample(brief, building) -> AttendanceSamples`: Beta show-up prior (by type + free/paid) from
  assumptions.yaml; 15-min concurrency curve fitted from Bluebikes Nov-2024 hourly trips + Numina profiles;
  overnight decay for hackathons; Monte Carlo 500 draws; exposes p50/p90 per block.
- `venue_optimizer.optimize(brief, p90, blocks) -> list[BuildingOption]` (top 3): CP-SAT over rooms in one
  building (default) or <=2 adjacent buildings; hard constraints capacity>=p90*1.1, step_free, overnight,
  AV; objective = room cost + inter-block walking distance + unused capacity; each option carries
  assignments, utilization, and a win/lose reason.
- `tech.size(brief, assignments, attendance) -> TechPlan`: Poisson devices/person; clients per room/block;
  APs needed vs room access_points -> rental APs; Mbps -> peak per room + GB/day; power circuits via
  load/(0.8*20*120) -> stations.
- `food_water.plan(brief, building, attendance) -> FoodWaterPlan`: Overpass restaurants/cafes <=800 m
  (cached); cost-tier via cuisine/brand heuristics + rate_cards; per-meal 3 vendor options + BU Dining;
  SimPy M/M/c serving-line recommendation; water litres/person/hr (ASSUMED) refill-vs-bottled;
  Overpass drinking_water.
- `transport.plan(brief, building, attendance) -> TransportPlan`: MBTA stops <=800 m + service window +
  alerts (elevator closure = accessibility risk) + late-night gaps; Bluebikes GBFS docks; parking
  (placeholder + OSM); crash-density KDE (Vision Zero + Cambridge) -> risk band + recommendation + caveats.
- `people.recommend(brief) -> list[Person]` (P1): topic embeddings; OpenAlex slice + cached API filtered to
  BU + nine campuses; aggregate by author; rank by similarity*log(citations)*recency; public fields only;
  institution-diversity check.
- `sponsors.recommend(brief, budget_gap) -> list[SponsorCategory]` (P1): topics->O*NET occupations->
  industries->sponsors_placeholder categories by embedding similarity; rank by fit + typical ask;
  suggested ask level covering the gap.
- `budget.estimate(plan) -> BudgetResult`: Monte Carlo over turnout + rate-card ranges -> per-line-item and
  total p10/p50/p90, cost/attendee, sponsorship gap = p50 - budget.
- `options.build(plan) -> {lean, balanced, premium}`: varies catering tier, rental APs, AV, security.
- `plan.build(brief) -> Plan`: the orchestrator calling attendance -> venue -> tech/food/transport ->
  budget, assembling the summary (recommended building, cost p10-p90, readiness score, top 3 risks).

### drill/
- `twin.run(plan, disruptions) -> DrillResult`: 15-min steps; delegates to power, network, air, queues,
  mobility; P0 systems (occupancy, power, mobility) plus verdict first, P1 (network, air, queues,
  sensitivity) after.
- `air.co2(N, Q, V, t)`: mass balance dC/dt = (N*G - Q*(C - C_out))/V, G=0.0052 L/s/person, C_out=420,
  amber 1000, red 1400.
- `montecarlo` drives draws; `verdict.assess` -> per-system status + first-failure time + tiered fixes
  (Do now / Plan for / Improve later) + before/after on re-run; readiness = weighted share ok across draws.
- `sensitivity` (P1) -> tornado inputs.

### privacy/
- `scrubber` (Presidio analyzer + custom BU_ID `\bU\d{8}\b`, MAC_ADDRESS, BSSID recognizers), `tokenizer`
  (HMAC-SHA256 deterministic), `vault` (separate SQLite + audit log), `risk_report` (entities/column,
  residual scan target 0, k-anonymity on quasi-identifiers, utility check). CLI `python -m app.privacy.scrub`.
- Aggregation guard: any aggregate cell < 5 people is suppressed.

### agent/
- `tools`: parse_brief, build_plan, compare_options, run_drill, get_live_alerts, get_provenance.
- `explainer` (P0 template) uses only tool-output numbers and cites source ids; `rag` (P1) over METHODS.md,
  ETHICS.md, dataset caveats, MBTA alert texts, placeholder README using MiniLM + NumPy cosine search.

### API (main.py)
Endpoints per Requirement 12; CORS for localhost:5173; all routes work with `LLM_PROVIDER=none`.

### Frontend (frontend/src/pages)
Intake, Plan, Drill (P0); Compare, Trust, Export (P1). MapLibre map with building/rooms/food/stops/docks/
parking + toggleable crash heat layer; Recharts for budget bands and tornado; status via colour AND text;
light/dark modes.

## Data Models

- `EventBrief`, `Question` (brief/)
- `AttendanceSamples { per_block: list[BlockStat{p50,p90,draws}] }`
- `BuildingOption { building_id, assignments, utilization, reason }`
- `TechPlan`, `FoodWaterPlan`, `TransportPlan`, `Person`, `SponsorCategory`
- `BudgetResult { line_items[], total_p10/p50/p90, cost_per_attendee, sponsorship_gap }`
- `Plan { brief, summary, venue, tech, food_water, transport, people?, budget, drill }`
- `DrillResult { per_system[], first_failure_time, fixes{do_now,plan_for,improve_later}, readiness }`
- `ProvenanceRow { output_key, label, source, value_summary }`
- Persistence: DuckDB `data/processed/eventtwin.duckdb` (buildings, rooms, parking, provenance, caches);
  privacy vault in a separate SQLite file.

## Error Handling

- LLM unavailable or invalid JSON -> rule-based fallback (never fails the request).
- External API failure -> cached response; if no cache, a labelled degraded result plus a caveat.
- Venue infeasibility -> report the unmet constraint rather than throwing.
- Privacy: cells < 5 suppressed; residual PII detected -> report flags it and blocks downstream use.
- All numeric outputs must carry a provenance label; a missing label is a server error in tests.

## Testing Strategy

- Unit tests (pytest) per service: attendance priors, CP-SAT constraints, AP/power formulas, CO2 mass
  balance (known closed-form checks), M/M/c waits, KDE risk bands, tokenizer determinism.
- Property-based checks where useful: provenance label present on every output number; aggregate
  suppression for n<5; tokenizer is deterministic and collision-resistant on sample data.
- Privacy: residual-scan = 0 on a seeded PII fixture; k-anonymity threshold enforced.
- Integration: the Requirement 14 acceptance brief returns a full plan in <10 s with cached APIs and
  `LLM_PROVIDER=none`; drill produces a verdict and a re-run before/after.
- Frontend: smoke tests that Intake -> Plan -> Drill render against a recorded plan JSON.

## Correctness Properties

### Property 1: Provenance totality
Every numeric field in a `Plan`, `BudgetResult`, or `DrillResult` has a matching `ProvenanceRow` whose
label is one of MEASURED, ASSUMED, PLACEHOLDER, SIMULATED.

**Validates: Requirements 1.1, 2.6, 8.4**

### Property 2: Placeholder labelling
Any value sourced from `data/placeholder/` is labelled PLACEHOLDER. Loaders skip the `# PLACEHOLDER`
comment row (comment="#" / skiprows=1) yet still emit the PLACEHOLDER provenance label.

**Validates: Requirements 1.7**

### Property 3: Aggregate suppression
For any aggregate derived from uploaded data, cells representing fewer than 5 people never appear in output.

**Validates: Requirements 1.9**

### Property 4: Venue hard constraints
In any returned assignment: assigned capacity >= p90 x 1.1; step_free holds when accessibility is needed;
overnight_allowed holds when the event is overnight; and the required AV level is satisfied.

**Validates: Requirements 3.3**

### Property 5: Tokenizer determinism
The same input token always maps to the same HMAC-SHA256 value, and distinct inputs do not collide on the
test corpus.

**Validates: Requirements 10.2**

### Property 6: Residual PII is zero
After scrubbing a seeded PII fixture, the residual scan count is 0.

**Validates: Requirements 10.4**

### Property 7: Offline determinism
With cached APIs and `LLM_PROVIDER=none`, the acceptance brief yields the same structural plan on repeated runs.

**Validates: Requirements 12.3, 14.2**

### Property 8: Explainer grounding
The explainer emits only numbers present in tool outputs and cites a source id for each number.

**Validates: Requirements 11.5**

### Property 9: CO2 steady state
`air.co2` converges to the closed-form steady state C_out + N*G/Q within tolerance.

**Validates: Requirements 9.3**

