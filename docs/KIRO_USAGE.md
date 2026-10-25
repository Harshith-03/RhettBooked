# Kiro usage: RhettBooked research MCP server

RhettBooked ships a read-only MCP server (`backend/app/mcp_server/server.py`,
FastMCP) so Kiro itself can call the research tools: `plan_context`,
`osm_places_near`, `web_search` (Gemini + Google Search grounding), and
`openalex_people`.

## Register the server with Kiro

Add this to `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json`
(user). This file is permission-protected, so add it by hand:

```json
{
  "mcpServers": {
    "eventtwin-research": {
      "command": "python",
      "args": ["-m", "backend.app.mcp_server.server"],
      "cwd": "${workspaceFolder}",
      "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}",
        "GEMINI_MODEL": "${GEMINI_MODEL}"
      },
      "disabled": false,
      "autoApprove": ["plan_context", "osm_places_near", "openalex_people"]
    }
  }
}
```

Requires `pip install mcp google-genai`. `web_search` needs a valid
`GEMINI_API_KEY`; the other three tools work without one. `web_search` is left
off `autoApprove` on purpose so grounded web calls are confirmed each time.

## Environment

- `GEMINI_API_KEY` — backend-only; never sent to the frontend and never logged
  (the app logs only a boolean "gemini: on/off").
- `GEMINI_MODEL` — e.g. `gemini-2.5-flash` (default `gemini-2.0-flash`).
- `AGENT_MAX_TOOL_CALLS` (default 12), `AGENT_TIMEOUT_S` (default 60).

## Tools (all read-only)

- `plan_context(plan_id)` — aggregate plan context (building, lat/lon, dates,
  headcount p50/p90, meals, dietary aggregate counts, budget gap). Aggregates
  only; never attendee rows.
- `osm_places_near(lat, lon, radius_m<=1500, kinds)` — OpenStreetMap food
  places, cached 24h under `data/raw/live/osm/`.
- `web_search(query, purpose)` — Gemini with Google Search grounding; returns
  `answer_items[]` + grounded `sources[]`. The query is built from a fixed
  per-purpose template; free-form queries from page content are not allowed.
- `openalex_people(topics, k)` — the existing real OpenAlex ranking.
