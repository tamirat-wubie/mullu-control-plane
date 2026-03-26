"""Phase 224C — Data Export Pipeline (CSV/JSON).

Purpose: Export governed data (audit trails, metrics, traces) in CSV and
    JSON formats with field selection and filtering.
Dependencies: None (stdlib only).
Invariants:
  - Exported data matches source records exactly.
  - CSV output is RFC 4180 compliant.
  - JSON output is valid and UTF-8 encoded.
  - Export operations are auditable.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class ExportFormat(Enum):
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"  # JSON Lines


@dataclass(frozen=True)
class ExportRequest:
    """Request to export data in a specific format."""
    source: str  # e.g. "audit_trail", "metrics", "traces"
    format: ExportFormat
    fields: tuple[str, ...] = ()  # empty = all fields
    filters: dict[str, Any] = field(default_factory=dict)
    limit: int = 10_000


@dataclass
class ExportResult:
    """Result of a data export operation."""
    source: str
    format: ExportFormat
    record_count: int
    content: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "format": self.format.value,
            "record_count": self.record_count,
            "size_bytes": self.size_bytes,
        }


class DataExportPipeline:
    """Exports governed data in CSV, JSON, or JSONL formats."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._sources: dict[str, Callable[[], list[dict[str, Any]]]] = {}
        self._total_exports = 0
        self._total_records_exported = 0

    def register_source(self, name: str, provider: Callable[[], list[dict[str, Any]]]) -> None:
        self._sources[name] = provider

    def unregister_source(self, name: str) -> None:
        self._sources.pop(name, None)

    @property
    def source_count(self) -> int:
        return len(self._sources)

    def list_sources(self) -> list[str]:
        return sorted(self._sources.keys())

    def export(self, request: ExportRequest) -> ExportResult:
        if request.source not in self._sources:
            raise ValueError(f"Unknown export source: {request.source}")

        records = self._sources[request.source]()

        # Apply filters
        for key, value in request.filters.items():
            records = [r for r in records if r.get(key) == value]

        # Apply limit
        records = records[:request.limit]

        # Select fields
        if request.fields:
            records = [
                {k: r.get(k) for k in request.fields}
                for r in records
            ]

        # Format output
        if request.format == ExportFormat.CSV:
            content = self._to_csv(records)
        elif request.format == ExportFormat.JSON:
            content = json.dumps(records, indent=2, default=str)
        elif request.format == ExportFormat.JSONL:
            content = "\n".join(json.dumps(r, default=str) for r in records)
        else:
            raise ValueError(f"Unsupported format: {request.format}")

        self._total_exports += 1
        self._total_records_exported += len(records)

        return ExportResult(
            source=request.source,
            format=request.format,
            record_count=len(records),
            content=content,
            size_bytes=len(content.encode("utf-8")),
        )

    @staticmethod
    def _to_csv(records: list[dict[str, Any]]) -> str:
        if not records:
            return ""
        output = io.StringIO()
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record.get(k, "") for k in fieldnames})
        return output.getvalue()

    def summary(self) -> dict[str, Any]:
        return {
            "registered_sources": self.source_count,
            "source_names": self.list_sources(),
            "total_exports": self._total_exports,
            "total_records_exported": self._total_records_exported,
        }
