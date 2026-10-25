"""
tools_impl.py

The actual logic behind the MCP tools, kept separate from the FastMCP wrapper so
it is importable and testable without the MCP SDK. All tools are read-only.
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import active_cache_dir
from .schemas import (
    OpenAlexIn,
    OpenAlexPerson,
    OpenAlexResult,
    OsmIn,
    OsmPlace,
    OsmResult,
    PlanContext,
    WebSearchIn,
    WebSearchResult,
    WebSource,
)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_CACHE_TTL_S = 24 * 3600

# web_search query templates per purpose. The model NEVER supplies a free-form
# query; the agent fills these fields, the server builds the final string.
QUERY_TEMPLATES = {
    "catering": (
        "catering or group food orders for a {headcount}-person event near "
        "{building} Boston for {meal}; include price per head and dietary options"
    ),
    "people": (
        "potential judges or keynote speakers in {topics} based in the Boston area "
        "with a public professional profile"
    ),
    "sponsors": (
        "Boston-area companies or organizations in {topics} with a public "
        "sponsorship or university-partnership program"
    ),
}


# --------------------------------------------------------------------------- #
# plan_context (aggregates only)
# --------------------------------------------------------------------------- #
def plan_context_from_plan(plan: dict, plan_id: str = "current") -> PlanContext:
    summary = plan.get("summary", {}) or {}
    venue = plan.get("venue", {}) or {}
    # Dietary aggregates: fall back to the ASSUMED shares if no upload exists.
    dietary = plan.get("dietary_counts") or {}
    meals = []
    food_tile = next((t for t in plan.get("tiles", []) if t.get("name") == "Food & Water"), None)
    if food_tile:
        meals = [m.get("meal") for m in (food_tile.get("details", {}).get("meals") or [])]
    lat = lon = None
    bref = plan.get("building_ref") or {}
    if bref:
        lat, lon = bref.get("lat"), bref.get("lon")
    return PlanContext(
        plan_id=plan_id,
        building=summary.get("recommended_building"),
        lat=lat,
        lon=lon,
        start=(plan.get("brief") or {}).get("start"),
        end=(plan.get("brief") or {}).get("end"),
        headcount_p50=int(summary.get("turnout_p50") or 0),
        headcount_p90=int(summary.get("turnout_p90") or 0),
        meals=[m for m in meals if m],
        dietary_counts=dietary,
        budget_gap=int(summary.get("sponsorship_gap") or 0),
    )


# --------------------------------------------------------------------------- #
# osm_places_near (Overpass, 24h cache)
# --------------------------------------------------------------------------- #
def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _osm_cache_path(inp: OsmIn) -> Path:
    d = active_cache_dir() / "osm"
    d.mkdir(parents=True, exist_ok=True)
    key = f"{inp.lat:.4f}_{inp.lon:.4f}_{inp.radius_m}_{'-'.join(sorted(inp.kinds))}"
    return d / f"{key}.json"


def osm_places_near(inp: OsmIn, *, fetch=None) -> OsmResult:
    """Query Overpass for amenities near a point, cached 24h. ``fetch`` is an
    injectable callable(query)->dict for tests (defaults to a live HTTP call)."""
    radius = min(int(inp.radius_m), 1500)
    use_cache = fetch is None   # live path only; injected fetch (tests) bypasses cache
    cache = _osm_cache_path(inp)
    if use_cache and cache.exists() and (time.time() - cache.stat().st_mtime) < OSM_CACHE_TTL_S:
        data = json.loads(cache.read_text(encoding="utf-8"))
        return _osm_from_overpass(data, inp, cached=True)

    amenity_re = "|".join(inp.kinds)
    q = (
        f"[out:json][timeout:25];"
        f'(node["amenity"~"{amenity_re}"](around:{radius},{inp.lat},{inp.lon});'
        f'way["amenity"~"{amenity_re}"](around:{radius},{inp.lat},{inp.lon}););'
        f"out center tags 40;"
    )
    data = (fetch or _overpass_fetch)(q)
    if use_cache:
        cache.write_text(json.dumps(data), encoding="utf-8")
    return _osm_from_overpass(data, inp, cached=False)


def _overpass_fetch(query: str) -> dict:  # pragma: no cover - live network
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=body, headers={"User-Agent": "eventtwin/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _osm_from_overpass(data: dict, inp: OsmIn, cached: bool) -> OsmResult:
    places: list[OsmPlace] = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        dist = int(_haversine_m(inp.lat, inp.lon, lat, lon)) if lat and lon else 0
        places.append(OsmPlace(
            name=name, cuisine=tags.get("cuisine", ""), distance_m=dist,
            website=tags.get("website", "") or tags.get("contact:website", ""),
            osm_id=f"{el.get('type', 'node')}/{el.get('id', '')}",
            lat=lat, lon=lon,
        ))
    places.sort(key=lambda p: p.distance_m)
    return OsmResult(places=places, cached=cached)


# --------------------------------------------------------------------------- #
# web_search (Gemini + Google Search grounding; templated query only)
# --------------------------------------------------------------------------- #
def build_query(purpose: str, fields: dict) -> str:
    tmpl = QUERY_TEMPLATES.get(purpose)
    if not tmpl:
        raise ValueError(f"no query template for purpose {purpose!r}")
    safe = {k: (v if v is not None else "") for k, v in fields.items()}
    return tmpl.format(**{**{"headcount": "", "building": "", "meal": "", "topics": ""}, **safe})


def web_search(inp: WebSearchIn, *, generate=None) -> WebSearchResult:
    """Call Gemini with Google Search grounding; return items + grounded sources.

    ``generate`` is injectable for tests: a callable(prompt)-> {"text","sources"}.
    Defaults to llm.gemini_generate(grounding=True).
    """
    if generate is None:
        from .. import llm
        generate = lambda p: llm.gemini_generate(p, grounding=True)
    out = generate(inp.query)
    text = out.get("text", "") or ""
    items = [line.strip("-• ").strip() for line in text.splitlines() if line.strip()]
    sources = [WebSource(url=s.get("url", ""), title=s.get("title", ""))
               for s in out.get("sources", []) if s.get("url")]
    return WebSearchResult(answer_items=items, sources=sources)


# --------------------------------------------------------------------------- #
# openalex_people (existing real ranking)
# --------------------------------------------------------------------------- #
def openalex_people(inp: OpenAlexIn) -> OpenAlexResult:
    from ..brief.models import EventBrief
    from ..plan import people as people_mod

    brief = EventBrief(description=" ".join(inp.topics), topics=list(inp.topics))
    res = people_mod.recommend(brief, top_n=inp.k)
    return OpenAlexResult(people=[
        OpenAlexPerson(
            name=p.name, institution=p.institution, topics=p.matching_topics,
            citations=p.citations, openalex_url=p.openalex_url,
        )
        for p in res.people
    ])
