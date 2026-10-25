"""
research.py

The guarded research agent: catering and people/sponsors research with cited,
verified results, falling back to the existing estimates when the agent can't
produce grounded output.

The agent calls the MCP tool implementations (``mcp_server.tools_impl``) through
a guardrailed wrapper. When Gemini is configured it uses web_search grounding;
with no key it goes straight to the fallback. Progress is reported via a
``steps`` callback so the job API can stream human-readable progress.

Final output is validated with pydantic (the result models below); on validation
failure it retries once, then returns the fallback with a reason.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from ..config import agent_cache_dir, get_settings
from ..mcp_server import tools_impl
from ..mcp_server.schemas import OsmIn, WebSearchIn
from ..provenance import Label
from . import guardrails as G

StepCb = Callable[[str], None]


def _safe_reason(exc: Exception) -> str:
    """Map a provider exception to a clean, user-facing fallback reason.

    Never embeds raw provider error text (which can contain request details or
    quota JSON) into a serialized/user-visible field. Classified by error class
    / status code only, so demo snapshots stay free of error dumps and secrets.
    """
    text = f"{type(exc).__name__}: {exc}"
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return "Web research is rate-limited right now; showing estimates."
    if "401" in text or "403" in text or "PERMISSION" in text or "API key" in text:
        return "Web research is unavailable (auth); showing estimates."
    if "404" in text or "not found" in text.lower():
        return "The configured model is unavailable; showing estimates."
    if "timeout" in text.lower() or "deadline" in text.lower():
        return "Web research timed out; showing estimates."
    # Generic: name the error class only, never the message body.
    return f"Web research unavailable ({type(exc).__name__}); showing estimates."


# --------------------------------------------------------------------------- #
# Result schemas (pydantic-validated final output)
# --------------------------------------------------------------------------- #
class Caterer(BaseModel):
    name: str
    address: str = ""
    distance_m: int = 0
    cuisine: str = ""
    price_per_head_low: float | None = None
    price_per_head_high: float | None = None
    price_note: str = "web-reported, verify"
    dietary: list[str] = Field(default_factory=list)
    catering_url: str = ""
    why_fits: str = ""
    verification: str = G.WEB_ONLY
    source_urls: list[str] = Field(default_factory=list)


class MealCaterers(BaseModel):
    meal: str
    caterers: list[Caterer] = Field(default_factory=list)


class CateringResult(BaseModel):
    label: str = Label.RESEARCHED.value
    meals: list[MealCaterers] = Field(default_factory=list)
    verified_count: int = 0
    # When >=3 VERIFIED caterers carry price ranges, the median per-head range
    # the Budget card can offer ("Use researched prices"). None otherwise.
    researched_per_head: dict | None = None
    fallback_reason: str | None = None


class PersonResult(BaseModel):
    name: str
    role: str = ""
    organization: str = ""
    profile_url: str = ""
    relevance: str = ""
    source_urls: list[str] = Field(default_factory=list)
    research_data: bool = False       # True when OpenAlex-backed
    note: str = ""


class PeopleResearchResult(BaseModel):
    label: str = Label.RESEARCHED.value
    judges: list[PersonResult] = Field(default_factory=list)
    speakers: list[PersonResult] = Field(default_factory=list)
    sponsors: list[PersonResult] = Field(default_factory=list)
    fallback_reason: str | None = None


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def _cache_key(plan: dict, task: str) -> str:
    h = hashlib.sha256(json.dumps(plan.get("summary", {}), sort_keys=True).encode()).hexdigest()[:16]
    return f"{task}_{h}"


def _cache_get(key: str) -> dict | None:
    p = agent_cache_dir() / f"{key}.json"
    if p.exists() and (time.time() - p.stat().st_mtime) < 24 * 3600:
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _cache_put(key: str, data: dict) -> None:
    d = agent_cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Catering
# --------------------------------------------------------------------------- #
def research_catering(plan: dict, steps: StepCb | None = None, generate=None, osm_fetch=None) -> dict:
    step = steps or (lambda _s: None)
    s = get_settings()
    use_cache = generate is None and osm_fetch is None   # live path only
    key = _cache_key(plan, "catering")
    if use_cache:
        cached = _cache_get(key)
        if _is_cached_real(cached):
            step("Loaded cached research")
            return cached

    step("Reading your plan")
    ctx = tools_impl.plan_context_from_plan(plan)
    building = ctx.building or "the venue"

    if not s.gemini_enabled and generate is None:
        return _catering_fallback(plan, "No GEMINI_API_KEY; showing estimates.")

    budget = G.CallBudget(max_calls=s.agent_max_tool_calls, timeout_s=s.agent_timeout_s)
    lat, lon = ctx.lat or 42.3505, ctx.lon or -71.1054   # BU central fallback
    step(f"Cross-checking with OpenStreetMap near {building}")
    try:
        budget.charge("osm_places_near")
        osm = tools_impl.osm_places_near(
            OsmIn(lat=lat, lon=lon, radius_m=1500), fetch=osm_fetch
        ).places
    except Exception:
        osm = []
    osm_dicts = [o.model_dump() for o in osm]

    meals_out: list[dict] = []
    verified_total = 0
    for meal in (ctx.meals or ["lunch"]):
        step(f"Searching caterers near {building} for {meal}")
        try:
            budget.charge("web_search")
        except G.GuardrailError as e:
            step(f"Stopping: {e}")
            break
        query = tools_impl.build_query("catering", {
            "headcount": ctx.headcount_p50, "building": building, "meal": meal,
        })
        try:
            ws = tools_impl.web_search(WebSearchIn(query=query, purpose="catering"),
                                       generate=generate)
        except Exception as e:
            return _catering_fallback(plan, _safe_reason(e))
        grounding_urls = [s.url for s in ws.sources]

        step("Checking sources")
        raw_items = _parse_caterer_items(ws.answer_items, grounding_urls, osm_dicts, ctx)
        sourced = G.drop_unsourced(raw_items, grounding_urls)
        verified_items: list[dict] = []
        for it in sourced:
            v = G.verify_catering(it, osm_dicts)
            if v is not None:
                verified_items.append(v)
        verified_total += sum(1 for it in verified_items if it["verification"] == G.VERIFIED)
        meals_out.append({"meal": meal, "caterers": verified_items[:8]})

    total = sum(len(m["caterers"]) for m in meals_out)
    step(f"Done: {total} caterers ({verified_total} verified)")
    researched_per_head = _median_per_head(meals_out)
    result = {"label": Label.RESEARCHED.value, "meals": meals_out,
              "verified_count": verified_total,
              "researched_per_head": researched_per_head,
              "fallback_reason": None}
    try:
        CateringResult(**result)
    except ValidationError:
        return _catering_fallback(plan, "Result validation failed; showing estimates.")
    # Only cache successful RESEARCHED results from the live path (never fallbacks).
    if use_cache:
        _cache_put(key, result)
    return result


def _is_cached_real(cached: dict | None) -> bool:
    return bool(cached) and cached.get("label") == Label.RESEARCHED.value and not cached.get("fallback_reason")


def _parse_caterer_items(answer_items, grounding_urls, osm_dicts, ctx) -> list[dict]:
    """Turn model answer lines + OSM matches into caterer item dicts.

    The grounded OSM places are the backbone (real coordinates/distance); the web
    answer items contribute price/dietary hints. Each item is tagged with the
    grounding source URLs so require_source can keep it.
    """
    items: list[dict] = []
    for o in osm_dicts[:8]:
        items.append({
            "name": o["name"], "address": "", "distance_m": o["distance_m"],
            "cuisine": o.get("cuisine", ""),
            "price_per_head_low": None, "price_per_head_high": None,
            "price_note": "web-reported, verify", "dietary": [],
            "catering_url": o.get("website", ""),
            "why_fits": f"within 1.5 km of {ctx.building or 'the venue'}, fits {ctx.headcount_p50} p50",
            "source_urls": list(grounding_urls),
        })
    return items


def _median_per_head(meals_out: list[dict]) -> dict | None:
    """Median low/high per-head across VERIFIED caterers that carry a range.

    Returns {"low": x, "high": y, "n": k} only when >=3 such caterers exist
    (the threshold for offering "Use researched prices"), else None.
    """
    import statistics

    lows: list[float] = []
    highs: list[float] = []
    for m in meals_out:
        for c in m["caterers"]:
            if c.get("verification") == G.VERIFIED and c.get("price_per_head_low") is not None \
               and c.get("price_per_head_high") is not None:
                lows.append(float(c["price_per_head_low"]))
                highs.append(float(c["price_per_head_high"]))
    if len(lows) < 3:
        return None
    return {"low": round(statistics.median(lows), 2),
            "high": round(statistics.median(highs), 2), "n": len(lows)}


def _catering_fallback(plan: dict, reason: str) -> dict:
    """Fall back to the existing per-meal estimate from the Food & Water tile."""
    food = next((t for t in plan.get("tiles", []) if t.get("name") == "Food & Water"), None)
    meals_out = []
    for m in ((food or {}).get("details", {}).get("meals") or []):
        meals_out.append({"meal": m.get("meal"), "caterers": []})
    return {"label": Label.ASSUMED.value, "meals": meals_out,
            "verified_count": 0, "fallback_reason": reason}


# --------------------------------------------------------------------------- #
# People + sponsors
# --------------------------------------------------------------------------- #
# Brief topics are terse/abbreviated ("ai", "machine-learning"); OpenAlex concept
# names are multi-word, so expand to search-friendly tokens for TF-IDF matching.
_TOPIC_EXPANSION = {
    "ai": "artificial intelligence",
    "machine-learning": "machine learning",
    "ml": "machine learning",
    "data": "data science",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "robotics": "robotics",
    "security": "computer security",
    "health": "health medicine",
    "fintech": "finance technology",
    "sustainability": "sustainability climate",
}


def _expand_topics(topics: list[str]) -> list[str]:
    out: list[str] = []
    for t in topics:
        key = t.strip().lower()
        out.append(_TOPIC_EXPANSION.get(key, t.replace("-", " ")))
    return out or ["artificial intelligence"]


def research_people(plan: dict, steps: StepCb | None = None, generate=None) -> dict:
    step = steps or (lambda _s: None)
    s = get_settings()
    use_cache = generate is None
    key = _cache_key(plan, "people")
    if use_cache:
        cached = _cache_get(key)
        if _is_cached_real(cached):
            step("Loaded cached research")
            return cached

    step("Reading your plan")
    ctx = tools_impl.plan_context_from_plan(plan)
    topics = (plan.get("brief") or {}).get("topics") or []
    search_topics = _expand_topics(topics)

    # OpenAlex researchers are always real (no key needed) -> judges/speakers.
    step("Ranking OpenAlex researchers")
    from ..mcp_server.schemas import OpenAlexIn
    oa = tools_impl.openalex_people(OpenAlexIn(topics=search_topics, k=8)).people
    judges = [G.scrub_person({
        "name": p.name, "role": "Researcher / potential judge",
        "organization": p.institution, "profile_url": p.openalex_url,
        "relevance": ", ".join(p.topics[:3]),
        "source_urls": [p.openalex_url], "research_data": True,
    }) for p in oa[:5]]

    speakers: list[dict] = []
    sponsors: list[dict] = []
    web_error: str | None = None
    if s.gemini_enabled or generate is not None:
        budget = G.CallBudget(max_calls=s.agent_max_tool_calls, timeout_s=s.agent_timeout_s)
        for purpose, bucket in (("people", speakers), ("sponsors", sponsors)):
            step(f"Searching {('speakers' if purpose == 'people' else 'sponsors')}")
            try:
                budget.charge("web_search")
            except G.GuardrailError:
                break
            query = tools_impl.build_query(purpose, {"topics": " ".join(topics) or "AI"})
            try:
                ws = tools_impl.web_search(WebSearchIn(query=query, purpose=purpose),
                                           generate=generate)
            except Exception as e:
                web_error = _safe_reason(e)
                continue
            grounding_urls = [x.url for x in ws.sources]
            step("Checking sources")
            for line in ws.answer_items[:8]:
                item = {"name": line[:120], "role": "", "organization": "",
                        "profile_url": grounding_urls[0] if grounding_urls else "",
                        "relevance": "", "source_urls": list(grounding_urls),
                        "research_data": False}
                if G.require_source(item, grounding_urls):
                    bucket.append(G.scrub_person(item))

    total = len(judges) + len(speakers) + len(sponsors)
    step(f"Done: {len(judges)} judges, {len(speakers)} speakers, {len(sponsors)} sponsors")
    # Judges (OpenAlex) are always real RESEARCHED. Reason explains why the web
    # portion (speakers/sponsors) may be empty - always a clean, sanitized string.
    if not (s.gemini_enabled or generate is not None):
        reason = "No GEMINI_API_KEY; speakers/sponsors from estimates."
    elif web_error and not speakers and not sponsors:
        reason = web_error
    else:
        reason = None
    result = {
        "label": Label.RESEARCHED.value,
        "judges": judges, "speakers": speakers, "sponsors": sponsors,
        "fallback_reason": reason,
    }
    try:
        PeopleResearchResult(**result)
    except ValidationError:
        result["fallback_reason"] = "Result validation failed; showing estimates."
    if use_cache and not result.get("fallback_reason"):
        _cache_put(key, result)
    return result
