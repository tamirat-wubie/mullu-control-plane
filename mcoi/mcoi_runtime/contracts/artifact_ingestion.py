"""Purpose: canonical universal artifact ingestion contracts.
Governance scope: artifact descriptors, fingerprints, parsing, structure extraction,
    semantic mapping, policy gating, ingestion records, and capability manifests.
Dependencies: shared contract base helpers.
Invariants:
  - Every artifact has explicit source, format, fingerprint, and provenance.
  - Parse results are one of: ACCEPTED, REJECTED, PARTIAL, UNSUPPORTED, MALFORMED,
    TOO_LARGE, POLICY_BLOCKED — never ambiguous.
  - Fingerprints are deterministic over content.
  - Artifacts are immutable once ingested — update by superseding.
  - Policy gating is fail-closed: no policy → POLICY_BLOCKED.
  - Extraction results are immutable structured outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArtifactSourceType(StrEnum):
    """Where an artifact originated."""

    FILE = "file"
    EMAIL_ATTACHMENT = "email_attachment"
    WEB_UPLOAD = "web_upload"
    API_PAYLOAD = "api_payload"
    REPOSITORY = "repository"
    ARCHIVE = "archive"
    MESSAGE_ATTACHMENT = "message_attachment"
    GENERATED = "generated"


class ArtifactFormat(StrEnum):
    """Detected or declared format of an artifact."""

    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    XML = "xml"
    CSV = "csv"
    TSV = "tsv"
    LOG = "log"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    CODE = "code"
    UNKNOWN = "unknown"


class ArtifactParseStatus(StrEnum):
    """Outcome of parsing an artifact."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    MALFORMED = "malformed"
    TOO_LARGE = "too_large"
    POLICY_BLOCKED = "policy_blocked"


class ArtifactSemanticType(StrEnum):
    """Semantic classification of what an artifact represents."""

    DOCUMENT = "document"
    DATASET = "dataset"
    CONFIG = "config"
    LOG_STREAM = "log_stream"
    SOURCE_CODE = "source_code"
    PATCH = "patch"
    TRANSCRIPT = "transcript"
    TABLE = "table"
    IMAGE_REFERENCE = "image_reference"
    ARCHIVE_CONTENT = "archive_content"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Artifact descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor(ContractRecord):
    """Canonical descriptor for an artifact before parsing.

    Captures source, format hint, filename, MIME type, and size.
    """

    artifact_id: str
    source_type: ArtifactSourceType
    source_ref: str
    filename: str
    mime_type: str
    format_hint: ArtifactFormat = ArtifactFormat.UNKNOWN
    size_bytes: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.source_type, ArtifactSourceType):
            raise ValueError("source_type must be an ArtifactSourceType value")
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "filename", require_non_empty_text(self.filename, "filename"))
        object.__setattr__(self, "mime_type", require_non_empty_text(self.mime_type, "mime_type"))
        if not isinstance(self.format_hint, ArtifactFormat):
            raise ValueError("format_hint must be an ArtifactFormat value")
        object.__setattr__(self, "size_bytes", require_non_negative_int(self.size_bytes, "size_bytes"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Artifact fingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactFingerprint(ContractRecord):
    """Deterministic content fingerprint for deduplication and integrity."""

    fingerprint_id: str
    artifact_id: str
    algorithm: str
    digest: str
    computed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint_id", require_non_empty_text(self.fingerprint_id, "fingerprint_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "algorithm", require_non_empty_text(self.algorithm, "algorithm"))
        object.__setattr__(self, "digest", require_non_empty_text(self.digest, "digest"))
        object.__setattr__(self, "computed_at", require_datetime_text(self.computed_at, "computed_at"))


# ---------------------------------------------------------------------------
# Artifact parse result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactParseResult(ContractRecord):
    """Result of parsing an artifact.

    Every artifact ends in a typed outcome — never ambiguous.
    """

    parse_id: str
    artifact_id: str
    format_detected: ArtifactFormat
    status: ArtifactParseStatus
    reason: str
    parsed_at: str
    content_preview: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parse_id", require_non_empty_text(self.parse_id, "parse_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.format_detected, ArtifactFormat):
            raise ValueError("format_detected must be an ArtifactFormat value")
        if not isinstance(self.status, ArtifactParseStatus):
            raise ValueError("status must be an ArtifactParseStatus value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "parsed_at", require_datetime_text(self.parsed_at, "parsed_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Artifact structure
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactStructure(ContractRecord):
    """Extracted structural representation of an artifact's content.

    Captures sections, keys, rows, fields — whatever the format yields.
    """

    structure_id: str
    artifact_id: str
    format: ArtifactFormat
    section_count: int = 0
    field_count: int = 0
    row_count: int = 0
    sections: Mapping[str, Any] = field(default_factory=dict)
    extracted_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "structure_id", require_non_empty_text(self.structure_id, "structure_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.format, ArtifactFormat):
            raise ValueError("format must be an ArtifactFormat value")
        object.__setattr__(self, "section_count", require_non_negative_int(self.section_count, "section_count"))
        object.__setattr__(self, "field_count", require_non_negative_int(self.field_count, "field_count"))
        object.__setattr__(self, "row_count", require_non_negative_int(self.row_count, "row_count"))
        object.__setattr__(self, "sections", freeze_value(self.sections))
        object.__setattr__(self, "extracted_at", require_datetime_text(self.extracted_at, "extracted_at"))


# ---------------------------------------------------------------------------
# Artifact semantic mapping
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactSemanticMapping(ContractRecord):
    """Semantic classification and tagging of an artifact.

    Maps a parsed artifact to its semantic type, domain, and tags.
    """

    mapping_id: str
    artifact_id: str
    semantic_type: ArtifactSemanticType
    domain: str
    tags: tuple[str, ...] = ()
    confidence: float = 0.5
    mapped_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "mapping_id", require_non_empty_text(self.mapping_id, "mapping_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.semantic_type, ArtifactSemanticType):
            raise ValueError("semantic_type must be an ArtifactSemanticType value")
        object.__setattr__(self, "domain", require_non_empty_text(self.domain, "domain"))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "mapped_at", require_datetime_text(self.mapped_at, "mapped_at"))


# ---------------------------------------------------------------------------
# Artifact policy decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactPolicyDecision(ContractRecord):
    """Result of evaluating artifact ingestion policy. Fail-closed."""

    decision_id: str
    artifact_id: str
    allowed: bool
    reason: str
    checks_passed: tuple[str, ...] = ()
    checks_failed: tuple[str, ...] = ()
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a boolean")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "checks_passed", freeze_value(list(self.checks_passed)))
        object.__setattr__(self, "checks_failed", freeze_value(list(self.checks_failed)))
        object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))


# ---------------------------------------------------------------------------
# Artifact ingestion record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactIngestionRecord(ContractRecord):
    """Complete immutable record of an artifact's ingestion lifecycle.

    Links descriptor, fingerprint, parse result, structure, semantic mapping,
    and policy decision into one auditable record.
    """

    record_id: str
    artifact_id: str
    descriptor: ArtifactDescriptor
    fingerprint: ArtifactFingerprint
    parse_result: ArtifactParseResult
    structure: ArtifactStructure | None
    semantic_mapping: ArtifactSemanticMapping | None
    policy_decision: ArtifactPolicyDecision
    status: ArtifactParseStatus
    lineage_ids: tuple[str, ...] = ()
    memory_ids: tuple[str, ...] = ()
    graph_node_ids: tuple[str, ...] = ()
    ingested_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.descriptor, ArtifactDescriptor):
            raise ValueError("descriptor must be an ArtifactDescriptor")
        if not isinstance(self.fingerprint, ArtifactFingerprint):
            raise ValueError("fingerprint must be an ArtifactFingerprint")
        if not isinstance(self.parse_result, ArtifactParseResult):
            raise ValueError("parse_result must be an ArtifactParseResult")
        if self.structure is not None and not isinstance(self.structure, ArtifactStructure):
            raise ValueError("structure must be an ArtifactStructure or None")
        if self.semantic_mapping is not None and not isinstance(self.semantic_mapping, ArtifactSemanticMapping):
            raise ValueError("semantic_mapping must be an ArtifactSemanticMapping or None")
        if not isinstance(self.policy_decision, ArtifactPolicyDecision):
            raise ValueError("policy_decision must be an ArtifactPolicyDecision")
        if not isinstance(self.status, ArtifactParseStatus):
            raise ValueError("status must be an ArtifactParseStatus value")
        object.__setattr__(self, "lineage_ids", freeze_value(list(self.lineage_ids)))
        object.__setattr__(self, "memory_ids", freeze_value(list(self.memory_ids)))
        object.__setattr__(self, "graph_node_ids", freeze_value(list(self.graph_node_ids)))
        object.__setattr__(self, "ingested_at", require_datetime_text(self.ingested_at, "ingested_at"))


# ---------------------------------------------------------------------------
# Artifact extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactExtractionField(ContractRecord):
    """A single extracted field from an artifact."""

    field_name: str
    field_value: str
    field_type: str = "string"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        object.__setattr__(self, "field_value", require_non_empty_text(self.field_value, "field_value"))
        object.__setattr__(self, "field_type", require_non_empty_text(self.field_type, "field_type"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class ArtifactExtractionResult(ContractRecord):
    """Result of extracting structured fields from an artifact."""

    extraction_id: str
    artifact_id: str
    fields: tuple[ArtifactExtractionField, ...]
    extracted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "extraction_id", require_non_empty_text(self.extraction_id, "extraction_id"))
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "fields", freeze_value(list(self.fields)))
        for f in self.fields:
            if not isinstance(f, ArtifactExtractionField):
                raise ValueError("each field must be an ArtifactExtractionField")
        object.__setattr__(self, "extracted_at", require_datetime_text(self.extracted_at, "extracted_at"))


# ---------------------------------------------------------------------------
# Artifact capability manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactCapabilityManifest(ContractRecord):
    """Declares which formats and semantic types the ingestion engine supports."""

    manifest_id: str
    supported_formats: tuple[ArtifactFormat, ...]
    supported_semantic_types: tuple[ArtifactSemanticType, ...]
    max_size_bytes: int
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "supported_formats", freeze_value(list(self.supported_formats)))
        for f in self.supported_formats:
            if not isinstance(f, ArtifactFormat):
                raise ValueError("each supported_format must be an ArtifactFormat value")
        object.__setattr__(self, "supported_semantic_types", freeze_value(list(self.supported_semantic_types)))
        for st in self.supported_semantic_types:
            if not isinstance(st, ArtifactSemanticType):
                raise ValueError("each supported_semantic_type must be an ArtifactSemanticType value")
        object.__setattr__(self, "max_size_bytes", require_positive_int(self.max_size_bytes, "max_size_bytes"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
