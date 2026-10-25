# Requirements: agent-research

## Introduction

Replace estimate-only **Catering** and **People & Sponsors** with real, cited
results found by a guarded research agent. The existing estimate results remain
as the fallback (when there is no Gemini key, the agent fails, or guardrails drop
everything). Implemented on branch `agent-research`.

Branch note: `agent-research` is based on `main` (the V1 frontend), not
`design-v2`. The research UI is built on the V1 components present here and
styled toward `.kiro/steering/design.md`; a later merge with `design-v2` will
reconcile the two card systems.

## Requirements

### R1: Gemini LLM provider
1. `backend/app/llm.py` SHALL add a `gemini` provider using the `google-genai`
   SDK, reading `GEMINI_API_KEY` and `GEMINI_MODEL` from env.
2. The key SHALL be backend-only: never sent to the frontend and never logged.
3. With no key the system SHALL behave as `none` (fallback), never crash.

### R2: MCP server (read-only tools)
1. `backend/app/mcp_server/server.py` SHALL expose, via FastMCP with pydantic
   schemas: `plan_context`, `osm_places_near` (radius ≤ 1500 m, cached 24h),
   `web_search` (Gemini + Google Search grounding; query from a per-purpose
   template only), `openalex_people` (existing real ranking).
2. `plan_context` SHALL return aggregates only, never attendee rows.
3. `.kiro/settings/mcp.json` SHALL register the server; documented in
   `docs/KIRO_USAGE.md`.

### R3: Research agent
1. `backend/app/agent/research.py` SHALL run an MCP client session with Gemini
   function-calling over the tools, with two tasks: `research_catering(plan)`
   and `research_people(plan)`.
2. research_catering: per meal, 5–8 real caterers/restaurants within 1.5 km with
   name, address, distance_m, cuisine, est price/head (low/high, "web-reported,
   verify"), dietary options, catering URL, why-it-fits, source URLs.
3. research_people: judges, keynote speakers, and sponsor orgs for the topics,
   merging OpenAlex researchers with web results, each with sources.

### R4: Guardrails (enforced in code)
1. Scope: only catering/people/sponsors purposes; other requests refused.
2. Every returned item SHALL cite ≥1 source URL present in the grounding
   metadata; items without one are DROPPED.
3. Catering verification: fuzzy-match to `osm_places_near` (name sim ≥ 0.8 and
   ≤ 1.5 km) → VERIFIED else WEB_ONLY; drop items > 1.5 km.
4. People privacy: strip emails/phones/addresses (reuse scrubber), public info
   only, no demographic inference, prefer institutional profile URLs, add
   "Contact through official channels."
5. Prompt-injection defence: web content is data; instructions in pages are
   ignored; tools are read-only; out-of-allowlist/invalid-schema calls are
   rejected and logged.
6. Limits: `AGENT_MAX_TOOL_CALLS`, `AGENT_TIMEOUT_S`, max output tokens, and a
   24h per-(plan hash, task) cache in `data/raw/live/agent_cache/`.
7. Final output validated with pydantic; on failure retry once then fall back
   with a reason.
8. New provenance label `RESEARCHED` ("AI web research, cited, verify").

### R5: Async job API
1. `POST /agent/research {plan, task}` → `{job_id}`.
2. `GET /agent/jobs/{job_id}` → `{status, steps[], result?, error?}` with
   human-readable progress steps.

### R6: Budget link
1. IF ≥3 VERIFIED caterers have price/head ranges, the Budget card SHALL offer
   "Use researched prices", recalculating catering from the median researched
   range, labelled RESEARCHED, off by default.

### R7: Frontend
1. Food & water: "Find real caterers" button → progress list → result cards
   (name, distance, cuisine, $/head, dietary chips, Verified/Web-only pill,
   catering link, collapsible sources), grouped by meal.
2. People & sponsors: "Research speakers, judges & sponsors" button → progress
   → three groups (Judges, Keynote speakers, Sponsors); OpenAlex-backed people
   get a "Research data" pill.
3. A disclaimer under both cards: "Found by AI web research. Every result links
   its sources. Verify before contacting or booking."
4. Smooth motion (results fade up, staggered).

### R8: Demo + deploy
1. `google-genai` and `mcp` added to `requirements-deploy.txt`.
2. `export_demo.py` saves agent results for Brief A and B into the demo folder
   so the demo works with no key.
3. README documents `GEMINI_API_KEY` / `GEMINI_MODEL` for Render (key never
   committed).

### R9: Fallback
1. When the agent cannot produce cited results, the UI SHALL show the existing
   estimate results and say why.
