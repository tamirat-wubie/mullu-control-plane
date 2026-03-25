"""Contract-level tests for artifact_ingestion contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.artifact_ingestion import (
    ArtifactCapabilityManifest,
    ArtifactDescriptor,
    ArtifactExtractionField,
    ArtifactExtractionResult,
    ArtifactFingerprint,
    ArtifactFormat,
    ArtifactIngestionRecord,
    ArtifactParseResult,
    ArtifactParseStatus,
    ArtifactPolicyDecision,
    ArtifactSemanticMapping,
    ArtifactSemanticType,
    ArtifactSourceType,
    ArtifactStructure,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# ArtifactDescriptor
# ---------------------------------------------------------------------------


class TestArtifactDescriptor:
    def _make(self, **kw):
        defaults = dict(
            artifact_id="art-1", source_type=ArtifactSourceType.FILE,
            source_ref="/data/file.json", filename="file.json",
            mime_type="application/json", created_at=NOW,
        )
        defaults.update(kw)
        return ArtifactDescriptor(**defaults)

    def test_valid(self):
        d = self._make()
        assert d.artifact_id == "art-1"
        assert d.format_hint == ArtifactFormat.UNKNOWN

    def test_empty_artifact_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(artifact_id="")

    def test_invalid_source_type(self):
        with pytest.raises(ValueError):
            self._make(source_type="carrier_pigeon")

    def test_metadata_frozen(self):
        d = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            d.metadata["new"] = "val"

    def test_all_source_types(self):
        for st in ArtifactSourceType:
            d = self._make(source_type=st)
            assert d.source_type == st

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["source_type"] == "file"


# ---------------------------------------------------------------------------
# ArtifactFingerprint
# ---------------------------------------------------------------------------


class TestArtifactFingerprint:
    def test_valid(self):
        fp = ArtifactFingerprint(
            fingerprint_id="fp-1", artifact_id="art-1",
            algorithm="sha256", digest="abc123", computed_at=NOW,
        )
        assert fp.algorithm == "sha256"

    def test_empty_digest_rejected(self):
        with pytest.raises(ValueError):
            ArtifactFingerprint(
                fingerprint_id="fp-1", artifact_id="art-1",
                algorithm="sha256", digest="", computed_at=NOW,
            )


# ---------------------------------------------------------------------------
# ArtifactParseResult
# ---------------------------------------------------------------------------


class TestArtifactParseResult:
    def _make(self, **kw):
        defaults = dict(
            parse_id="parse-1", artifact_id="art-1",
            format_detected=ArtifactFormat.JSON,
            status=ArtifactParseStatus.ACCEPTED,
            reason="Valid JSON", parsed_at=NOW,
        )
        defaults.update(kw)
        return ArtifactParseResult(**defaults)

    def test_valid(self):
        p = self._make()
        assert p.status == ArtifactParseStatus.ACCEPTED

    def test_all_statuses(self):
        for s in ArtifactParseStatus:
            p = self._make(status=s)
            assert p.status == s

    def test_all_formats(self):
        for f in ArtifactFormat:
            p = self._make(format_detected=f)
            assert p.format_detected == f

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            self._make(reason="")


# ---------------------------------------------------------------------------
# ArtifactStructure
# ---------------------------------------------------------------------------


class TestArtifactStructure:
    def test_valid(self):
        s = ArtifactStructure(
            structure_id="struct-1", artifact_id="art-1",
            format=ArtifactFormat.CSV, field_count=5, row_count=100,
            extracted_at=NOW,
        )
        assert s.row_count == 100

    def test_sections_frozen(self):
        s = ArtifactStructure(
            structure_id="struct-1", artifact_id="art-1",
            format=ArtifactFormat.JSON,
            sections={"keys": ["a", "b"]}, extracted_at=NOW,
        )
        with pytest.raises(TypeError):
            s.sections["new"] = "val"


# ---------------------------------------------------------------------------
# ArtifactSemanticMapping
# ---------------------------------------------------------------------------


class TestArtifactSemanticMapping:
    def _make(self, **kw):
        defaults = dict(
            mapping_id="map-1", artifact_id="art-1",
            semantic_type=ArtifactSemanticType.CONFIG,
            domain="ops", confidence=0.8, mapped_at=NOW,
        )
        defaults.update(kw)
        return ArtifactSemanticMapping(**defaults)

    def test_valid(self):
        m = self._make()
        assert m.semantic_type == ArtifactSemanticType.CONFIG

    def test_all_semantic_types(self):
        for st in ArtifactSemanticType:
            m = self._make(semantic_type=st)
            assert m.semantic_type == st

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.5)

    def test_tags_frozen(self):
        m = self._make(tags=("a", "b"))
        assert isinstance(m.tags, tuple)


# ---------------------------------------------------------------------------
# ArtifactPolicyDecision
# ---------------------------------------------------------------------------


class TestArtifactPolicyDecision:
    def test_allowed(self):
        d = ArtifactPolicyDecision(
            decision_id="apd-1", artifact_id="art-1",
            allowed=True, reason="All checks passed",
            checks_passed=("size_ok",), evaluated_at=NOW,
        )
        assert d.allowed is True

    def test_denied(self):
        d = ArtifactPolicyDecision(
            decision_id="apd-1", artifact_id="art-1",
            allowed=False, reason="Too large",
            checks_failed=("size",), evaluated_at=NOW,
        )
        assert d.allowed is False


# ---------------------------------------------------------------------------
# ArtifactExtractionField / Result
# ---------------------------------------------------------------------------


class TestArtifactExtractionField:
    def test_valid(self):
        f = ArtifactExtractionField(
            field_name="name", field_value="John",
        )
        assert f.confidence == 1.0

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            ArtifactExtractionField(field_name="", field_value="x")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            ArtifactExtractionField(
                field_name="x", field_value="y", confidence=2.0,
            )


class TestArtifactExtractionResult:
    def test_valid(self):
        f = ArtifactExtractionField(field_name="k", field_value="v")
        r = ArtifactExtractionResult(
            extraction_id="ext-1", artifact_id="art-1",
            fields=(f,), extracted_at=NOW,
        )
        assert len(r.fields) == 1

    def test_invalid_field_rejected(self):
        with pytest.raises(ValueError):
            ArtifactExtractionResult(
                extraction_id="ext-1", artifact_id="art-1",
                fields=("not a field",), extracted_at=NOW,
            )


# ---------------------------------------------------------------------------
# ArtifactCapabilityManifest
# ---------------------------------------------------------------------------


class TestArtifactCapabilityManifest:
    def test_valid(self):
        m = ArtifactCapabilityManifest(
            manifest_id="man-1",
            supported_formats=(ArtifactFormat.JSON, ArtifactFormat.CSV),
            supported_semantic_types=(ArtifactSemanticType.CONFIG,),
            max_size_bytes=1024,
            created_at=NOW,
        )
        assert len(m.supported_formats) == 2

    def test_zero_max_size_rejected(self):
        with pytest.raises(ValueError):
            ArtifactCapabilityManifest(
                manifest_id="man-1",
                supported_formats=(),
                supported_semantic_types=(),
                max_size_bytes=0,
                created_at=NOW,
            )

    def test_invalid_format_in_list(self):
        with pytest.raises(ValueError):
            ArtifactCapabilityManifest(
                manifest_id="man-1",
                supported_formats=("bad_format",),
                supported_semantic_types=(),
                max_size_bytes=1024,
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# ArtifactIngestionRecord
# ---------------------------------------------------------------------------


class TestArtifactIngestionRecord:
    def _make_full(self):
        desc = ArtifactDescriptor(
            artifact_id="art-1", source_type=ArtifactSourceType.FILE,
            source_ref="/f.json", filename="f.json",
            mime_type="application/json", created_at=NOW,
        )
        fp = ArtifactFingerprint(
            fingerprint_id="fp-1", artifact_id="art-1",
            algorithm="sha256", digest="abc", computed_at=NOW,
        )
        pr = ArtifactParseResult(
            parse_id="p-1", artifact_id="art-1",
            format_detected=ArtifactFormat.JSON,
            status=ArtifactParseStatus.ACCEPTED,
            reason="OK", parsed_at=NOW,
        )
        pol = ArtifactPolicyDecision(
            decision_id="apd-1", artifact_id="art-1",
            allowed=True, reason="All checks passed", evaluated_at=NOW,
        )
        return ArtifactIngestionRecord(
            record_id="rec-1", artifact_id="art-1",
            descriptor=desc, fingerprint=fp,
            parse_result=pr, structure=None,
            semantic_mapping=None, policy_decision=pol,
            status=ArtifactParseStatus.ACCEPTED,
            ingested_at=NOW,
        )

    def test_valid(self):
        r = self._make_full()
        assert r.status == ArtifactParseStatus.ACCEPTED

    def test_lineage_ids_frozen(self):
        r = self._make_full()
        assert isinstance(r.lineage_ids, tuple)

    def test_frozen(self):
        r = self._make_full()
        with pytest.raises(AttributeError):
            r.artifact_id = "new"


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_source_type_count(self):
        assert len(ArtifactSourceType) == 8

    def test_format_count(self):
        assert len(ArtifactFormat) == 19

    def test_parse_status_count(self):
        assert len(ArtifactParseStatus) == 7

    def test_semantic_type_count(self):
        assert len(ArtifactSemanticType) == 11
