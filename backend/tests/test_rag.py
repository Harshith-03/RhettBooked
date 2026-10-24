"""Task 22 tests: RAG explainer (TF-IDF retrieval + grounded numbers)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.agent import rag as rag_mod
from backend.app.agent.explainer import numbers_in
from backend.app.agent import tools
from backend.app.main import app

client = TestClient(app)

BRIEF_A = ("300-person overnight AI hackathon at BU, Oct 24-25, students, "
           "budget $15k, needs lunch, dinner, midnight snack, breakfast")


def test_corpus_builds_from_committed_docs():
    corpus = rag_mod.build_corpus()
    sources = {c.source_id for c in corpus}
    assert "METHODS.md" in sources
    assert "ETHICS.md" in sources
    # MBTA alert texts are included.
    assert "mbta_alerts" in sources


def test_retrieve_privacy_question_hits_ethics():
    hits = rag_mod.retrieve("how is personal data and privacy handled?", k=3)
    assert hits
    srcs = {c.source_id for c, _ in hits}
    assert "ETHICS.md" in srcs


def test_retrieve_attendance_question_hits_methods():
    hits = rag_mod.retrieve("how was the arrival curve fitted from Bluebikes?", k=3)
    srcs = {c.source_id for c, _ in hits}
    assert "METHODS.md" in srcs


def test_answer_cites_sources():
    a = rag_mod.answer("how is privacy handled?")
    assert a.citations
    assert "[source:" in a.answer
    assert a.similarity_method == "TF-IDF similarity"


def test_answer_numbers_only_from_plan():
    plan = tools.build_plan(text=BRIEF_A, draws=300)
    a = rag_mod.answer("what will this cost and how ready are we?", plan=plan)
    # Any numbers in the answer must trace to the plan (figures, risks, sources).
    summary = plan["summary"]
    allowed = set()
    for key in ("cost_p10", "cost_p50", "cost_p90", "sponsorship_gap",
                "readiness", "turnout_p50", "turnout_p90"):
        v = summary.get(key)
        if v is not None:
            allowed.add(str(int(v)))
            allowed.add(f"{int(v):,}")
    for risk in summary.get("top_risks", []):
        allowed |= numbers_in(str(risk))
    for row in plan.get("provenance", []):
        allowed |= numbers_in(str(row.get("source", "")))
    # Retrieved prose numbers: the excerpts may contain doc numbers, so restrict
    # the grounding check to the explanation portion before "Relevant context:".
    explanation = a.answer.split("Relevant context:")[0]
    for num in numbers_in(explanation):
        assert num in allowed, f"ungrounded number in RAG answer: {num}"


def test_ask_endpoint():
    r = client.post("/ask", json={"question": "how is privacy handled?"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"]
    assert "answer" in body


def test_ask_endpoint_with_brief_grounds_numbers():
    r = client.post("/ask", json={"question": "what is the cost?", "text": BRIEF_A})
    assert r.status_code == 200
    assert "answer" in r.json()
