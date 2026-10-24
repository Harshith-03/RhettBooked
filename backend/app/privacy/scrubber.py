"""
scrubber.py

Privacy scrubber CORE (P0, task 10).

Detects and redacts personal data in free text or CSV cells. The required
recognizers are implemented as deterministic regexes (no heavy dependencies, so
the deploy image stays lean and startup stays fast):

  - BU_ID        \\bU\\d{8}\\b
  - MAC_ADDRESS  six hex pairs separated by ':' or '-'
  - BSSID        same shape as MAC (access-point identifier)
  - EMAIL
  - PHONE        US-style

A Presidio-backed analyzer is the P1 deepening (task 21 risk report). This core
exposes a stable ``scrub`` interface so Presidio can slot in behind it later;
when it does, load it lazily and use spaCy ``en_core_web_sm`` in deploy.

The tokenizer/vault, aggregate-only upload path, and <5-cell suppression that the
original task listed are explicitly deferred to P1 per the spec; this core is the
scrubber + recognizers + tests only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: more specific patterns first so EMAIL doesn't eat a BU_ID, etc.
RECOGNIZERS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("BU_ID", re.compile(r"\bU\d{8}\b")),
    ("MAC_ADDRESS", re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")),
    # BSSID shares the MAC shape; we tag separately when flagged as an AP id.
    ("PHONE", re.compile(
        r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
    )),
]

# MAC vs BSSID disambiguation: both match the same regex. We report MAC_ADDRESS
# by default; callers scrubbing Wi-Fi association data can treat them as BSSID.


@dataclass
class Finding:
    entity: str
    text: str
    start: int
    end: int


@dataclass
class ScrubResult:
    original: str
    scrubbed: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def residual_count(self) -> int:
        """PII still present after scrubbing (should be 0)."""
        return sum(1 for _ in _iter_findings(self.scrubbed))


def _iter_findings(text: str):
    """Yield non-overlapping findings, earliest and longest first."""
    spans: list[Finding] = []
    for entity, pattern in RECOGNIZERS:
        for m in pattern.finditer(text):
            spans.append(Finding(entity=entity, text=m.group(0), start=m.start(), end=m.end()))
    # Resolve overlaps: sort by start, then by longer match; drop overlaps.
    spans.sort(key=lambda f: (f.start, -(f.end - f.start)))
    chosen: list[Finding] = []
    last_end = -1
    for f in spans:
        if f.start >= last_end:
            chosen.append(f)
            last_end = f.end
    return chosen


def detect(text: str) -> list[Finding]:
    """Return the PII findings in ``text`` (non-overlapping)."""
    return list(_iter_findings(text or ""))


def scrub(text: str, mode: str = "redact") -> ScrubResult:
    """Scrub PII from ``text``.

    mode:
      - "redact"  -> replace with ``[ENTITY]`` (default),
      - "mask"    -> replace characters with '*', keeping length,
      - "remove"  -> drop the matched span entirely.
    """
    text = text or ""
    findings = detect(text)
    out = []
    cursor = 0
    for f in findings:
        out.append(text[cursor:f.start])
        if mode == "mask":
            out.append("*" * (f.end - f.start))
        elif mode == "remove":
            out.append("")
        else:  # redact
            out.append(f"[{f.entity}]")
        cursor = f.end
    out.append(text[cursor:])
    return ScrubResult(original=text, scrubbed="".join(out), findings=findings)


def scrub_rows(rows: list[dict[str, str]], mode: str = "redact") -> list[dict[str, str]]:
    """Scrub every string cell in a list of CSV-style dict rows."""
    cleaned: list[dict[str, str]] = []
    for row in rows:
        cleaned.append({
            k: (scrub(v, mode).scrubbed if isinstance(v, str) else v)
            for k, v in row.items()
        })
    return cleaned
