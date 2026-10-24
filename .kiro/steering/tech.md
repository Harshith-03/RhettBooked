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

Secrets only in .env; never commit .env, secrets/, or data/raw/.