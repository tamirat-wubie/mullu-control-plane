"""Purpose: verify strict capability manifest registry ingress contracts.
Governance scope: manifest admission input typing and hot-reload metadata gates.
Dependencies: pytest, JSON manifests, and capability manifest registry contracts.
Invariants: loose manifest ingress values are rejected instead of coerced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.capability_manifest import CapabilityManifestAdmissionStatus
from mcoi_runtime.core.capability_manifest_registry import CapabilityManifestRegistry


def test_registry_rejects_non_text_environment_without_admitting_manifest(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(tmp_path)
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment=7)  # type: ignore[arg-type]

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert admission.environment == "unknown"
    assert "manifest_parse_error:environment must be a non-empty string" in admission.errors
    assert registry.manifest_count == 0


def test_registry_does_not_coerce_malformed_capability_id_into_rejection(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(tmp_path, capability_id=123)
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert admission.capability_id == "unknown"
    assert any("manifest_parse_error:" in error for error in admission.errors)
    assert registry.manifest_count == 0


def test_hot_reload_metadata_rejects_non_text_allowed_environment(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "hot_reload_allowed_environments": ["local", 3],
            "production_hot_reload_allowed": False,
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local", hot_reload=True)

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "hot_reload_allowed_environments_invalid:1" in admission.errors
    assert "hot_reload_environment_not_allowed:local" not in admission.errors
    assert registry.manifest_count == 0


def test_hot_reload_metadata_accepts_text_allowed_environment(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "hot_reload_allowed_environments": [" local "],
            "production_hot_reload_allowed": False,
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local", hot_reload=True)

    assert admission.status is CapabilityManifestAdmissionStatus.ADMITTED
    assert admission.capability_id == "sample.read"
    assert admission.errors == ()
    assert registry.manifest_count == 1


def test_registry_reports_malformed_schema_inventory_without_payload_leak(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest_repo(tmp_path)
    (tmp_path / "schemas" / "broken.schema.json").write_text(
        "{secret-schema-payload",
        encoding="utf-8",
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert admission.capability_id == "sample.read"
    assert admission.errors == (
        "manifest_validation_error:schema_registry_malformed:schemas/broken.schema.json",
    )
    assert "secret-schema-payload" not in repr(admission)
    assert registry.manifest_count == 0


def test_repair_template_metadata_accepts_registered_template_binding(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "file",
            "causal_repair_template_action_type": "edit",
            "causal_repair_effect_class": "internal_versioned",
            "causal_repair_reversibility_class": "version_restore",
            "causal_repair_snapshot_quality": 3,
            "causal_repair_template_evidence": [
                "before_hash",
                "version_id",
                "restore_pointer",
            ],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.ADMITTED
    assert admission.errors == ()
    assert admission.manifest is not None
    assert admission.manifest.metadata["causal_repair_template_domain"] == "file"
    assert registry.manifest_count == 1


def test_repair_template_metadata_rejects_missing_action_type(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "file",
            "causal_repair_template_evidence": [
                "before_hash",
                "version_id",
                "restore_pointer",
            ],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "causal_repair_template_action_type_required" in admission.errors
    assert admission.manifest is None
    assert registry.manifest_count == 0


def test_repair_template_metadata_rejects_unknown_template(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "calendar",
            "causal_repair_template_action_type": "delete_event",
            "causal_repair_template_evidence": ["event_id"],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "causal_repair_template_unknown:calendar.delete_event" in admission.errors
    assert admission.capability_id == "sample.read"
    assert registry.manifest_count == 0


def test_repair_template_metadata_rejects_snapshot_below_template_minimum(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "file",
            "causal_repair_template_action_type": "edit",
            "causal_repair_effect_class": "internal_versioned",
            "causal_repair_reversibility_class": "version_restore",
            "causal_repair_snapshot_quality": 2,
            "causal_repair_template_evidence": [
                "before_hash",
                "version_id",
                "restore_pointer",
            ],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "causal_repair_snapshot_quality_below_template_minimum" in admission.errors
    assert "causal_repair_template_evidence_missing:version_id,restore_pointer" not in admission.errors
    assert registry.manifest_count == 0


def test_repair_template_metadata_rejects_missing_required_template_evidence(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "file",
            "causal_repair_template_action_type": "edit",
            "causal_repair_effect_class": "internal_versioned",
            "causal_repair_reversibility_class": "version_restore",
            "causal_repair_snapshot_quality": 3,
            "causal_repair_template_evidence": ["before_hash"],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert (
        "causal_repair_template_evidence_missing:version_id,restore_pointer"
        in admission.errors
    )
    assert admission.manifest is None
    assert registry.manifest_count == 0


def test_repair_template_metadata_rejects_class_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest_repo(
        tmp_path,
        metadata={
            "causal_repair_template_domain": "file",
            "causal_repair_template_action_type": "edit",
            "causal_repair_effect_class": "user_visible",
            "causal_repair_reversibility_class": "version_restore",
            "causal_repair_snapshot_quality": 3,
            "causal_repair_template_evidence": [
                "before_hash",
                "version_id",
                "restore_pointer",
            ],
        },
    )
    registry = CapabilityManifestRegistry(repo_root=tmp_path, clock=lambda: "2026-05-31T00:00:00Z")

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "causal_repair_effect_class_mismatch" in admission.errors
    assert "causal_repair_reversibility_class_mismatch" not in admission.errors
    assert registry.manifest_count == 0


def _write_manifest_repo(
    repo_root: Path,
    *,
    capability_id: object = "sample.read",
    metadata: dict[str, Any] | None = None,
) -> Path:
    schemas_dir = repo_root / "schemas"
    manifests_dir = repo_root / "capabilities" / "sample" / "manifests"
    tests_dir = repo_root / "tests"
    schemas_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    tests_dir.mkdir()
    (schemas_dir / "sample.input.schema.json").write_text(
        json.dumps({"$id": "urn:mullusi:schema:sample-input:1"}),
        encoding="utf-8",
    )
    (schemas_dir / "sample.output.schema.json").write_text(
        json.dumps({"$id": "urn:mullusi:schema:sample-output:1"}),
        encoding="utf-8",
    )
    (tests_dir / "test_sample_manifest.py").write_text(
        "def test_sample_manifest_evidence():\n    assert True\n",
        encoding="utf-8",
    )
    manifest_payload: dict[str, Any] = {
        "capability_id": capability_id,
        "version": 1,
        "kind": "sample",
        "risk": "low",
        "owner": "platform",
        "input_schema_ref": "schemas/sample.input.schema.json",
        "output_schema_ref": "urn:mullusi:schema:sample-output:1",
        "allowed_environments": ["local"],
        "required_gates": ["unit_tests"],
        "rollback_required": False,
        "sandbox_required": False,
        "effect_bearing": False,
        "maturity": "C6",
        "evidence_refs": ["tests/test_sample_manifest.py"],
        "policy_refs": ["policy://sample/read-only"],
        "receipt_contract_ref": "urn:mullusi:schema:sample-output:1",
        "metadata": metadata if metadata is not None else {},
    }
    manifest_path = manifests_dir / "sample_read.capability.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    return manifest_path
