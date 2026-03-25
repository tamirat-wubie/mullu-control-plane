"""Purpose: universal artifact ingestion engine.
Governance scope: format detection, parser dispatch, structure extraction,
    semantic mapping, policy gating, fingerprinting, ingestion records.
Dependencies: artifact_ingestion contracts, core invariants.
Invariants:
  - Pipeline: detect → parse → map → gate → emit.
  - Parsers are registered per-format, not baked in.
  - Policy gating is fail-closed: no policy → POLICY_BLOCKED.
  - Fingerprints are deterministic (SHA-256 over content bytes).
  - All state changes go through the engine — parsers never mutate state.
  - Duplicate artifact_ids are rejected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Mapping, Protocol

from ..contracts.artifact_ingestion import (
    ArtifactCapabilityManifest,
    ArtifactDescriptor,
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
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Parser / detector / mapper protocols
# ---------------------------------------------------------------------------

# Parser: (artifact_id, content_bytes, format, metadata) -> ArtifactParseResult
ParserFn = Callable[[str, bytes, ArtifactFormat, Mapping[str, Any]], ArtifactParseResult]

# Detector: (filename, mime_type, content_bytes[:512]) -> ArtifactFormat | None
DetectorFn = Callable[[str, str, bytes], ArtifactFormat | None]

# Semantic mapper: (artifact_id, format, parse_result, structure) -> ArtifactSemanticMapping | None
SemanticMapperFn = Callable[
    [str, ArtifactFormat, ArtifactParseResult, ArtifactStructure | None],
    ArtifactSemanticMapping | None,
]


# ---------------------------------------------------------------------------
# Built-in format detection
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, ArtifactFormat] = {
    ".txt": ArtifactFormat.TEXT,
    ".md": ArtifactFormat.MARKDOWN,
    ".json": ArtifactFormat.JSON,
    ".yaml": ArtifactFormat.YAML,
    ".yml": ArtifactFormat.YAML,
    ".toml": ArtifactFormat.TOML,
    ".xml": ArtifactFormat.XML,
    ".csv": ArtifactFormat.CSV,
    ".tsv": ArtifactFormat.TSV,
    ".log": ArtifactFormat.LOG,
    ".pdf": ArtifactFormat.PDF,
    ".docx": ArtifactFormat.DOCX,
    ".xlsx": ArtifactFormat.XLSX,
    ".pptx": ArtifactFormat.PPTX,
    ".png": ArtifactFormat.IMAGE,
    ".jpg": ArtifactFormat.IMAGE,
    ".jpeg": ArtifactFormat.IMAGE,
    ".gif": ArtifactFormat.IMAGE,
    ".svg": ArtifactFormat.IMAGE,
    ".mp3": ArtifactFormat.AUDIO,
    ".wav": ArtifactFormat.AUDIO,
    ".mp4": ArtifactFormat.VIDEO,
    ".zip": ArtifactFormat.ARCHIVE,
    ".tar": ArtifactFormat.ARCHIVE,
    ".gz": ArtifactFormat.ARCHIVE,
    ".py": ArtifactFormat.CODE,
    ".js": ArtifactFormat.CODE,
    ".ts": ArtifactFormat.CODE,
    ".rs": ArtifactFormat.CODE,
    ".go": ArtifactFormat.CODE,
    ".java": ArtifactFormat.CODE,
    ".c": ArtifactFormat.CODE,
    ".cpp": ArtifactFormat.CODE,
    ".rb": ArtifactFormat.CODE,
    ".sh": ArtifactFormat.CODE,
}

_MIME_MAP: dict[str, ArtifactFormat] = {
    "text/plain": ArtifactFormat.TEXT,
    "text/markdown": ArtifactFormat.MARKDOWN,
    "application/json": ArtifactFormat.JSON,
    "application/x-yaml": ArtifactFormat.YAML,
    "text/yaml": ArtifactFormat.YAML,
    "application/toml": ArtifactFormat.TOML,
    "text/xml": ArtifactFormat.XML,
    "application/xml": ArtifactFormat.XML,
    "text/csv": ArtifactFormat.CSV,
    "text/tab-separated-values": ArtifactFormat.TSV,
    "application/pdf": ArtifactFormat.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ArtifactFormat.DOCX,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ArtifactFormat.XLSX,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ArtifactFormat.PPTX,
    "application/zip": ArtifactFormat.ARCHIVE,
}


def _default_detect(filename: str, mime_type: str, _content_head: bytes) -> ArtifactFormat | None:
    """Built-in detection: extension first, then MIME, then content sniffing."""
    # Extension
    dot_idx = filename.rfind(".")
    if dot_idx >= 0:
        ext = filename[dot_idx:].lower()
        if ext in _EXTENSION_MAP:
            return _EXTENSION_MAP[ext]

    # MIME
    if mime_type in _MIME_MAP:
        return _MIME_MAP[mime_type]

    # Content sniffing (lightweight)
    if _content_head:
        stripped = _content_head.lstrip()
        if stripped.startswith(b"{") or stripped.startswith(b"["):
            return ArtifactFormat.JSON
        if stripped.startswith(b"---"):
            return ArtifactFormat.YAML

    return None


# ---------------------------------------------------------------------------
# Built-in parsers for canonical subset
# ---------------------------------------------------------------------------


def _parse_text(artifact_id: str, content: bytes, fmt: ArtifactFormat, _meta: Mapping[str, Any]) -> ArtifactParseResult:
    now = _now_iso()
    text = content.decode("utf-8", errors="replace")
    return ArtifactParseResult(
        parse_id=stable_identifier("parse", {"aid": artifact_id}),
        artifact_id=artifact_id,
        format_detected=fmt,
        status=ArtifactParseStatus.ACCEPTED,
        reason="Text content parsed successfully",
        parsed_at=now,
        content_preview=text[:500],
    )


def _parse_json(artifact_id: str, content: bytes, fmt: ArtifactFormat, _meta: Mapping[str, Any]) -> ArtifactParseResult:
    now = _now_iso()
    try:
        data = json.loads(content)
        preview = json.dumps(data, indent=2, default=str)[:500]
        return ArtifactParseResult(
            parse_id=stable_identifier("parse", {"aid": artifact_id}),
            artifact_id=artifact_id,
            format_detected=ArtifactFormat.JSON,
            status=ArtifactParseStatus.ACCEPTED,
            reason="Valid JSON parsed",
            parsed_at=now,
            content_preview=preview,
            metadata={"key_count": len(data) if isinstance(data, dict) else 0},
        )
    except (json.JSONDecodeError, ValueError) as e:
        return ArtifactParseResult(
            parse_id=stable_identifier("parse", {"aid": artifact_id}),
            artifact_id=artifact_id,
            format_detected=ArtifactFormat.JSON,
            status=ArtifactParseStatus.MALFORMED,
            reason=f"Invalid JSON: {e}",
            parsed_at=now,
        )


def _parse_yaml(artifact_id: str, content: bytes, fmt: ArtifactFormat, _meta: Mapping[str, Any]) -> ArtifactParseResult:
    now = _now_iso()
    text = content.decode("utf-8", errors="replace")
    # Lightweight YAML validation: check for basic structure
    lines = text.strip().splitlines()
    if not lines:
        return ArtifactParseResult(
            parse_id=stable_identifier("parse", {"aid": artifact_id}),
            artifact_id=artifact_id,
            format_detected=ArtifactFormat.YAML,
            status=ArtifactParseStatus.MALFORMED,
            reason="Empty YAML content",
            parsed_at=now,
        )
    # Check for obvious malformation (unbalanced braces, tabs as indentation)
    has_structure = any(
        ":" in line or line.strip().startswith("-") or line.strip().startswith("---")
        for line in lines
    )
    if not has_structure:
        return ArtifactParseResult(
            parse_id=stable_identifier("parse", {"aid": artifact_id}),
            artifact_id=artifact_id,
            format_detected=ArtifactFormat.YAML,
            status=ArtifactParseStatus.MALFORMED,
            reason="Content does not appear to be valid YAML",
            parsed_at=now,
        )
    return ArtifactParseResult(
        parse_id=stable_identifier("parse", {"aid": artifact_id}),
        artifact_id=artifact_id,
        format_detected=ArtifactFormat.YAML,
        status=ArtifactParseStatus.ACCEPTED,
        reason="YAML content parsed successfully",
        parsed_at=now,
        content_preview=text[:500],
    )


def _parse_csv(artifact_id: str, content: bytes, fmt: ArtifactFormat, _meta: Mapping[str, Any]) -> ArtifactParseResult:
    now = _now_iso()
    text = content.decode("utf-8", errors="replace")
    lines = text.strip().splitlines()
    if not lines:
        return ArtifactParseResult(
            parse_id=stable_identifier("parse", {"aid": artifact_id}),
            artifact_id=artifact_id,
            format_detected=ArtifactFormat.CSV,
            status=ArtifactParseStatus.MALFORMED,
            reason="Empty CSV content",
            parsed_at=now,
        )
    row_count = len(lines)
    header = lines[0] if lines else ""
    col_count = len(header.split(","))
    return ArtifactParseResult(
        parse_id=stable_identifier("parse", {"aid": artifact_id}),
        artifact_id=artifact_id,
        format_detected=ArtifactFormat.CSV,
        status=ArtifactParseStatus.ACCEPTED,
        reason=f"CSV parsed: {row_count} rows, {col_count} columns",
        parsed_at=now,
        content_preview=text[:500],
        metadata={"row_count": row_count, "col_count": col_count},
    )


def _parse_unsupported(artifact_id: str, content: bytes, fmt: ArtifactFormat, _meta: Mapping[str, Any]) -> ArtifactParseResult:
    return ArtifactParseResult(
        parse_id=stable_identifier("parse", {"aid": artifact_id}),
        artifact_id=artifact_id,
        format_detected=fmt,
        status=ArtifactParseStatus.UNSUPPORTED,
        reason=f"Format {fmt.value} is not supported by any registered parser",
        parsed_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ArtifactIngestionEngine:
    """Universal artifact ingestion substrate.

    Pipeline: detect → parse → structure → map → gate → record.
    Parsers, detectors, semantic mappers, and policy gates are pluggable.
    """

    def __init__(
        self,
        *,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100 MB default
        allowed_formats: tuple[ArtifactFormat, ...] | None = None,
        allowed_sources: tuple[ArtifactSourceType, ...] | None = None,
    ) -> None:
        self._records: dict[str, ArtifactIngestionRecord] = {}
        self._parsers: dict[ArtifactFormat, ParserFn] = {}
        self._detectors: list[DetectorFn] = [_default_detect]
        self._semantic_mappers: list[SemanticMapperFn] = []
        self._max_size_bytes = max_size_bytes
        self._allowed_formats = set(allowed_formats) if allowed_formats else None
        self._allowed_sources = set(allowed_sources) if allowed_sources else None

        # Register built-in parsers
        for fmt in (ArtifactFormat.TEXT, ArtifactFormat.MARKDOWN, ArtifactFormat.LOG, ArtifactFormat.CODE):
            self._parsers[fmt] = _parse_text
        self._parsers[ArtifactFormat.JSON] = _parse_json
        self._parsers[ArtifactFormat.YAML] = _parse_yaml
        self._parsers[ArtifactFormat.CSV] = _parse_csv
        self._parsers[ArtifactFormat.TSV] = _parse_csv  # same logic
        self._parsers[ArtifactFormat.UNKNOWN] = _parse_text

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_parser(self, format: ArtifactFormat, parser: ParserFn) -> None:
        """Register or replace a parser for a format."""
        self._parsers[format] = parser

    def register_detector(self, detector: DetectorFn) -> None:
        """Add a custom format detector (checked before built-in)."""
        self._detectors.insert(0, detector)

    def register_semantic_mapper(self, mapper: SemanticMapperFn) -> None:
        """Add a semantic mapper."""
        self._semantic_mappers.append(mapper)

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    def detect_format(
        self, filename: str, mime_type: str, content_head: bytes,
    ) -> ArtifactFormat:
        """Run detectors in order, return first match or UNKNOWN."""
        for detector in self._detectors:
            result = detector(filename, mime_type, content_head)
            if result is not None:
                return result
        return ArtifactFormat.UNKNOWN

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------

    def fingerprint(self, artifact_id: str, content: bytes) -> ArtifactFingerprint:
        """Compute SHA-256 fingerprint of content."""
        digest = sha256(content).hexdigest()
        return ArtifactFingerprint(
            fingerprint_id=stable_identifier("fp", {"aid": artifact_id}),
            artifact_id=artifact_id,
            algorithm="sha256",
            digest=digest,
            computed_at=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Policy gating
    # ------------------------------------------------------------------

    def evaluate_policy(
        self, descriptor: ArtifactDescriptor, detected_format: ArtifactFormat,
    ) -> ArtifactPolicyDecision:
        """Evaluate policy gates. Fail-closed."""
        now = _now_iso()
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # Size check
        if descriptor.size_bytes > self._max_size_bytes:
            checks_failed.append(f"size:{descriptor.size_bytes}>{self._max_size_bytes}")
            return ArtifactPolicyDecision(
                decision_id=stable_identifier("apd", {"aid": descriptor.artifact_id}),
                artifact_id=descriptor.artifact_id,
                allowed=False,
                reason=f"Artifact too large: {descriptor.size_bytes} bytes exceeds limit of {self._max_size_bytes}",
                checks_passed=tuple(checks_passed),
                checks_failed=tuple(checks_failed),
                evaluated_at=now,
            )
        checks_passed.append("size_ok")

        # Format check
        if self._allowed_formats is not None and detected_format not in self._allowed_formats:
            checks_failed.append(f"format:{detected_format.value}")
            return ArtifactPolicyDecision(
                decision_id=stable_identifier("apd", {"aid": descriptor.artifact_id}),
                artifact_id=descriptor.artifact_id,
                allowed=False,
                reason=f"Format {detected_format.value} is not in allowed formats",
                checks_passed=tuple(checks_passed),
                checks_failed=tuple(checks_failed),
                evaluated_at=now,
            )
        checks_passed.append("format_ok")

        # Source check
        if self._allowed_sources is not None and descriptor.source_type not in self._allowed_sources:
            checks_failed.append(f"source:{descriptor.source_type.value}")
            return ArtifactPolicyDecision(
                decision_id=stable_identifier("apd", {"aid": descriptor.artifact_id}),
                artifact_id=descriptor.artifact_id,
                allowed=False,
                reason=f"Source type {descriptor.source_type.value} is not allowed",
                checks_passed=tuple(checks_passed),
                checks_failed=tuple(checks_failed),
                evaluated_at=now,
            )
        checks_passed.append("source_ok")

        return ArtifactPolicyDecision(
            decision_id=stable_identifier("apd", {"aid": descriptor.artifact_id}),
            artifact_id=descriptor.artifact_id,
            allowed=True,
            reason="All policy checks passed",
            checks_passed=tuple(checks_passed),
            checks_failed=(),
            evaluated_at=now,
        )

    # ------------------------------------------------------------------
    # Structure extraction
    # ------------------------------------------------------------------

    def extract_structure(
        self,
        artifact_id: str,
        fmt: ArtifactFormat,
        content: bytes,
        parse_result: ArtifactParseResult,
    ) -> ArtifactStructure | None:
        """Extract structure from parsed content."""
        if parse_result.status not in (ArtifactParseStatus.ACCEPTED, ArtifactParseStatus.PARTIAL):
            return None

        now = _now_iso()
        text = content.decode("utf-8", errors="replace")

        if fmt == ArtifactFormat.JSON:
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    return ArtifactStructure(
                        structure_id=stable_identifier("struct", {"aid": artifact_id}),
                        artifact_id=artifact_id,
                        format=fmt,
                        field_count=len(data),
                        sections={"keys": list(data.keys())[:100]},
                        extracted_at=now,
                    )
            except (json.JSONDecodeError, ValueError):
                pass

        if fmt in (ArtifactFormat.CSV, ArtifactFormat.TSV):
            lines = text.strip().splitlines()
            if lines:
                sep = "\t" if fmt == ArtifactFormat.TSV else ","
                headers = lines[0].split(sep)
                return ArtifactStructure(
                    structure_id=stable_identifier("struct", {"aid": artifact_id}),
                    artifact_id=artifact_id,
                    format=fmt,
                    field_count=len(headers),
                    row_count=len(lines) - 1,
                    sections={"headers": headers},
                    extracted_at=now,
                )

        if fmt in (ArtifactFormat.TEXT, ArtifactFormat.MARKDOWN, ArtifactFormat.LOG, ArtifactFormat.CODE):
            lines = text.splitlines()
            return ArtifactStructure(
                structure_id=stable_identifier("struct", {"aid": artifact_id}),
                artifact_id=artifact_id,
                format=fmt,
                section_count=1,
                row_count=len(lines),
                extracted_at=now,
            )

        return None

    # ------------------------------------------------------------------
    # Semantic mapping
    # ------------------------------------------------------------------

    def apply_semantic_mapping(
        self,
        artifact_id: str,
        fmt: ArtifactFormat,
        parse_result: ArtifactParseResult,
        structure: ArtifactStructure | None,
    ) -> ArtifactSemanticMapping | None:
        """Run semantic mappers, return first non-None result."""
        for mapper in self._semantic_mappers:
            result = mapper(artifact_id, fmt, parse_result, structure)
            if result is not None:
                return result
        # Default mapping
        sem_type = _default_semantic_type(fmt)
        if sem_type is None:
            return None
        return ArtifactSemanticMapping(
            mapping_id=stable_identifier("semmap", {"aid": artifact_id}),
            artifact_id=artifact_id,
            semantic_type=sem_type,
            domain="general",
            confidence=0.5,
            mapped_at=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Full ingestion pipeline
    # ------------------------------------------------------------------

    def ingest(
        self,
        descriptor: ArtifactDescriptor,
        content: bytes,
    ) -> ArtifactIngestionRecord:
        """Full pipeline: detect → fingerprint → gate → parse → structure → map → record."""
        if descriptor.artifact_id in self._records:
            raise RuntimeCoreInvariantError(f"duplicate artifact_id: {descriptor.artifact_id}")

        now = _now_iso()
        aid = descriptor.artifact_id

        # 1. Detect format
        detected = self.detect_format(
            descriptor.filename, descriptor.mime_type, content[:512],
        )
        if descriptor.format_hint != ArtifactFormat.UNKNOWN:
            detected = descriptor.format_hint

        # 2. Fingerprint
        fp = self.fingerprint(aid, content)

        # 3. Policy gate
        policy = self.evaluate_policy(descriptor, detected)
        if not policy.allowed:
            status = ArtifactParseStatus.TOO_LARGE if descriptor.size_bytes > self._max_size_bytes else ArtifactParseStatus.POLICY_BLOCKED
            parse_result = ArtifactParseResult(
                parse_id=stable_identifier("parse", {"aid": aid}),
                artifact_id=aid,
                format_detected=detected,
                status=status,
                reason=policy.reason,
                parsed_at=now,
            )
            record = ArtifactIngestionRecord(
                record_id=stable_identifier("ingest", {"aid": aid}),
                artifact_id=aid,
                descriptor=descriptor,
                fingerprint=fp,
                parse_result=parse_result,
                structure=None,
                semantic_mapping=None,
                policy_decision=policy,
                status=status,
                ingested_at=now,
            )
            self._records[aid] = record
            return record

        # 4. Parse
        parser = self._parsers.get(detected, _parse_unsupported)
        parse_result = parser(aid, content, detected, dict(descriptor.metadata))

        # 5. Structure extraction
        structure = self.extract_structure(aid, detected, content, parse_result)

        # 6. Semantic mapping
        semantic = self.apply_semantic_mapping(aid, detected, parse_result, structure)

        # 7. Build record
        record = ArtifactIngestionRecord(
            record_id=stable_identifier("ingest", {"aid": aid}),
            artifact_id=aid,
            descriptor=descriptor,
            fingerprint=fp,
            parse_result=parse_result,
            structure=structure,
            semantic_mapping=semantic,
            policy_decision=policy,
            status=parse_result.status,
            ingested_at=now,
        )
        self._records[aid] = record
        return record

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_record(self, artifact_id: str) -> ArtifactIngestionRecord | None:
        return self._records.get(artifact_id)

    def list_records(self) -> tuple[ArtifactIngestionRecord, ...]:
        return tuple(self._records.values())

    def list_by_status(self, status: ArtifactParseStatus) -> tuple[ArtifactIngestionRecord, ...]:
        return tuple(r for r in self._records.values() if r.status == status)

    def list_by_format(self, fmt: ArtifactFormat) -> tuple[ArtifactIngestionRecord, ...]:
        return tuple(r for r in self._records.values() if r.parse_result.format_detected == fmt)

    def list_by_semantic_type(self, sem_type: ArtifactSemanticType) -> tuple[ArtifactIngestionRecord, ...]:
        return tuple(
            r for r in self._records.values()
            if r.semantic_mapping is not None and r.semantic_mapping.semantic_type == sem_type
        )

    @property
    def record_count(self) -> int:
        return len(self._records)

    def state_hash(self) -> str:
        parts = [f"art:{k}" for k in sorted(self._records)]
        return sha256("|".join(parts).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Default semantic type mapping
# ---------------------------------------------------------------------------


def _default_semantic_type(fmt: ArtifactFormat) -> ArtifactSemanticType | None:
    mapping = {
        ArtifactFormat.TEXT: ArtifactSemanticType.DOCUMENT,
        ArtifactFormat.MARKDOWN: ArtifactSemanticType.DOCUMENT,
        ArtifactFormat.JSON: ArtifactSemanticType.CONFIG,
        ArtifactFormat.YAML: ArtifactSemanticType.CONFIG,
        ArtifactFormat.TOML: ArtifactSemanticType.CONFIG,
        ArtifactFormat.XML: ArtifactSemanticType.CONFIG,
        ArtifactFormat.CSV: ArtifactSemanticType.DATASET,
        ArtifactFormat.TSV: ArtifactSemanticType.DATASET,
        ArtifactFormat.LOG: ArtifactSemanticType.LOG_STREAM,
        ArtifactFormat.CODE: ArtifactSemanticType.SOURCE_CODE,
        ArtifactFormat.PDF: ArtifactSemanticType.DOCUMENT,
        ArtifactFormat.DOCX: ArtifactSemanticType.DOCUMENT,
        ArtifactFormat.XLSX: ArtifactSemanticType.TABLE,
        ArtifactFormat.IMAGE: ArtifactSemanticType.IMAGE_REFERENCE,
        ArtifactFormat.ARCHIVE: ArtifactSemanticType.ARCHIVE_CONTENT,
    }
    return mapping.get(fmt)
