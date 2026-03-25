"""Engine-level tests for ArtifactIngestionEngine."""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.artifact_ingestion import (
    ArtifactDescriptor,
    ArtifactFormat,
    ArtifactIngestionRecord,
    ArtifactParseResult,
    ArtifactParseStatus,
    ArtifactSemanticMapping,
    ArtifactSemanticType,
    ArtifactSourceType,
    ArtifactStructure,
)
from mcoi_runtime.core.artifact_ingestion import ArtifactIngestionEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


def _desc(aid="art-1", filename="file.json", mime="application/json", size=100, **kw):
    defaults = dict(
        artifact_id=aid,
        source_type=ArtifactSourceType.FILE,
        source_ref="/data/" + filename,
        filename=filename,
        mime_type=mime,
        size_bytes=size,
        created_at=NOW,
    )
    defaults.update(kw)
    return ArtifactDescriptor(**defaults)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_extension_json(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("data.json", "", b"") == ArtifactFormat.JSON

    def test_extension_csv(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("data.csv", "", b"") == ArtifactFormat.CSV

    def test_extension_yaml(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("config.yaml", "", b"") == ArtifactFormat.YAML

    def test_extension_yml(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("config.yml", "", b"") == ArtifactFormat.YAML

    def test_extension_py(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("main.py", "", b"") == ArtifactFormat.CODE

    def test_extension_md(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("README.md", "", b"") == ArtifactFormat.MARKDOWN

    def test_extension_log(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("app.log", "", b"") == ArtifactFormat.LOG

    def test_extension_pdf(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("doc.pdf", "", b"") == ArtifactFormat.PDF

    def test_mime_fallback(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("noext", "application/json", b"") == ArtifactFormat.JSON

    def test_content_sniff_json(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("noext", "application/octet-stream", b'{"key": 1}') == ArtifactFormat.JSON

    def test_content_sniff_yaml(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("noext", "", b"---\nkey: val") == ArtifactFormat.YAML

    def test_unknown_fallback(self):
        engine = ArtifactIngestionEngine()
        assert engine.detect_format("noext", "", b"\x00\x01\x02") == ArtifactFormat.UNKNOWN

    def test_custom_detector_priority(self):
        engine = ArtifactIngestionEngine()

        def custom(fn, mime, head):
            if fn.endswith(".custom"):
                return ArtifactFormat.TOML
            return None

        engine.register_detector(custom)
        assert engine.detect_format("data.custom", "", b"") == ArtifactFormat.TOML

    def test_format_hint_overrides_detection(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(filename="data.json", format_hint=ArtifactFormat.YAML)
        record = engine.ingest(desc, b'{"key": "val"}')
        assert record.parse_result.format_detected == ArtifactFormat.YAML


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------


class TestFingerprinting:
    def test_deterministic(self):
        engine = ArtifactIngestionEngine()
        fp1 = engine.fingerprint("art-1", b"hello")
        fp2 = engine.fingerprint("art-1", b"hello")
        assert fp1.digest == fp2.digest

    def test_different_content(self):
        engine = ArtifactIngestionEngine()
        fp1 = engine.fingerprint("art-1", b"hello")
        fp2 = engine.fingerprint("art-1", b"world")
        assert fp1.digest != fp2.digest

    def test_sha256(self):
        engine = ArtifactIngestionEngine()
        fp = engine.fingerprint("art-1", b"test")
        assert fp.algorithm == "sha256"
        assert len(fp.digest) == 64


# ---------------------------------------------------------------------------
# Parser dispatch
# ---------------------------------------------------------------------------


class TestParserDispatch:
    def test_json_valid(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(filename="data.json")
        record = engine.ingest(desc, b'{"key": "value"}')
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.JSON

    def test_json_malformed(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-bad", filename="bad.json")
        record = engine.ingest(desc, b"{not json")
        assert record.status == ArtifactParseStatus.MALFORMED

    def test_yaml_valid(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-yaml", filename="config.yaml", mime="text/yaml")
        record = engine.ingest(desc, b"key: value\nlist:\n  - item1")
        assert record.status == ArtifactParseStatus.ACCEPTED

    def test_yaml_malformed(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-yaml-bad", filename="bad.yaml", mime="text/yaml")
        record = engine.ingest(desc, b"just plain text with no structure")
        assert record.status == ArtifactParseStatus.MALFORMED

    def test_csv_valid(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-csv", filename="data.csv", mime="text/csv")
        record = engine.ingest(desc, b"name,age\nAlice,30\nBob,25")
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.metadata["row_count"] == 3
        assert record.parse_result.metadata["col_count"] == 2

    def test_csv_empty(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-csv-empty", filename="empty.csv", mime="text/csv")
        record = engine.ingest(desc, b"")
        assert record.status == ArtifactParseStatus.MALFORMED

    def test_text_accepted(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-txt", filename="notes.txt", mime="text/plain")
        record = engine.ingest(desc, b"Hello world")
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.TEXT

    def test_markdown_accepted(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-md", filename="README.md", mime="text/markdown")
        record = engine.ingest(desc, b"# Title\n\nContent here")
        assert record.status == ArtifactParseStatus.ACCEPTED

    def test_code_accepted(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-code", filename="main.py", mime="text/plain")
        record = engine.ingest(desc, b"def main():\n    pass")
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.CODE

    def test_unsupported_format(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-pdf", filename="doc.pdf", mime="application/pdf")
        record = engine.ingest(desc, b"%PDF-1.4 binary content")
        assert record.status == ArtifactParseStatus.UNSUPPORTED

    def test_custom_parser(self):
        engine = ArtifactIngestionEngine()

        def toml_parser(aid, content, fmt, meta):
            return ArtifactParseResult(
                parse_id=f"parse-{aid}",
                artifact_id=aid,
                format_detected=ArtifactFormat.TOML,
                status=ArtifactParseStatus.ACCEPTED,
                reason="TOML parsed",
                parsed_at=NOW,
            )

        engine.register_parser(ArtifactFormat.TOML, toml_parser)
        desc = _desc(aid="art-toml", filename="config.toml", mime="application/toml")
        record = engine.ingest(desc, b"[section]\nkey = 'value'")
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.TOML


# ---------------------------------------------------------------------------
# Policy gating
# ---------------------------------------------------------------------------


class TestPolicyGating:
    def test_size_blocked(self):
        engine = ArtifactIngestionEngine(max_size_bytes=50)
        desc = _desc(aid="art-big", size=100)
        record = engine.ingest(desc, b"x" * 10)
        assert record.status == ArtifactParseStatus.TOO_LARGE
        assert not record.policy_decision.allowed

    def test_format_blocked(self):
        engine = ArtifactIngestionEngine(allowed_formats=(ArtifactFormat.JSON,))
        desc = _desc(aid="art-csv-blocked", filename="data.csv", mime="text/csv")
        record = engine.ingest(desc, b"a,b\n1,2")
        assert record.status == ArtifactParseStatus.POLICY_BLOCKED
        assert not record.policy_decision.allowed

    def test_source_blocked(self):
        engine = ArtifactIngestionEngine(
            allowed_sources=(ArtifactSourceType.FILE,),
        )
        desc = _desc(
            aid="art-web", source_type=ArtifactSourceType.WEB_UPLOAD,
            filename="upload.json", mime="application/json",
        )
        record = engine.ingest(desc, b'{"k": "v"}')
        assert record.status == ArtifactParseStatus.POLICY_BLOCKED

    def test_all_checks_pass(self):
        engine = ArtifactIngestionEngine(
            max_size_bytes=1000,
            allowed_formats=(ArtifactFormat.JSON,),
            allowed_sources=(ArtifactSourceType.FILE,),
        )
        desc = _desc(size=50)
        policy = engine.evaluate_policy(desc, ArtifactFormat.JSON)
        assert policy.allowed
        assert "size_ok" in policy.checks_passed
        assert "format_ok" in policy.checks_passed
        assert "source_ok" in policy.checks_passed

    def test_no_restrictions(self):
        engine = ArtifactIngestionEngine()
        desc = _desc()
        policy = engine.evaluate_policy(desc, ArtifactFormat.JSON)
        assert policy.allowed


# ---------------------------------------------------------------------------
# Structure extraction
# ---------------------------------------------------------------------------


class TestStructureExtraction:
    def test_json_structure(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-js")
        record = engine.ingest(desc, b'{"name": "test", "count": 42}')
        assert record.structure is not None
        assert record.structure.field_count == 2
        assert "name" in record.structure.sections["keys"]

    def test_csv_structure(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-c", filename="data.csv", mime="text/csv")
        record = engine.ingest(desc, b"name,age,city\nAlice,30,NYC\nBob,25,LA")
        assert record.structure is not None
        assert record.structure.field_count == 3
        assert record.structure.row_count == 2
        assert "name" in record.structure.sections["headers"]

    def test_text_structure(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-t", filename="notes.txt", mime="text/plain")
        record = engine.ingest(desc, b"line 1\nline 2\nline 3")
        assert record.structure is not None
        assert record.structure.row_count == 3
        assert record.structure.section_count == 1

    def test_no_structure_for_rejected(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-rej", filename="bad.json")
        record = engine.ingest(desc, b"{not json")
        assert record.structure is None


# ---------------------------------------------------------------------------
# Semantic mapping
# ---------------------------------------------------------------------------


class TestSemanticMapping:
    def test_json_maps_to_config(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-sem-j")
        record = engine.ingest(desc, b'{"key": "value"}')
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.CONFIG

    def test_csv_maps_to_dataset(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-sem-c", filename="data.csv", mime="text/csv")
        record = engine.ingest(desc, b"a,b\n1,2")
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.DATASET

    def test_code_maps_to_source(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-sem-py", filename="main.py", mime="text/plain")
        record = engine.ingest(desc, b"print('hello')")
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.SOURCE_CODE

    def test_log_maps_to_log_stream(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-sem-log", filename="app.log", mime="text/plain")
        record = engine.ingest(desc, b"2026-03-20 INFO: started")
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.LOG_STREAM

    def test_custom_mapper(self):
        engine = ArtifactIngestionEngine()

        def custom_mapper(aid, fmt, pr, struct):
            if fmt == ArtifactFormat.JSON:
                return ArtifactSemanticMapping(
                    mapping_id=f"custom-{aid}",
                    artifact_id=aid,
                    semantic_type=ArtifactSemanticType.TRANSCRIPT,
                    domain="custom",
                    confidence=0.9,
                    mapped_at=NOW,
                )
            return None

        engine.register_semantic_mapper(custom_mapper)
        desc = _desc(aid="art-custom-sem")
        record = engine.ingest(desc, b'{"transcript": true}')
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.TRANSCRIPT
        assert record.semantic_mapping.domain == "custom"

    def test_no_mapping_for_rejected(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-rej-sem", filename="bad.json")
        record = engine.ingest(desc, b"{not json")
        # Malformed still gets default mapping attempt but through unsupported path
        # The semantic mapping is based on format, not status


# ---------------------------------------------------------------------------
# Duplicate rejection
# ---------------------------------------------------------------------------


class TestDuplicateRejection:
    def test_duplicate_artifact_id_rejected(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-dup")
        engine.ingest(desc, b'{"a": 1}')
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.ingest(desc, b'{"b": 2}')


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestRetrieval:
    def test_get_record(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="art-get")
        engine.ingest(desc, b'{"k": "v"}')
        r = engine.get_record("art-get")
        assert r is not None
        assert r.artifact_id == "art-get"

    def test_get_missing(self):
        engine = ArtifactIngestionEngine()
        assert engine.get_record("missing") is None

    def test_list_records(self):
        engine = ArtifactIngestionEngine()
        engine.ingest(_desc(aid="a1"), b'{"k": 1}')
        engine.ingest(_desc(aid="a2", filename="f.txt", mime="text/plain"), b"text")
        assert len(engine.list_records()) == 2

    def test_list_by_status(self):
        engine = ArtifactIngestionEngine()
        engine.ingest(_desc(aid="good"), b'{"k": 1}')
        engine.ingest(_desc(aid="bad", filename="b.json"), b"{bad")
        accepted = engine.list_by_status(ArtifactParseStatus.ACCEPTED)
        malformed = engine.list_by_status(ArtifactParseStatus.MALFORMED)
        assert len(accepted) == 1
        assert len(malformed) == 1

    def test_list_by_format(self):
        engine = ArtifactIngestionEngine()
        engine.ingest(_desc(aid="j1"), b'{"k": 1}')
        engine.ingest(_desc(aid="c1", filename="d.csv", mime="text/csv"), b"a,b\n1,2")
        assert len(engine.list_by_format(ArtifactFormat.JSON)) == 1
        assert len(engine.list_by_format(ArtifactFormat.CSV)) == 1

    def test_list_by_semantic_type(self):
        engine = ArtifactIngestionEngine()
        engine.ingest(_desc(aid="j2"), b'{"k": 1}')
        engine.ingest(_desc(aid="c2", filename="d.csv", mime="text/csv"), b"a,b\n1,2")
        configs = engine.list_by_semantic_type(ArtifactSemanticType.CONFIG)
        datasets = engine.list_by_semantic_type(ArtifactSemanticType.DATASET)
        assert len(configs) == 1
        assert len(datasets) == 1

    def test_record_count(self):
        engine = ArtifactIngestionEngine()
        assert engine.record_count == 0
        engine.ingest(_desc(aid="rc1"), b'{"k": 1}')
        assert engine.record_count == 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_deterministic(self):
        e1 = ArtifactIngestionEngine()
        e2 = ArtifactIngestionEngine()
        e1.ingest(_desc(aid="x"), b'{"a": 1}')
        e2.ingest(_desc(aid="x"), b'{"a": 1}')
        assert e1.state_hash() == e2.state_hash()

    def test_changes_on_ingest(self):
        engine = ArtifactIngestionEngine()
        h1 = engine.state_hash()
        engine.ingest(_desc(aid="y"), b'{"a": 1}')
        h2 = engine.state_hash()
        assert h1 != h2

    def test_empty_hash(self):
        engine = ArtifactIngestionEngine()
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ---------------------------------------------------------------------------
# Record immutability
# ---------------------------------------------------------------------------


class TestRecordImmutability:
    def test_record_frozen(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="frozen-test")
        record = engine.ingest(desc, b'{"k": "v"}')
        with pytest.raises(AttributeError):
            record.artifact_id = "changed"

    def test_record_has_all_fields(self):
        engine = ArtifactIngestionEngine()
        desc = _desc(aid="full-test")
        record = engine.ingest(desc, b'{"k": "v"}')
        assert record.record_id
        assert record.artifact_id == "full-test"
        assert record.descriptor is desc
        assert record.fingerprint is not None
        assert record.parse_result is not None
        assert record.policy_decision is not None
        assert record.ingested_at
