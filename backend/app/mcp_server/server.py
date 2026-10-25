"""
server.py

FastMCP server exposing the read-only research tools over MCP (stdio). The `mcp`
SDK is imported lazily inside ``build_server`` / ``main`` so this module loads
(and the tool impls stay testable) even when the SDK is not installed.

Run as a server:
    python -m backend.app.mcp_server.server
"""

from __future__ import annotations

from .schemas import OpenAlexIn, OsmIn, PlanContextIn, WebSearchIn
from . import tools_impl

# A tiny in-process plan registry so plan_context(plan_id) can resolve a plan the
# agent has staged. The agent sets the current plan before invoking tools.
_PLAN_REGISTRY: dict[str, dict] = {}


def register_plan(plan_id: str, plan: dict) -> None:
    _PLAN_REGISTRY[plan_id] = plan


def build_server():  # pragma: no cover - requires the mcp SDK
    """Construct the FastMCP server with the four read-only tools."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("eventtwin-research")

    @mcp.tool()
    def plan_context(plan_id: str) -> dict:
        """Aggregate plan context (building, dates, headcount, meals, dietary
        aggregates, budget gap). Never returns attendee rows."""
        plan = _PLAN_REGISTRY.get(plan_id, {})
        return tools_impl.plan_context_from_plan(plan, plan_id).model_dump()

    @mcp.tool()
    def osm_places_near(lat: float, lon: float, radius_m: int = 1000,
                        kinds: list[str] | None = None) -> dict:
        """Food places within radius_m (<=1500) of a point, from OpenStreetMap."""
        inp = OsmIn(lat=lat, lon=lon, radius_m=min(radius_m, 1500),
                    kinds=kinds or ["restaurant", "fast_food", "cafe", "caterer"])
        return tools_impl.osm_places_near(inp).model_dump()

    @mcp.tool()
    def web_search(query: str, purpose: str) -> dict:
        """Gemini + Google Search grounding; returns answer items and grounded
        sources. purpose must be catering|people|sponsors."""
        return tools_impl.web_search(WebSearchIn(query=query, purpose=purpose)).model_dump()

    @mcp.tool()
    def openalex_people(topics: list[str], k: int = 8) -> dict:
        """Real OpenAlex researcher ranking for the given topics."""
        return tools_impl.openalex_people(OpenAlexIn(topics=topics, k=k)).model_dump()

    return mcp


def main() -> None:  # pragma: no cover - runs the stdio server
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
