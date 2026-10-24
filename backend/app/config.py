"""
config.py

Central configuration and path resolution for the EventTwin backend.

Reads environment variables (optionally from a project-root .env) and exposes a
single ``settings`` object plus canonical filesystem paths. No secrets are
printed or logged; only key *names* are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Repo root is three levels up from this file: backend/app/config.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical data locations (see .kiro/specs/eventtwin-core).
DATA_DIR = REPO_ROOT / "data"
RAW_BU_DIR = DATA_DIR / "raw" / "bu"            # real MEASURED datasets
RAW_LIVE_DIR = DATA_DIR / "raw" / "live"        # cached external API responses
PLACEHOLDER_DIR = DATA_DIR / "placeholder"      # PLACEHOLDER datasets
REFERENCE_DIR = DATA_DIR / "reference"          # bu_buildings_ref.csv etc.
PROCESSED_DIR = DATA_DIR / "processed"          # DuckDB lives here
CONFIG_DIR = REPO_ROOT / "config"               # assumptions.yaml, rate cards

DUCKDB_PATH = PROCESSED_DIR / "eventtwin.duckdb"
ASSUMPTIONS_PATH = CONFIG_DIR / "assumptions.yaml"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments, no overrides of real env."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip inline comments and surrounding whitespace/quotes from the value.
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings sourced from the environment."""

    llm_provider: str = "none"          # bedrock | anthropic | ollama | none
    llm_api_key: str = ""
    mbta_api_key: str = ""
    token_key: str = ""
    vault_path: str = "secrets/vault.sqlite"
    cors_origin: str = "http://localhost:5173"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider.lower() != "none"


@lru_cache(maxsize=1)
def load_assumptions() -> dict:
    """Load and cache the ASSUMED parameter table from config/assumptions.yaml."""
    if not ASSUMPTIONS_PATH.exists():
        return {}
    import yaml

    return yaml.safe_load(ASSUMPTIONS_PATH.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        llm_provider=os.environ.get("LLM_PROVIDER", "none").strip() or "none",
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        mbta_api_key=os.environ.get("MBTA_API_KEY", "").strip(),
        token_key=os.environ.get("TOKEN_KEY", "").strip(),
        vault_path=os.environ.get("VAULT_PATH", "secrets/vault.sqlite").strip(),
        cors_origin=os.environ.get("CORS_ORIGIN", "http://localhost:5173").strip(),
    )


settings = get_settings()
