"""
provenance.py

The cross-cutting provenance layer. Every numeric output in EventTwin must carry
a label - MEASURED, ASSUMED, PLACEHOLDER, or SIMULATED - plus a source string.

This module defines:
  - the allowed label set and a ``Label`` string-enum,
  - a ``ProvenanceRow`` record,
  - a ``ProvenanceStore`` that persists rows to the DuckDB ``provenance`` table,
  - an in-memory ``ProvenanceRecorder`` for use inside a single request/plan.

The DuckDB table schema::

    provenance(
        output_key   VARCHAR,   -- dotted key e.g. "venue.recommended.capacity"
        label        VARCHAR,   -- one of the four labels
        source       VARCHAR,   -- human-readable source / citation
        value_summary VARCHAR,  -- short string summary of the value
        recorded_at  TIMESTAMP  -- when the row was recorded
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable

from .config import DUCKDB_PATH


class Label(str, Enum):
    """The only provenance labels EventTwin recognises."""

    MEASURED = "MEASURED"
    ASSUMED = "ASSUMED"
    PLACEHOLDER = "PLACEHOLDER"
    SIMULATED = "SIMULATED"


ALLOWED_LABELS: frozenset[str] = frozenset(label.value for label in Label)


def _coerce_label(label: str | Label) -> str:
    value = label.value if isinstance(label, Label) else str(label)
    if value not in ALLOWED_LABELS:
        raise ValueError(
            f"Invalid provenance label {value!r}; must be one of {sorted(ALLOWED_LABELS)}"
        )
    return value


@dataclass(frozen=True)
class ProvenanceRow:
    """A single provenance record for one output number (or dataset row)."""

    output_key: str
    label: str
    source: str
    value_summary: str = ""
    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _coerce_label(self.label))
        if not self.output_key:
            raise ValueError("output_key must be non-empty")


class ProvenanceRecorder:
    """Collect provenance rows during a computation, then flush them to a store.

    Services call ``record(output_key, label, source, value_summary)`` as they
    produce numbers; the orchestrator flushes the batch to the DuckDB table.
    """

    def __init__(self) -> None:
        self._rows: list[ProvenanceRow] = []

    def record(
        self,
        output_key: str,
        label: str | Label,
        source: str,
        value_summary: str = "",
    ) -> ProvenanceRow:
        row = ProvenanceRow(
            output_key=output_key,
            label=_coerce_label(label),
            source=source,
            value_summary=value_summary,
        )
        self._rows.append(row)
        return row

    @property
    def rows(self) -> list[ProvenanceRow]:
        return list(self._rows)

    def labels_present(self) -> set[str]:
        return {r.label for r in self._rows}

    def extend(self, rows: Iterable[ProvenanceRow]) -> None:
        self._rows.extend(rows)

    def clear(self) -> None:
        self._rows.clear()


_DDL = """
CREATE TABLE IF NOT EXISTS provenance (
    output_key    VARCHAR,
    label         VARCHAR,
    source        VARCHAR,
    value_summary VARCHAR,
    recorded_at   TIMESTAMP
);
"""


class ProvenanceStore:
    """Persist and query provenance rows in DuckDB.

    A path of ``:memory:`` keeps everything in-process, which the unit tests use.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = ":memory:" if db_path == ":memory:" else Path(db_path or DUCKDB_PATH)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        import duckdb  # imported lazily so importing this module never requires duckdb

        target = ":memory:" if self.db_path == ":memory:" else str(self.db_path)
        return duckdb.connect(target)

    def _ensure_schema(self) -> None:
        con = self._connect()
        try:
            con.execute(_DDL)
        finally:
            con.close()

    def add(self, rows: Iterable[ProvenanceRow]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        con = self._connect()
        try:
            con.execute(_DDL)
            con.executemany(
                "INSERT INTO provenance "
                "(output_key, label, source, value_summary, recorded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (r.output_key, r.label, r.source, r.value_summary, r.recorded_at)
                    for r in rows
                ],
            )
        finally:
            con.close()
        return len(rows)

    def all(self) -> list[dict]:
        con = self._connect()
        try:
            con.execute(_DDL)
            cur = con.execute(
                "SELECT output_key, label, source, value_summary, recorded_at "
                "FROM provenance ORDER BY recorded_at"
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            con.close()

    def label_counts(self) -> dict[str, int]:
        """Return a count per label, including zeros for labels not yet present."""
        counts = {label.value: 0 for label in Label}
        con = self._connect()
        try:
            con.execute(_DDL)
            cur = con.execute(
                "SELECT label, COUNT(*) FROM provenance GROUP BY label"
            )
            for label, n in cur.fetchall():
                counts[label] = int(n)
        finally:
            con.close()
        return counts
