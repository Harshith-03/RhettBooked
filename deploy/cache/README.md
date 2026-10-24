# Deploy cache

Cached external-API responses (OSM Overpass, MBTA live, Bluebikes GBFS, OpenAlex)
for the acceptance briefs, so the deployed app makes **no external calls at
startup**. The app reads this directory when `EVENTTWIN_CACHE=deploy/cache` is set.

Current status: the P0 slice built so far (intake → attendance → venue → budget →
drill) uses only committed BU CSV data and the demo DuckDB — it makes no external
API calls. The food (task 15), transport-live (task 16), and people (task 18)
services will write their cached responses here; this directory is the committed
cache they fall back to offline.

Contents are MEASURED/PLACEHOLDER public data only — no personal data.
