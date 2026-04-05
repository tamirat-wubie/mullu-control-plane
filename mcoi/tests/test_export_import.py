"""Tests for export/import engine and deployment profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.export_import import (
    ArtifactType,
    ExportArtifactRef,
    ExportFormat,
    ExportManifest,
    ImportStatus,
    ImportValidationResult,
)
from mcoi_runtime.core.export_import import ExportEngine, ImportEngine
from mcoi_runtime.app.deployment_profiles import (
    BUILTIN_PROFILES,
    DeploymentProfile,
    LOCAL_DEV,
    OPERATOR_APPROVED,
    PILOT_PROD,
    SAFE_READONLY,
    SANDBOXED,
    get_profile,
    list_profiles,
)


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


# --- Export contracts ---


class TestExportContracts:
    def test_artifact_ref(self):
        ref = ExportArtifactRef(
            artifact_id="rb-1",
            artifact_type=ArtifactType.RUNBOOK,
            content_hash="abc123",
        )
        assert ref.artifact_type is ArtifactType.RUNBOOK

    def test_manifest(self):
        m = ExportManifest(
            manifest_id="exp-1",
            platform_version="0.1.0",
            exported_at=FIXED_CLOCK,
            format=ExportFormat.JSON_BUNDLE,
            artifact_count=3,
        )
        assert m.artifact_count == 3

    def test_import_valid(self):
        r = ImportValidationResult(status=ImportStatus.VALID, expected_count=2, found_count=2)
        assert r.is_valid

    def test_import_invalid(self):
        r = ImportValidationResult(status=ImportStatus.MISSING_ARTIFACTS, missing_ids=("x",))
        assert not r.is_valid


# --- Export engine ---


class TestExportEngine:
    def test_export_creates_bundle(self, tmp_path: Path):
        engine = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {
            "rb-1": (ArtifactType.RUNBOOK, json.dumps({"name": "backup"})),
            "trace-1": (ArtifactType.TRACE, json.dumps({"entry": "test"})),
        }
        bundle_path = tmp_path / "export.json"
        manifest = engine.export_bundle(artifacts=artifacts, output_path=bundle_path)

        assert manifest.artifact_count == 2
        assert manifest.format is ExportFormat.JSON_BUNDLE
        assert bundle_path.exists()

    def test_export_bundle_is_valid_json(self, tmp_path: Path):
        engine = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {"a": (ArtifactType.CONFIG, json.dumps({"key": "val"}))}
        bundle_path = tmp_path / "export.json"
        engine.export_bundle(artifacts=artifacts, output_path=bundle_path)

        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert "manifest" in raw
        assert "artifacts" in raw

    def test_export_manifest_has_hashes(self, tmp_path: Path):
        engine = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {"x": (ArtifactType.RUNBOOK, json.dumps({"data": 42}))}
        bundle_path = tmp_path / "export.json"
        manifest = engine.export_bundle(artifacts=artifacts, output_path=bundle_path)

        assert len(manifest.artifacts) == 1
        assert manifest.artifacts[0].content_hash  # Non-empty hash


# --- Import engine ---


class TestImportEngine:
    def test_validate_valid_bundle(self, tmp_path: Path):
        # Create a valid bundle
        export = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {"rb-1": (ArtifactType.RUNBOOK, json.dumps({"name": "test"}))}
        bundle_path = tmp_path / "bundle.json"
        export.export_bundle(artifacts=artifacts, output_path=bundle_path)

        # Validate
        importer = ImportEngine()
        result = importer.validate_bundle(bundle_path)
        assert result.is_valid
        assert result.expected_count == 1
        assert result.found_count == 1

    def test_validate_missing_file(self, tmp_path: Path):
        importer = ImportEngine()
        result = importer.validate_bundle(tmp_path / "nonexistent.json")
        assert result.status is ImportStatus.MISSING_ARTIFACTS
        assert result.error_message == "bundle file not found"

    def test_validate_malformed_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json!!", encoding="utf-8")
        importer = ImportEngine()
        result = importer.validate_bundle(bad)
        assert result.status is ImportStatus.INVALID_MANIFEST
        assert result.error_message == "cannot read bundle (JSONDecodeError)"
        assert "Expecting value" not in result.error_message

    def test_validate_unreadable_bundle_is_bounded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        original_read_text = Path.read_text

        def crashing_read_text(self: Path, *args, **kwargs):
            if self == bad:
                raise OSError("secret bundle read failure")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", crashing_read_text)

        importer = ImportEngine()
        result = importer.validate_bundle(bad)

        assert result.status is ImportStatus.INVALID_MANIFEST
        assert result.error_message == "cannot read bundle (OSError)"
        assert "secret bundle read failure" not in result.error_message

    def test_validate_missing_manifest_section(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"only": "data"}), encoding="utf-8")
        importer = ImportEngine()
        result = importer.validate_bundle(bad)
        assert result.status is ImportStatus.INVALID_MANIFEST

    def test_validate_integrity_failure(self, tmp_path: Path):
        # Create valid bundle then tamper
        export = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {"rb-1": (ArtifactType.RUNBOOK, json.dumps({"name": "test"}))}
        bundle_path = tmp_path / "bundle.json"
        export.export_bundle(artifacts=artifacts, output_path=bundle_path)

        # Tamper with artifact data
        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        raw["artifacts"]["rb-1"]["data"]["name"] = "TAMPERED"
        bundle_path.write_text(json.dumps(raw), encoding="utf-8")

        importer = ImportEngine()
        result = importer.validate_bundle(bundle_path)
        assert result.status is ImportStatus.INTEGRITY_FAILURE
        assert "rb-1" in result.integrity_failures

    def test_load_valid_bundle(self, tmp_path: Path):
        export = ExportEngine(clock=lambda: FIXED_CLOCK)
        artifacts = {
            "rb-1": (ArtifactType.RUNBOOK, json.dumps({"name": "backup"})),
            "t-1": (ArtifactType.TRACE, json.dumps({"entry": "data"})),
        }
        bundle_path = tmp_path / "bundle.json"
        export.export_bundle(artifacts=artifacts, output_path=bundle_path)

        importer = ImportEngine()
        loaded = importer.load_bundle(bundle_path)
        assert loaded is not None
        assert loaded["rb-1"]["name"] == "backup"
        assert loaded["t-1"]["entry"] == "data"

    def test_load_invalid_bundle_returns_none(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("bad", encoding="utf-8")
        importer = ImportEngine()
        assert importer.load_bundle(bad) is None

    def test_round_trip(self, tmp_path: Path):
        """Export then import preserves data exactly."""
        export = ExportEngine(clock=lambda: FIXED_CLOCK)
        original = {"key": "value", "nested": {"a": 1}}
        artifacts = {"cfg-1": (ArtifactType.CONFIG, json.dumps(original))}
        bundle_path = tmp_path / "bundle.json"
        export.export_bundle(artifacts=artifacts, output_path=bundle_path)

        importer = ImportEngine()
        loaded = importer.load_bundle(bundle_path)
        assert loaded["cfg-1"] == original


# --- Deployment profiles ---


class TestDeploymentProfiles:
    def test_local_dev(self):
        assert LOCAL_DEV.autonomy_mode == "bounded_autonomous"
        assert LOCAL_DEV.import_enabled is True
        assert LOCAL_DEV.max_retention_days == 7

    def test_safe_readonly(self):
        assert SAFE_READONLY.autonomy_mode == "observe_only"
        assert SAFE_READONLY.import_enabled is False

    def test_operator_approved(self):
        assert OPERATOR_APPROVED.autonomy_mode == "approval_required"

    def test_sandboxed(self):
        assert SANDBOXED.autonomy_mode == "suggest_only"

    def test_pilot_prod(self):
        assert PILOT_PROD.autonomy_mode == "approval_required"
        assert PILOT_PROD.policy_pack_id == "default-safe"
        assert PILOT_PROD.max_retention_days == 180

    def test_all_builtin_profiles_exist(self):
        assert len(BUILTIN_PROFILES) == 5
        for pid in ("local-dev", "safe-readonly", "operator-approved", "sandboxed", "pilot-prod"):
            assert pid in BUILTIN_PROFILES

    def test_get_profile(self):
        p = get_profile("local-dev")
        assert p is LOCAL_DEV

    def test_get_profile_missing(self):
        assert get_profile("nonexistent") is None

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) == 5
        # Sorted by profile_id
        assert profiles[0].profile_id == "local-dev"

    def test_to_config_dict(self):
        cfg = LOCAL_DEV.to_config_dict()
        assert cfg["autonomy_mode"] == "bounded_autonomous"
        assert "shell_command" in cfg["enabled_executor_routes"]

    def test_empty_profile_id_rejected(self):
        with pytest.raises(ValueError):
            DeploymentProfile(profile_id="", name="x", description="x", autonomy_mode="observe_only")

    def test_no_profile_widens_beyond_mode(self):
        """No built-in profile uses bounded_autonomous except local-dev."""
        for pid, profile in BUILTIN_PROFILES.items():
            if pid != "local-dev":
                assert profile.autonomy_mode != "bounded_autonomous", \
                    f"{pid} should not be bounded_autonomous"
