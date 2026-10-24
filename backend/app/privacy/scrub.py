"""
scrub.py

CLI: scrub PII from a CSV and write a cleaned copy.

Usage:
    python -m backend.app.privacy.scrub <input.csv> [--out cleaned.csv] [--mode redact|mask|remove]

Prints a per-entity finding count summary. If --out is omitted, writes
``<input>.scrubbed.csv`` next to the input.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from .scrubber import detect, scrub


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrub PII from a CSV")
    ap.add_argument("input", help="Path to the input CSV")
    ap.add_argument("--out", default=None, help="Output path (default: <input>.scrubbed.csv)")
    ap.add_argument("--mode", default="redact", choices=["redact", "mask", "remove"])
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.out) if args.out else in_path.with_suffix(".scrubbed.csv")

    counts: Counter[str] = Counter()
    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    cleaned = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                for finding in detect(v):
                    counts[finding.entity] += 1
                new_row[k] = scrub(v, args.mode).scrubbed
            else:
                new_row[k] = v
        cleaned.append(new_row)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned)

    print(f"Scrubbed {len(rows)} rows -> {out_path}")
    if counts:
        for entity, n in sorted(counts.items()):
            print(f"  {entity}: {n}")
    else:
        print("  no PII detected")


if __name__ == "__main__":
    main()
