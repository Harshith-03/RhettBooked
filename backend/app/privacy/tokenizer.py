"""
tokenizer.py

Deterministic HMAC tokenizer + separate SQLite vault with an audit log (P1).

- ``tokenize(value)`` -> a stable HMAC-SHA256 token (same input -> same token),
  storing the reverse mapping in a vault SQLite file (VAULT_PATH) so authorized
  ``detokenize(token)`` can recover the original under audit.
- Every tokenize/detokenize is written to an audit log table with a timestamp.

The HMAC key comes from TOKEN_KEY (env). If unset, a process-local key is used
and a warning flag is set (tokens are then not stable across restarts).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..config import REPO_ROOT, settings


def _vault_path() -> Path:
    p = Path(settings.vault_path or "secrets/vault.sqlite")
    return p if p.is_absolute() else (REPO_ROOT / p)


def _key() -> tuple[bytes, bool]:
    """Return (key_bytes, is_ephemeral)."""
    k = (settings.token_key or "").strip()
    # The repo's sample .env ships an unresolved placeholder; treat it as unset.
    if not k or k.startswith("<"):
        return (os.urandom(32), True)
    return (k.encode("utf-8"), False)


class Vault:
    """SQLite-backed token vault with an audit log."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _vault_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key, self.ephemeral = _key()
        self._conn = sqlite3.connect(str(self.path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS vault ("
            "token TEXT PRIMARY KEY, value TEXT NOT NULL, entity TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS audit ("
            "ts TEXT, action TEXT, token TEXT, entity TEXT)"
        )
        self._conn.commit()

    def _hmac(self, value: str) -> str:
        return hmac.new(self._key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def _audit(self, action: str, token: str, entity: str = "") -> None:
        self._conn.execute(
            "INSERT INTO audit (ts, action, token, entity) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), action, token, entity),
        )
        self._conn.commit()

    def tokenize(self, value: str, entity: str = "") -> str:
        token = self._hmac(value)
        self._conn.execute(
            "INSERT OR IGNORE INTO vault (token, value, entity) VALUES (?,?,?)",
            (token, value, entity),
        )
        self._conn.commit()
        self._audit("tokenize", token, entity)
        return token

    def detokenize(self, token: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM vault WHERE token = ?", (token,)
        ).fetchone()
        self._audit("detokenize", token)
        return row[0] if row else None

    def audit_log(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, action, token, entity FROM audit ORDER BY ts"
        ).fetchall()
        return [{"ts": r[0], "action": r[1], "token": r[2], "entity": r[3]} for r in rows]

    def close(self) -> None:
        self._conn.close()
