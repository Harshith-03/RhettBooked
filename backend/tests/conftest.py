"""Pytest configuration: make the repo root importable so `backend.app...` resolves."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import os

import pytest


@pytest.fixture(autouse=True)
def _force_llm_none(monkeypatch):
    """Pin the LLM env to 'none' for the core suite so tests of the offline
    guarantee don't depend on the developer's .env (which may set gemini).

    Agent tests that need gemini/mocked behaviour override this explicitly.
    """
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    # Settings are lru_cached; refresh so provider()/health read 'none' here.
    from backend.app import config as _config

    _config.get_settings.cache_clear()
    yield
    _config.get_settings.cache_clear()
