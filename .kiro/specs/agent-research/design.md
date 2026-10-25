# Design: agent-research

## Architecture

```
Frontend (research buttons + progress + result cards)
  POST /agent/research -> {job_id};  poll GET /agent/jobs/{job_id}
        |
FastAPI  (in-process JobStore: dict[job_id] -> Job{status, steps[], result, error})
        |  runs the agent in a background thread
backend/app/agent/research.py  (Gemini function-calling over MCP tools)
        |  MCP client session (stdio) ->
backend/app/mcp_server/server.py (FastMCP; read-only tools)
   plan_context | osm_places_near | web_search(Gemini+grounding) | openalex_people
        |
backend/app/agent/guardrails.py (scope, source-required, OSM verify, privacy, limits)
```

## Pieces

### llm.py gemini provider
`_gemini_client()` lazily imports `google.genai`, reads `settings.gemini_api_key`
/ `gemini_model`. `gemini_generate(prompt, tools=None, grounding=False, max_tokens)`
returns text + grounding metadata (sources). No key -> `LLMUnavailable`. The key
is never put in a response body or log line (we log only a boolean "gemini: on").

### config
New Settings fields + env: `gemini_api_key`, `gemini_model` (default
"gemini-2.0-flash"), `agent_max_tool_calls` (default 12), `agent_timeout_s`
(default 60). Agent cache dir = `active_cache_dir()/agent_cache`.

### MCP server (FastMCP)
Each tool has a pydantic input + output model. `web_search` builds the query from
a fixed template per purpose (catering/people/sponsors) using plan fields, calls
Gemini with Google Search grounding, and returns `answer_items[]` + `sources[]`
drawn from `grounding_metadata.grounding_chunks[].web`. `osm_places_near` queries
Overpass and caches JSON 24h under `data/raw/live/osm/`. `openalex_people` wraps
the existing `plan.people.recommend`-style ranking over the committed CSV.

### Agent (research.py)
Opens an MCP client session to the server, exposes the four tools to Gemini as
function declarations, and loops (bounded by `agent_max_tool_calls` /
`agent_timeout_s`). Emits progress steps into the Job. On completion, runs the
raw items through guardrails, validates with pydantic, caches the result.

Fallback: if Gemini is unavailable or guardrails drop everything, return the
existing estimate output (food_water meal costs for catering; people+sponsors
`recommend` for people) tagged with `fallback_reason`.

### Guardrails (code, not prompt)
- `check_scope(purpose)` -> raise/refuse if not in {catering, people, sponsors}.
- `require_source(item, grounding_urls)` -> drop items whose sources aren't in
  the grounding set.
- `verify_catering(item, osm_results)` -> difflib ratio ≥ 0.8 and ≤ 1500 m ->
  VERIFIED, else WEB_ONLY; drop > 1500 m.
- `scrub_person(item)` -> run scrubber (remove mode) on all text fields; drop
  profile URLs that look like contact dumps; append the official-channels note.
- `validate_tool_call(name, args)` -> name in allowlist and args match the tool
  schema, else reject + log.
- `enforce_limits` via a call counter + deadline in the agent loop.

### Provenance
Add `RESEARCHED = "RESEARCHED"` to `Label` (auto-joins ALLOWED_LABELS). Update
the two hardcoded 4-label lists (`/trust` endpoint, `TrustPanel`) to include it.

### Job API
`POST /agent/research` creates a Job, starts a thread running the agent, returns
`job_id`. `GET /agent/jobs/{id}` returns the job. Steps are appended as the agent
works ("Reading your plan", "Searching caterers near GSU", "Cross-checking with
OpenStreetMap", "Checking sources", "Done: 6 caterers (4 verified)").

### Budget link
`/plan` (or the budget card) exposes researched prices when ≥3 VERIFIED caterers
carry ranges; the frontend toggles catering to the median researched range,
labelled RESEARCHED. Backend budget gains an optional `researched_per_head`.

## Testing (mocked Gemini/search)
no-source-dropped; email/phone stripped; far caterer dropped; OSM match ->
VERIFIED; injected page instruction ignored; out-of-scope refused; tool-call cap
enforced; no-key fallback. Frontend: result cards render from a demo agent
snapshot; Verified/Web-only pill; sources present.
