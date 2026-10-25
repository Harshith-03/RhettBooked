# RhettBooked

An event-planning digital twin for Boston University (formerly "EventTwin").
An admin describes an event in one sentence; RhettBooked produces a complete,
data-backed plan — venue & rooms (CP-SAT over real BU event spaces), turnout
(Monte Carlo with a Bluebikes/Numina-fitted arrival curve), food & water, getting
there (MBTA, parking), people & sponsors (OpenAlex + a guarded research agent),
a probabilistic budget, three plan options (Lean/Balanced/Premium), and a
digital-twin stress-test drill. Every number is labelled MEASURED, ASSUMED,
PLACEHOLDER, SIMULATED, or RESEARCHED.

Backend: FastAPI (Render). Frontend: React + Vite (Vercel). See `.kiro/specs/`
for the full specs, `docs/METHODS.md` for the data science, `docs/NUMBERS.md`
for every pitch figure recomputed, and `docs/ETHICS.md` for the commitments.

- **Live demo:** https://rhettbooked.vercel.app
- **Repo:** https://github.com/Harshith-03/RhettBooked

## Project status

Feature-complete for the DS+X submission. Backend **209 tests pass**, frontend
**24 tests pass**, frontend build clean. The app works fully with
`LLM_PROVIDER=none` (rule-based parser, curated/estimate fallbacks, bundled demo
snapshots), so it demos even with no key and no backend.

## Run it locally

```powershell
# Backend (FastAPI on :8000)
python -m pip install -r requirements.txt
$env:PYTHONPATH="."; python -m uvicorn backend.app.main:app --reload

# Backend tests
$env:PYTHONPATH="."; python -m pytest -p no:cacheprovider -q

# Frontend (Vite on :5173)
cd frontend; npm install; npm run dev

# Frontend tests + production build
cd frontend; npm test; npm run build

# Regenerate the bundled demo snapshots after a backend output change
$env:PYTHONPATH="."; python -m backend.scripts.export_demo
```

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
| `GEMINI_MODEL` | Gemini model id | set a current model (e.g. `gemini-2.5-flash`) |
| `AGENT_MAX_TOOL_CALLS` | agent tool-call cap | default 12 |
| `AGENT_TIMEOUT_S` | agent wall-clock limit | default 60 |

Set `GEMINI_API_KEY` in Render → Environment (secret), never in git. Without a
key, the research agent falls back to labelled results — curated real caterers
(PLACEHOLDER) for catering and OpenAlex judges for people — and the rest of the
app is unaffected. If the configured `GEMINI_MODEL` is unavailable or
rate-limited, the agent catches the error (sanitized, never leaking provider
text) and falls back the same way.

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
3. If the frontend origin differs from `https://rhettbooked.vercel.app`, update
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
