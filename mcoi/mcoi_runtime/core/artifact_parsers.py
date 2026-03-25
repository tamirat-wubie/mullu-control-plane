"""Purpose: artifact parser registry and test parsers.
Governance scope: registering, selecting, and managing artifact parsers
    with deterministic test implementations per parser family.
Dependencies: artifact_parser contracts, artifact_ingestion contracts,
    core invariants.
Invariants:
  - No duplicate parser IDs.
  - Only AVAILABLE/DEGRADED parsers participate in selection.
  - Every parser exposes a capability manifest.
  - Deterministic test parsers produce predictable output.
  - Immutable returns only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.artifact_parser import (
    ArtifactParserDescriptor,
    NormalizedParseOutput,
    ParseCapability,
    ParseOutputKind,
    ParserCapabilityLevel,
    ParserCapabilityManifest,
    ParserFailureMode,
    ParserFamily,
    ParserHealthReport,
    ParserStatus,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Abstract parser base
# ---------------------------------------------------------------------------


class ArtifactParser(ABC):
    """Abstract base for all artifact parsers."""

    @abstractmethod
    def parser_id(self) -> str: ...

    @abstractmethod
    def family(self) -> ParserFamily: ...

    @abstractmethod
    def descriptor(self) -> ArtifactParserDescriptor: ...

    @abstractmethod
    def manifest(self) -> ParserCapabilityManifest: ...

    @abstractmethod
    def can_parse(self, filename: str, mime_type: str, size_bytes: int) -> bool: ...

    @abstractmethod
    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput: ...

    @abstractmethod
    def health_check(self) -> ParserHealthReport: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ArtifactParserRegistry:
    """Central registry for artifact parsers."""

    def __init__(self) -> None:
        self._parsers: dict[str, ArtifactParser] = {}
        self._descriptors: dict[str, ArtifactParserDescriptor] = {}
        self._manifests: dict[str, ParserCapabilityManifest] = {}

    def register(self, parser: ArtifactParser) -> ArtifactParserDescriptor:
        """Register a parser. Rejects duplicates."""
        if not isinstance(parser, ArtifactParser):
            raise RuntimeCoreInvariantError("parser must be an ArtifactParser")
        pid = parser.parser_id()
        if pid in self._parsers:
            raise RuntimeCoreInvariantError(f"parser '{pid}' already registered")
        desc = parser.descriptor()
        manifest = parser.manifest()
        self._parsers[pid] = parser
        self._descriptors[pid] = desc
        self._manifests[pid] = manifest
        return desc

    def get_parser(self, parser_id: str) -> ArtifactParser:
        if parser_id not in self._parsers:
            raise RuntimeCoreInvariantError(f"parser '{parser_id}' not found")
        return self._parsers[parser_id]

    def get_descriptor(self, parser_id: str) -> ArtifactParserDescriptor:
        if parser_id not in self._descriptors:
            raise RuntimeCoreInvariantError(f"parser '{parser_id}' not found")
        return self._descriptors[parser_id]

    def get_manifest(self, parser_id: str) -> ParserCapabilityManifest:
        if parser_id not in self._manifests:
            raise RuntimeCoreInvariantError(f"parser '{parser_id}' not found")
        return self._manifests[parser_id]

    def list_parsers(
        self, *, family: ParserFamily | None = None,
        status: ParserStatus | None = None,
    ) -> tuple[ArtifactParserDescriptor, ...]:
        result = list(self._descriptors.values())
        if family is not None:
            result = [d for d in result if d.family == family]
        if status is not None:
            result = [d for d in result if d.status == status]
        return tuple(sorted(result, key=lambda d: d.parser_id))

    def list_available(self) -> tuple[ArtifactParserDescriptor, ...]:
        return tuple(
            d for d in sorted(self._descriptors.values(), key=lambda d: d.parser_id)
            if d.status in (ParserStatus.AVAILABLE, ParserStatus.DEGRADED)
        )

    def select_for_file(
        self, filename: str, mime_type: str = "", size_bytes: int = 0,
    ) -> tuple[ArtifactParser, ...]:
        """Find all available parsers that can handle this file."""
        candidates = []
        for pid in sorted(self._parsers):
            desc = self._descriptors[pid]
            if desc.status not in (ParserStatus.AVAILABLE, ParserStatus.DEGRADED):
                continue
            parser = self._parsers[pid]
            if parser.can_parse(filename, mime_type, size_bytes):
                candidates.append(parser)
        return tuple(candidates)

    def parse(
        self, parser_id: str, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        parser = self.get_parser(parser_id)
        return parser.parse(artifact_id, filename, content)

    def auto_parse(
        self, artifact_id: str, filename: str, content: bytes,
        mime_type: str = "",
    ) -> NormalizedParseOutput | None:
        """Auto-select best parser and parse. Returns None if no parser found."""
        candidates = self.select_for_file(filename, mime_type, len(content))
        if not candidates:
            return None
        return candidates[0].parse(artifact_id, filename, content)

    def health_check(self, parser_id: str) -> ParserHealthReport:
        parser = self.get_parser(parser_id)
        return parser.health_check()

    def health_check_all(self) -> tuple[ParserHealthReport, ...]:
        reports = []
        for pid in sorted(self._parsers):
            reports.append(self._parsers[pid].health_check())
        return tuple(reports)

    @property
    def parser_count(self) -> int:
        return len(self._parsers)

    def state_hash(self) -> str:
        h = sha256()
        for pid in sorted(self._parsers):
            d = self._descriptors[pid]
            h.update(f"parser:{pid}:{d.family.value}:{d.status.value}:{d.version}".encode())
        return h.hexdigest()


# ---------------------------------------------------------------------------
# Test parsers — one per family
# ---------------------------------------------------------------------------


class _BaseTestParser(ArtifactParser):
    """Shared logic for deterministic test parsers."""

    _FAMILY: ParserFamily
    _NAME: str
    _EXTENSIONS: tuple[str, ...]
    _MIME_TYPES: tuple[str, ...]
    _MAX_SIZE: int = 104857600  # 100MB
    _OUTPUT_KIND: ParseOutputKind = ParseOutputKind.TEXT

    def __init__(self, parser_id: str | None = None) -> None:
        self._id = parser_id or f"test-{self._FAMILY.value}"
        self._now = _now_iso()
        self._parsed = 0
        self._failed = 0

    def parser_id(self) -> str:
        return self._id

    def family(self) -> ParserFamily:
        return self._FAMILY

    def descriptor(self) -> ArtifactParserDescriptor:
        return ArtifactParserDescriptor(
            parser_id=self._id,
            name=self._NAME,
            family=self._FAMILY,
            status=ParserStatus.AVAILABLE,
            version="1.0.0",
            manifest_id=stable_identifier("p-manifest", {"pid": self._id}),
            tags=("test",),
            created_at=self._now,
        )

    def manifest(self) -> ParserCapabilityManifest:
        return ParserCapabilityManifest(
            manifest_id=stable_identifier("p-manifest", {"pid": self._id}),
            parser_id=self._id,
            family=self._FAMILY,
            capabilities=(
                ParseCapability(
                    format_name=self._FAMILY.value,
                    extensions=self._EXTENSIONS,
                    mime_types=self._MIME_TYPES,
                    capability_level=ParserCapabilityLevel.FULL_CONTENT,
                    max_size_bytes=self._MAX_SIZE,
                    output_kinds=(self._OUTPUT_KIND.value,),
                ),
            ),
            reliability_score=0.95,
            created_at=self._now,
        )

    def can_parse(self, filename: str, mime_type: str, size_bytes: int) -> bool:
        if size_bytes > self._MAX_SIZE:
            return False
        lower = filename.lower()
        if any(lower.endswith(ext) for ext in self._EXTENSIONS):
            return True
        if mime_type and mime_type in self._MIME_TYPES:
            return True
        return False

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        now = _now_iso()
        self._parsed += 1
        text = self._extract_text(content)
        words = len(text.split()) if text else 0
        return NormalizedParseOutput(
            output_id=stable_identifier("parse-out", {
                "pid": self._id, "aid": artifact_id, "ts": now,
            }),
            parser_id=self._id,
            artifact_id=artifact_id,
            family=self._FAMILY,
            output_kind=self._OUTPUT_KIND,
            text_content=text,
            page_count=self._estimate_pages(content),
            word_count=words,
            has_images=self._detect_images(content),
            has_tables=self._detect_tables(content),
            extracted_metadata={
                "filename": filename,
                "size_bytes": len(content),
                "parser": self._id,
            },
            parsed_at=now,
        )

    def _extract_text(self, content: bytes) -> str:
        try:
            return content.decode("utf-8", errors="replace")
        except (UnicodeDecodeError, AttributeError):
            return f"[binary content: {len(content)} bytes]"

    def _estimate_pages(self, content: bytes) -> int:
        # ~3000 chars per page heuristic
        return max(1, len(content) // 3000)

    def _detect_images(self, content: bytes) -> bool:
        return False

    def _detect_tables(self, content: bytes) -> bool:
        return False

    def health_check(self) -> ParserHealthReport:
        return ParserHealthReport(
            report_id=stable_identifier("p-health", {"pid": self._id, "ts": _now_iso()}),
            parser_id=self._id,
            status=ParserStatus.AVAILABLE,
            reliability_score=0.95,
            artifacts_parsed=self._parsed,
            artifacts_failed=self._failed,
            avg_parse_ms=25.0,
            reported_at=_now_iso(),
        )


class PdfTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.DOCUMENT
    _NAME = "PDF Test Parser"
    _EXTENSIONS = (".pdf",)
    _MIME_TYPES = ("application/pdf",)
    _OUTPUT_KIND = ParseOutputKind.TEXT

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-pdf")

    def _extract_text(self, content: bytes) -> str:
        # Deterministic test: simulate PDF text extraction
        if content[:4] == b"%PDF":
            return f"[PDF content extracted: {len(content)} bytes]"
        return content.decode("utf-8", errors="replace")

    def _estimate_pages(self, content: bytes) -> int:
        return max(1, len(content) // 4000)

    def _detect_images(self, content: bytes) -> bool:
        return b"Image" in content or b"image" in content


class DocxTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.DOCUMENT
    _NAME = "DOCX Test Parser"
    _EXTENSIONS = (".docx", ".doc")
    _MIME_TYPES = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    )
    _OUTPUT_KIND = ParseOutputKind.TEXT

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-docx")

    def _extract_text(self, content: bytes) -> str:
        if content[:2] == b"PK":  # ZIP-based format
            return f"[DOCX content extracted: {len(content)} bytes]"
        return content.decode("utf-8", errors="replace")


class XlsxTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.SPREADSHEET
    _NAME = "XLSX Test Parser"
    _EXTENSIONS = (".xlsx", ".xls", ".csv", ".tsv")
    _MIME_TYPES = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/tab-separated-values",
    )
    _OUTPUT_KIND = ParseOutputKind.TABLE

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-xlsx")

    def _detect_tables(self, content: bytes) -> bool:
        return True

    def _extract_text(self, content: bytes) -> str:
        text = content.decode("utf-8", errors="replace")
        if "," in text or "\t" in text:
            lines = text.strip().split("\n")
            return f"[Spreadsheet: {len(lines)} rows]"
        return text

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        result = super().parse(artifact_id, filename, content)
        # Add table structure for CSV/TSV
        text = content.decode("utf-8", errors="replace")
        lines = text.strip().split("\n")
        if lines:
            sep = "\t" if "\t" in lines[0] else ","
            headers = [h.strip() for h in lines[0].split(sep)]
            rows = []
            for line in lines[1:]:
                cells = [c.strip() for c in line.split(sep)]
                rows.append(dict(zip(headers, cells)))
            table_data = {"headers": tuple(headers), "row_count": len(rows)}
            return NormalizedParseOutput(
                output_id=result.output_id,
                parser_id=result.parser_id,
                artifact_id=result.artifact_id,
                family=result.family,
                output_kind=ParseOutputKind.TABLE,
                text_content=result.text_content,
                structured_data=table_data,
                tables=(table_data,),
                page_count=1,
                word_count=result.word_count,
                has_tables=True,
                extracted_metadata=result.extracted_metadata,
                parsed_at=result.parsed_at,
            )
        return result


class PptxTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.PRESENTATION
    _NAME = "PPTX Test Parser"
    _EXTENSIONS = (".pptx", ".ppt")
    _MIME_TYPES = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    )
    _OUTPUT_KIND = ParseOutputKind.TEXT

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-pptx")

    def _extract_text(self, content: bytes) -> str:
        if content[:2] == b"PK":
            return f"[PPTX content extracted: {len(content)} bytes, slides detected]"
        return content.decode("utf-8", errors="replace")

    def _detect_images(self, content: bytes) -> bool:
        return True  # presentations typically have images


class ImageTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.IMAGE
    _NAME = "Image Metadata Test Parser"
    _EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg")
    _MIME_TYPES = (
        "image/png", "image/jpeg", "image/gif",
        "image/bmp", "image/webp", "image/tiff", "image/svg+xml",
    )
    _OUTPUT_KIND = ParseOutputKind.METADATA_ONLY

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-image")

    def _extract_text(self, content: bytes) -> str:
        return f"[Image: {len(content)} bytes]"

    def _detect_images(self, content: bytes) -> bool:
        return True

    def _estimate_pages(self, content: bytes) -> int:
        return 1

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        now = _now_iso()
        self._parsed += 1
        # Detect basic image format from magic bytes
        fmt = "unknown"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            fmt = "png"
        elif content[:2] == b"\xff\xd8":
            fmt = "jpeg"
        elif content[:3] == b"GIF":
            fmt = "gif"

        return NormalizedParseOutput(
            output_id=stable_identifier("parse-out", {
                "pid": self._id, "aid": artifact_id, "ts": now,
            }),
            parser_id=self._id,
            artifact_id=artifact_id,
            family=self._FAMILY,
            output_kind=ParseOutputKind.METADATA_ONLY,
            text_content=f"[Image: {fmt}, {len(content)} bytes]",
            page_count=1,
            word_count=0,
            has_images=True,
            extracted_metadata={
                "filename": filename,
                "size_bytes": len(content),
                "detected_format": fmt,
                "parser": self._id,
            },
            parsed_at=now,
        )


class AudioTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.AUDIO
    _NAME = "Audio Transcript Test Parser"
    _EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac")
    _MIME_TYPES = (
        "audio/mpeg", "audio/wav", "audio/ogg",
        "audio/mp4", "audio/flac", "audio/aac",
    )
    _OUTPUT_KIND = ParseOutputKind.TEXT

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-audio")

    def _extract_text(self, content: bytes) -> str:
        return f"[Audio transcript placeholder: {len(content)} bytes]"

    def _estimate_pages(self, content: bytes) -> int:
        return 1


class ArchiveTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.ARCHIVE
    _NAME = "Archive/Container Test Parser"
    _EXTENSIONS = (".zip", ".tar", ".gz", ".tar.gz", ".tgz", ".7z", ".rar")
    _MIME_TYPES = (
        "application/zip", "application/x-tar",
        "application/gzip", "application/x-7z-compressed",
    )
    _OUTPUT_KIND = ParseOutputKind.TREE

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-archive")

    def _extract_text(self, content: bytes) -> str:
        return f"[Archive: {len(content)} bytes]"

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        now = _now_iso()
        self._parsed += 1
        return NormalizedParseOutput(
            output_id=stable_identifier("parse-out", {
                "pid": self._id, "aid": artifact_id, "ts": now,
            }),
            parser_id=self._id,
            artifact_id=artifact_id,
            family=self._FAMILY,
            output_kind=ParseOutputKind.TREE,
            text_content=f"[Archive: {len(content)} bytes]",
            structured_data={
                "archive_type": "zip" if content[:2] == b"PK" else "unknown",
                "estimated_entries": max(1, len(content) // 1000),
            },
            page_count=1,
            word_count=0,
            extracted_metadata={
                "filename": filename,
                "size_bytes": len(content),
                "parser": self._id,
            },
            parsed_at=now,
        )


class RepoTestParser(_BaseTestParser):
    _FAMILY = ParserFamily.REPOSITORY
    _NAME = "Repo Bundle/Patch/Manifest Test Parser"
    _EXTENSIONS = (".patch", ".diff", ".bundle", "Makefile", "Dockerfile",
                   "package.json", "Cargo.toml", "pyproject.toml",
                   "requirements.txt", ".gitignore")
    _MIME_TYPES = ("text/x-diff", "text/x-patch")
    _OUTPUT_KIND = ParseOutputKind.KEY_VALUE

    def __init__(self, parser_id: str | None = None) -> None:
        super().__init__(parser_id or "test-repo")

    def can_parse(self, filename: str, mime_type: str, size_bytes: int) -> bool:
        if size_bytes > self._MAX_SIZE:
            return False
        lower = filename.lower()
        base = lower.rsplit("/", 1)[-1] if "/" in lower else lower
        # Match by extension or exact filename
        if any(lower.endswith(ext) for ext in self._EXTENSIONS):
            return True
        if base in ("makefile", "dockerfile", "package.json", "cargo.toml",
                     "pyproject.toml", "requirements.txt", ".gitignore"):
            return True
        if mime_type and mime_type in self._MIME_TYPES:
            return True
        return False

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        now = _now_iso()
        self._parsed += 1
        text = content.decode("utf-8", errors="replace")
        lines = text.strip().split("\n")

        # Detect repo artifact type
        base = filename.rsplit("/", 1)[-1].lower() if "/" in filename else filename.lower()
        artifact_type = "unknown"
        if base.endswith(".patch") or base.endswith(".diff"):
            artifact_type = "patch"
        elif base == "package.json":
            artifact_type = "npm_manifest"
        elif base == "cargo.toml":
            artifact_type = "cargo_manifest"
        elif base == "pyproject.toml":
            artifact_type = "python_manifest"
        elif base == "requirements.txt":
            artifact_type = "python_requirements"
        elif base == "dockerfile":
            artifact_type = "dockerfile"
        elif base == "makefile":
            artifact_type = "makefile"

        return NormalizedParseOutput(
            output_id=stable_identifier("parse-out", {
                "pid": self._id, "aid": artifact_id, "ts": now,
            }),
            parser_id=self._id,
            artifact_id=artifact_id,
            family=self._FAMILY,
            output_kind=ParseOutputKind.KEY_VALUE,
            text_content=text,
            word_count=len(text.split()),
            structured_data={
                "artifact_type": artifact_type,
                "line_count": len(lines),
            },
            page_count=1,
            extracted_metadata={
                "filename": filename,
                "size_bytes": len(content),
                "artifact_type": artifact_type,
                "parser": self._id,
            },
            parsed_at=now,
        )


# ---------------------------------------------------------------------------
# Convenience: register all test parsers
# ---------------------------------------------------------------------------


def register_all_test_parsers(
    registry: ArtifactParserRegistry,
) -> tuple[ArtifactParserDescriptor, ...]:
    """Register one test parser per family. Returns descriptors."""
    parsers = [
        PdfTestParser(),
        DocxTestParser(),
        XlsxTestParser(),
        PptxTestParser(),
        ImageTestParser(),
        AudioTestParser(),
        ArchiveTestParser(),
        RepoTestParser(),
    ]
    descs = []
    for parser in parsers:
        descs.append(registry.register(parser))
    return tuple(descs)
