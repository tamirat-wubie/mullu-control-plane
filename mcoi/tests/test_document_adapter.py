"""Tests for the local document adapter.

Covers: file loading, fingerprinting determinism, path handling,
unsupported extensions, and missing files.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from mcoi_runtime.adapters.document_adapter import (
    DocumentLoadStatus,
    LocalDocumentAdapter,
)
from mcoi_runtime.contracts.document import DocumentFormat
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@pytest.fixture
def adapter() -> LocalDocumentAdapter:
    return LocalDocumentAdapter()


# --- File loading tests ---


class TestLoadFile:
    def test_load_text_file(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        # tmp_path is a pathlib.Path from pytest
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "sample.txt"
        p.write_text("hello world", encoding="utf-8")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document is not None
        assert result.document.text == "hello world"
        assert result.document.format is DocumentFormat.TEXT

    def test_load_markdown_file(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "readme.md"
        p.write_text("# Title\nContent", encoding="utf-8")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document is not None
        assert result.document.format is DocumentFormat.MARKDOWN

    def test_load_json_file(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "data.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document is not None
        assert result.document.format is DocumentFormat.JSON

    def test_load_markdown_extension(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "doc.markdown"
        p.write_text("content", encoding="utf-8")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.LOADED
        assert result.document is not None
        assert result.document.format is DocumentFormat.MARKDOWN


# --- Missing file tests ---


class TestMissingFile:
    def test_not_found_returns_status(self, adapter: LocalDocumentAdapter) -> None:
        result = adapter.load("/nonexistent/path/to/file.txt")
        assert result.status is DocumentLoadStatus.NOT_FOUND
        assert result.document is None
        assert result.error_message == "file not found"

    def test_empty_path_raises(self, adapter: LocalDocumentAdapter) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            adapter.load("")

    def test_whitespace_path_raises(self, adapter: LocalDocumentAdapter) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            adapter.load("   ")


# --- Unsupported extension tests ---


class TestUnsupportedExtension:
    def test_unsupported_extension_returns_status(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "image.png"
        p.write_bytes(b"\x89PNG")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.UNSUPPORTED
        assert result.document is None
        assert "unsupported extension" in (result.error_message or "")

    def test_no_extension_unsupported(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "Makefile"
        p.write_text("all: build", encoding="utf-8")
        result = adapter.load(str(p))
        assert result.status is DocumentLoadStatus.UNSUPPORTED


class TestReadErrors:
    def test_read_error_is_bounded(self, adapter: LocalDocumentAdapter, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        import pathlib

        p = pathlib.Path(str(tmp_path)) / "sample.txt"
        p.write_text("hello world", encoding="utf-8")
        original_read_text = pathlib.Path.read_text

        def crashing_read_text(self: pathlib.Path, *args, **kwargs):
            if self == p:
                raise OSError("secret document failure")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "read_text", crashing_read_text)

        result = adapter.load(str(p))

        assert result.status is DocumentLoadStatus.READ_ERROR
        assert result.document is None
        assert result.error_message == "read error (OSError)"
        assert "secret document failure" not in (result.error_message or "")


# --- Fingerprinting tests ---


class TestFingerprinting:
    def test_fingerprint_deterministic(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "stable.txt"
        p.write_text("deterministic content", encoding="utf-8")
        r1 = adapter.load(str(p))
        r2 = adapter.load(str(p))
        assert r1.document is not None
        assert r2.document is not None
        assert r1.document.fingerprint.content_hash == r2.document.fingerprint.content_hash
        assert r1.document.fingerprint.byte_length == r2.document.fingerprint.byte_length

    def test_different_content_different_fingerprint(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p1 = pathlib.Path(str(tmp_path)) / "a.txt"
        p2 = pathlib.Path(str(tmp_path)) / "b.txt"
        p1.write_text("content A", encoding="utf-8")
        p2.write_text("content B", encoding="utf-8")
        r1 = adapter.load(str(p1))
        r2 = adapter.load(str(p2))
        assert r1.document is not None
        assert r2.document is not None
        assert r1.document.fingerprint.content_hash != r2.document.fingerprint.content_hash

    def test_fingerprint_byte_length(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "sized.txt"
        content = "hello"
        p.write_text(content, encoding="utf-8")
        result = adapter.load(str(p))
        assert result.document is not None
        assert result.document.fingerprint.byte_length == len(content.encode("utf-8"))

    def test_fingerprint_line_count(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "lines.txt"
        content = "line1\nline2\nline3"
        p.write_text(content, encoding="utf-8")
        result = adapter.load(str(p))
        assert result.document is not None
        # line_count = newlines + 1 if content is non-empty
        assert result.document.fingerprint.line_count == 3


# --- Path handling tests ---


class TestPathHandling:
    def test_source_path_preserved(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "path_test.txt"
        p.write_text("content", encoding="utf-8")
        result = adapter.load(str(p))
        assert result.document is not None
        assert result.document.source_path == str(p)

    def test_document_id_stable(self, adapter: LocalDocumentAdapter, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "id_test.txt"
        p.write_text("content", encoding="utf-8")
        r1 = adapter.load(str(p))
        r2 = adapter.load(str(p))
        assert r1.document is not None
        assert r2.document is not None
        assert r1.document.document_id == r2.document.document_id
