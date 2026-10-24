"""
models.py

The EventBrief pydantic v2 model (Requirement 1.1), its `needs` sub-model, the
event-type enum, and the follow-up Question model.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    hackathon = "hackathon"
    conference = "conference"
    career_fair = "career_fair"
    workshop = "workshop"
    social = "social"
    other = "other"


class Needs(BaseModel):
    """Facility needs implied by the brief."""

    wifi_heavy: bool = False
    av: bool = False
    stage: bool = False
    breakout_rooms: bool = False
    quiet_room: bool = False
    sleeping_rooms: bool = False


class EventBrief(BaseModel):
    """Structured description of an event (Requirement 1.1)."""

    name: str | None = None
    type: EventType | None = None
    description: str = ""
    start: str | None = None          # ISO date "YYYY-MM-DD" when known
    end: str | None = None
    start_time: str | None = None     # "HH:MM" when known
    end_time: str | None = None
    overnight: bool = False
    expected_registrations: int | None = None
    audience: str | None = None
    budget_usd: int | None = None
    meals: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    preferred_area: str | None = None
    topics: list[str] = Field(default_factory=list)
    needs: Needs = Field(default_factory=Needs)

    def food_implied(self) -> bool:
        """True when the brief implies catering (meals requested or food words)."""
        if self.meals:
            return True
        text = self.description.lower()
        return any(w in text for w in ("food", "cater", "meal", "lunch", "dinner",
                                       "breakfast", "snack"))


class Question(BaseModel):
    """A single follow-up question for a missing critical field."""

    field: str
    prompt: str
