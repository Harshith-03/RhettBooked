"""
llm.py

The single LLM adapter for EventTwin. The LLM has exactly two jobs:
  1. parse a free-text brief into strict JSON (``parse_json``), and
  2. explain already-computed results in words (``explain``).

Every number is produced by a model elsewhere; the LLM never invents figures.

Providers: bedrock | anthropic | ollama | none (selected by ``LLM_PROVIDER``).
With ``none``:
  - ``parse_json`` raises ``LLMUnavailable`` so callers use the rule-based path, and
  - ``explain`` returns deterministic template text built only from the context
    passed in (no external call).

The real provider calls (bedrock/anthropic/ollama) are intentionally thin stubs
here in task 1; they raise ``LLMUnavailable`` until wired up, so the whole system
keeps working under ``LLM_PROVIDER=none``.
"""

from __future__ import annotations

from typing import Any

from .config import settings


class LLMUnavailable(RuntimeError):
    """Raised when no LLM can satisfy a request (provider ``none`` or a failure).

    Callers MUST catch this and fall back to the rule-based path.
    """


def provider() -> str:
    return settings.llm_provider.lower()


def parse_json(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse ``prompt`` into JSON constrained to ``schema``.

    Raises ``LLMUnavailable`` when the provider is ``none`` or not yet wired up,
    signalling the caller to use the regex/keyword fallback.
    """
    p = provider()
    if p == "none":
        raise LLMUnavailable("LLM_PROVIDER=none: use the rule-based parser")
    # bedrock | anthropic | ollama are not wired up in task 1.
    raise LLMUnavailable(f"LLM provider {p!r} not configured yet")


def explain(context: dict[str, Any]) -> str:
    """Produce a human explanation of results.

    Under ``LLM_PROVIDER=none`` (or any unconfigured provider) this returns the
    deterministic template explainer, which uses only values from ``context``.
    """
    p = provider()
    if p == "none":
        return template_explain(context)
    # Real providers are not wired up yet; fall back to the template so callers
    # never fail. (A stricter mode can raise LLMUnavailable instead.)
    return template_explain(context)


def template_explain(context: dict[str, Any]) -> str:
    """Deterministic, grounded explanation built only from ``context`` values.

    The template emits only numbers present in ``context`` and never introduces
    new figures, satisfying the "explainer grounding" correctness property.
    """
    lines: list[str] = []
    summary = context.get("summary") if isinstance(context, dict) else None
    if isinstance(summary, dict):
        building = summary.get("recommended_building")
        if building:
            lines.append(f"Recommended venue: {building}.")
        cost_p10 = summary.get("cost_p10")
        cost_p90 = summary.get("cost_p90")
        if cost_p10 is not None and cost_p90 is not None:
            lines.append(f"Estimated cost ranges from {cost_p10} to {cost_p90} (p10-p90).")
        readiness = summary.get("readiness")
        if readiness is not None:
            lines.append(f"Drill readiness score: {readiness}/100.")
        risks = summary.get("top_risks")
        if isinstance(risks, (list, tuple)) and risks:
            joined = "; ".join(str(r) for r in risks)
            lines.append(f"Top risks: {joined}.")
    if not lines:
        lines.append("No results available to explain yet.")
    return " ".join(lines)
