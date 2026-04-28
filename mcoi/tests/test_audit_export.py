"""Audit Trail Export Tests — JSON Lines and CSV compliance exports."""

import csv
import io
import json

import pytest
from mcoi_runtime.governance.audit.trail import AuditTrail
from mcoi_runtime.governance.audit.export import (
    AuditExporter,
    AuditExportResult,
    ExportMetadata,
)


def _trail_with_entries(n=5):
    trail = AuditTrail(clock=lambda: "2026-04-07T12:00:00Z")
    for i in range(n):
        trail.record(
            action=f"action.{i % 3}",
            actor_id=f"user-{i % 2}",
            tenant_id=f"t{(i % 2) + 1}",
            target=f"resource-{i}",
            outcome="success" if i % 3 != 2 else "denied",
            detail={"index": i, "note": f"entry {i}"},
        )
    return trail


def _exporter(trail=None, n=5):
    t = trail or _trail_with_entries(n)
    return AuditExporter(audit_trail=t, clock=lambda: "2026-04-07T12:30:00Z")


# ── JSON Lines export ──────────────────────────────────────────

class TestJSONLExport:
    def test_export_all(self):
        exp = _exporter()
        result = exp.export_jsonl()
        assert result.success is True
        lines = result.content.strip().split("\n")
        assert len(lines) == 5
        for line in lines:
            entry = json.loads(line)
            assert "entry_id" in entry
            assert "action" in entry
            assert "tenant_id" in entry

    def test_export_metadata(self):
        exp = _exporter()
        result = exp.export_jsonl()
        m = result.metadata
        assert m.format == "jsonl"
        assert m.entry_count == 5
        assert m.exported_at == "2026-04-07T12:30:00Z"
        assert m.export_hash != ""
        assert m.export_id == "export-1"

    def test_export_filtered_by_tenant(self):
        exp = _exporter()
        result = exp.export_jsonl(tenant_id="t1")
        lines = result.content.strip().split("\n")
        for line in lines:
            assert json.loads(line)["tenant_id"] == "t1"

    def test_export_filtered_by_outcome(self):
        exp = _exporter()
        result = exp.export_jsonl(outcome="denied")
        lines = [l for l in result.content.strip().split("\n") if l]
        for line in lines:
            assert json.loads(line)["outcome"] == "denied"

    def test_export_filtered_by_actor(self):
        exp = _exporter()
        result = exp.export_jsonl(actor_id="user-0")
        lines = [l for l in result.content.strip().split("\n") if l]
        for line in lines:
            assert json.loads(line)["actor_id"] == "user-0"

    def test_export_with_limit(self):
        exp = _exporter(n=20)
        result = exp.export_jsonl(limit=5)
        lines = result.content.strip().split("\n")
        assert len(lines) == 5

    def test_export_empty_trail(self):
        trail = AuditTrail(clock=lambda: "2026-04-07T12:00:00Z")
        exp = _exporter(trail=trail)
        result = exp.export_jsonl()
        assert result.success is True
        assert result.content == ""
        assert result.metadata.entry_count == 0

    def test_export_with_chain_verification(self):
        exp = _exporter()
        result = exp.export_jsonl(verify_chain=True)
        assert result.metadata.chain_verified is True
        assert result.metadata.chain_valid is True

    def test_export_hash_deterministic(self):
        exp = _exporter()
        r1 = exp.export_jsonl()
        r2 = exp.export_jsonl()
        assert r1.metadata.export_hash == r2.metadata.export_hash

    def test_export_with_redacted_detail(self):
        exp = _exporter()
        result = exp.export_jsonl(redact_detail=True)
        lines = result.content.strip().split("\n")
        for line in lines:
            entry = json.loads(line)
            for v in entry["detail"].values():
                assert v == "[REDACTED]"

    def test_filters_in_metadata(self):
        exp = _exporter()
        result = exp.export_jsonl(tenant_id="t1", outcome="denied")
        assert result.metadata.filters["tenant_id"] == "t1"
        assert result.metadata.filters["outcome"] == "denied"


# ── CSV export ─────────────────────────────────────────────────

class TestCSVExport:
    def test_export_all(self):
        exp = _exporter()
        result = exp.export_csv()
        assert result.success is True
        reader = csv.DictReader(io.StringIO(result.content))
        rows = list(reader)
        assert len(rows) == 5
        assert "entry_id" in rows[0]
        assert "action" in rows[0]

    def test_csv_metadata(self):
        exp = _exporter()
        result = exp.export_csv()
        assert result.metadata.format == "csv"
        assert result.metadata.entry_count == 5

    def test_csv_filtered_by_tenant(self):
        exp = _exporter()
        result = exp.export_csv(tenant_id="t1")
        reader = csv.DictReader(io.StringIO(result.content))
        for row in reader:
            assert row["tenant_id"] == "t1"

    def test_csv_detail_is_json(self):
        exp = _exporter()
        result = exp.export_csv()
        reader = csv.DictReader(io.StringIO(result.content))
        for row in reader:
            detail = json.loads(row["detail"])
            assert isinstance(detail, dict)

    def test_csv_with_redacted_detail(self):
        exp = _exporter()
        result = exp.export_csv(redact_detail=True)
        reader = csv.DictReader(io.StringIO(result.content))
        for row in reader:
            detail = json.loads(row["detail"])
            for v in detail.values():
                assert v == "[REDACTED]"

    def test_csv_with_chain_verification(self):
        exp = _exporter()
        result = exp.export_csv(verify_chain=True)
        assert result.metadata.chain_verified is True
        assert result.metadata.chain_valid is True

    def test_csv_empty_trail(self):
        trail = AuditTrail(clock=lambda: "2026-04-07T12:00:00Z")
        exp = _exporter(trail=trail)
        result = exp.export_csv()
        assert result.success is True
        assert result.metadata.entry_count == 0
        # Should have header row only
        lines = result.content.strip().split("\n")
        assert len(lines) == 1  # Just header


# ── Export counter ─────────────────────────────────────────────

class TestExportCounter:
    def test_export_count_increments(self):
        exp = _exporter()
        assert exp.export_count == 0
        exp.export_jsonl()
        assert exp.export_count == 1
        exp.export_csv()
        assert exp.export_count == 2

    def test_export_ids_unique(self):
        exp = _exporter()
        r1 = exp.export_jsonl()
        r2 = exp.export_csv()
        assert r1.metadata.export_id != r2.metadata.export_id


# ── Edge cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_large_detail_truncated_in_source(self):
        """Audit trail truncates large details; export reflects that."""
        trail = AuditTrail(clock=lambda: "2026-04-07T12:00:00Z")
        big_detail = {"data": "x" * 100_000}
        trail.record(
            action="test", actor_id="u1", tenant_id="t1",
            target="res", outcome="success", detail=big_detail,
        )
        exp = _exporter(trail=trail)
        result = exp.export_jsonl()
        entry = json.loads(result.content)
        assert entry["detail"].get("_truncated") is True

    def test_no_filter_match_returns_empty(self):
        exp = _exporter()
        result = exp.export_jsonl(tenant_id="nonexistent")
        assert result.content == ""
        assert result.metadata.entry_count == 0

    def test_combined_filters(self):
        exp = _exporter(n=10)
        result = exp.export_jsonl(tenant_id="t1", outcome="success")
        lines = [l for l in result.content.strip().split("\n") if l]
        for line in lines:
            e = json.loads(line)
            assert e["tenant_id"] == "t1"
            assert e["outcome"] == "success"
