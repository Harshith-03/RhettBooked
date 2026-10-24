# EventTwin backend image for Render.
# Build context is the REPO ROOT (see render.yaml dockerContext), so paths below
# are relative to the project root.
FROM python:3.11-slim

# Faster, quieter Python; no .pyc, unbuffered logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime deps first for better layer caching.
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

# App code, config, committed data, and the demo DuckDB + cache.
COPY backend ./backend
COPY config ./config
COPY data ./data
COPY deploy ./deploy

# Use the committed, personal-data-free demo DuckDB and offline cache so the
# container needs no build step or external calls at startup.
ENV EVENTTWIN_DB=deploy/eventtwin_demo.duckdb \
    EVENTTWIN_CACHE=deploy/cache \
    LLM_PROVIDER=none

# Render provides $PORT. Default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT expands at runtime.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
