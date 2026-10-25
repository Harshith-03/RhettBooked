"""
export_demo.py

Regenerate the frontend demo snapshots from the backend.

For each acceptance brief (A and B) this writes saved JSON responses for:
  - /brief/parse   -> parse.json
  - /plan          -> plan.json
  - /drill/run     -> drill.json
  - /drill/compare -> drill_fixes.json   (before/after a standard fix set)

By default it drives the app in-process via FastAPI's TestClient (no running
server needed). Pass --base-url http://localhost:8000 to hit a live backend.

Output: frontend/src/demo/<briefA|briefB>/<name>.json

Run:
    python -m backend.scripts.export_demo
    python -m backend.scripts.export_demo --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "frontend" / "src" / "demo"

BRIEFS = {
    "briefA": (
        "300-person overnight AI hackathon at BU, Oct 24-25, students, budget "
        "$15k, needs lunch, dinner, midnight snack, breakfast"
    ),
    "briefB": (
        "300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, "
        "budget $15k, needs lunch, dinner, midnight snack, breakfast"
    ),
}

# A standard fix set for the drill/compare snapshot.
STD_FIXES = {"add_room_capacity": 300, "add_power_circuits": 12, "shuttle": True}


class _Caller:
    """Call endpoints either in-process (TestClient) or over HTTP."""

    def __init__(self, base_url: str | None):
        self.base_url = base_url
        if base_url:
            import httpx

            self._client = httpx.Client(base_url=base_url, timeout=30.0)
            self._mode = "http"
        else:
            import sys

            if str(REPO_ROOT) not in sys.path:
                sys.path.insert(0, str(REPO_ROOT))
            from fastapi.testclient import TestClient

            from backend.app.main import app

            self._client = TestClient(app)
            self._mode = "inproc"

    def post(self, path: str, payload: dict) -> dict:
        r = self._client.post(path, json=payload)
        r.raise_for_status()
        return r.json()

    def run_job(self, payload: dict) -> dict:
        """Start a research job and poll until done; return the final job dict."""
        import time as _time

        job_id = self.post("/agent/research", payload)["job_id"]
        for _ in range(100):
            r = self._client.get(f"/agent/jobs/{job_id}")
            r.raise_for_status()
            job = r.json()
            if job["status"] in ("done", "error"):
                return job
            _time.sleep(0.05)
        return job


def export(base_url: str | None = None) -> None:
    caller = _Caller(base_url)
    for key, text in BRIEFS.items():
        out_dir = DEMO_DIR / key
        out_dir.mkdir(parents=True, exist_ok=True)

        parse = caller.post("/brief/parse", {"text": text})
        _write(out_dir / "parse.json", parse)

        plan = caller.post("/plan", {"brief": parse["brief"], "draws": 500})
        _write(out_dir / "plan.json", plan)

        drill = caller.post("/drill/run", {"brief": parse["brief"]})
        _write(out_dir / "drill.json", drill)

        drill_fixes = caller.post(
            "/drill/compare", {"brief": parse["brief"], "applied_fixes": STD_FIXES}
        )
        _write(out_dir / "drill_fixes.json", drill_fixes)

        _write(out_dir / "options.json",
               caller.post("/plan/options", {"brief": parse["brief"], "draws": 500}))
        _write(out_dir / "people.json",
               caller.post("/people", {"brief": parse["brief"]}))
        _write(out_dir / "sponsors.json",
               caller.post("/sponsors", {"brief": parse["brief"], "draws": 500}))
        _write(out_dir / "trust.json",
               caller.post("/trust", {"brief": parse["brief"], "draws": 500}))

        # Research agent results (catering + people). With no GEMINI_API_KEY these
        # are the fallback shapes, which the demo UI renders without a key.
        _write(out_dir / "agent_catering.json",
               caller.run_job({"brief": parse["brief"], "task": "catering"}))
        _write(out_dir / "agent_people.json",
               caller.run_job({"brief": parse["brief"], "task": "people"}))

        print(f"  {key}: parse, plan, drill, drill_fixes, options, people, sponsors, "
              f"trust, agent_catering, agent_people")

    print(f"Demo snapshots written to {DEMO_DIR}")


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate frontend demo snapshots")
    ap.add_argument("--base-url", default=None,
                    help="Live backend URL (default: in-process TestClient)")
    args = ap.parse_args()
    export(args.base_url)


if __name__ == "__main__":
    main()
