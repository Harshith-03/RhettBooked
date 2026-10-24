"""
intake.py

Rule-based intake parser (P0). `parse(text)` extracts an EventBrief from free
text using regex/keyword rules and returns it together with the follow-up
questions for any missing critical fields.

The LLM-with-strict-JSON path is deferred to P1 per the spec; under
`LLM_PROVIDER=none` (the P0 default) this rule-based path is the only one used.
If an LLM provider were configured, `parse` would try `llm.parse_json` first and
fall back here on `LLMUnavailable`, but task 3 ships the fallback only.
"""

from __future__ import annotations

import re
from datetime import date

from .models import EventBrief, EventType, Needs, Question
from .questions import missing

# --------------------------------------------------------------------------- #
# Event type keywords
# --------------------------------------------------------------------------- #
_TYPE_KEYWORDS: list[tuple[EventType, tuple[str, ...]]] = [
    (EventType.hackathon, ("hackathon", "hack-a-thon", "hacking")),
    (EventType.career_fair, ("career fair", "job fair", "recruiting fair")),
    (EventType.conference, ("conference", "summit", "symposium")),
    (EventType.workshop, ("workshop", "bootcamp", "training", "tutorial")),
    (EventType.social, ("mixer", "social", "party", "networking night", "gala")),
]

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# "Oct 24-25", "Oct 31-Nov 1 2026", "October 24-25, 2026", "Oct 24"
_DATE_RE = re.compile(
    r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})"
    r"(?:\s*[-\u2013]\s*(?:([A-Za-z]{3,9})\.?\s+)?(\d{1,2}))?"
    r"(?:[,\s]+(\d{4}))?",
    re.IGNORECASE,
)

# "$15k", "$15,000", "15k budget", "budget of $15000"
_BUDGET_RE = re.compile(
    r"\$?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|thousand)?",
    re.IGNORECASE,
)

# "300-person", "300 people", "300 attendees", "300 participants", "300 students"
_HEADCOUNT_RE = re.compile(
    r"\b(\d{2,6})\s*[- ]?\s*(?:person|people|attendee|attendees|participant|"
    r"participants|guest|guests|student|students|registrant|registrants)\b",
    re.IGNORECASE,
)

_MEAL_WORDS = {
    "breakfast": ("breakfast",),
    "lunch": ("lunch",),
    "dinner": ("dinner",),
    "snack": ("snack", "midnight snack", "refreshments"),
}

_DEFAULT_YEAR = 2026  # acceptance briefs are in 2026


def _month(name: str) -> int | None:
    return _MONTHS.get(name.lower()) or _MONTHS.get(name[:3].lower())


def parse_dates(text: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) parsed from the first date expression."""
    m = _DATE_RE.search(text)
    if not m:
        return None, None
    smon_name, sday, emon_name, eday, year = m.groups()
    smon = _month(smon_name)
    if not smon:
        return None, None
    yr = int(year) if year else _DEFAULT_YEAR
    try:
        start = date(yr, smon, int(sday))
    except ValueError:
        return None, None
    end = start
    if eday:
        emon = _month(emon_name) if emon_name else smon
        if emon:
            try:
                end = date(yr, emon, int(eday))
                # Handle a month rollover without an explicit year change.
                if end < start and emon < smon:
                    end = date(yr + 1, emon, int(eday))
            except ValueError:
                end = start
    return start.isoformat(), end.isoformat()


def parse_budget(text: str) -> int | None:
    """Return a budget in whole USD, interpreting a trailing 'k' as thousands."""
    # Prefer a $-prefixed or budget-adjacent number.
    candidates: list[int] = []
    for m in _BUDGET_RE.finditer(text):
        raw, suffix = m.group(1), m.group(2)
        # Skip bare small numbers that are clearly not budgets unless $ or k present.
        has_dollar = text[max(0, m.start() - 1): m.start()] == "$"
        num = float(raw.replace(",", ""))
        if suffix and suffix.lower() in ("k", "thousand"):
            num *= 1000
        elif not has_dollar and num < 1000:
            # e.g. "300" headcount; ignore unless flagged as budget nearby.
            window = text[max(0, m.start() - 12): m.start()].lower()
            if "budget" not in window:
                continue
        candidates.append(int(round(num)))
    if not candidates:
        return None
    # The largest plausible value is usually the budget.
    return max(candidates)


def parse_headcount(text: str) -> int | None:
    m = _HEADCOUNT_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def parse_type(text: str) -> EventType | None:
    low = text.lower()
    for etype, keywords in _TYPE_KEYWORDS:
        if any(k in low for k in keywords):
            return etype
    return None


def parse_meals(text: str) -> list[str]:
    low = text.lower()
    meals: list[str] = []
    for meal, words in _MEAL_WORDS.items():
        if any(w in low for w in words):
            meals.append(meal)
    # Keep a stable chronological order.
    order = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}
    return sorted(set(meals), key=lambda m: order.get(m, 99))


def parse_overnight(text: str, start: str | None, end: str | None) -> bool:
    low = text.lower()
    if any(w in low for w in ("overnight", "all-night", "all night", "24-hour",
                              "24 hour", "sleeping")):
        return True
    # A multi-day span implies overnight.
    if start and end and start != end:
        return True
    return False


def parse_audience(text: str) -> str | None:
    low = text.lower()
    if "student" in low:
        return "students"
    if "faculty" in low:
        return "faculty"
    if "alumni" in low:
        return "alumni"
    if "professional" in low or "industry" in low:
        return "professionals"
    if "public" in low:
        return "public"
    return None


def parse_topics(text: str) -> list[str]:
    low = text.lower()
    topics: list[str] = []
    topic_words = {
        "ai": ["ai ", "artificial intelligence", " a.i."],
        "machine-learning": ["machine learning", " ml ", "deep learning"],
        "data": ["data science", "data engineering", "analytics"],
        "health": ["health", "medical", "biotech"],
        "fintech": ["fintech", "finance"],
        "sustainability": ["sustainability", "climate", "clean energy"],
        "security": ["cybersecurity", "security"],
        "robotics": ["robotics", "robot"],
    }
    padded = f" {low} "
    for topic, needles in topic_words.items():
        if any(n in padded for n in needles):
            topics.append(topic)
    return topics


def parse_needs(text: str, etype: EventType | None, overnight: bool) -> Needs:
    low = text.lower()
    wifi = etype == EventType.hackathon or any(
        w in low for w in ("wifi", "wi-fi", "wifi-heavy", "high bandwidth",
                            "internet", "laptops")
    )
    av = any(w in low for w in ("av", "a/v", "projector", "sound", "mic",
                                "keynote", "presentation", "stage"))
    stage = any(w in low for w in ("stage", "keynote", "ceremony"))
    breakout = any(w in low for w in ("breakout", "break-out", "workshop",
                                      "track", "sessions"))
    quiet = any(w in low for w in ("quiet room", "nursing", "prayer",
                                   "quiet space"))
    sleeping = overnight or any(w in low for w in ("sleeping", "sleep room",
                                                    "nap", "rest area"))
    return Needs(
        wifi_heavy=wifi,
        av=av,
        stage=stage,
        breakout_rooms=breakout,
        quiet_room=quiet,
        sleeping_rooms=sleeping,
    )


def parse(text: str) -> tuple[EventBrief, list[Question]]:
    """Parse free text into an (EventBrief, follow-up questions) pair."""
    text = text or ""
    etype = parse_type(text)
    start, end = parse_dates(text)
    overnight = parse_overnight(text, start, end)
    headcount = parse_headcount(text)
    budget = parse_budget(text)
    meals = parse_meals(text)
    audience = parse_audience(text)
    topics = parse_topics(text)
    needs = parse_needs(text, etype, overnight)

    brief = EventBrief(
        name=None,
        type=etype,
        description=text.strip(),
        start=start,
        end=end,
        overnight=overnight,
        expected_registrations=headcount,
        audience=audience,
        budget_usd=budget,
        meals=meals,
        topics=topics,
        needs=needs,
    )
    return brief, missing(brief)
