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
    from .config import get_settings
    return get_settings().llm_provider.lower()


def gemini_available() -> bool:
    """True when a Gemini key is configured (never logs the key itself)."""
    from .config import get_settings
    return get_settings().gemini_enabled


def _gemini_client():
    """Lazily construct a google-genai client. Raises LLMUnavailable with no key."""
    from .config import get_settings
    s = get_settings()
    if not s.gemini_enabled:
        raise LLMUnavailable("GEMINI_API_KEY not set")
    try:
        from google import genai  # lazy import so the module loads without the SDK
    except Exception as e:  # pragma: no cover - SDK missing
        raise LLMUnavailable(f"google-genai SDK unavailable: {e}")
    return genai.Client(api_key=s.gemini_api_key)


def gemini_generate(
    prompt: str,
    *,
    grounding: bool = False,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Generate text with Gemini, optionally with Google Search grounding.

    Returns {"text": str, "sources": [{"url","title"}]}. Sources come ONLY from
    the response's grounding metadata (never fabricated here). Raises
    LLMUnavailable when no key / SDK. The API key is never included in the
    return value and never logged.
    """
    from .config import get_settings
    s = get_settings()
    client = _gemini_client()
    from google.genai import types  # type: ignore

    config_kwargs: dict[str, Any] = {
        "max_output_tokens": max_tokens or s.agent_max_output_tokens,
    }
    if grounding:
        config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    resp = client.models.generate_content(
        model=s.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return {"text": getattr(resp, "text", "") or "", "sources": _grounding_sources(resp)}


def _grounding_sources(resp: Any) -> list[dict[str, str]]:
    """Extract {url,title} from Gemini grounding metadata, de-duped."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        for cand in getattr(resp, "candidates", []) or []:
            gm = getattr(cand, "grounding_metadata", None)
            for chunk in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(chunk, "web", None)
                url = getattr(web, "uri", None) or getattr(web, "url", None)
                title = getattr(web, "title", None) or ""
                if url and url not in seen:
                    seen.add(url)
                    out.append({"url": url, "title": title})
    except Exception:
        pass
    return out


def parse_json(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse ``prompt`` into JSON constrained to ``schema``.

    Raises ``LLMUnavailable`` when the provider is ``none`` or not yet wired up,
    signalling the caller to use the regex/keyword fallback.
    """
    p = provider()
    if p == "none":
        raise LLMUnavailable("LLM_PROVIDER=none: use the rule-based parser")
    # Gemini/bedrock/anthropic/ollama JSON parsing is not wired for the brief
    # parser (the rule-based path is authoritative); the research agent uses
    # gemini_generate directly.
    raise LLMUnavailable(f"LLM provider {p!r} not configured for parse_json")


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
