"""Purpose: export/import engine — bundle, validate, and restore platform artifacts.
Governance scope: export/import orchestration only.
Dependencies: export/import contracts, persistence serialization, invariant helpers.
Invariants:
  - Exports produce deterministic bundles with integrity hashes.
  - Imports validate manifests and hashes before applying.
  - No silent data loss or corruption.
  - Provenance is preserved through export/import cycles.
"""

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.export_import import (
    ArtifactType,
    ExportArtifactRef,
    ExportFormat,
    ExportManifest,
    ImportStatus,
    ImportValidationResult,
)
from .invariants import ensure_non_empty_text, stable_identifier


PLATFORM_VERSION = "0.1.0"


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _bounded_bundle_read_error(exc: Exception) -> str:
    """Return a stable bundle-read failure without raw filesystem detail."""
    return f"cannot read bundle ({type(exc).__name__})"


class ExportEngine:
    """Exports platform artifacts to a JSON bundle with manifest."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    def export_bundle(
        self,
        *,
        artifacts: Mapping[str, tuple[ArtifactType, str]],
        output_path: Path,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExportManifest:
        """Export artifacts to a JSON bundle file.

        Args:
            artifacts: Mapping of artifact_id -> (artifact_type, json_content)
            output_path: Path to write the bundle
            metadata: Optional metadata to include in manifest
        """
        refs: list[ExportArtifactRef] = []
        bundle_data: dict[str, Any] = {}

        for artifact_id, (artifact_type, content) in sorted(artifacts.items()):
            ensure_non_empty_text("artifact_id", artifact_id)
            parsed = json.loads(content)
            # Normalize to canonical form for deterministic hashing
            normalized = json.dumps(parsed, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            content_hash = _content_hash(normalized)
            refs.append(ExportArtifactRef(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                content_hash=content_hash,
            ))
            bundle_data[artifact_id] = {
                "type": artifact_type.value,
                "content_hash": content_hash,
                "data": parsed,
            }

        manifest_id = stable_identifier("export", {
            "artifact_count": len(artifacts),
            "exported_at": self._clock(),
        })

        manifest = ExportManifest(
            manifest_id=manifest_id,
            platform_version=PLATFORM_VERSION,
            exported_at=self._clock(),
            format=ExportFormat.JSON_BUNDLE,
            artifact_count=len(artifacts),
            artifacts=tuple(refs),
            metadata=metadata or {},
        )

        # Build final bundle
        full_bundle = {
            "manifest": {
                "manifest_id": manifest.manifest_id,
                "platform_version": manifest.platform_version,
                "exported_at": manifest.exported_at,
                "format": manifest.format.value,
                "artifact_count": manifest.artifact_count,
                "artifacts": [
                    {"artifact_id": r.artifact_id, "artifact_type": r.artifact_type.value, "content_hash": r.content_hash}
                    for r in refs
                ],
            },
            "artifacts": bundle_data,
        }

        # Atomic write
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(output_path.parent), suffix=".tmp")
        try:
            content = json.dumps(full_bundle, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(output_path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return manifest


class ImportEngine:
    """Validates and loads platform artifact bundles."""

    def validate_bundle(self, bundle_path: Path) -> ImportValidationResult:
        """Validate a bundle file without applying it."""
        if not bundle_path.exists():
            return ImportValidationResult(
                status=ImportStatus.MISSING_ARTIFACTS,
                error_message="bundle file not found",
            )

        try:
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ImportValidationResult(
                status=ImportStatus.INVALID_MANIFEST,
                error_message=_bounded_bundle_read_error(exc),
            )

        if not isinstance(raw, dict) or "manifest" not in raw or "artifacts" not in raw:
            return ImportValidationResult(
                status=ImportStatus.INVALID_MANIFEST,
                error_message="bundle missing manifest or artifacts section",
            )

        manifest = raw["manifest"]
        artifacts = raw["artifacts"]

        manifest_id = manifest.get("manifest_id")
        expected_count = manifest.get("artifact_count", 0)
        declared_artifacts = manifest.get("artifacts", [])

        # Check version
        bundle_version = manifest.get("platform_version", "")
        if bundle_version != PLATFORM_VERSION:
            return ImportValidationResult(
                status=ImportStatus.VERSION_MISMATCH,
                manifest_id=manifest_id,
                expected_count=expected_count,
                found_count=len(artifacts),
                error_message=f"version mismatch: bundle={bundle_version}, platform={PLATFORM_VERSION}",
            )

        # Check artifact presence and integrity
        missing: list[str] = []
        integrity_failures: list[str] = []

        for ref in declared_artifacts:
            aid = ref.get("artifact_id", "")
            expected_hash = ref.get("content_hash", "")
            if aid not in artifacts:
                missing.append(aid)
                continue
            # Verify content hash
            actual_data = json.dumps(artifacts[aid].get("data", {}), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            actual_hash = _content_hash(actual_data)
            if actual_hash != expected_hash:
                integrity_failures.append(aid)

        if missing:
            return ImportValidationResult(
                status=ImportStatus.MISSING_ARTIFACTS,
                manifest_id=manifest_id,
                expected_count=expected_count,
                found_count=len(artifacts),
                missing_ids=tuple(missing),
            )

        if integrity_failures:
            return ImportValidationResult(
                status=ImportStatus.INTEGRITY_FAILURE,
                manifest_id=manifest_id,
                expected_count=expected_count,
                found_count=len(artifacts),
                integrity_failures=tuple(integrity_failures),
            )

        return ImportValidationResult(
            status=ImportStatus.VALID,
            manifest_id=manifest_id,
            expected_count=expected_count,
            found_count=len(artifacts),
        )

    def load_bundle(self, bundle_path: Path) -> Mapping[str, Any] | None:
        """Load a validated bundle's artifacts. Returns None if validation fails."""
        validation = self.validate_bundle(bundle_path)
        if not validation.is_valid:
            return None

        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        return {
            aid: entry["data"]
            for aid, entry in raw["artifacts"].items()
        }
