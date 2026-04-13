"""Audit Trail Export — Compliance-grade bulk export of audit entries.

Purpose: Export audit trail entries in standard formats (JSON Lines, CSV)
    for compliance review (SOC2, GDPR, regulatory), incident investigation,
    and external analysis tools.
Governance scope: read-only export — does not modify audit trail.
Dependencies: audit_trail.py (AuditEntry, AuditTrail).
Invariants:
  - Export is read-only — audit trail is never modified.
  - Chain integrity is verified before export (optional).
  - Export includes compliance metadata (export timestamp, hash, filter criteria).
  - PII in audit detail is optionally redacted in export.
  - Bounded: export respects limit parameter.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

from mcoi_runtime.core.audit_trail import AuditEntry, AuditTrail


@dataclass(frozen=True, slots=True)
class ExportMetadata:
    """Metadata attached to every audit export."""

    export_id: str
    format: str  # "jsonl", "csv"
    entry_count: int
    exported_at: str
    filters: dict[str, Any]
    chain_verified: bool
    chain_valid: bool
    export_hash: str  # SHA-256 of export content


@dataclass(frozen=True, slots=True)
class AuditExportResult:
    """Result of an audit export operation."""

    success: bool
    content: str  # The exported data (JSONL or CSV string)
    metadata: ExportMetadata
    error: str = ""


class AuditExporter:
    """Compliance-grade audit trail exporter.

    Supports JSON Lines (machine-readable, streaming) and CSV (spreadsheet)
    formats with filtering, integrity verification, and compliance metadata.

    Usage:
        exporter = AuditExporter(audit_trail=trail, clock=clock)

        # Export all entries as JSON Lines
        result = exporter.export_jsonl()

        # Export denials for tenant t1 as CSV
        result = exporter.export_csv(tenant_id="t1", outcome="denied")

        # Export with chain verification
        result = exporter.export_jsonl(verify_chain=True)
    """

    MAX_EXPORT_ENTRIES = 100_000

    def __init__(
        self,
        *,
        audit_trail: AuditTrail,
        clock: Callable[[], str],
    ) -> None:
        self._trail = audit_trail
        self._clock = clock
        self._export_count = 0

    def _filter_entries(
        self,
        *,
        tenant_id: str = "",
        action: str = "",
        outcome: str = "",
        actor_id: str = "",
        limit: int = 0,
    ) -> list[AuditEntry]:
        """Filter audit entries. limit=0 means use MAX_EXPORT_ENTRIES."""
        effective_limit = limit if limit > 0 else self.MAX_EXPORT_ENTRIES
        return self._trail.query(
            tenant_id=tenant_id or None,
            action=action or None,
            outcome=outcome or None,
            actor_id=actor_id or None,
            limit=effective_limit,
        )

    @staticmethod
    def _sanitize_csv_value(value: str) -> str:
        """Sanitize a string value to prevent CSV formula injection.

        CSV readers (Excel, LibreOffice) interpret cells starting with
        =, +, -, @, \\t, \\r as formulas.  Prefix with a single quote
        to force text interpretation.
        """
        if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{value}"
        return value

    def _entry_to_dict(self, entry: AuditEntry, *, redact_detail: bool = False) -> dict[str, Any]:
        """Convert an AuditEntry to a serializable dict."""
        detail = entry.detail
        if redact_detail and detail:
            detail = {k: "[REDACTED]" for k in detail}
        return {
            "entry_id": entry.entry_id,
            "sequence": entry.sequence,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "tenant_id": entry.tenant_id,
            "target": entry.target,
            "outcome": entry.outcome,
            "detail": detail,
            "entry_hash": entry.entry_hash,
            "previous_hash": entry.previous_hash,
            "recorded_at": entry.recorded_at,
        }

    def _make_export_id(self) -> str:
        self._export_count += 1
        return f"export-{self._export_count}"

    def _build_metadata(
        self,
        *,
        export_id: str,
        fmt: str,
        entry_count: int,
        content: str,
        filters: dict[str, Any],
        chain_verified: bool,
        chain_valid: bool,
    ) -> ExportMetadata:
        export_hash = sha256(content.encode()).hexdigest()[:16]
        return ExportMetadata(
            export_id=export_id,
            format=fmt,
            entry_count=entry_count,
            exported_at=self._clock(),
            filters=filters,
            chain_verified=chain_verified,
            chain_valid=chain_valid,
            export_hash=export_hash,
        )

    def export_jsonl(
        self,
        *,
        tenant_id: str = "",
        action: str = "",
        outcome: str = "",
        actor_id: str = "",
        limit: int = 0,
        verify_chain: bool = False,
        redact_detail: bool = False,
    ) -> AuditExportResult:
        """Export audit entries as JSON Lines (one JSON object per line).

        JSON Lines is the preferred format for machine processing,
        streaming ingestion (Elasticsearch, Datadog), and large exports.
        """
        filters = {
            k: v for k, v in {
                "tenant_id": tenant_id, "action": action,
                "outcome": outcome, "actor_id": actor_id,
                "limit": limit,
            }.items() if v
        }

        chain_valid = True
        chain_verified = False
        if verify_chain:
            chain_valid, _ = self._trail.verify_chain()
            chain_verified = True

        entries = self._filter_entries(
            tenant_id=tenant_id, action=action,
            outcome=outcome, actor_id=actor_id, limit=limit,
        )

        lines = []
        for entry in entries:
            d = self._entry_to_dict(entry, redact_detail=redact_detail)
            lines.append(json.dumps(d, sort_keys=True, default=str))
        content = "\n".join(lines)

        export_id = self._make_export_id()
        metadata = self._build_metadata(
            export_id=export_id, fmt="jsonl",
            entry_count=len(entries), content=content,
            filters=filters, chain_verified=chain_verified,
            chain_valid=chain_valid,
        )

        return AuditExportResult(
            success=True, content=content, metadata=metadata,
        )

    def export_csv(
        self,
        *,
        tenant_id: str = "",
        action: str = "",
        outcome: str = "",
        actor_id: str = "",
        limit: int = 0,
        verify_chain: bool = False,
        redact_detail: bool = False,
    ) -> AuditExportResult:
        """Export audit entries as CSV.

        CSV format is suitable for spreadsheet analysis and simple
        compliance review workflows.
        """
        filters = {
            k: v for k, v in {
                "tenant_id": tenant_id, "action": action,
                "outcome": outcome, "actor_id": actor_id,
                "limit": limit,
            }.items() if v
        }

        chain_valid = True
        chain_verified = False
        if verify_chain:
            chain_valid, _ = self._trail.verify_chain()
            chain_verified = True

        entries = self._filter_entries(
            tenant_id=tenant_id, action=action,
            outcome=outcome, actor_id=actor_id, limit=limit,
        )

        output = io.StringIO()
        fieldnames = [
            "entry_id", "sequence", "action", "actor_id", "tenant_id",
            "target", "outcome", "detail", "entry_hash", "previous_hash",
            "recorded_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            d = self._entry_to_dict(entry, redact_detail=redact_detail)
            d["detail"] = json.dumps(d["detail"], sort_keys=True, default=str)
            # Sanitize all string values to prevent CSV formula injection
            for k, v in d.items():
                if isinstance(v, str):
                    d[k] = self._sanitize_csv_value(v)
            writer.writerow(d)
        content = output.getvalue()

        export_id = self._make_export_id()
        metadata = self._build_metadata(
            export_id=export_id, fmt="csv",
            entry_count=len(entries), content=content,
            filters=filters, chain_verified=chain_verified,
            chain_valid=chain_valid,
        )

        return AuditExportResult(
            success=True, content=content, metadata=metadata,
        )

    def stream_jsonl(
        self,
        *,
        tenant_id: str = "",
        action: str = "",
        outcome: str = "",
        actor_id: str = "",
        limit: int = 0,
        redact_detail: bool = False,
    ) -> Any:
        """Streaming JSONL export — yields one line at a time.

        Use this for large exports to avoid loading all entries into
        memory at once.  Each yield is a complete JSON line (no newline).

        Usage:
            for line in exporter.stream_jsonl(tenant_id="t1"):
                file.write(line + "\\n")
        """
        from typing import Generator
        entries = self._filter_entries(
            tenant_id=tenant_id, action=action,
            outcome=outcome, actor_id=actor_id, limit=limit,
        )
        for entry in entries:
            d = self._entry_to_dict(entry, redact_detail=redact_detail)
            yield json.dumps(d, sort_keys=True, default=str)

    @property
    def export_count(self) -> int:
        return self._export_count
