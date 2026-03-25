"""Contract-level tests for artifact_parser contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.artifact_parser import (
    ArtifactParserDescriptor,
    NormalizedParseOutput,
    ParseCapability,
    ParseOutputKind,
    ParserCapabilityLevel,
    ParserCapabilityManifest,
    ParserFailureMode,
    ParserFamily,
    ParserHealthReport,
    ParserPolicyConstraint,
    ParserStatus,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum value counts
# ---------------------------------------------------------------------------


class TestEnumCounts:
    def test_parser_family_count(self):
        assert len(ParserFamily) == 8

    def test_parser_status_count(self):
        assert len(ParserStatus) == 4

    def test_parse_output_kind_count(self):
        assert len(ParseOutputKind) == 6

    def test_parser_capability_level_count(self):
        assert len(ParserCapabilityLevel) == 3


# ---------------------------------------------------------------------------
# ParseCapability
# ---------------------------------------------------------------------------


class TestParseCapability:
    def _make(self, **kw):
        defaults = dict(
            format_name="pdf",
            extensions=(".pdf",),
            mime_types=("application/pdf",),
            capability_level=ParserCapabilityLevel.FULL_CONTENT,
            max_size_bytes=1024,
            output_kinds=("text",),
        )
        defaults.update(kw)
        return ParseCapability(**defaults)

    def test_valid(self):
        c = self._make()
        assert c.format_name == "pdf"
        assert c.max_size_bytes == 1024

    def test_empty_format_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(format_name="")

    def test_invalid_capability_level(self):
        with pytest.raises(ValueError):
            self._make(capability_level="deep")

    def test_frozen_immutability(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.format_name = "docx"

    def test_extensions_frozen(self):
        c = self._make(extensions=[".pdf", ".doc"])
        assert isinstance(c.extensions, tuple)
        with pytest.raises((TypeError, AttributeError)):
            c.extensions.append(".xls")

    def test_negative_max_size_bytes_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_size_bytes=-1)

    def test_zero_max_size_bytes_accepted(self):
        c = self._make(max_size_bytes=0)
        assert c.max_size_bytes == 0

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["format_name"] == "pdf"
        assert d["capability_level"] == ParserCapabilityLevel.FULL_CONTENT
        assert isinstance(d["extensions"], list)


# ---------------------------------------------------------------------------
# ParserPolicyConstraint
# ---------------------------------------------------------------------------


class TestParserPolicyConstraint:
    def _make(self, **kw):
        defaults = dict(
            constraint_id="cst-1",
            description="Max file size",
            constraint_type="size_limit",
            value="10MB",
            enforced=True,
        )
        defaults.update(kw)
        return ParserPolicyConstraint(**defaults)

    def test_valid(self):
        c = self._make()
        assert c.constraint_id == "cst-1"
        assert c.enforced is True

    def test_empty_constraint_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(constraint_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._make(description="")

    def test_empty_constraint_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(constraint_type="")

    def test_frozen_immutability(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.constraint_id = "cst-2"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["constraint_id"] == "cst-1"
        assert d["enforced"] is True


# ---------------------------------------------------------------------------
# ParserFailureMode
# ---------------------------------------------------------------------------


class TestParserFailureMode:
    def _make(self, **kw):
        defaults = dict(
            mode_id="fm-1",
            description="Timeout on large files",
            severity="medium",
            is_recoverable=True,
            recommended_action="retry with smaller chunk",
        )
        defaults.update(kw)
        return ParserFailureMode(**defaults)

    def test_valid(self):
        fm = self._make()
        assert fm.mode_id == "fm-1"
        assert fm.severity == "medium"

    def test_empty_mode_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(mode_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._make(description="")

    def test_severity_low(self):
        fm = self._make(severity="low")
        assert fm.severity == "low"

    def test_severity_high(self):
        fm = self._make(severity="high")
        assert fm.severity == "high"

    def test_severity_critical(self):
        fm = self._make(severity="critical")
        assert fm.severity == "critical"

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            self._make(severity="extreme")

    def test_frozen_immutability(self):
        fm = self._make()
        with pytest.raises(AttributeError):
            fm.severity = "high"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["mode_id"] == "fm-1"
        assert d["severity"] == "medium"


# ---------------------------------------------------------------------------
# ParserCapabilityManifest
# ---------------------------------------------------------------------------


class TestParserCapabilityManifest:
    def _make(self, **kw):
        defaults = dict(
            manifest_id="mf-1",
            parser_id="p-1",
            family=ParserFamily.DOCUMENT,
            reliability_score=0.95,
            created_at=NOW,
        )
        defaults.update(kw)
        return ParserCapabilityManifest(**defaults)

    def test_valid(self):
        m = self._make()
        assert m.manifest_id == "mf-1"
        assert m.family == ParserFamily.DOCUMENT
        assert m.reliability_score == 0.95

    def test_empty_manifest_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(manifest_id="")

    def test_empty_parser_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(parser_id="")

    def test_invalid_family_type(self):
        with pytest.raises(ValueError):
            self._make(family="unknown")

    def test_reliability_score_zero(self):
        m = self._make(reliability_score=0.0)
        assert m.reliability_score == 0.0

    def test_reliability_score_one(self):
        m = self._make(reliability_score=1.0)
        assert m.reliability_score == 1.0

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=1.01)

    def test_reliability_score_negative_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=-0.1)

    def test_frozen_immutability(self):
        m = self._make()
        with pytest.raises(AttributeError):
            m.manifest_id = "mf-2"

    def test_metadata_frozen(self):
        m = self._make(metadata={"key": "val"})
        with pytest.raises(TypeError):
            m.metadata["new"] = "x"

    def test_capabilities_frozen(self):
        cap = ParseCapability(
            format_name="pdf", extensions=(".pdf",),
            mime_types=("application/pdf",),
            max_size_bytes=0,
        )
        m = self._make(capabilities=[cap])
        assert isinstance(m.capabilities, tuple)
        with pytest.raises((TypeError, AttributeError)):
            m.capabilities.append(cap)

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["manifest_id"] == "mf-1"
        assert d["family"] == ParserFamily.DOCUMENT
        assert isinstance(d["reliability_score"], float)


# ---------------------------------------------------------------------------
# ArtifactParserDescriptor
# ---------------------------------------------------------------------------


class TestArtifactParserDescriptor:
    def _make(self, **kw):
        defaults = dict(
            parser_id="p-1",
            name="PDF Parser",
            family=ParserFamily.DOCUMENT,
            status=ParserStatus.AVAILABLE,
            version="1.0.0",
            manifest_id="mf-1",
            created_at=NOW,
        )
        defaults.update(kw)
        return ArtifactParserDescriptor(**defaults)

    def test_valid(self):
        d = self._make()
        assert d.parser_id == "p-1"
        assert d.name == "PDF Parser"
        assert d.status == ParserStatus.AVAILABLE

    def test_empty_parser_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(parser_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(name="")

    def test_invalid_family_type(self):
        with pytest.raises(ValueError):
            self._make(family="video")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="broken")

    def test_frozen_immutability(self):
        d = self._make()
        with pytest.raises(AttributeError):
            d.parser_id = "p-2"

    def test_tags_frozen(self):
        d = self._make(tags=["fast", "reliable"])
        assert isinstance(d.tags, tuple)
        with pytest.raises((TypeError, AttributeError)):
            d.tags.append("new")

    def test_metadata_frozen(self):
        d = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            d.metadata["new"] = "x"

    def test_all_statuses(self):
        for s in ParserStatus:
            d = self._make(status=s)
            assert d.status == s

    def test_all_families(self):
        for f in ParserFamily:
            d = self._make(family=f)
            assert d.family == f

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["parser_id"] == "p-1"
        assert d["family"] == ParserFamily.DOCUMENT
        assert d["status"] == ParserStatus.AVAILABLE


# ---------------------------------------------------------------------------
# NormalizedParseOutput
# ---------------------------------------------------------------------------


class TestNormalizedParseOutput:
    def _make(self, **kw):
        defaults = dict(
            output_id="out-1",
            parser_id="p-1",
            artifact_id="art-1",
            family=ParserFamily.DOCUMENT,
            output_kind=ParseOutputKind.TEXT,
            text_content="Hello world",
            page_count=1,
            word_count=2,
            parsed_at=NOW,
        )
        defaults.update(kw)
        return NormalizedParseOutput(**defaults)

    def test_valid(self):
        o = self._make()
        assert o.output_id == "out-1"
        assert o.word_count == 2

    def test_empty_output_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(output_id="")

    def test_empty_parser_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(parser_id="")

    def test_empty_artifact_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(artifact_id="")

    def test_invalid_family_type(self):
        with pytest.raises(ValueError):
            self._make(family="video")

    def test_invalid_output_kind_type(self):
        with pytest.raises(ValueError):
            self._make(output_kind="raw")

    def test_negative_page_count_rejected(self):
        with pytest.raises(ValueError):
            self._make(page_count=-1)

    def test_negative_word_count_rejected(self):
        with pytest.raises(ValueError):
            self._make(word_count=-1)

    def test_zero_counts_accepted(self):
        o = self._make(page_count=0, word_count=0)
        assert o.page_count == 0
        assert o.word_count == 0

    def test_structured_data_frozen(self):
        o = self._make(structured_data={"key": "val"})
        with pytest.raises(TypeError):
            o.structured_data["new"] = "x"

    def test_tables_frozen(self):
        o = self._make(tables=[{"col": "a"}])
        assert isinstance(o.tables, tuple)
        with pytest.raises((TypeError, AttributeError)):
            o.tables.append({"col": "b"})

    def test_extracted_metadata_frozen(self):
        o = self._make(extracted_metadata={"author": "Alice"})
        with pytest.raises(TypeError):
            o.extracted_metadata["title"] = "Doc"

    def test_frozen_immutability(self):
        o = self._make()
        with pytest.raises(AttributeError):
            o.output_id = "out-2"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["output_id"] == "out-1"
        assert d["family"] == ParserFamily.DOCUMENT
        assert d["output_kind"] == ParseOutputKind.TEXT


# ---------------------------------------------------------------------------
# ParserHealthReport
# ---------------------------------------------------------------------------


class TestParserHealthReport:
    def _make(self, **kw):
        defaults = dict(
            report_id="rpt-1",
            parser_id="p-1",
            status=ParserStatus.AVAILABLE,
            reliability_score=0.99,
            artifacts_parsed=100,
            artifacts_failed=2,
            avg_parse_ms=45.5,
            reported_at=NOW,
        )
        defaults.update(kw)
        return ParserHealthReport(**defaults)

    def test_valid(self):
        r = self._make()
        assert r.report_id == "rpt-1"
        assert r.artifacts_parsed == 100

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_empty_parser_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(parser_id="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="offline")

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=1.5)

    def test_reliability_score_negative_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=-0.01)

    def test_negative_artifacts_parsed_rejected(self):
        with pytest.raises(ValueError):
            self._make(artifacts_parsed=-1)

    def test_negative_artifacts_failed_rejected(self):
        with pytest.raises(ValueError):
            self._make(artifacts_failed=-1)

    def test_zero_counts_accepted(self):
        r = self._make(artifacts_parsed=0, artifacts_failed=0)
        assert r.artifacts_parsed == 0
        assert r.artifacts_failed == 0

    def test_active_failure_modes_frozen(self):
        r = self._make(active_failure_modes=["fm-1", "fm-2"])
        assert isinstance(r.active_failure_modes, tuple)
        with pytest.raises((TypeError, AttributeError)):
            r.active_failure_modes.append("fm-3")

    def test_frozen_immutability(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.report_id = "rpt-2"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["report_id"] == "rpt-1"
        assert d["status"] == ParserStatus.AVAILABLE
        assert isinstance(d["reliability_score"], float)
