"""
guardrails.py

Code-enforced guardrails for the research agent (not just prompt text).

These functions are pure and independently testable:
  - check_scope(purpose)               -> only catering/people/sponsors allowed
  - require_source(item, grounding)     -> drop items without a grounded source URL
  - verify_catering(item, osm)          -> VERIFIED (OSM match) | WEB_ONLY; drop > 1.5 km
  - scrub_person(item)                  -> strip emails/phones/addresses, add note
  - validate_tool_call(name, args)      -> allowlist + arg-shape check
  - CallBudget                          -> enforce max tool calls + deadline
"""

from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..privacy.scrubber import scrub

ALLOWED_PURPOSES = frozenset({"catering", "people", "sponsors"})
ALLOWED_TOOLS = frozenset({
    "plan_context", "osm_places_near", "web_search", "openalex_people",
})
NAME_SIM_THRESHOLD = 0.8
MAX_DISTANCE_M = 1500.0
OFFICIAL_CHANNELS_NOTE = "Contact through official channels."

VERIFIED = "VERIFIED"
WEB_ONLY = "WEB_ONLY"
# A hand-picked real vendor shown when live web research is unavailable. Not
# OSM-cross-checked (so not VERIFIED) and not pulled from a live search (so not
# WEB_ONLY); the UI labels it as a curated real option to verify before booking.
CURATED = "CURATED"


class GuardrailError(Exception):
    """Raised for an out-of-scope purpose or a rejected tool call."""


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #
def check_scope(purpose: str) -> str:
    p = (purpose or "").strip().lower()
    if p not in ALLOWED_PURPOSES:
        raise GuardrailError(f"out-of-scope purpose: {purpose!r}")
    return p


# --------------------------------------------------------------------------- #
# Source-required
# --------------------------------------------------------------------------- #
def _item_source_urls(item: dict[str, Any]) -> list[str]:
    srcs = item.get("source_urls") or item.get("sources") or []
    out = []
    for s in srcs:
        if isinstance(s, dict):
            u = s.get("url")
        else:
            u = s
        if u:
            out.append(str(u))
    return out


def _normalize_url(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower()).rstrip("/")


def _host(u: str) -> str:
    return _normalize_url(u).split("/", 1)[0]


def require_source(item: dict[str, Any], grounding_urls: list[str]) -> bool:
    """True if the item cites a URL grounded in the metadata.

    A cited URL counts as grounded when it equals a grounding URL, is a path
    under one (prefix), or shares the same host. This lets an item cite a deeper
    page on a domain that appears in the grounding set, while still dropping
    URLs from domains that never appeared.
    """
    grounded = {_normalize_url(u) for u in grounding_urls}
    grounded_hosts = {_host(u) for u in grounding_urls}
    for u in _item_source_urls(item):
        nu = _normalize_url(u)
        if nu in grounded:
            return True
        if any(nu.startswith(gu) or gu.startswith(nu) for gu in grounded):
            return True
        if _host(u) in grounded_hosts:
            return True
    return False


def drop_unsourced(items: list[dict], grounding_urls: list[str]) -> list[dict]:
    return [it for it in items if require_source(it, grounding_urls)]


# --------------------------------------------------------------------------- #
# Catering verification against OSM
# --------------------------------------------------------------------------- #
def _name_sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def verify_catering(item: dict[str, Any], osm_results: list[dict]) -> dict[str, Any] | None:
    """Label an item VERIFIED (OSM match) or WEB_ONLY; drop if > 1.5 km.

    Returns the item with 'verification' set, or None if it should be dropped.
    """
    dist = item.get("distance_m")
    if isinstance(dist, (int, float)) and dist > MAX_DISTANCE_M:
        return None

    best = 0.0
    best_dist = None
    for o in osm_results or []:
        sim = _name_sim(item.get("name", ""), o.get("name", ""))
        if sim > best:
            best = sim
            best_dist = o.get("distance_m")
    matched = best >= NAME_SIM_THRESHOLD and (
        best_dist is None or best_dist <= MAX_DISTANCE_M
    )
    out = dict(item)
    out["verification"] = VERIFIED if matched else WEB_ONLY
    out["name_match_score"] = round(best, 3)
    if not matched:
        out["verify_note"] = "verify before booking"
    return out


# --------------------------------------------------------------------------- #
# People privacy
# --------------------------------------------------------------------------- #
# A loose US-style street-address pattern (number + street words). The scrubber
# covers emails/phones; this adds addresses, which the scrubber does not catch.
_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.\- ]{2,40}\b"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|"
    r"court|ct|square|sq|place|pl)\b\.?",
    re.IGNORECASE,
)

_SCRUB_FIELDS = ("name", "role", "title", "organization", "relevance", "why_fits")


def _strip_text(value: str) -> str:
    # Emails + phones via the shared scrubber (remove mode), then addresses.
    cleaned = scrub(value, mode="remove").scrubbed
    cleaned = _ADDRESS_RE.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")


def scrub_person(item: dict[str, Any]) -> dict[str, Any]:
    """Strip emails/phones/addresses from a person item; add the channels note."""
    out = dict(item)
    for f in _SCRUB_FIELDS:
        if isinstance(out.get(f), str):
            out[f] = _strip_text(out[f])
    # Profile URL preferred from institutional/organizational domains; drop
    # obvious contact dumps (mailto:, tel:).
    url = str(out.get("profile_url") or out.get("url") or "")
    if url.lower().startswith(("mailto:", "tel:")):
        url = ""
    out["profile_url"] = url
    note = out.get("note") or ""
    if OFFICIAL_CHANNELS_NOTE not in note:
        out["note"] = (note + " " + OFFICIAL_CHANNELS_NOTE).strip()
    return out


# --------------------------------------------------------------------------- #
# Tool-call validation (allowlist + arg shape)
# --------------------------------------------------------------------------- #
_TOOL_REQUIRED_ARGS = {
    "plan_context": {"plan_id"},
    "osm_places_near": {"lat", "lon"},
    "web_search": {"query", "purpose"},
    "openalex_people": {"topics"},
}


def validate_tool_call(name: str, args: dict[str, Any]) -> None:
    """Raise GuardrailError if the tool is not allowlisted or args are invalid."""
    if name not in ALLOWED_TOOLS:
        raise GuardrailError(f"tool not in allowlist: {name!r}")
    required = _TOOL_REQUIRED_ARGS.get(name, set())
    missing = required - set((args or {}).keys())
    if missing:
        raise GuardrailError(f"{name}: missing args {sorted(missing)}")
    if name == "osm_places_near":
        radius = args.get("radius_m", 0)
        if isinstance(radius, (int, float)) and radius > MAX_DISTANCE_M:
            raise GuardrailError("osm_places_near: radius_m exceeds 1500")
    if name == "web_search":
        check_scope(args.get("purpose", ""))


# --------------------------------------------------------------------------- #
# Limits
# --------------------------------------------------------------------------- #
@dataclass
class CallBudget:
    """Bounds the agent: max tool calls + a wall-clock deadline."""

    max_calls: int
    timeout_s: float
    _calls: int = 0
    _start: float = field(default_factory=time.monotonic)
    log: list[str] = field(default_factory=list)

    def charge(self, tool_name: str) -> None:
        if self._calls >= self.max_calls:
            raise GuardrailError(f"tool-call cap reached ({self.max_calls})")
        if (time.monotonic() - self._start) > self.timeout_s:
            raise GuardrailError(f"agent timeout ({self.timeout_s}s)")
        self._calls += 1
        self.log.append(tool_name)

    @property
    def calls(self) -> int:
        return self._calls
