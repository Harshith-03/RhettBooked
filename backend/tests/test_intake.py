"""Task 3 tests: EventBrief model + rule-based intake + follow-up questions."""

from __future__ import annotations

import os

from backend.app.brief import EventType, parse
from backend.app.brief.intake import (
    parse_budget,
    parse_dates,
    parse_headcount,
    parse_meals,
)

# The two acceptance briefs (Requirement 14).
BRIEF_A = (
    "300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, "
    "needs lunch, dinner, midnight snack, breakfast"
)
BRIEF_B = (
    "300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, "
    "budget $15k, needs lunch, dinner, midnight snack, breakfast"
)


def test_runs_under_llm_provider_none():
    # The rule-based path is the only one used; confirm the env default.
    assert os.environ.get("LLM_PROVIDER", "none") == "none"


# --------------------------------------------------------------------------- #
# Acceptance brief A
# --------------------------------------------------------------------------- #
def test_brief_a_parses_all_critical_fields():
    brief, questions = parse(BRIEF_A)
    assert brief.type == EventType.hackathon
    assert brief.expected_registrations == 300
    assert brief.budget_usd == 15000
    assert brief.overnight is True
    assert brief.audience == "students"
    assert brief.start == "2026-10-24"
    assert brief.end == "2026-10-25"
    assert brief.meals == ["breakfast", "lunch", "snack", "dinner"]
    assert "ai" in brief.topics
    # Hackathon implies a wifi-heavy, overnight-with-sleeping setup.
    assert brief.needs.wifi_heavy is True
    assert brief.needs.sleeping_rooms is True
    # Every critical field present -> zero follow-up questions.
    assert questions == []


def test_brief_b_parses_cross_month_dates():
    brief, questions = parse(BRIEF_B)
    assert brief.start == "2026-10-31"
    assert brief.end == "2026-11-01"
    assert brief.overnight is True
    assert brief.budget_usd == 15000
    assert questions == []


# --------------------------------------------------------------------------- #
# Follow-up questions (<= 3, only for missing critical fields)
# --------------------------------------------------------------------------- #
def test_missing_critical_fields_produce_questions():
    brief, questions = parse("We want to host a thing sometime soon.")
    fields = {q.field for q in questions}
    # type, dates, headcount, budget are all missing; capped at 3.
    assert len(questions) <= 3
    assert fields.issubset(
        {"type", "start", "expected_registrations", "budget_usd", "meals"}
    )


def test_meals_question_only_when_food_implied():
    # Food implied (catering) but no specific meals named -> meals question appears.
    brief, questions = parse(
        "Conference on May 5 2026 for 120 people, $8k budget, catering needed"
    )
    fields = {q.field for q in questions}
    assert "meals" in fields

    # No food mention -> no meals question even though meals list is empty.
    brief2, questions2 = parse(
        "Conference on May 5 2026 for 120 people, $8k budget"
    )
    fields2 = {q.field for q in questions2}
    assert "meals" not in fields2
    assert questions2 == []


def test_question_cap_is_three():
    _, questions = parse("")
    assert len(questions) <= 3


# --------------------------------------------------------------------------- #
# Unit-level parser helpers
# --------------------------------------------------------------------------- #
def test_parse_headcount_variants():
    assert parse_headcount("300-person event") == 300
    assert parse_headcount("about 150 attendees") == 150
    assert parse_headcount("500 students expected") == 500
    assert parse_headcount("no numbers here") is None


def test_parse_budget_variants():
    assert parse_budget("$15k") == 15000
    assert parse_budget("budget $15,000") == 15000
    assert parse_budget("budget of 20k") == 20000
    assert parse_budget("no money mentioned") is None


def test_parse_budget_ignores_headcount_number():
    # "300-person ... budget $15k" must return 15000, not 300.
    assert parse_budget(BRIEF_A) == 15000


def test_parse_dates_single_and_range_and_cross_month():
    assert parse_dates("Oct 24-25") == ("2026-10-24", "2026-10-25")
    assert parse_dates("Oct 31-Nov 1, 2026") == ("2026-10-31", "2026-11-01")
    assert parse_dates("May 5 2026") == ("2026-05-05", "2026-05-05")
    assert parse_dates("no dates") == (None, None)


def test_parse_meals_order_and_dedup():
    meals = parse_meals("breakfast, lunch, dinner, midnight snack, lunch again")
    assert meals == ["breakfast", "lunch", "snack", "dinner"]
