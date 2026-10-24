"""
rag.py

Retrieval-augmented explainer (P1, task 22).

Builds a small corpus over committed text sources:
  - docs/METHODS.md
  - docs/ETHICS.md
  - data/placeholder/README.md (dataset caveats)
  - MBTA alert texts (from the committed stops dataset)
Chunks them, retrieves the most relevant chunks for a question using **TF-IDF
similarity** (scikit-learn, same embed() seam as people/sponsors; MiniLM is the
documented swap-in), and composes an answer that CITES source ids.

Grounding: any numbers in the answer come only from the optional ``plan`` tool
output (reusing the template explainer), never from the retrieved prose. The
retrieved chunks provide explanation/citation, not figures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..data import loaders
from ..provenance import Label, ProvenanceRow
from .explainer import explain as template_explain

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = REPO_ROOT / "docs"
SOURCES = {
    "METHODS.md": DOCS / "METHODS.md",
    "ETHICS.md": DOCS / "ETHICS.md",
    "placeholder/README.md": REPO_ROOT / "data" / "placeholder" / "README.md",
}
SIMILARITY_NAME = "TF-IDF similarity"


@dataclass
class Chunk:
    source_id: str
    text: str


@dataclass
class RagAnswer:
    answer: str
    citations: list[str]
    retrieved: list[dict]
    similarity_method: str
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "retrieved": self.retrieved,
            "similarity_method": self.similarity_method,
        }


def _chunk_text(text: str, source_id: str, size: int = 400) -> list[Chunk]:
    chunks: list[Chunk] = []
    para = [p.strip() for p in text.split("\n\n") if p.strip()]
    buf = ""
    for p in para:
        if len(buf) + len(p) > size and buf:
            chunks.append(Chunk(source_id=source_id, text=buf.strip()))
            buf = ""
        buf += " " + p
    if buf.strip():
        chunks.append(Chunk(source_id=source_id, text=buf.strip()))
    return chunks


@lru_cache(maxsize=1)
def build_corpus() -> tuple[Chunk, ...]:
    chunks: list[Chunk] = []
    for sid, path in SOURCES.items():
        if path.exists():
            chunks.extend(_chunk_text(path.read_text(encoding="utf-8"), sid))
    # MBTA alert texts from the committed stops dataset.
    try:
        stops, _ = loaders.load_mbta_stops()
        seen = set()
        for s in stops:
            if s.disruption and s.disruption.raw and s.disruption.raw not in seen:
                seen.add(s.disruption.raw)
                chunks.append(Chunk(source_id="mbta_alerts", text=s.disruption.raw))
    except Exception:
        pass
    return tuple(chunks)


def retrieve(question: str, k: int = 3) -> list[tuple[Chunk, float]]:
    corpus = build_corpus()
    if not corpus or not question.strip():
        return []
    from ..plan.people import embed  # shared TF-IDF embed seam

    texts = [question] + [c.text for c in corpus]
    vec, matrix = embed(texts)
    q = matrix[0]
    docs = matrix[1:]
    sims = (docs @ q.T).toarray().ravel()
    ranked = sorted(zip(corpus, sims), key=lambda cs: -cs[1])
    return [(c, float(s)) for c, s in ranked[:k] if s > 0]


def answer(question: str, plan: dict | None = None, k: int = 3) -> RagAnswer:
    hits = retrieve(question, k=k)
    citations = []
    retrieved = []
    seen_src = set()
    for chunk, score in hits:
        retrieved.append({"source_id": chunk.source_id,
                          "score": round(score, 4),
                          "excerpt": chunk.text[:200]})
        if chunk.source_id not in seen_src:
            seen_src.add(chunk.source_id)
            citations.append(chunk.source_id)

    parts: list[str] = []
    # Numbers (if any) come only from the plan tool output, never the prose.
    if plan:
        parts.append(template_explain(plan))
    if hits:
        parts.append("Relevant context: " + " ".join(
            f"{c.text[:160]} [source: {c.source_id}]" for c, _ in hits[:2]
        ))
    else:
        parts.append("No relevant documentation found for that question.")

    prov = [ProvenanceRow(
        output_key="rag.answer", label=Label.MEASURED,
        source=f"{SIMILARITY_NAME} retrieval over committed docs + MBTA alerts",
        value_summary=f"cited {', '.join(citations) or 'none'}",
    )]
    return RagAnswer(
        answer=" ".join(parts).strip(),
        citations=citations,
        retrieved=retrieved,
        similarity_method=SIMILARITY_NAME,
        provenance=prov,
    )
