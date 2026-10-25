# EventTwin

An event-planning digital twin for Boston University. Backend: FastAPI (Render).
Frontend: React + Vite (Vercel). See `.kiro/specs/` for the full specs.

## Backend deployment (Render)

The backend ships as a Docker image (`backend/Dockerfile`, `render.yaml`) using
the committed `deploy/eventtwin_demo.duckdb`, so no build step or external calls
are needed at startup.

### Environment variables

| Variable | Purpose | Notes |
|----------|---------|-------|
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `localhost:5173` always allowed |
| `EVENTTWIN_DB` | DuckDB path | default `deploy/eventtwin_demo.duckdb` |
| `EVENTTWIN_CACHE` | cached-response dir | default `deploy/cache` |
| `LLM_PROVIDER` | `gemini` \| `none` | `none` runs everything on estimates |
| `GEMINI_API_KEY` | Gemini key for the research agent | **backend-only; never commit; never sent to the frontend or logged** |
| `GEMINI_MODEL` | Gemini model id | e.g. `gemini-2.0-flash` (set a current model) |
| `AGENT_MAX_TOOL_CALLS` | agent tool-call cap | default 12 |
| `AGENT_TIMEOUT_S` | agent wall-clock limit | default 60 |

Set `GEMINI_API_KEY` in Render → Environment (secret), never in git. Without a
key, the research agent returns the existing estimate results (labelled) and the
rest of the app is unaffected. If the configured `GEMINI_MODEL` is unavailable,
the agent catches the error and falls back to estimates.

### Research agent

`POST /agent/research {text|brief, task: catering|people}` → `{job_id}`; poll
`GET /agent/jobs/{job_id}` for `{status, steps[], result}`. The research MCP
server and tools are documented in `docs/KIRO_USAGE.md`.

## Frontend

See `frontend/README.md`. Set `VITE_API_URL` to the deployed backend.
