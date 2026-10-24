# EventTwin frontend

Single-page React + Vite + TypeScript + Tailwind app. One page: intake box +
example chips → summary bar → tiles (Venue, Food & Water, Getting There, Budget,
Drill) → drill panel with "Run drill" and "Apply fixes & re-run".

## Configuration

The backend base URL is read from `VITE_API_URL` (default
`http://localhost:8000`). No URLs are hard-coded.

```bash
cp .env.example .env   # then edit VITE_API_URL if needed
```

On Vercel, set `VITE_API_URL` in Project Settings → Environment Variables.

## Develop

```bash
npm install
npm run dev      # http://localhost:5173
```

## Build / deploy

```bash
npm run build    # type-checks, outputs dist/
npm run preview  # serve the production build locally
```

`vercel.json` rewrites all routes to `/index.html` so the SPA handles routing.
Deploy by pointing Vercel at this `frontend/` directory (framework preset: Vite).

## Demo fallback

If a live API call fails or takes longer than 8 s, the app loads a bundled demo
snapshot from `src/demo/` and shows a small **Demo snapshot** badge, so the demo
always works offline.

Regenerate the snapshots from the backend:

```bash
# in-process (no running server needed):
python -m backend.scripts.export_demo
# or against a live backend:
python -m backend.scripts.export_demo --base-url http://localhost:8000
```
