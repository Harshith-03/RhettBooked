# EventTwin (RhettBooked)

An event-planning digital twin for Boston University. Backend: FastAPI (Render).
Frontend: React + Vite (Vercel). See `.kiro/specs/` for the full specs.

- **Live demo:** https://RhettBooked.vercel.app
- **Repo:** https://github.com/Harshith-03/RhettBooked

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

### Deploy checklist (Render)

`render.yaml` already sets `LLM_PROVIDER=gemini`, `GEMINI_MODEL`,
`EVENTTWIN_DB/CACHE`, and `ALLOWED_ORIGINS`. The ONE thing you must do by hand:

1. Render → service **RhettBooked-api** → Environment → add **`GEMINI_API_KEY`**
   (marked `sync: false` in the blueprint, so Render prompts for it). Paste the
   key, save, and let it redeploy.
2. Verify: open `https://<your-render-url>/health`. It should show
   `"llm_provider":"gemini"` and `"gemini":true`. If `"gemini":false`, the key
   isn't set on Render (it is NOT read from the local `.env`, which is never
   committed).
3. If the frontend origin differs from `https://RhettBooked.vercel.app`, update
   `ALLOWED_ORIGINS` in the Render dashboard (or `render.yaml`) to match.

### Deploy checklist (Vercel, frontend)

1. Import the repo, root directory `frontend/`, framework preset **Vite**.
2. Set **`VITE_API_URL`** to the Render backend URL
   (e.g. `https://rhettbooked-api.onrender.com`) in Project Settings →
   Environment Variables. Redeploy so the build picks it up.
3. The app falls back to bundled demo snapshots if the backend is unreachable
   (a grey "Demo snapshot" pill appears), so the demo works even before the
   backend is up.

### Research agent

`POST /agent/research {text|brief, task: catering|people}` → `{job_id}`; poll
`GET /agent/jobs/{job_id}` for `{status, steps[], result}`. The research MCP
server and tools are documented in `docs/KIRO_USAGE.md`.

## Frontend

See `frontend/README.md`. Set `VITE_API_URL` to the deployed backend.
