"""Purpose: artifact parser contracts.
Governance scope: typed descriptors, capability manifests, parse outputs,
    health reports, and policy constraints for artifact parser families.
Dependencies: _base contract utilities.
Invariants:
  - Every parser declares its family, supported formats, and capability manifest.
  - All outputs are frozen and immutable.
  - Reliability scores are unit floats [0.0, 1.0].
  - Size constraints are non-negative integers.
  - Failure modes are explicitly enumerated per parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ParserFamily(Enum):
    """High-level parser family classification."""
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    IMAGE = "image"
    AUDIO = "audio"
    ARCHIVE = "archive"
    REPOSITORY = "repository"
    PLAINTEXT = "plaintext"


class ParserStatus(Enum):
    """Operational status of a parser instance."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class ParseOutputKind(Enum):
    """What kind of structured output the parser produces."""
    TEXT = "text"
    TABLE = "table"
    KEY_VALUE = "key_value"
    TREE = "tree"
    METADATA_ONLY = "metadata_only"
    BINARY_DESCRIPTOR = "binary_descriptor"


class ParserCapabilityLevel(Enum):
    """Depth of parsing capability."""
    METADATA = "metadata"
    STRUCTURE = "structure"
    FULL_CONTENT = "full_content"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParseCapability(ContractRecord):
    """Describes a specific format this parser can handle."""

    format_name: str = ""
    extensions: tuple[str, ...] = ()
    mime_types: tuple[str, ...] = ()
    capability_level: ParserCapabilityLevel = ParserCapabilityLevel.FULL_CONTENT
    max_size_bytes: int = 0
    output_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "format_name",
            require_non_empty_text(self.format_name, "format_name"),
        )
        object.__setattr__(
            self, "extensions",
            freeze_value(list(self.extensions)),
        )
        object.__setattr__(
            self, "mime_types",
            freeze_value(list(self.mime_types)),
        )
        if not isinstance(self.capability_level, ParserCapabilityLevel):
            raise ValueError("capability_level must be a ParserCapabilityLevel")
        object.__setattr__(
            self, "max_size_bytes",
            require_non_negative_int(self.max_size_bytes, "max_size_bytes"),
        )
        object.__setattr__(
            self, "output_kinds",
            freeze_value(list(self.output_kinds)),
        )


@dataclass(frozen=True, slots=True)
class ParserPolicyConstraint(ContractRecord):
    """Policy constraint governing parser behavior."""

    constraint_id: str = ""
    description: str = ""
    constraint_type: str = ""
    value: str = ""
    enforced: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "constraint_id",
            require_non_empty_text(self.constraint_id, "constraint_id"),
        )
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(
            self, "constraint_type",
            require_non_empty_text(self.constraint_type, "constraint_type"),
        )


@dataclass(frozen=True, slots=True)
class ParserFailureMode(ContractRecord):
    """Describes a known failure mode for a parser."""

    mode_id: str = ""
    description: str = ""
    severity: str = "medium"
    is_recoverable: bool = True
    recommended_action: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mode_id",
            require_non_empty_text(self.mode_id, "mode_id"),
        )
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError("severity must be low, medium, high, or critical")


@dataclass(frozen=True, slots=True)
class ParserCapabilityManifest(ContractRecord):
    """Full capability manifest for an artifact parser.

    Exposes supported formats, limits, policy constraints,
    reliability score, and known failure modes.
    """

    manifest_id: str = ""
    parser_id: str = ""
    family: ParserFamily = ParserFamily.PLAINTEXT
    capabilities: tuple[ParseCapability, ...] = ()
    max_concurrent_parses: int = 1
    supports_streaming: bool = False
    supports_incremental: bool = False
    policy_constraints: tuple[ParserPolicyConstraint, ...] = ()
    failure_modes: tuple[ParserFailureMode, ...] = ()
    reliability_score: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manifest_id",
            require_non_empty_text(self.manifest_id, "manifest_id"),
        )
        object.__setattr__(
            self, "parser_id",
            require_non_empty_text(self.parser_id, "parser_id"),
        )
        if not isinstance(self.family, ParserFamily):
            raise ValueError("family must be a ParserFamily")
        object.__setattr__(
            self, "capabilities",
            freeze_value(list(self.capabilities)),
        )
        object.__setattr__(
            self, "policy_constraints",
            freeze_value(list(self.policy_constraints)),
        )
        object.__setattr__(
            self, "failure_modes",
            freeze_value(list(self.failure_modes)),
        )
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ArtifactParserDescriptor(ContractRecord):
    """Canonical descriptor for a registered artifact parser."""

    parser_id: str = ""
    name: str = ""
    family: ParserFamily = ParserFamily.PLAINTEXT
    status: ParserStatus = ParserStatus.AVAILABLE
    version: str = "1.0.0"
    manifest_id: str = ""
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parser_id",
            require_non_empty_text(self.parser_id, "parser_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.family, ParserFamily):
            raise ValueError("family must be a ParserFamily")
        if not isinstance(self.status, ParserStatus):
            raise ValueError("status must be a ParserStatus")
        object.__setattr__(
            self, "version",
            require_non_empty_text(self.version, "version"),
        )
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class NormalizedParseOutput(ContractRecord):
    """Structured output from a parser after processing an artifact."""

    output_id: str = ""
    parser_id: str = ""
    artifact_id: str = ""
    family: ParserFamily = ParserFamily.PLAINTEXT
    output_kind: ParseOutputKind = ParseOutputKind.TEXT
    text_content: str = ""
    structured_data: Mapping[str, Any] = field(default_factory=dict)
    tables: tuple[Mapping[str, Any], ...] = ()
    page_count: int = 0
    word_count: int = 0
    has_images: bool = False
    has_tables: bool = False
    language_hint: str = ""
    extracted_metadata: Mapping[str, Any] = field(default_factory=dict)
    parsed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "output_id",
            require_non_empty_text(self.output_id, "output_id"),
        )
        object.__setattr__(
            self, "parser_id",
            require_non_empty_text(self.parser_id, "parser_id"),
        )
        object.__setattr__(
            self, "artifact_id",
            require_non_empty_text(self.artifact_id, "artifact_id"),
        )
        if not isinstance(self.family, ParserFamily):
            raise ValueError("family must be a ParserFamily")
        if not isinstance(self.output_kind, ParseOutputKind):
            raise ValueError("output_kind must be a ParseOutputKind")
        object.__setattr__(
            self, "page_count",
            require_non_negative_int(self.page_count, "page_count"),
        )
        object.__setattr__(
            self, "word_count",
            require_non_negative_int(self.word_count, "word_count"),
        )
        object.__setattr__(
            self, "structured_data",
            freeze_value(dict(self.structured_data)),
        )
        object.__setattr__(
            self, "tables",
            freeze_value(list(self.tables)),
        )
        object.__setattr__(
            self, "extracted_metadata",
            freeze_value(dict(self.extracted_metadata)),
        )
        require_datetime_text(self.parsed_at, "parsed_at")


@dataclass(frozen=True, slots=True)
class ParserHealthReport(ContractRecord):
    """Point-in-time health report for an artifact parser."""

    report_id: str = ""
    parser_id: str = ""
    status: ParserStatus = ParserStatus.AVAILABLE
    reliability_score: float = 1.0
    artifacts_parsed: int = 0
    artifacts_failed: int = 0
    avg_parse_ms: float = 0.0
    active_failure_modes: tuple[str, ...] = ()
    reported_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "report_id",
            require_non_empty_text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self, "parser_id",
            require_non_empty_text(self.parser_id, "parser_id"),
        )
        if not isinstance(self.status, ParserStatus):
            raise ValueError("status must be a ParserStatus")
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        object.__setattr__(
            self, "artifacts_parsed",
            require_non_negative_int(self.artifacts_parsed, "artifacts_parsed"),
        )
        object.__setattr__(
            self, "artifacts_failed",
            require_non_negative_int(self.artifacts_failed, "artifacts_failed"),
        )
        object.__setattr__(
            self, "active_failure_modes",
            freeze_value(list(self.active_failure_modes)),
        )
        require_datetime_text(self.reported_at, "reported_at")
