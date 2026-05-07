"""Tests for Phase 224C — Data Export Pipeline."""
from __future__ import annotations

import csv
import io
import json
import pytest

from mcoi_runtime.core.data_export import (
    DataExportPipeline,
    ExportFormat,
    ExportRequest,
)


@pytest.fixture
def pipeline():
    p = DataExportPipeline()
    p.register_source("audit", lambda: [
        {"id": "1", "action": "login", "tenant": "t1", "timestamp": "2024-01-01"},
        {"id": "2", "action": "logout", "tenant": "t1", "timestamp": "2024-01-02"},
        {"id": "3", "action": "login", "tenant": "t2", "timestamp": "2024-01-03"},
    ])
    return p


class TestDataExportPipeline:
    def test_register_source(self, pipeline):
        assert pipeline.source_count == 1
        assert "audit" in pipeline.list_sources()

    def test_export_json(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSON)
        result = pipeline.export(req)
        assert result.record_count == 3
        parsed = json.loads(result.content)
        assert len(parsed) == 3
        assert result.size_bytes > 0

    def test_export_csv(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.CSV)
        result = pipeline.export(req)
        assert result.record_count == 3
        reader = csv.DictReader(io.StringIO(result.content))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["action"] == "login"

    def test_export_jsonl(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSONL)
        result = pipeline.export(req)
        lines = result.content.strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # each line is valid JSON

    def test_field_selection(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSON, fields=("id", "action"))
        result = pipeline.export(req)
        parsed = json.loads(result.content)
        assert set(parsed[0].keys()) == {"id", "action"}

    def test_filter(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSON, filters={"tenant": "t1"})
        result = pipeline.export(req)
        assert result.record_count == 2

    def test_limit(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSON, limit=1)
        result = pipeline.export(req)
        assert result.record_count == 1

    def test_unknown_source(self, pipeline):
        req = ExportRequest(source="nonexistent", format=ExportFormat.JSON)
        with pytest.raises(ValueError, match="Unknown export source") as exc_info:
            pipeline.export(req)
        assert "nonexistent" not in str(exc_info.value)

    def test_unsupported_format_is_bounded(self, pipeline):
        req = ExportRequest(source="audit", format="yaml")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Unsupported export format") as exc_info:
            pipeline.export(req)
        assert "yaml" not in str(exc_info.value)

    def test_empty_source(self):
        p = DataExportPipeline()
        p.register_source("empty", lambda: [])
        req = ExportRequest(source="empty", format=ExportFormat.JSON)
        result = p.export(req)
        assert result.record_count == 0

    def test_csv_empty(self):
        p = DataExportPipeline()
        p.register_source("empty", lambda: [])
        req = ExportRequest(source="empty", format=ExportFormat.CSV)
        result = p.export(req)
        assert result.content == ""

    def test_unregister_source(self, pipeline):
        pipeline.unregister_source("audit")
        assert pipeline.source_count == 0

    def test_summary(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.JSON)
        pipeline.export(req)
        s = pipeline.summary()
        assert s["total_exports"] == 1
        assert s["total_records_exported"] == 3
        assert "audit" in s["source_names"]

    def test_result_to_dict(self, pipeline):
        req = ExportRequest(source="audit", format=ExportFormat.CSV)
        result = pipeline.export(req)
        d = result.to_dict()
        assert d["format"] == "csv"
        assert d["record_count"] == 3
