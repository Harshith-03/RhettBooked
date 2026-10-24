# Tech stack (decided)

Backend: Python 3.11, FastAPI, pydantic v2, pandas, DuckDB (data/processed/eventtwin.duckdb), NumPy/SciPy,

OR-Tools (CP-SAT) for room assignment, SimPy for queues, scikit-learn (KDE), sentence-transformers

(all-MiniLM-L6-v2) with NumPy cosine search for RAG and people matching, Presidio + spaCy + Faker for

privacy, httpx, pytest.

External free APIs: OpenStreetMap Overpass (food, parking, water fountains), MBTA V3 API, Bluebikes

GBFS, OpenAlex API. Cache every response to data/raw/live/ and fall back to cache when offline.

LLM: backend/app/llm.py adapter (bedrock|anthropic|ollama|none), selected by env.

Frontend: React 18 + Vite + TypeScript + Tailwind, MapLibre GL, Recharts, lucide-react. Clean

operations-dashboard style, light and dark modes, status shown with colour AND text.

Secrets only in .env; never commit .env or secrets/.

Git policy (must match the root .gitignore):

- Ignored: .env, secrets/, __pycache__/, *.pyc, .venv/, venv/, node_modules/, frontend/dist/,

  .pytest_cache/, data/processed/*.duckdb, and data/raw/live/.

- Committed on purpose: deploy/eventtwin_demo.duckdb (a personal-data-free demo DB the Docker image

  uses at startup), and the public datasets data/raw/bu/ and data/raw/v3..v5/ which the image needs.

Deploy: the backend ships as a Docker image (backend/Dockerfile, python:3.11-slim) built from the REPO

ROOT context, running uvicorn on $PORT; Render blueprint in render.yaml with a /health check. The app

reads EVENTTWIN_DB (default deploy/eventtwin_demo.duckdb), EVENTTWIN_CACHE (deploy/cache), and CORS

origins from ALLOWED_ORIGINS (comma-separated; localhost:5173 always allowed). Use requirements-deploy.txt

(runtime only) in the image; if the privacy scrubber is added, lazy-load it and use spaCy en_core_web_sm,

not lg.