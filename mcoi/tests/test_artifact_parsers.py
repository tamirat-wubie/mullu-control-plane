"""Tests for ArtifactParserRegistry and all test parser families.

Covers registration, retrieval, listing, file selection, parsing,
auto-parsing, health checks, state hashing, and per-family parser
behaviour.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.artifact_parsers import (
    ArchiveTestParser,
    ArtifactParser,
    ArtifactParserRegistry,
    AudioTestParser,
    DocxTestParser,
    ImageTestParser,
    PdfTestParser,
    PptxTestParser,
    RepoTestParser,
    XlsxTestParser,
    register_all_test_parsers,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.artifact_parser import (
    ArtifactParserDescriptor,
    NormalizedParseOutput,
    ParseOutputKind,
    ParserCapabilityManifest,
    ParserFamily,
    ParserHealthReport,
    ParserStatus,
)


# ---- fixtures ---------------------------------------------------------------


@pytest.fixture()
def registry() -> ArtifactParserRegistry:
    return ArtifactParserRegistry()


@pytest.fixture()
def full_registry() -> ArtifactParserRegistry:
    reg = ArtifactParserRegistry()
    register_all_test_parsers(reg)
    return reg


# ---- registration -----------------------------------------------------------


class TestRegistration:
    def test_register_parser(self, registry: ArtifactParserRegistry) -> None:
        parser = PdfTestParser()
        desc = registry.register(parser)
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.parser_id == parser.parser_id()
        assert registry.parser_count == 1

    def test_reject_duplicate(self, registry: ArtifactParserRegistry) -> None:
        registry.register(PdfTestParser())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered") as exc_info:
            registry.register(PdfTestParser())
        assert "test-pdf" not in str(exc_info.value)

    def test_reject_non_artifact_parser(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="must be an ArtifactParser"):
            registry.register("not-a-parser")  # type: ignore[arg-type]

    def test_reject_plain_object(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="must be an ArtifactParser"):
            registry.register(42)  # type: ignore[arg-type]


# ---- retrieval --------------------------------------------------------------


class TestRetrieval:
    def test_get_parser(self, full_registry: ArtifactParserRegistry) -> None:
        parser = full_registry.get_parser("test-pdf")
        assert isinstance(parser, PdfTestParser)

    def test_get_descriptor(self, full_registry: ArtifactParserRegistry) -> None:
        desc = full_registry.get_descriptor("test-pdf")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.parser_id == "test-pdf"

    def test_get_manifest(self, full_registry: ArtifactParserRegistry) -> None:
        manifest = full_registry.get_manifest("test-pdf")
        assert isinstance(manifest, ParserCapabilityManifest)
        assert manifest.parser_id == "test-pdf"

    def test_missing_parser_raises(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_parser("nonexistent")
        assert "nonexistent" not in str(exc_info.value)

    def test_missing_descriptor_raises(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_descriptor("nonexistent")
        assert "nonexistent" not in str(exc_info.value)

    def test_missing_manifest_raises(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_manifest("nonexistent")
        assert "nonexistent" not in str(exc_info.value)


# ---- listing ----------------------------------------------------------------


class TestListing:
    def test_list_parsers_all(self, full_registry: ArtifactParserRegistry) -> None:
        all_descs = full_registry.list_parsers()
        assert len(all_descs) == 8
        assert all(isinstance(d, ArtifactParserDescriptor) for d in all_descs)

    def test_list_parsers_by_family(self, full_registry: ArtifactParserRegistry) -> None:
        doc_descs = full_registry.list_parsers(family=ParserFamily.DOCUMENT)
        assert len(doc_descs) == 2  # PdfTestParser + DocxTestParser
        assert all(d.family == ParserFamily.DOCUMENT for d in doc_descs)

    def test_list_parsers_by_status(self, full_registry: ArtifactParserRegistry) -> None:
        available = full_registry.list_parsers(status=ParserStatus.AVAILABLE)
        assert len(available) == 8  # all test parsers start AVAILABLE

    def test_list_parsers_by_status_empty(self, full_registry: ArtifactParserRegistry) -> None:
        disabled = full_registry.list_parsers(status=ParserStatus.DISABLED)
        assert len(disabled) == 0

    def test_list_available(self, full_registry: ArtifactParserRegistry) -> None:
        available = full_registry.list_available()
        assert len(available) == 8
        for d in available:
            assert d.status in (ParserStatus.AVAILABLE, ParserStatus.DEGRADED)


# ---- selection --------------------------------------------------------------


class TestSelection:
    def test_select_for_pdf(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("report.pdf")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-pdf" in parser_ids

    def test_select_for_csv(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("data.csv")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-xlsx" in parser_ids

    def test_select_for_docx(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("document.docx")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-docx" in parser_ids

    def test_select_for_xlsx(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("spreadsheet.xlsx")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-xlsx" in parser_ids

    def test_select_for_pptx(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("slides.pptx")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-pptx" in parser_ids

    def test_select_for_png(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("photo.png")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-image" in parser_ids

    def test_select_for_mp3(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("audio.mp3")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-audio" in parser_ids

    def test_select_for_zip(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("archive.zip")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-archive" in parser_ids

    def test_select_for_patch(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("fix.patch")
        assert len(parsers) >= 1
        parser_ids = [p.parser_id() for p in parsers]
        assert "test-repo" in parser_ids

    def test_select_for_unknown_returns_empty(self, full_registry: ArtifactParserRegistry) -> None:
        parsers = full_registry.select_for_file("mystery.xyz123")
        assert parsers == ()

    def test_select_empty_registry(self, registry: ArtifactParserRegistry) -> None:
        parsers = registry.select_for_file("report.pdf")
        assert parsers == ()


# ---- parsing ----------------------------------------------------------------


class TestParsing:
    def test_parse_via_registry(self, full_registry: ArtifactParserRegistry) -> None:
        content = b"Hello world this is a test document."
        result = full_registry.parse("test-pdf", "art-001", "doc.pdf", content)
        assert isinstance(result, NormalizedParseOutput)
        assert result.parser_id == "test-pdf"
        assert result.artifact_id == "art-001"

    def test_parse_missing_parser_raises(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            registry.parse("nonexistent", "art-001", "doc.pdf", b"data")

    def test_auto_parse_selects_best(self, full_registry: ArtifactParserRegistry) -> None:
        content = b"col1,col2\nval1,val2\n"
        result = full_registry.auto_parse("art-002", "data.csv", content)
        assert result is not None
        assert isinstance(result, NormalizedParseOutput)
        assert result.artifact_id == "art-002"

    def test_auto_parse_pdf(self, full_registry: ArtifactParserRegistry) -> None:
        content = b"%PDF-1.4 fake pdf content here"
        result = full_registry.auto_parse("art-003", "report.pdf", content)
        assert result is not None
        assert result.parser_id == "test-pdf"
        assert "PDF content extracted" in result.text_content

    def test_auto_parse_no_match_returns_none(self, full_registry: ArtifactParserRegistry) -> None:
        result = full_registry.auto_parse("art-004", "mystery.xyz123", b"data")
        assert result is None

    def test_parse_tracks_count(self, registry: ArtifactParserRegistry) -> None:
        parser = PdfTestParser()
        registry.register(parser)
        registry.parse("test-pdf", "a1", "f1.pdf", b"data1")
        registry.parse("test-pdf", "a2", "f2.pdf", b"data2")
        report = registry.health_check("test-pdf")
        assert report.artifacts_parsed == 2


# ---- health -----------------------------------------------------------------


class TestHealth:
    def test_health_check_single(self, full_registry: ArtifactParserRegistry) -> None:
        report = full_registry.health_check("test-pdf")
        assert isinstance(report, ParserHealthReport)
        assert report.parser_id == "test-pdf"
        assert report.status == ParserStatus.AVAILABLE
        assert report.reliability_score == 0.95

    def test_health_check_missing_raises(self, registry: ArtifactParserRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            registry.health_check("nonexistent")

    def test_health_check_all(self, full_registry: ArtifactParserRegistry) -> None:
        reports = full_registry.health_check_all()
        assert len(reports) == 8
        parser_ids = {r.parser_id for r in reports}
        assert "test-pdf" in parser_ids
        assert "test-xlsx" in parser_ids
        assert all(isinstance(r, ParserHealthReport) for r in reports)

    def test_health_check_all_empty(self, registry: ArtifactParserRegistry) -> None:
        reports = registry.health_check_all()
        assert reports == ()


# ---- state hash -------------------------------------------------------------


class TestStateHash:
    def test_state_hash_deterministic(self, full_registry: ArtifactParserRegistry) -> None:
        h1 = full_registry.state_hash()
        h2 = full_registry.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_register(self, registry: ArtifactParserRegistry) -> None:
        h_empty = registry.state_hash()
        registry.register(PdfTestParser())
        h_one = registry.state_hash()
        assert h_empty != h_one
        registry.register(DocxTestParser())
        h_two = registry.state_hash()
        assert h_one != h_two

    def test_state_hash_length_16(self, full_registry: ArtifactParserRegistry) -> None:
        h = full_registry.state_hash()
        assert len(h) == 64
        # Should be valid hex
        int(h, 16)

    def test_state_hash_empty_registry(self, registry: ArtifactParserRegistry) -> None:
        h = registry.state_hash()
        assert len(h) == 64


# ---- register_all_test_parsers ----------------------------------------------


class TestRegisterAll:
    def test_registers_eight(self) -> None:
        reg = ArtifactParserRegistry()
        descs = register_all_test_parsers(reg)
        assert len(descs) == 8
        assert reg.parser_count == 8

    def test_each_produces_valid_descriptor(self) -> None:
        reg = ArtifactParserRegistry()
        descs = register_all_test_parsers(reg)
        for desc in descs:
            assert isinstance(desc, ArtifactParserDescriptor)
            assert desc.parser_id
            assert desc.name
            assert isinstance(desc.family, ParserFamily)
            assert desc.status == ParserStatus.AVAILABLE
            assert desc.version == "1.0.0"

    def test_each_produces_valid_manifest(self) -> None:
        reg = ArtifactParserRegistry()
        register_all_test_parsers(reg)
        for desc in reg.list_parsers():
            manifest = reg.get_manifest(desc.parser_id)
            assert isinstance(manifest, ParserCapabilityManifest)
            assert manifest.parser_id == desc.parser_id
            assert manifest.manifest_id
            assert isinstance(manifest.family, ParserFamily)
            assert manifest.reliability_score == 0.95


# ---- per-family parser tests ------------------------------------------------


class TestPdfTestParser:
    def test_family(self) -> None:
        assert PdfTestParser().family() == ParserFamily.DOCUMENT

    def test_parser_id(self) -> None:
        assert PdfTestParser().parser_id() == "test-pdf"

    def test_custom_id(self) -> None:
        p = PdfTestParser(parser_id="custom-pdf")
        assert p.parser_id() == "custom-pdf"

    def test_can_parse_pdf(self) -> None:
        assert PdfTestParser().can_parse("file.pdf", "", 0) is True

    def test_cannot_parse_txt(self) -> None:
        assert PdfTestParser().can_parse("file.txt", "", 0) is False

    def test_can_parse_by_mime(self) -> None:
        assert PdfTestParser().can_parse("file", "application/pdf", 0) is True

    def test_parse_pdf_magic(self) -> None:
        result = PdfTestParser().parse("art-1", "doc.pdf", b"%PDF-1.4 content")
        assert "PDF content extracted" in result.text_content

    def test_parse_non_pdf_content(self) -> None:
        result = PdfTestParser().parse("art-1", "doc.pdf", b"plain text")
        assert result.text_content == "plain text"

    def test_detect_images(self) -> None:
        result = PdfTestParser().parse("art-1", "doc.pdf", b"some Image data")
        assert result.has_images is True


class TestDocxTestParser:
    def test_family(self) -> None:
        assert DocxTestParser().family() == ParserFamily.DOCUMENT

    def test_parser_id(self) -> None:
        assert DocxTestParser().parser_id() == "test-docx"

    def test_can_parse_docx(self) -> None:
        assert DocxTestParser().can_parse("file.docx", "", 0) is True

    def test_can_parse_doc(self) -> None:
        assert DocxTestParser().can_parse("file.doc", "", 0) is True

    def test_parse_zip_magic(self) -> None:
        result = DocxTestParser().parse("art-1", "doc.docx", b"PK\x03\x04 content")
        assert "DOCX content extracted" in result.text_content


class TestXlsxTestParser:
    def test_family(self) -> None:
        assert XlsxTestParser().family() == ParserFamily.SPREADSHEET

    def test_parser_id(self) -> None:
        assert XlsxTestParser().parser_id() == "test-xlsx"

    def test_can_parse_xlsx(self) -> None:
        assert XlsxTestParser().can_parse("file.xlsx", "", 0) is True

    def test_can_parse_csv(self) -> None:
        assert XlsxTestParser().can_parse("file.csv", "", 0) is True

    def test_can_parse_tsv(self) -> None:
        assert XlsxTestParser().can_parse("file.tsv", "", 0) is True

    def test_output_kind_table(self) -> None:
        result = XlsxTestParser().parse("art-1", "data.csv", b"a,b\n1,2\n")
        assert result.output_kind == ParseOutputKind.TABLE

    def test_has_tables(self) -> None:
        result = XlsxTestParser().parse("art-1", "data.csv", b"a,b\n1,2\n")
        assert result.has_tables is True

    def test_csv_parsing_produces_table_with_headers(self) -> None:
        content = b"name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        result = XlsxTestParser().parse("art-1", "data.csv", content)
        assert result.output_kind == ParseOutputKind.TABLE
        assert result.has_tables is True
        # structured_data should contain headers and row_count
        assert "headers" in result.structured_data
        headers = result.structured_data["headers"]
        assert "name" in headers
        assert "age" in headers
        assert "city" in headers
        assert result.structured_data["row_count"] == 2
        # tables tuple should also be populated
        assert len(result.tables) == 1
        assert result.tables[0]["row_count"] == 2

    def test_tsv_parsing(self) -> None:
        content = b"col1\tcol2\nval1\tval2\n"
        result = XlsxTestParser().parse("art-1", "data.tsv", content)
        assert result.output_kind == ParseOutputKind.TABLE
        assert "col1" in result.structured_data["headers"]


class TestPptxTestParser:
    def test_family(self) -> None:
        assert PptxTestParser().family() == ParserFamily.PRESENTATION

    def test_parser_id(self) -> None:
        assert PptxTestParser().parser_id() == "test-pptx"

    def test_can_parse_pptx(self) -> None:
        assert PptxTestParser().can_parse("slides.pptx", "", 0) is True

    def test_can_parse_ppt(self) -> None:
        assert PptxTestParser().can_parse("slides.ppt", "", 0) is True

    def test_detect_images_always(self) -> None:
        result = PptxTestParser().parse("art-1", "s.pptx", b"PK content")
        assert result.has_images is True

    def test_parse_zip_magic(self) -> None:
        result = PptxTestParser().parse("art-1", "s.pptx", b"PK\x03\x04 slides")
        assert "PPTX content extracted" in result.text_content


class TestImageTestParser:
    def test_family(self) -> None:
        assert ImageTestParser().family() == ParserFamily.IMAGE

    def test_parser_id(self) -> None:
        assert ImageTestParser().parser_id() == "test-image"

    def test_can_parse_png(self) -> None:
        assert ImageTestParser().can_parse("photo.png", "", 0) is True

    def test_can_parse_jpeg(self) -> None:
        assert ImageTestParser().can_parse("photo.jpg", "", 0) is True
        assert ImageTestParser().can_parse("photo.jpeg", "", 0) is True

    def test_output_kind_metadata_only(self) -> None:
        result = ImageTestParser().parse("art-1", "img.png", b"\x89PNG\r\n\x1a\n data")
        assert result.output_kind == ParseOutputKind.METADATA_ONLY

    def test_has_images(self) -> None:
        result = ImageTestParser().parse("art-1", "img.png", b"\x89PNG\r\n\x1a\n data")
        assert result.has_images is True

    def test_detect_png_format(self) -> None:
        result = ImageTestParser().parse("art-1", "img.png", b"\x89PNG\r\n\x1a\n data")
        assert result.extracted_metadata["detected_format"] == "png"

    def test_detect_jpeg_format(self) -> None:
        result = ImageTestParser().parse("art-1", "img.jpg", b"\xff\xd8\xff\xe0 data")
        assert result.extracted_metadata["detected_format"] == "jpeg"

    def test_detect_unknown_format(self) -> None:
        result = ImageTestParser().parse("art-1", "img.bmp", b"\x42\x4d data")
        assert result.extracted_metadata["detected_format"] == "unknown"


class TestAudioTestParser:
    def test_family(self) -> None:
        assert AudioTestParser().family() == ParserFamily.AUDIO

    def test_parser_id(self) -> None:
        assert AudioTestParser().parser_id() == "test-audio"

    def test_can_parse_mp3(self) -> None:
        assert AudioTestParser().can_parse("song.mp3", "", 0) is True

    def test_can_parse_wav(self) -> None:
        assert AudioTestParser().can_parse("audio.wav", "", 0) is True

    def test_can_parse_ogg(self) -> None:
        assert AudioTestParser().can_parse("audio.ogg", "", 0) is True

    def test_parse_placeholder(self) -> None:
        result = AudioTestParser().parse("art-1", "a.mp3", b"audio data")
        assert "Audio transcript placeholder" in result.text_content


class TestArchiveTestParser:
    def test_family(self) -> None:
        assert ArchiveTestParser().family() == ParserFamily.ARCHIVE

    def test_parser_id(self) -> None:
        assert ArchiveTestParser().parser_id() == "test-archive"

    def test_can_parse_zip(self) -> None:
        assert ArchiveTestParser().can_parse("file.zip", "", 0) is True

    def test_can_parse_tar(self) -> None:
        assert ArchiveTestParser().can_parse("file.tar", "", 0) is True

    def test_can_parse_tar_gz(self) -> None:
        assert ArchiveTestParser().can_parse("file.tar.gz", "", 0) is True

    def test_output_kind_tree(self) -> None:
        result = ArchiveTestParser().parse("art-1", "a.zip", b"PK\x03\x04 content")
        assert result.output_kind == ParseOutputKind.TREE

    def test_detect_zip_type(self) -> None:
        result = ArchiveTestParser().parse("art-1", "a.zip", b"PK\x03\x04 content")
        assert result.structured_data["archive_type"] == "zip"

    def test_detect_unknown_type(self) -> None:
        result = ArchiveTestParser().parse("art-1", "a.tar", b"tar content")
        assert result.structured_data["archive_type"] == "unknown"


class TestRepoTestParser:
    def test_family(self) -> None:
        assert RepoTestParser().family() == ParserFamily.REPOSITORY

    def test_parser_id(self) -> None:
        assert RepoTestParser().parser_id() == "test-repo"

    def test_can_parse_patch(self) -> None:
        assert RepoTestParser().can_parse("fix.patch", "", 0) is True

    def test_can_parse_diff(self) -> None:
        assert RepoTestParser().can_parse("change.diff", "", 0) is True

    def test_can_parse_dockerfile(self) -> None:
        assert RepoTestParser().can_parse("Dockerfile", "", 0) is True

    def test_can_parse_package_json(self) -> None:
        assert RepoTestParser().can_parse("package.json", "", 0) is True

    def test_can_parse_cargo_toml(self) -> None:
        assert RepoTestParser().can_parse("Cargo.toml", "", 0) is True

    def test_can_parse_pyproject_toml(self) -> None:
        assert RepoTestParser().can_parse("pyproject.toml", "", 0) is True

    def test_output_kind_key_value(self) -> None:
        result = RepoTestParser().parse("art-1", "fix.patch", b"diff content")
        assert result.output_kind == ParseOutputKind.KEY_VALUE

    def test_detect_patch_type(self) -> None:
        result = RepoTestParser().parse("art-1", "fix.patch", b"--- a/file\n+++ b/file\n")
        assert result.structured_data["artifact_type"] == "patch"

    def test_detect_npm_manifest(self) -> None:
        result = RepoTestParser().parse("art-1", "package.json", b'{"name":"pkg"}')
        assert result.structured_data["artifact_type"] == "npm_manifest"

    def test_detect_dockerfile(self) -> None:
        result = RepoTestParser().parse("art-1", "Dockerfile", b"FROM ubuntu:22.04\n")
        assert result.structured_data["artifact_type"] == "dockerfile"

    def test_cannot_parse_unknown(self) -> None:
        assert RepoTestParser().can_parse("mystery.xyz", "", 0) is False

    def test_size_limit_respected(self) -> None:
        # Exceeding MAX_SIZE should return False
        huge = 104857600 + 1  # > 100MB
        assert RepoTestParser().can_parse("fix.patch", "", huge) is False
