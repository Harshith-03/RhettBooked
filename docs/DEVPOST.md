# RhettBooked — Devpost

Copy/paste-ready submission text. Every number here is reproduced in
`docs/NUMBERS.md` and labelled MEASURED / ASSUMED / PLACEHOLDER / SIMULATED /
RESEARCHED in the app's Trust view.

---

## Elevator pitch

Describe a Boston University event in one sentence and get a complete,
data-backed plan — venue, turnout, food, transit, people, budget, three cost
options and a digital-twin stress-test — where every number is labelled by how we
know it.

---

## Inspiration

Planning a campus event means juggling a dozen unknowns: which room fits, how many
people actually show up, what it costs, how everyone gets home if the Green Line is
down. Each lives in a different spreadsheet or someone's head. We wanted one
honest planner that models each piece from real data and never hides a guess behind
a confident number — so an organiser can see not just the answer, but how trustworthy
it is.

---

## What it does

From a single sentence ("300-person overnight AI hackathon at BU, Oct 24–25, budget
$15k, needs lunch/dinner/snack/breakfast") RhettBooked produces:

- **Venue & rooms** — a CP-SAT optimizer assigns the schedule's blocks to real BU
  event spaces (38 measured spaces) and recommends a building (e.g. GSU).
- **Turnout** — a Monte Carlo over a Beta show-up prior, with the 15-minute
  arrival/departure curve **fitted from real Bluebikes + Numina mobility data**.
- **Food & water** — BU dining-hall matching plus a guarded research agent that
  finds real caterers (with sources) or shows curated real options when offline.
- **Getting there** — nearest MBTA stops (accessibility flagged), parking, and
  planned disruptions (e.g. a Green Line closure with a fare-free Route 57 shuttle).
- **People & sponsors** — real OpenAlex researchers ranked as potential judges,
  public professional info only.
- **Budget** — a probabilistic budget (p10/p50/p90) tuned for a student event, with
  BU-provided resources shown as $0 in-kind.
- **Three options** — Lean / Balanced / Premium, side by side, with live
  client-side customization sliders.
- **Drill** — a digital-twin stress test (power, occupancy, getting-home) that finds
  the first failure, proposes fixes, and re-runs to show readiness before→after.

---

## How we built it

- **Backend:** Python 3.11, FastAPI, pydantic v2, pandas, DuckDB, NumPy, OR-Tools
  (CP-SAT), scikit-learn, httpx. A provenance layer stamps every output with a
  label and source and persists it to a `provenance` table.
- **Data science (not "an API call"):** models produce every number. The arrival
  curve is a fitted presence profile (running balance of Bluebikes starts−ends,
  blended 70/30 with Numina pedestrian counts); turnout and budget are Monte Carlo;
  venue assignment is CP-SAT; people ranking is TF-IDF/cosine over OpenAlex topics.
- **LLM is optional:** `backend/app/llm.py` is a provider adapter (gemini|none). The
  app runs fully on rule-based parsing and templates with `LLM_PROVIDER=none`. The
  LLM only parses the brief and explains results — it never invents numbers.
- **Guarded research agent + MCP:** a read-only MCP server exposes `plan_context`,
  `osm_places_near`, `web_search` (Gemini + Google Search grounding) and
  `openalex_people`. Guardrails are code-enforced: tool allowlist, call/time caps,
  "no source, no result", OSM cross-check for caterers, and a privacy scrubber for
  people. Web content is treated as data, never instructions.
- **Frontend:** React 18 + Vite + TypeScript + Tailwind + framer-motion. A VS
  Code-style docked layout: a full-width main pane with the three plan options and
  detail cards, and a docked side panel holding the live Customize sliders and a
  chat-style brief. Light/dark, status shown as colour **and** text.
- **Privacy:** uploaded registration data is scrubbed (emails/IDs/MAC/phones
  redacted) and survives only as aggregate counts with cells under five suppressed;
  HMAC tokenization with a separate vault supports audited re-linking.

---

## Challenges we ran into

- **Honest fallbacks under a rate limit.** Our live Gemini key hit its free-tier
  quota mid-build. Rather than fake caterer data, we built a sanitizer so provider
  errors never leak into snapshots or secrets, and a *curated real-caterer*
  fallback (labelled PLACEHOLDER, real URLs, no invented prices).
- **A real validation, not a flattering one.** We threw out an in-sample "RMSE
  0.022" that only measured our own smoothing and replaced it with a temporal
  holdout (fit on Nov 1–15, test on Nov 16–30).
- **Realistic cost.** The first budget looked like a corporate gala. We retuned the
  (clearly PLACEHOLDER) rate cards to student-event levels and modelled BU-provided
  resources as in-kind $0, landing a 300-person hackathon near $5k–$10k.

---

## Accomplishments that we're proud of

- A **temporal-holdout** arrival model that beats the naive trapezoid baseline by
  ~4.6× on RMSE (**0.107 vs 0.499**) with near-perfect rank correlation
  (**0.974 vs 0.006**) on the held-out weekend.
- **Every number labelled and traceable** — a Trust view and `/provenance` endpoint
  expose the MEASURED/ASSUMED/PLACEHOLDER/SIMULATED/RESEARCHED mix.
- A research agent with **code-enforced** guardrails, not just prompt text.
- Works end-to-end **with no API key and no backend** (bundled demo snapshots).

---

## What we learned

- Provenance is a feature, not paperwork — labelling forced honest modelling.
- "Calling an LLM is not data science": keeping the models in code (CP-SAT, Monte
  Carlo, KDE/fit) and the LLM to parsing/explaining made the project stronger.
- Guardrails belong in code where they can be tested, not in a prompt.

---

## What's next

- Confirm the PLACEHOLDER BU room/rate data against official BU Reservations.
- Blend more months of Bluebikes and BU-specific pedestrian counts into the curve.
- Presidio/spaCy NER in the scrubber (names, not just regex patterns).
- A draggable panel splitter and per-card deep-dives.

---

## How we used Kiro

We built RhettBooked with Kiro as the primary development environment, driving the
spec-first workflow in `.kiro/specs/eventtwin-core` and a set of steering rules
(`.kiro/steering/`) for tech stack, product, design system, and hard operating
rules (never push without approval, real data only, every number labelled, secrets
only in `.env`). Kiro also runs our **research MCP server** (see
`docs/KIRO_USAGE.md`): `plan_context`, `osm_places_near`, `web_search`, and
`openalex_people`, so the same guarded tools the app uses are callable from the
IDE. Agent hooks run tests on change.

---

## Additional info

- **Two submissions, separate repos.** RhettBooked (this repo) is the DS+X entry at
  https://rhettbooked.vercel.app; the frozen Hackachusetts entry is a separate repo.
- **Reproduce the numbers:** `docs/NUMBERS.md` lists each figure with the exact
  command. Tests: backend `python -m pytest`, frontend `npm test`.
- **Data sources:** BU event spaces (measured), MBTA GTFS, Bluebikes Nov 2024,
  Boston Numina, OpenAlex, OpenStreetMap Overpass. Room capacities/rates are
  PLACEHOLDER until confirmed with BU Reservations.
