"""Golden scenario tests for document automation.

Proves end-to-end document ingest, fingerprint, extraction, verification,
and adapter behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.document import (
    DocumentContent,
    DocumentFingerprint,
    DocumentFormat,
    DocumentVerificationStatus,
    ExtractionStatus,
)
from mcoi_runtime.core.document import (
    compute_fingerprint,
    detect_format,
    extract_fields,
    extract_json_fields,
    ingest_document,
    verify_extraction,
)
from mcoi_runtime.adapters.document_adapter import (
    DocumentLoadStatus,
    LocalDocumentAdapter,
)


# --- Fingerprinting ---


class TestFingerprinting:
    def test_deterministic_for_same_content(self):
        fp1 = compute_fingerprint("doc-1", "hello world")
        fp2 = compute_fingerprint("doc-1", "hello world")
        assert fp1.content_hash == fp2.content_hash
        assert fp1.byte_length == fp2.byte_length
        assert fp1.line_count == fp2.line_count

    def test_different_content_different_hash(self):
        fp1 = compute_fingerprint("doc-1", "hello")
        fp2 = compute_fingerprint("doc-1", "world")
        assert fp1.content_hash != fp2.content_hash

    def test_byte_length_correct(self):
        fp = compute_fingerprint("doc-1", "abc")
        assert fp.byte_length == 3

    def test_line_count_correct(self):
        fp = compute_fingerprint("doc-1", "line1\nline2\nline3")
        assert fp.line_count == 3

    def test_empty_content(self):
        fp = compute_fingerprint("doc-1", "")
        assert fp.byte_length == 0
        assert fp.line_count == 0


# --- Format detection ---


class TestFormatDetection:
    def test_txt(self):
        assert detect_format("file.txt") is DocumentFormat.TEXT

    def test_md(self):
        assert detect_format("README.md") is DocumentFormat.MARKDOWN

    def test_markdown(self):
        assert detect_format("notes.markdown") is DocumentFormat.MARKDOWN

    def test_json(self):
        assert detect_format("config.json") is DocumentFormat.JSON

    def test_unknown(self):
        assert detect_format("file.pdf") is DocumentFormat.UNKNOWN

    def test_case_insensitive(self):
        assert detect_format("FILE.TXT") is DocumentFormat.TEXT


# --- Ingest ---


class TestIngest:
    def test_ingest_produces_content_with_fingerprint(self):
        doc = ingest_document("doc-1", "test.txt", "hello world")
        assert doc.document_id == "doc-1"
        assert doc.format is DocumentFormat.TEXT
        assert doc.text == "hello world"
        assert doc.fingerprint.content_hash is not None
        assert doc.fingerprint.byte_length == 11


# --- Field extraction ---


class TestFieldExtraction:
    def test_extract_all_fields(self):
        doc = ingest_document("doc-1", "test.txt", "hello world")
        result = extract_fields(doc, {
            "greeting": lambda text: "hello" if "hello" in text else None,
            "subject": lambda text: "world" if "world" in text else None,
        })
        assert result.extracted_count == 2
        assert result.missing_count == 0
        assert result.malformed_count == 0

    def test_extract_missing_field(self):
        doc = ingest_document("doc-1", "test.txt", "hello world")
        result = extract_fields(doc, {
            "absent": lambda text: None,
        })
        assert result.extracted_count == 0
        assert result.missing_count == 1

    def test_extract_malformed_field(self):
        doc = ingest_document("doc-1", "test.txt", "hello world")
        result = extract_fields(doc, {
            "bad": lambda text: 1 / 0,  # Raises ZeroDivisionError
        })
        assert result.extracted_count == 0
        assert result.malformed_count == 1

    def test_extract_none_extractor_means_missing(self):
        doc = ingest_document("doc-1", "test.txt", "hello")
        result = extract_fields(doc, {"field": None})
        assert result.missing_count == 1

    def test_fields_are_sorted_by_name(self):
        doc = ingest_document("doc-1", "test.txt", "x")
        result = extract_fields(doc, {
            "z_field": lambda t: "z",
            "a_field": lambda t: "a",
        })
        assert result.fields[0].field_name == "a_field"
        assert result.fields[1].field_name == "z_field"


# --- JSON extraction ---


class TestJsonExtraction:
    def test_extract_json_fields_success(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Alice", "age": 30}))
        result = extract_json_fields(doc, ("name", "age"))
        assert result.extracted_count == 2
        assert result.missing_count == 0

    def test_extract_json_fields_missing(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Alice"}))
        result = extract_json_fields(doc, ("name", "email"))
        assert result.extracted_count == 1
        assert result.missing_count == 1

    def test_extract_json_malformed_json(self):
        doc = ingest_document("doc-1", "data.json", "not json!!")
        result = extract_json_fields(doc, ("name",))
        assert result.malformed_count == 1

    def test_extract_json_wrong_format(self):
        doc = ingest_document("doc-1", "data.txt", '{"name": "Alice"}')
        result = extract_json_fields(doc, ("name",))
        assert result.malformed_count == 1  # Not JSON format


# --- Verification ---


class TestVerification:
    def test_all_fields_match(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Alice", "age": 30}))
        extraction = extract_json_fields(doc, ("name", "age"))
        result = verify_extraction(extraction, ("name", "age"))
        assert result.status is DocumentVerificationStatus.PASS
        assert len(result.matched_fields) == 2
        assert len(result.missing_fields) == 0

    def test_missing_field_fails(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Alice"}))
        extraction = extract_json_fields(doc, ("name", "email"))
        result = verify_extraction(extraction, ("name", "email"))
        assert result.status is DocumentVerificationStatus.PARTIAL
        assert "email" in result.missing_fields
        assert result.reason == "missing required fields"
        assert "email" not in result.reason

    def test_all_fields_missing(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({}))
        extraction = extract_json_fields(doc, ("x", "y"))
        result = verify_extraction(extraction, ("x", "y"))
        assert result.status is DocumentVerificationStatus.FAIL

    def test_value_mismatch(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Bob"}))
        extraction = extract_json_fields(doc, ("name",))
        result = verify_extraction(
            extraction, ("name",), expected_values={"name": "Alice"},
        )
        assert result.status is DocumentVerificationStatus.FAIL
        assert "name" in result.mismatched_fields
        assert result.reason == "field values did not match expectations"
        assert "name" not in result.reason

    def test_missing_and_mismatch_reason_is_combined_and_bounded(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Bob"}))
        extraction = extract_json_fields(doc, ("name", "email"))
        result = verify_extraction(
            extraction,
            ("name", "email"),
            expected_values={"name": "Alice"},
        )
        assert result.status is DocumentVerificationStatus.FAIL
        assert result.reason == "missing required fields; field values did not match expectations"
        assert "name" not in result.reason
        assert "email" not in result.reason

    def test_pass_with_expected_values(self):
        doc = ingest_document("doc-1", "data.json", json.dumps({"name": "Alice"}))
        extraction = extract_json_fields(doc, ("name",))
        result = verify_extraction(
            extraction, ("name",), expected_values={"name": "Alice"},
        )
        assert result.status is DocumentVerificationStatus.PASS


# --- Local document adapter ---


class TestLocalDocumentAdapter:
    def test_load_txt(self, tmp_path: Path):
        (tmp_path / "test.txt").write_text("hello world", encoding="utf-8")
        adapter = LocalDocumentAdapter()
        result = adapter.load(str(tmp_path / "test.txt"))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document is not None
        assert result.document.format is DocumentFormat.TEXT
        assert result.document.text == "hello world"

    def test_load_json(self, tmp_path: Path):
        (tmp_path / "data.json").write_text('{"key": "val"}', encoding="utf-8")
        adapter = LocalDocumentAdapter()
        result = adapter.load(str(tmp_path / "data.json"))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document.format is DocumentFormat.JSON

    def test_load_markdown(self, tmp_path: Path):
        (tmp_path / "notes.md").write_text("# Title", encoding="utf-8")
        adapter = LocalDocumentAdapter()
        result = adapter.load(str(tmp_path / "notes.md"))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document.format is DocumentFormat.MARKDOWN

    def test_not_found(self):
        adapter = LocalDocumentAdapter()
        result = adapter.load("/nonexistent/path/file.txt")
        assert result.status is DocumentLoadStatus.NOT_FOUND

    def test_unsupported_extension(self, tmp_path: Path):
        (tmp_path / "file.pdf").write_text("data", encoding="utf-8")
        adapter = LocalDocumentAdapter()
        result = adapter.load(str(tmp_path / "file.pdf"))
        assert result.status is DocumentLoadStatus.UNSUPPORTED

    def test_end_to_end_ingest_extract_verify(self, tmp_path: Path):
        """Golden scenario: load JSON file -> extract fields -> verify."""
        data = {"name": "Alice", "role": "engineer", "level": 3}
        (tmp_path / "profile.json").write_text(json.dumps(data), encoding="utf-8")

        adapter = LocalDocumentAdapter()
        load = adapter.load(str(tmp_path / "profile.json"))
        assert load.status is DocumentLoadStatus.LOADED

        extraction = extract_json_fields(load.document, ("name", "role", "level"))
        assert extraction.extracted_count == 3

        verification = verify_extraction(
            extraction,
            ("name", "role", "level"),
            expected_values={"name": "Alice", "level": 3},
        )
        assert verification.status is DocumentVerificationStatus.PASS
        assert len(verification.matched_fields) == 3
