"""Pydantic input/output schemas for the MCP research tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- plan_context ---
class PlanContextIn(BaseModel):
    plan_id: str


class PlanContext(BaseModel):
    plan_id: str
    building: str | None = None
    lat: float | None = None
    lon: float | None = None
    start: str | None = None
    end: str | None = None
    headcount_p50: int = 0
    headcount_p90: int = 0
    meals: list[str] = Field(default_factory=list)
    dietary_counts: dict[str, int] = Field(default_factory=dict)  # aggregates only
    budget_gap: int = 0


# --- osm_places_near ---
class OsmIn(BaseModel):
    lat: float
    lon: float
    radius_m: int = 1000
    kinds: list[str] = Field(default_factory=lambda: ["restaurant", "fast_food", "cafe", "caterer"])


class OsmPlace(BaseModel):
    name: str
    cuisine: str = ""
    distance_m: int = 0
    website: str = ""
    osm_id: str = ""
    lat: float | None = None
    lon: float | None = None


class OsmResult(BaseModel):
    places: list[OsmPlace] = Field(default_factory=list)
    cached: bool = False


# --- web_search ---
class WebSearchIn(BaseModel):
    query: str
    purpose: str  # catering | people | sponsors


class WebSource(BaseModel):
    url: str
    title: str = ""


class WebSearchResult(BaseModel):
    answer_items: list[str] = Field(default_factory=list)
    sources: list[WebSource] = Field(default_factory=list)


# --- openalex_people ---
class OpenAlexIn(BaseModel):
    topics: list[str]
    k: int = 8


class OpenAlexPerson(BaseModel):
    name: str
    institution: str = ""
    topics: list[str] = Field(default_factory=list)
    citations: int = 0
    openalex_url: str = ""


class OpenAlexResult(BaseModel):
    people: list[OpenAlexPerson] = Field(default_factory=list)
