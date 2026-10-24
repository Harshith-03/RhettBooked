# Requirements Document

## Introduction

EventTwin is an event-planning digital twin for Boston University. An admin describes an event in plain
language and EventTwin produces ONE organized plan across seven sections (Venue, Tech, Food & Water,
Getting There, People, Budget, Drill), plus three side-by-side plan options (Lean / Balanced / Premium).

This spec covers the core end-to-end system: intake, attendance modelling, venue optimization, tech/power,
food & water, transport, people & sponsors, budget, the digital-twin drill, privacy, the agent/RAG layer,
the HTTP API, and the frontend.

Guiding rules (from steering): every number is labelled MEASURED / ASSUMED / PLACEHOLDER / SIMULATED with
its source; real data always wins over placeholder data; models produce every number while the LLM only
parses the brief and explains results; the BU event spaces, dining, parking, MBTA stops and bus routes are
now real MEASURED datasets (in `data/raw/bu/`), and placeholder rows are used only to fill gaps those real
files do not cover (e.g. buildings with no listed event spaces); all uploaded/scraped data passes through
the privacy scrubber first and personal data survives only as aggregate counts; everything must work with
`LLM_PROVIDER=none`; people recommendations expose only public information and never infer demographics.

### Priority tags
- **P0** = must be working by 7:30 PM today (thin end-to-end plan plus deepened core sections).
- **P1** = overnight work (deeper models, secondary UI, polish).

### Loader rule (carried from prior decision, extended for real data)
Every loader MUST read placeholder CSVs with `comment="#"` (or `skiprows=1`) so the `# PLACEHOLDER`
row is skipped, and MUST still record the PLACEHOLDER label in the provenance table.

Real-data-wins rule: the real BU datasets live in `data/raw/bu/` (canonical names
`bu_event_spaces.csv`, `bu_dining_locations.csv`, `mbta_stations_bu.csv`, `mbta_bus_routes_bu.csv`,
`bu_parking.csv`). Where a real file covers an entity, the real row wins and is labelled MEASURED;
placeholder rows are used only to fill the entities the real files do not cover, and those stay labelled
PLACEHOLDER. Each real CSV is still read with `comment="#"` so any leading comment row is skipped.

### Data source map (real = MEASURED unless noted)
- `bu_event_spaces.csv` -> table `event_spaces` (MEASURED). Blank layout-capacity column = that layout is
  not offered and is stored as NULL (never 0). When `max_capacity` is blank it is derived as the max of
  the per-layout capacity columns.
- `bu_dining_locations.csv` -> table `dining` (MEASURED). Hours like `08:00-22:00` are parsed; blank hours
  are "unknown" and flagged "check hours" (the planner never assumes a location is open).
- `mbta_stations_bu.csv` -> table `mbta_stops` (MEASURED; `walk_min_ASSUMED` stays ASSUMED). The
  `service_alert` free text is parsed into structured planned disruptions (start date, end date, affected
  lines, shuttle note). `wheelchair_accessible` + `accessibility_notes` drive accessibility flags.
- `mbta_bus_routes_bu.csv` -> table `bus_routes` (MEASURED).
- `bu_parking.csv` -> table `parking` (MEASURED when present in `data/raw/bu/`; otherwise the placeholder
  `data/placeholder/bu_parking.csv` is used and labelled PLACEHOLDER).
- `data/reference/bu_buildings_ref.csv` -> table `buildings` (a reference the map and walking distances
  need), keyed by `building_code`, covering every code that appears in `event_spaces`, `dining` and the
  placeholder buildings. Columns: `building_code, name, address, lat, lon, overnight_allowed,
  accessible_entrance, label`. lat/lon copied from placeholder `bu_buildings.csv` where the name matches
  (keep that label), otherwise approximated from the address and labelled ASSUMED; `overnight_allowed` and
  `accessible_entrance` are ASSUMED unless a note says otherwise (e.g. "Elevators unlock 1 hr before/after
  events" records an access restriction).

## Glossary
- **EventBrief**: the structured pydantic model describing an event.
- **p90 occupancy**: the 90th-percentile concurrent attendance for a block, from the attendance model.
- **Provenance**: a record of every output number's label (MEASURED/ASSUMED/PLACEHOLDER/SIMULATED) and source.
- **Drill**: a digital-twin stress test stepping the plan through 15-minute blocks under disruptions.
- **Readiness score**: 0-100 weighted share of systems "ok" across Monte Carlo draws.

---

## Requirements

## Requirement 1: Intake (P0)

**User Story:** As an event admin, I want to describe my event in plain text and upload an optional
registration CSV, so that EventTwin builds a structured brief while asking only for what is missing.

#### Acceptance Criteria
1. THE SYSTEM SHALL define an `EventBrief` pydantic v2 model with fields: name, type
   (hackathon|conference|career_fair|workshop|social|other), description, dates and times, overnight
   (bool), expected_registrations, audience, budget_usd, meals[], accessibility_needs,
   preferred_area, topics[], and needs (wifi_heavy, av, stage, breakout_rooms, quiet_room, sleeping_rooms).
2. WHEN free text is submitted THE SYSTEM SHALL parse it into an `EventBrief`.
3. WHERE `LLM_PROVIDER` is not `none` THE SYSTEM SHALL parse using the LLM constrained to a strict JSON schema.
4. WHERE `LLM_PROVIDER` is `none` OR the LLM parse fails THE SYSTEM SHALL parse using a regex/keyword fallback.
5. WHEN required critical fields are missing after parsing THE SYSTEM SHALL return at most 3 follow-up
   questions covering ONLY the missing critical fields.
6. WHEN all critical fields are present THE SYSTEM SHALL return zero follow-up questions.
7. WHEN a registration CSV is uploaded THE SYSTEM SHALL pass it through the privacy scrubber before any use.
8. THE SYSTEM SHALL retain from an uploaded CSV only aggregates: headcount, dietary counts by category,
   accessibility counts, and affiliation mix.
9. IF any aggregate cell represents fewer than 5 people THEN THE SYSTEM SHALL suppress that cell.

## Requirement 2: Attendance (P0)

**User Story:** As a planner, I want a realistic turnout and concurrency curve, so that every downstream
model sizes to real demand.

#### Acceptance Criteria
1. THE SYSTEM SHALL estimate expected turnout as registrations x a show-up rate drawn from a
   Beta prior selected by event type and whether the event is free, read from `config/assumptions.yaml`.
2. THE SYSTEM SHALL produce a peak-concurrency curve per 15-minute block.
3. WHERE the event is an overnight hackathon THE SYSTEM SHALL apply an overnight decay to the curve.
4. THE SYSTEM SHALL fit the arrival/departure shape from Bluebikes Nov 2024 hourly trips near the chosen
   building combined with Numina pedestrian profiles.
5. THE SYSTEM SHALL expose attendance samples via Monte Carlo with 500 draws for use by all later models.
6. THE SYSTEM SHALL label turnout outputs SIMULATED and the priors ASSUMED with their sources.

## Requirement 3: Venue optimizer (P0)

**User Story:** As a planner, I want rooms assigned per schedule block, so that I get the best building fit.

#### Acceptance Criteria
1. THE SYSTEM SHALL accept the brief, the attendance p90, and schedule blocks (main hall, breakouts,
   food area, quiet/sleeping rooms).
2. THE SYSTEM SHALL build the optimizer `rooms` set as the UNION of `event_spaces` (MEASURED) and
   placeholder rooms for buildings NOT present in `event_spaces` (e.g. CDS), the latter labelled PLACEHOLDER.
3. THE SYSTEM SHALL fill and label as ASSUMED any room field missing from the source data:
   `power_circuits = ceil(sqft / 400)`, `access_points = ceil(max_capacity / 40)`, `rate_per_hour` from
   `rate_cards.yaml` by room size, and `ventilation_cfm = 7.5 x max_capacity`.
4. THE SYSTEM SHALL assign rooms per block using CP-SAT across ONE building by default, or up to 2
   adjacent buildings.
5. THE SYSTEM SHALL map each schedule block to a layout and size the block against THAT layout's capacity
   column: hackathon work = classroom (fallback banquet_round), ceremony/keynote = theatre_lecture or
   fixed_seats, meals = buffet or banquet_round, networking = reception. A room whose needed layout column
   is NULL CANNOT host that block.
6. THE SYSTEM SHALL treat air-wall rooms (parsed from the notes, e.g. GSU-219 splitting into GSU-219A +
   GSU-219B) as mutually exclusive: the optimizer may book the whole room OR its parts, never both at once.
7. THE SYSTEM SHALL enforce hard constraints: capacity (for the block's layout) >= p90 occupancy x 1.1;
   step_free when accessibility is needed; overnight_allowed when the event is overnight; and the required
   AV level met.
8. THE SYSTEM SHALL minimize an objective of room cost + walking distance between blocks + unused capacity.
9. THE SYSTEM SHALL return the top 3 building options, each with assignments, utilization, and the reason
   it won or lost.
10. IF no feasible assignment exists THEN THE SYSTEM SHALL report which constraint could not be satisfied.

## Requirement 4: Tech, network and power (P0)

**User Story:** As a planner, I want Wi-Fi, data and power sized per room, so that I know what to rent.

#### Acceptance Criteria
1. THE SYSTEM SHALL model devices per person as Poisson with a prior by event type.
2. THE SYSTEM SHALL compute concurrent clients per room per block and APs needed = clients / per-AP
   comfortable limit (ASSUMED).
3. WHEN APs needed exceeds a room's `access_points` THE SYSTEM SHALL report the gap as rental APs.
4. THE SYSTEM SHALL compute data usage as Mbps per active device by event type, yielding peak Mbps per
   room and total GB per day.
5. THE SYSTEM SHALL compute power as watts per device and circuits needed = load / (0.8 x 20 A x 120 V),
   yielding power stations to rent.

## Requirement 5: Food & water (P0)

**User Story:** As a planner, I want meal and water plans with vendor options, so that nobody waits or goes hungry.

#### Acceptance Criteria
1. THE SYSTEM SHALL query Overpass for amenity=restaurant|fast_food|cafe within 800 m of the building and
   cache the results.
2. THE SYSTEM SHALL classify each place into a cost tier using cuisine/brand heuristics plus
   `rate_cards.yaml`, labelled ASSUMED.
3. THE SYSTEM SHALL plan each meal using the headcount at that meal time from attendance and dietary
   splits from aggregates or ASSUMED shares.
4. THE SYSTEM SHALL prefer BU dining halls (table `dining`, MEASURED) that are OPEN during the meal
   window first, THEN fall back to OSM restaurants. A dining location with blank/unknown hours is NOT
   treated as open; it is offered only with a "check hours" flag.
5. THE SYSTEM SHALL return 3 vendor options per meal (cheapest, best-rated-proxy, closest) with cost ranges.
6. THE SYSTEM SHALL model the serving queue as an M/M/c queue in SimPy and recommend a line count from the
   expected wait.
7. THE SYSTEM SHALL compute water need as litres per person per active hour (ASSUMED), comparing refill
   stations vs bottled with cost, and query Overpass amenity=drinking_water near the building.

## Requirement 6: Getting there (P0)

**User Story:** As an attendee planner, I want transit, bikes, parking and late-night safety, so that
people arrive and leave safely.

#### Acceptance Criteria
1. THE SYSTEM SHALL list MBTA stops within 800 m from the real `mbta_stops` dataset (MEASURED) and the
   API, with service in the event window, plus nearby bus routes from `bus_routes` (MEASURED).
2. WHEN the event dates overlap a planned disruption parsed from `mbta_stops.service_alert` THE SYSTEM
   SHALL add that disruption to the plan's top risks AND auto-include it in the drill (e.g. the Green Line
   closure Oct 31-Nov 1 2026 with the Route 57 shuttle, fare-free).
3. WHEN live alerts affect those stops THE SYSTEM SHALL surface them AND flag elevator closures as an
   accessibility risk.
4. THE SYSTEM SHALL derive stop accessibility from `wheelchair_accessible` + `accessibility_notes`
   (e.g. Blandford Street is not accessible) and flag inaccessible nearest stops.
5. THE SYSTEM SHALL identify late-night service gaps within the event window.
6. THE SYSTEM SHALL list Bluebikes docks nearby using GBFS capacity and parking options from the real
   `parking` table (MEASURED when `data/raw/bu/bu_parking.csv` is present, else PLACEHOLDER) plus OSM.
7. THE SYSTEM SHALL compute a crash-density KDE (Vision Zero + Cambridge) along walking corridors to the
   nearest stops, returning a risk band and a recommendation (shuttle window, buddy walk).
8. THE SYSTEM SHALL display dataset caveats for the safety layer.

## Requirement 7: People and sponsors (P1)

**User Story:** As an organizer, I want judge/speaker and sponsor suggestions from public data, so that I
can build a program without scraping private data.

#### Acceptance Criteria
1. THE SYSTEM SHALL embed the brief's topics and search the OpenAlex works slice and, with caching, the
   OpenAlex API filtered to BU and the nine campuses.
2. THE SYSTEM SHALL aggregate works by author and rank by topic similarity x log(citations) x recency.
3. THE SYSTEM SHALL return for each person only name, institution, top matching work titles, and the
   OpenAlex profile link.
4. THE SYSTEM SHALL include an institution-diversity check.
5. THE SYSTEM SHALL NOT return contact information and SHALL NOT infer gender, race, or other demographics.
6. THE SYSTEM SHALL map topics to O*NET occupations by embedding similarity, occupations to industries,
   and industries to the sponsors_placeholder categories.
7. THE SYSTEM SHALL rank sponsor categories by fit and typical ask, and output a suggested ask level that
   covers the budget gap.

## Requirement 8: Budget and options (P0)

**User Story:** As a planner, I want a probabilistic budget and three plan tiers, so that I can see cost
and the sponsorship gap.

#### Acceptance Criteria
1. THE SYSTEM SHALL run Monte Carlo over turnout and rate-card ranges to produce cost per line item and a
   total p10/p50/p90, plus cost per attendee.
2. THE SYSTEM SHALL compute the sponsorship gap as p50 cost minus budget.
3. THE SYSTEM SHALL build Lean / Balanced / Premium plans varying catering tier, rental APs, AV, and
   security level for the Compare view.
4. THE SYSTEM SHALL label budget outputs SIMULATED and rate-card inputs ASSUMED.

## Requirement 9: Drill - digital-twin stress test (P0 core; P1 extended)

**User Story:** As a planner, I want to stress-test the chosen plan, so that I find failures and fixes
before the event.

#### Acceptance Criteria
1. THE SYSTEM SHALL step the chosen plan through 15-minute blocks evaluating (P0) room occupancy vs
   capacity, power circuits, AP load, and late-night departures vs transit plus crash exposure.
2. THE SYSTEM SHALL evaluate (P1) network load, air quality, and food/restroom queues.
3. THE SYSTEM SHALL compute CO2 by mass balance dC/dt = (N*G - Q*(C - C_out))/V with G = 0.0052 L/s/person,
   C_out = 420 ppm, amber at 1000 ppm, red at 1400 ppm.
4. THE SYSTEM SHALL support disruptions: Green Line outage, +30% turnout, rain, an AP down, elevator
   closure. WHEN the event dates overlap a planned disruption from `mbta_stops` THE SYSTEM SHALL
   auto-include that disruption (e.g. the Oct 31-Nov 1 2026 Green Line closure) in the drill run.
5. THE SYSTEM SHALL return per-system status (ok/strained/failing), first-failure time, and tiered fixes
   (Do now / Plan for / Improve later).
6. WHEN the user applies fixes and re-runs THE SYSTEM SHALL show before/after results.
7. THE SYSTEM SHALL compute a readiness score 0-100 as the weighted share of systems ok across Monte
   Carlo draws.

## Requirement 10: Privacy (P0 core; P1 report UI)

**User Story:** As a data steward, I want PII scrubbed and audited, so that no personal data leaks into plans.

#### Acceptance Criteria
1. THE SYSTEM SHALL run a Presidio analyzer with custom recognizers for BU_ID (`\bU\d{8}\b`),
   MAC_ADDRESS, and BSSID.
2. THE SYSTEM SHALL generate deterministic HMAC-SHA256 tokens stored in a separate SQLite vault with an
   audit log.
3. THE SYSTEM SHALL provide redact, mask, and generalize operators.
4. THE SYSTEM SHALL produce a risk report with entities per column, a residual scan targeting 0, a
   k-anonymity check on quasi-identifiers, and a utility check.
5. THE SYSTEM SHALL provide a CLI `python -m app.privacy.scrub <csv>`.

## Requirement 11: Agent and RAG (P0 parser + template explainer; P1 RAG)

**User Story:** As a user, I want explanations grounded in the actual outputs, so that I trust the plan.

#### Acceptance Criteria
1. THE SYSTEM SHALL expose tools: parse_brief, build_plan, compare_options, run_drill, get_live_alerts,
   get_provenance.
2. THE SYSTEM SHALL provide a template-based explainer (P0) that uses only numbers from tool outputs.
3. THE SYSTEM SHALL build a RAG corpus (P1) over METHODS.md, ETHICS.md, dataset caveats, MBTA alert texts,
   and the placeholder README.
4. THE SYSTEM SHALL cite source ids in explanations.
5. THE SYSTEM SHALL NOT introduce numbers that are absent from the tool outputs.

## Requirement 12: API (P0)

**User Story:** As the frontend, I want HTTP endpoints, so that I can drive the whole flow.

#### Acceptance Criteria
1. THE SYSTEM SHALL expose POST /brief/parse, POST /plan, POST /plan/options, POST /drill/run,
   POST /drill/compare, POST /privacy/upload, GET /provenance, GET /assumptions, GET /live/alerts.
2. THE SYSTEM SHALL enable CORS for http://localhost:5173.
3. THE SYSTEM SHALL operate fully when `LLM_PROVIDER=none`.

## Requirement 13: Frontend (P0: Intake, Plan, Drill; P1: Compare, Trust, Export, polish)

**User Story:** As an admin, I want a clear dashboard, so that the plan is organized and not overwhelming.

#### Acceptance Criteria
1. THE Intake page SHALL show one large "Describe your event" text box, an example chip, and an optional
   CSV upload, and SHALL show up to 3 follow-up questions inline.
2. THE Plan page SHALL show a summary bar (recommended building, cost p10-p90, readiness score, top 3
   risks) and 7 tiles (Venue, Tech, Food & Water, Getting There, People, Budget, Drill), each with a
   one-line status and a details drawer.
3. THE Plan page SHALL include a map of the building, rooms, food, stops, docks, parking, and a toggleable
   crash heat layer.
4. THE Drill page SHALL show a floor/room grid coloured by worst system, a time scrubber with play, a
   first-failure timeline, a narration panel, and an "Apply fixes & re-run" action.
5. THE Compare page (P1) SHALL show Lean/Balanced/Premium columns with cost, readiness, and trade-offs.
6. THE Trust page (P1) SHALL show provenance, label counts (MEASURED/ASSUMED/PLACEHOLDER/SIMULATED), the
   privacy report, and a sensitivity tornado chart.
7. THE Export page (P1) SHALL produce a one-page printable plan plus run-of-show and a budget CSV.
8. THE SYSTEM SHALL convey status with colour AND text, and support light and dark modes.

## Requirement 14: End-to-end acceptance (P0)

**User Story:** As a judge, I want one brief to produce a full plan quickly offline, so that the demo works.

#### Acceptance Criteria
1. **Brief A (main demo).** WHEN the brief "300-person overnight AI hackathon at BU, Oct 24-25, students,
   budget $15k, needs lunch, dinner, midnight snack, breakfast" is submitted with cached APIs THE SYSTEM
   SHALL return within 10 seconds a plan containing a recommended building, room assignments,
   tech/power/water numbers, 3 vendor options per meal, transit and parking, a p10-p90 budget, and a drill
   verdict with fixes and a re-run.
2. **Brief A (main demo).** THE SYSTEM SHALL NOT surface the Oct 31-Nov 1 2026 Green Line closure for
   Brief A, because the Oct 24-25 dates do not overlap that planned disruption.
3. **Brief B (disruption).** WHEN the SAME 300-person overnight AI hackathon is submitted for Oct 31-Nov 1
   2026 THE SYSTEM SHALL list the Green Line closure as a top risk, SHALL present the Route 57 shuttle
   (fare-free) as the mitigation, AND the drill SHALL include that closure in its run.
4. THE SYSTEM SHALL satisfy acceptance criteria 1-3 with `LLM_PROVIDER=none`.

## Requirement 15: Real BU data integration and labelling (P0)

**User Story:** As a planner, I want the plan built on the real BU datasets with correct labels, so that
recommendations reflect actual spaces, dining, transit and parking rather than placeholders.

#### Acceptance Criteria
1. THE SYSTEM SHALL load the real CSVs from `data/raw/bu/` into tables `event_spaces`, `dining`,
   `mbta_stops`, `bus_routes`, and `parking`, each labelled MEASURED (with `walk_min_ASSUMED` kept ASSUMED
   and placeholder-derived rooms kept PLACEHOLDER).
2. WHEN a layout-capacity column is blank THE SYSTEM SHALL store NULL (not 0) and SHALL derive a blank
   `max_capacity` as the max of the per-layout capacities.
3. THE SYSTEM SHALL build `data/reference/bu_buildings_ref.csv` covering every building_code used by
   `event_spaces`, `dining`, and the placeholder buildings, with lat/lon from placeholder `bu_buildings.csv`
   where names match (else ASSUMED) and `overnight_allowed`/`accessible_entrance` ASSUMED unless a note
   indicates a restriction.
4. THE SYSTEM SHALL ensure every row in the optimizer `rooms` set carries a provenance label
   (MEASURED, ASSUMED, or PLACEHOLDER).
5. THE SYSTEM SHALL parse `mbta_stops.service_alert` into structured planned disruptions (start date,
   end date, affected lines, shuttle note) used by transport risks and the drill.

#### Test coverage (added)
- Blank capacity columns are loaded as NULL (not 0).
- Air-wall exclusivity: the optimizer never books a whole air-wall room and one of its parts at the same time.
- An event on Oct 31 2026 triggers the Green Line planned-closure risk and the drill auto-includes it.
- Every `rooms` row has a provenance label.

