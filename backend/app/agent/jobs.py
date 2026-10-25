"""
jobs.py

A minimal in-process async job store for the research agent. Each job runs the
agent in a background thread and records human-readable progress steps that the
GET /agent/jobs/{id} endpoint streams back.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import research as research_mod


@dataclass
class Job:
    job_id: str
    task: str                       # catering | people
    status: str = "running"         # running | done | error
    steps: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_step(self, s: str) -> None:
        with self._lock:
            self.steps.append(s)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.job_id,
                "task": self.task,
                "status": self.status,
                "steps": list(self.steps),
                "result": self.result,
                "error": self.error,
            }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, task: str) -> Job:
        job = Job(job_id=uuid.uuid4().hex[:12], task=task)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self, job: Job, plan: dict) -> None:
        t = threading.Thread(target=self._run, args=(job, plan), daemon=True)
        t.start()

    def _run(self, job: Job, plan: dict) -> None:
        try:
            fn = (research_mod.research_catering if job.task == "catering"
                  else research_mod.research_people)
            result = fn(plan, steps=job.add_step)
            with job._lock:
                job.result = result
                job.status = "done"
        except Exception as e:  # pragma: no cover - defensive
            with job._lock:
                job.error = str(e)
                job.status = "error"
            job.add_step(f"Error: {e}")


STORE = JobStore()
