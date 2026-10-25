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
    allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    eventtwin_db: str = ""              # EVENTTWIN_DB override (e.g. deploy/eventtwin_demo.duckdb)
    cache_dir: str = ""                # EVENTTWIN_CACHE override for cached API responses
    # Gemini + research agent (backend-only; keys never sent to the frontend/logs).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    agent_max_tool_calls: int = 12
    agent_timeout_s: int = 60
    agent_max_output_tokens: int = 2048

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider.lower() != "none"

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) and not self.gemini_api_key.startswith("<")

    @property
    def cors_origin(self) -> str:
        """Back-compat single-origin accessor (first allowed origin)."""
        return self.allowed_origins[0] if self.allowed_origins else "http://localhost:5173"


def active_db_path() -> Path:
    """DuckDB path the app should read: the EVENTTWIN_DB override, else the default.

    The deploy image sets EVENTTWIN_DB=deploy/eventtwin_demo.duckdb (committed,
    personal-data-free) so no build step is needed at container startup.
    """
    override = os.environ.get("EVENTTWIN_DB", "").strip()
    if override:
        p = Path(override)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return DUCKDB_PATH


def active_cache_dir() -> Path:
    """Cached external-API response directory: EVENTTWIN_CACHE override, else default."""
    override = os.environ.get("EVENTTWIN_CACHE", "").strip()
    if override:
        p = Path(override)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return RAW_LIVE_DIR


def _parse_origins(raw: str) -> tuple[str, ...]:
    """Parse ALLOWED_ORIGINS (comma-separated); always include localhost:5173."""
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "http://localhost:5173" not in origins:
        origins.append("http://localhost:5173")
    # De-dup, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return tuple(out)


@lru_cache(maxsize=1)
def load_assumptions() -> dict:
    """Load and cache the ASSUMED parameter table from config/assumptions.yaml."""
    if not ASSUMPTIONS_PATH.exists():
        return {}
    import yaml

    return yaml.safe_load(ASSUMPTIONS_PATH.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # ALLOWED_ORIGINS is the canonical multi-origin var; fall back to the older
    # single CORS_ORIGIN for local dev convenience.
    raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if not raw_origins:
        raw_origins = os.environ.get("CORS_ORIGIN", "http://localhost:5173").strip()
    return Settings(
        llm_provider=os.environ.get("LLM_PROVIDER", "none").strip() or "none",
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        mbta_api_key=os.environ.get("MBTA_API_KEY", "").strip(),
        token_key=os.environ.get("TOKEN_KEY", "").strip(),
        vault_path=os.environ.get("VAULT_PATH", "secrets/vault.sqlite").strip(),
        allowed_origins=_parse_origins(raw_origins),
        eventtwin_db=os.environ.get("EVENTTWIN_DB", "").strip(),
        cache_dir=os.environ.get("EVENTTWIN_CACHE", "").strip(),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash",
        agent_max_tool_calls=_int_env("AGENT_MAX_TOOL_CALLS", 12),
        agent_timeout_s=_int_env("AGENT_TIMEOUT_S", 60),
        agent_max_output_tokens=_int_env("AGENT_MAX_OUTPUT_TOKENS", 2048),
    )


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def agent_cache_dir() -> Path:
    """Directory for 24h cached completed research per (plan hash, task)."""
    d = active_cache_dir() / "agent_cache"
    return d


settings = get_settings()
