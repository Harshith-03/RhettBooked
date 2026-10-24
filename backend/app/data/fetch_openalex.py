"""
fetch_openalex.py

ONE-TIME fetch of public OpenAlex works for BU (and optionally the other
Hackachusetts campuses), used by the people/judges recommender (task 18).

Constraints (privacy + politeness):
  - Filter to the institution(s) and works from 2022 onward.
  - Add mailto= for the OpenAlex polite pool (OPENALEX_MAILTO env, else a default).
  - Cap at ~2000 works.
  - Store ONLY public scholarly fields: author display name, institution, work
    title, year, citation count, concepts/topics, and OpenAlex IDs/URLs.
    NO emails, NO contact data, NO gender/demographic inference.

Outputs:
  - Raw cache (JSON pages) -> data/raw/live/openalex/  (gitignored)
  - Committed compact table -> data/raw/v3/openalex/authors_topics.csv
      columns: author_name, author_id, institution, works, citations, topics
      (topics = pipe-joined concept display names across the author's works)

Run:
    python -m backend.app.data.fetch_openalex
    python -m backend.app.data.fetch_openalex --campuses   # BU + other campuses
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw" / "live" / "openalex"
OUT_DIR = REPO_ROOT / "data" / "raw" / "v3" / "openalex"
OUT_CSV = OUT_DIR / "authors_topics.csv"

# OpenAlex institution IDs (ROR-backed). BU is the primary; the others are the
# Hackachusetts campuses (optional via --campuses).
BU_INSTITUTION = "I111236770"           # Boston University
OTHER_CAMPUSES = [
    "I121332785",  # Northeastern
    "I75001271",   # MIT
    "I136199984",  # Harvard
    "I84218800",   # Tufts
]
FROM_YEAR = 2022
MAX_WORKS = 2000
PER_PAGE = 200


def _mailto() -> str:
    return os.environ.get("OPENALEX_MAILTO", "").strip() or "eventtwin@example.edu"


def _fetch_page(institution_ids: list[str], page: int) -> dict:
    # Use classic offset (page=) pagination: keyless and within the 10k cap.
    # (cursor= paging now requires a free OpenAlex API key; page= does not.)
    # OpenAlex rejects percent-encoded ':' '|' ',' in the filter value, so the
    # filter/select are built raw and only the mailto is lightly encoded.
    filt = (
        f"institutions.id:{'|'.join(institution_ids)},"
        f"from_publication_date:{FROM_YEAR}-01-01"
    )
    select = "id,display_name,publication_year,cited_by_count,authorships,concepts"
    mailto_q = urllib.parse.quote(_mailto(), safe="@.")
    url = (
        "https://api.openalex.org/works"
        f"?filter={filt}&select={select}&per-page={PER_PAGE}"
        f"&page={page}&mailto={mailto_q}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": f"eventtwin ({_mailto()})"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(use_campuses: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    institution_ids = [BU_INSTITUTION] + (OTHER_CAMPUSES if use_campuses else [])

    # author_id -> aggregate of PUBLIC fields only.
    authors: dict[str, dict] = {}
    fetched = 0
    page = 1

    while fetched < MAX_WORKS:
        data = _fetch_page(institution_ids, page)
        results = data.get("results", [])
        if not results:
            break
        # Cache the raw page.
        (RAW_DIR / f"works_p{page:03d}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        for work in results:
            fetched += 1
            title = work.get("display_name") or ""
            year = work.get("publication_year")
            cites = int(work.get("cited_by_count") or 0)
            concepts = [
                c.get("display_name") for c in (work.get("concepts") or [])
                if c.get("level", 0) <= 2 and c.get("display_name")
            ][:5]
            for a in (work.get("authorships") or []):
                author = a.get("author") or {}
                aid = author.get("id")
                name = author.get("display_name")
                if not aid or not name:
                    continue
                insts = a.get("institutions") or []
                inst_name = insts[0].get("display_name") if insts else ""
                rec = authors.setdefault(aid, {
                    "author_name": name,
                    "author_id": aid,
                    "institution": inst_name,
                    "works": 0,
                    "citations": 0,
                    "topics": defaultdict(int),
                    "latest_year": 0,
                })
                rec["works"] += 1
                rec["citations"] += cites
                rec["latest_year"] = max(rec["latest_year"], year or 0)
                for c in concepts:
                    rec["topics"][c] += 1
            if fetched >= MAX_WORKS:
                break
        page += 1
        time.sleep(0.2)  # be polite

    if not authors:
        print("ERROR: no works returned from OpenAlex.", file=sys.stderr)
        raise SystemExit(1)

    # Write the compact committed table (public fields only).
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# OpenAlex public scholarly fields only; no contact/demographic data"])
        w.writerow(["author_name", "author_id", "institution", "works",
                    "citations", "latest_year", "topics"])
        for rec in authors.values():
            topics = "|".join(
                t for t, _ in sorted(rec["topics"].items(), key=lambda kv: -kv[1])[:8]
            )
            w.writerow([rec["author_name"], rec["author_id"], rec["institution"],
                        rec["works"], rec["citations"], rec["latest_year"], topics])

    print(f"Fetched {fetched} works -> {len(authors)} authors")
    print(f"Wrote {OUT_CSV}")
    return OUT_CSV


def main() -> None:
    ap = argparse.ArgumentParser(description="One-time OpenAlex fetch for BU works")
    ap.add_argument("--campuses", action="store_true",
                    help="Include the other Hackachusetts campuses")
    args = ap.parse_args()
    fetch(use_campuses=args.campuses)


if __name__ == "__main__":
    main()
