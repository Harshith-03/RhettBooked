"""Task 11 tests: agent tools + grounded template explainer."""

from __future__ import annotations

from backend.app.agent import explainer as explainer_mod
from backend.app.agent import tools
from backend.app.agent.explainer import numbers_in

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")
BRIEF_B = ("300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def test_tool_registry_has_all_six():
    assert set(tools.TOOLS) == {
        "parse_brief", "build_plan", "run_drill", "compare_options",
        "get_live_alerts", "get_provenance",
    }


def test_parse_brief_tool():
    out = tools.parse_brief(BRIEF_A)
    assert out["brief"]["type"] == "hackathon"
    assert out["brief"]["budget_usd"] == 15000


def test_build_plan_tool_returns_full_plan():
    out = tools.build_plan(text=BRIEF_A, draws=200)
    assert out["summary"]["recommended_building"]
    assert out["budget"]["line_items"]


def test_run_drill_tool_brief_b_has_green_line():
    out = tools.run_drill(text=BRIEF_B)
    assert any("Green Line" in r for r in out["top_risks"])
    assert out["planned_disruptions"]


def test_compare_options_tool_before_after():
    out = tools.compare_options(text=BRIEF_A, applied_fixes={"add_room_capacity": 200})
    assert "before" in out and "after" in out


def test_get_live_alerts_tool():
    out = tools.get_live_alerts()
    assert any("Green Line" in " ".join(a["lines"]) for a in out["alerts"])


# --------------------------------------------------------------------------- #
# Explainer grounding: only numbers present in the plan, with source citations
# --------------------------------------------------------------------------- #
def test_explainer_uses_only_plan_numbers():
    plan = tools.build_plan(text=BRIEF_A, draws=300)
    text = explainer_mod.explain(plan)

    # Every number in the explanation must appear in the plan's figures.
    summary = plan["summary"]
    allowed = set()
    for key in ("cost_p10", "cost_p50", "cost_p90", "sponsorship_gap",
                "readiness", "turnout_p50", "turnout_p90"):
        v = summary.get(key)
        if v is not None:
            allowed.add(str(int(v)))
            allowed.add(f"{int(v):,}")
    # Risk strings and source citations are verbatim tool/plan content
    # (e.g. "Power failing from 10:15", "Monte Carlo 300 draws", "P0 systems"),
    # so any digits inside them trace to the plan and are grounded too.
    for risk in summary.get("top_risks", []):
        allowed |= numbers_in(str(risk))
    for row in plan.get("provenance", []):
        allowed |= numbers_in(str(row.get("source", "")))

    for num in numbers_in(text):
        assert num in allowed, f"ungrounded number in explanation: {num}"


def test_explainer_cites_sources():
    plan = tools.build_plan(text=BRIEF_A, draws=300)
    text = explainer_mod.explain(plan)
    assert "[source:" in text
    # The recommended building is named.
    assert plan["summary"]["recommended_building"] in text


def test_explainer_brief_b_mentions_green_line():
    plan = tools.build_plan(text=BRIEF_B, draws=300)
    text = explainer_mod.explain(plan)
    assert "Green Line" in text


def test_explainer_empty_plan():
    assert explainer_mod.explain({}) == "No results available to explain yet."
