import json
import urllib.request
from urllib.error import HTTPError

from backend.app.data import fetch_openalex as fo

# Try classic page= offset pagination (keyless, capped at 10k results).
for page in (1, 2, 3):
    url = (
        "https://api.openalex.org/works"
        f"?filter=institutions.id:{fo.BU_INSTITUTION},from_publication_date:2022-01-01"
        "&select=id,display_name,publication_year,cited_by_count,authorships,concepts"
        f"&per-page=200&page={page}&mailto={fo._mailto()}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": f"eventtwin ({fo._mailto()})"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read())
        print(f"page {page}: OK, {len(d['results'])} results")
    except HTTPError as e:
        print(f"page {page}: HTTP {e.code} {e.read().decode()[:150]}")
