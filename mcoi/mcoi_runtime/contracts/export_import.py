"""Purpose: canonical export/import contracts for platform portability.
Governance scope: export manifest, import validation, and artifact bundle typing.
Dependencies: shared contract base helpers.
Invariants:
  - Exports are deterministic for identical inputs.
  - Imports validate integrity before applying.
  - No silent data loss during export or import.
  - Artifact provenance is preserved through export/import cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class ExportFormat(StrEnum):
    JSON_BUNDLE = "json_bundle"


class ImportStatus(StrEnum):
    VALID = "valid"
    INVALID_MANIFEST = "invalid_manifest"
    MISSING_ARTIFACTS = "missing_artifacts"
    VERSION_MISMATCH = "version_mismatch"
    INTEGRITY_FAILURE = "integrity_failure"


class ArtifactType(StrEnum):
    RUNBOOK = "runbook"
    TRACE = "trace"
    REPLAY = "replay"
    SNAPSHOT = "snapshot"
    SKILL_RECORD = "skill_record"
    TELEMETRY_SNAPSHOT = "telemetry_snapshot"
    CONFIG = "config"


@dataclass(frozen=True, slots=True)
class ExportArtifactRef(ContractRecord):
    """Reference to one artifact included in an export bundle."""

    artifact_id: str
    artifact_type: ArtifactType
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.artifact_type, ArtifactType):
            raise ValueError("artifact_type must be an ArtifactType value")
        object.__setattr__(self, "content_hash", require_non_empty_text(self.content_hash, "content_hash"))


@dataclass(frozen=True, slots=True)
class ExportManifest(ContractRecord):
    """Manifest describing an export bundle's contents and integrity."""

    manifest_id: str
    platform_version: str
    exported_at: str
    format: ExportFormat
    artifact_count: int
    artifacts: tuple[ExportArtifactRef, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "platform_version", require_non_empty_text(self.platform_version, "platform_version"))
        object.__setattr__(self, "exported_at", require_non_empty_text(self.exported_at, "exported_at"))
        if not isinstance(self.format, ExportFormat):
            raise ValueError("format must be an ExportFormat value")
        if not isinstance(self.artifact_count, int) or self.artifact_count < 0:
            raise ValueError("artifact_count must be a non-negative integer")
        object.__setattr__(self, "artifacts", freeze_value(list(self.artifacts)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ImportValidationResult(ContractRecord):
    """Result of validating an import bundle before applying."""

    status: ImportStatus
    manifest_id: str | None = None
    expected_count: int = 0
    found_count: int = 0
    missing_ids: tuple[str, ...] = ()
    integrity_failures: tuple[str, ...] = ()
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ImportStatus):
            raise ValueError("status must be an ImportStatus value")
        object.__setattr__(self, "missing_ids", freeze_value(list(self.missing_ids)))
        object.__setattr__(self, "integrity_failures", freeze_value(list(self.integrity_failures)))

    @property
    def is_valid(self) -> bool:
        return self.status is ImportStatus.VALID
