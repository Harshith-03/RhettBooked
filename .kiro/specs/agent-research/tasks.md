# Tasks: agent-research

- [x] 1. Config + RESEARCHED label + gemini provider in llm.py
- [x] 2. Guardrails module (scope, source-required, OSM verify, privacy, limits, validation)
- [x] 3. MCP server (FastMCP): plan_context, osm_places_near, web_search, openalex_people + mcp.json
- [x] 4. Research agent (research.py): catering + people, with fallback
- [x] 5. Async job API: POST /agent/research, GET /agent/jobs/{id}
- [x] 6. Budget link: researched per-head when >=3 verified
- [x] 7. Frontend: Food caterers + People/sponsors research UI (progress + result cards + disclaimer)
- [x] 8. Demo snapshots + requirements-deploy + README env docs
- [x] 9. Tests (backend guardrails + API, frontend render) + build

Complete on branch agent-research. Backend 207 tests pass; frontend builds + 8
tests pass. Not pushed.

Notes:
- mcp.json is documented in docs/KIRO_USAGE.md (the .kiro/settings path is
  permission-protected; add it by hand).
- `.kiro/settings/mcp.json` NOT written (protected path) - see KIRO_USAGE.md.
- The committed .env has GEMINI_MODEL=gemini-2.5-flash which the API reports as
  retired; set a current model. The agent falls back to estimates on any error.
