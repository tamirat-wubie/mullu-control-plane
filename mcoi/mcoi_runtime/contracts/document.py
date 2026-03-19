"""Purpose: canonical document automation contract mapping.
Governance scope: document descriptor, content, fingerprint, extraction, and verification typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every document carries explicit identity and deterministic fingerprint.
  - Extraction fields are typed and bounded.
  - Verification compares extracted fields against expectations explicitly.
  - No fabricated extraction — missing fields are explicit, not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class DocumentFormat(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
    UNKNOWN = "unknown"


class ExtractionStatus(StrEnum):
    EXTRACTED = "extracted"
    MISSING = "missing"
    MALFORMED = "malformed"


class DocumentVerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class DocumentFingerprint(ContractRecord):
    """Deterministic content fingerprint for a document."""

    fingerprint_id: str
    document_id: str
    content_hash: str
    byte_length: int
    line_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint_id", require_non_empty_text(self.fingerprint_id, "fingerprint_id"))
        object.__setattr__(self, "document_id", require_non_empty_text(self.document_id, "document_id"))
        object.__setattr__(self, "content_hash", require_non_empty_text(self.content_hash, "content_hash"))
        if not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ValueError("byte_length must be a non-negative integer")
        if not isinstance(self.line_count, int) or self.line_count < 0:
            raise ValueError("line_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class DocumentContent(ContractRecord):
    """Raw loaded content of a document."""

    document_id: str
    format: DocumentFormat
    text: str
    source_path: str
    fingerprint: DocumentFingerprint

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", require_non_empty_text(self.document_id, "document_id"))
        if not isinstance(self.format, DocumentFormat):
            raise ValueError("format must be a DocumentFormat value")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        object.__setattr__(self, "source_path", require_non_empty_text(self.source_path, "source_path"))
        if not isinstance(self.fingerprint, DocumentFingerprint):
            raise ValueError("fingerprint must be a DocumentFingerprint instance")


@dataclass(frozen=True, slots=True)
class DocumentDescriptor(ContractRecord):
    """Identity and metadata for a registered document."""

    document_id: str
    name: str
    format: DocumentFormat
    source_path: str
    fingerprint: DocumentFingerprint
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", require_non_empty_text(self.document_id, "document_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.format, DocumentFormat):
            raise ValueError("format must be a DocumentFormat value")
        object.__setattr__(self, "source_path", require_non_empty_text(self.source_path, "source_path"))
        if not isinstance(self.fingerprint, DocumentFingerprint):
            raise ValueError("fingerprint must be a DocumentFingerprint instance")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ExtractionField(ContractRecord):
    """One extracted field from a document."""

    field_name: str
    status: ExtractionStatus
    value: Any = None
    line_number: int | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        if not isinstance(self.status, ExtractionStatus):
            raise ValueError("status must be an ExtractionStatus value")
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "value", freeze_value(self.value))


@dataclass(frozen=True, slots=True)
class ExtractionResult(ContractRecord):
    """Result of extracting typed fields from a document."""

    extraction_id: str
    document_id: str
    fields: tuple[ExtractionField, ...]
    extracted_count: int
    missing_count: int
    malformed_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "extraction_id", require_non_empty_text(self.extraction_id, "extraction_id"))
        object.__setattr__(self, "document_id", require_non_empty_text(self.document_id, "document_id"))
        object.__setattr__(self, "fields", freeze_value(list(self.fields)))
        if not isinstance(self.extracted_count, int) or self.extracted_count < 0:
            raise ValueError("extracted_count must be a non-negative integer")
        if not isinstance(self.missing_count, int) or self.missing_count < 0:
            raise ValueError("missing_count must be a non-negative integer")
        if not isinstance(self.malformed_count, int) or self.malformed_count < 0:
            raise ValueError("malformed_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class DocumentVerificationResult(ContractRecord):
    """Result of verifying extracted fields against expectations."""

    verification_id: str
    document_id: str
    extraction_id: str
    status: DocumentVerificationStatus
    expected_fields: tuple[str, ...]
    matched_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "document_id", require_non_empty_text(self.document_id, "document_id"))
        object.__setattr__(self, "extraction_id", require_non_empty_text(self.extraction_id, "extraction_id"))
        if not isinstance(self.status, DocumentVerificationStatus):
            raise ValueError("status must be a DocumentVerificationStatus value")
        object.__setattr__(self, "expected_fields", freeze_value(list(self.expected_fields)))
        object.__setattr__(self, "matched_fields", freeze_value(list(self.matched_fields)))
        object.__setattr__(self, "missing_fields", freeze_value(list(self.missing_fields)))
        object.__setattr__(self, "mismatched_fields", freeze_value(list(self.mismatched_fields)))
