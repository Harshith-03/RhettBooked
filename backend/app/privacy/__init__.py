"""Privacy: PII scrubber core + recognizers (P0). Tokenizer/vault/report are P1."""

from .scrubber import Finding, ScrubResult, detect, scrub, scrub_rows

__all__ = ["Finding", "ScrubResult", "detect", "scrub", "scrub_rows"]
