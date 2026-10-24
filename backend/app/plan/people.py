"""
people.py

People / judge / speaker recommender (P1, task 18).

Ranks authors from the committed OpenAlex table
(`data/raw/v3/openalex/authors_topics.csv`) against the brief's topics by
    score = topic_similarity * log1p(citations) * recency
using **TF-IDF similarity** (scikit-learn TfidfVectorizer) behind an ``embed()``
seam. MiniLM sentence embeddings are a documented future swap-in.

Returns PUBLIC fields only (name, institution, matching topics, OpenAlex URL) and
NEVER contact data or inferred demographics. Includes an institution-diversity
check so the list is not dominated by one institution.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..provenance import Label, ProvenanceRow

OPENALEX_CSV = (
    Path(__file__).resolve().parents[3]
    / "data" / "raw" / "v3" / "openalex" / "authors_topics.csv"
)
SIMILARITY_NAME = "TF-IDF similarity"   # shown in docs/UI; MiniLM is a swap-in
MAX_PER_INSTITUTION = 3                 # institution-diversity cap in the top list


@dataclass
class Person:
    name: str
    institution: str
    matching_topics: list[str]
    citations: int
    latest_year: int
    openalex_url: str
    score: float


@dataclass
class PeopleResult:
    people: list[Person]
    similarity_method: str
    institution_diversity: dict[str, int]
    provenance: list[ProvenanceRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "similarity_method": self.similarity_method,
            "institution_diversity": self.institution_diversity,
            "people": [
                {
                    "name": p.name, "institution": p.institution,
                    "matching_topics": p.matching_topics, "citations": p.citations,
                    "latest_year": p.latest_year, "openalex_url": p.openalex_url,
                    "score": round(p.score, 4),
                }
                for p in self.people
            ],
        }


def _load_authors() -> list[dict]:
    if not OPENALEX_CSV.exists():
        return []
    with OPENALEX_CSV.open(encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    if not rows:
        return []
    header = rows[0]
    idx = {name: header.index(name) for name in header}
    out = []
    for r in rows[1:]:
        out.append({
            "author_name": r[idx["author_name"]],
            "author_id": r[idx["author_id"]],
            "institution": r[idx["institution"]],
            "citations": int(r[idx["citations"]] or 0),
            "latest_year": int(r[idx["latest_year"]] or 0),
            "topics": r[idx["topics"]],
        })
    return out


def embed(corpus: list[str]):
    """Vectorize a text corpus. TF-IDF today; MiniLM is a documented swap-in."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(lowercase=True, token_pattern=r"[A-Za-z][A-Za-z\-]+")
    matrix = vec.fit_transform(corpus)
    return vec, matrix


def recommend(brief, top_n: int = 8) -> PeopleResult:
    authors = _load_authors()
    topics = list(getattr(brief, "topics", []) or [])
    query = " ".join(topics) or (getattr(brief, "description", "") or "")

    prov: list[ProvenanceRow] = []
    if not authors or not query.strip():
        return PeopleResult(
            people=[], similarity_method=SIMILARITY_NAME,
            institution_diversity={},
            provenance=[ProvenanceRow(
                output_key="people.recommend", label=Label.MEASURED,
                source="OpenAlex authors_topics.csv",
                value_summary="no authors or no query topics")],
        )

    # Corpus: the query first, then each author's topic string.
    corpus = [query] + [a["topics"].replace("|", " ") for a in authors]
    vec, matrix = embed(corpus)
    import numpy as np

    q = matrix[0]
    docs = matrix[1:]
    # Cosine similarity (TF-IDF rows are L2-normalized by default).
    sims = (docs @ q.T).toarray().ravel()

    this_year = date.today().year
    scored: list[Person] = []
    for a, sim in zip(authors, sims):
        if sim <= 0:
            continue
        recency = 1.0 / (1 + max(0, this_year - a["latest_year"]))
        score = float(sim) * math.log1p(a["citations"]) * recency
        matching = [t for t in a["topics"].split("|")
                    if any(tok.lower() in t.lower() for tok in query.split())][:4]
        scored.append(Person(
            name=a["author_name"], institution=a["institution"],
            matching_topics=matching or a["topics"].split("|")[:3],
            citations=a["citations"], latest_year=a["latest_year"],
            openalex_url=a["author_id"], score=score,
        ))

    scored.sort(key=lambda p: -p.score)

    # Institution-diversity: cap how many from any one institution make the list.
    diverse: list[Person] = []
    per_inst: dict[str, int] = {}
    for p in scored:
        inst = p.institution or "Unknown"
        if per_inst.get(inst, 0) >= MAX_PER_INSTITUTION:
            continue
        per_inst[inst] = per_inst.get(inst, 0) + 1
        diverse.append(p)
        if len(diverse) >= top_n:
            break

    diversity = {}
    for p in diverse:
        diversity[p.institution or "Unknown"] = diversity.get(p.institution or "Unknown", 0) + 1

    prov.append(ProvenanceRow(
        output_key="people.recommend", label=Label.MEASURED,
        source=f"OpenAlex authors_topics.csv ranked by {SIMILARITY_NAME} x log(citations) x recency",
        value_summary=f"{len(diverse)} people across {len(diversity)} institutions",
    ))
    return PeopleResult(
        people=diverse, similarity_method=SIMILARITY_NAME,
        institution_diversity=diversity, provenance=prov,
    )
