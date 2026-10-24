"""
questions.py

`missing(brief)` returns at most 3 follow-up questions covering ONLY the missing
critical fields (Requirement 1.5-1.6). Critical fields:

  - type
  - dates (start)
  - expected_registrations
  - budget_usd
  - meals (ONLY when the brief implies food but no meals were extracted)

When every critical field is present, returns an empty list.
"""

from __future__ import annotations

from .models import EventBrief, Question

MAX_QUESTIONS = 3

_PROMPTS = {
    "type": "What kind of event is this (hackathon, conference, career fair, workshop, or social)?",
    "start": "What date (or dates) will the event run?",
    "expected_registrations": "Roughly how many people do you expect?",
    "budget_usd": "What is your approximate budget in USD?",
    "meals": "Which meals do you need catered (breakfast, lunch, dinner, snacks)?",
}


def missing(brief: EventBrief) -> list[Question]:
    questions: list[Question] = []

    if brief.type is None:
        questions.append(Question(field="type", prompt=_PROMPTS["type"]))
    if not brief.start:
        questions.append(Question(field="start", prompt=_PROMPTS["start"]))
    if brief.expected_registrations is None:
        questions.append(
            Question(field="expected_registrations",
                     prompt=_PROMPTS["expected_registrations"])
        )
    if brief.budget_usd is None:
        questions.append(Question(field="budget_usd", prompt=_PROMPTS["budget_usd"]))
    # meals is critical only when food is implied but none were captured.
    if brief.food_implied() and not brief.meals:
        questions.append(Question(field="meals", prompt=_PROMPTS["meals"]))

    return questions[:MAX_QUESTIONS]
