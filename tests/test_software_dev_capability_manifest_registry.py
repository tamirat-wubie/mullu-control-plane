"""Purpose: verify governed capability manifest admission.

Governance scope: manifest schemas, software-development manifest fixtures,
schema/receipt reference resolution, environment admission, sandbox and rollback
requirements, and production hot-reload denial.
Dependencies: capability manifest registry, capability manifest contracts, and
schema validation helper.
Invariants:
  - Every software-development manifest is schema-valid and registry-admitted locally.
  - Missing policies or schemas reject before admission.
  - Effect-bearing manifests require sandbox and rollback declarations.
  - Production hot reload is blocked for effect-bearing manifests below C6/C7.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from mcoi_runtime.contracts.capability_manifest import CapabilityManifest, CapabilityManifestAdmissionStatus
from mcoi_runtime.core.capability_manifest_registry import CapabilityManifestRegistry
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = ROOT / "capabilities" / "software_dev" / "manifests"
MANIFEST_SCHEMA_PATH = ROOT / "schemas" / "software_dev" / "capability_manifest.schema.json"


def test_software_dev_capability_manifests_are_schema_valid() -> None:
    schema = _load_schema(MANIFEST_SCHEMA_PATH)
    manifest_paths = tuple(sorted(MANIFEST_DIR.glob("*.capability.json")))

    assert len(manifest_paths) == 6
    for manifest_path in manifest_paths:
        payload = _load_json(manifest_path)
        assert _validate_schema_instance(schema, payload) == []
        assert payload["kind"] == "software_dev"
        assert payload["policy_refs"]


def test_capability_manifest_registry_admits_software_dev_directory_locally() -> None:
    registry = CapabilityManifestRegistry(repo_root=ROOT, clock=_clock)
    admissions = registry.admit_directory(MANIFEST_DIR, environment="local")
    read_model = registry.read_model()
    admitted_ids = {admission.capability_id for admission in admissions}

    assert len(admissions) == 6
    assert all(admission.status is CapabilityManifestAdmissionStatus.ADMITTED for admission in admissions)
    assert read_model["manifest_count"] == 6
    assert set(read_model["capability_ids"]) == admitted_ids
    assert registry.get_manifest("software_dev.change.run").effect_bearing is True
    assert registry.get_manifest("software_dev.repo_map.read").effect_bearing is False


def test_capability_manifest_registry_rejects_missing_policy_refs(tmp_path: Path) -> None:
    temp_repo = _make_temp_manifest_repo(_temp_payload("software_dev_change_run.capability.json"), root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    payload = _load_json(manifest_path)
    payload["policy_refs"] = []
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert registry.manifest_count == 0
    assert any("policy_refs" in error for error in admission.errors)


def test_capability_manifest_registry_rejects_unresolved_schema_refs(tmp_path: Path) -> None:
    temp_repo = _make_temp_manifest_repo(_temp_payload("software_dev_change_run.capability.json"), root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    payload = _load_json(manifest_path)
    payload["input_schema_ref"] = "schemas/software_dev/missing.input.schema.json"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert registry.manifest_count == 0
    assert "input_schema_ref_unresolved:schemas/software_dev/missing.input.schema.json" in admission.errors


def test_capability_manifest_registry_blocks_effects_without_sandbox_and_rollback(tmp_path: Path) -> None:
    payload = _temp_payload("software_dev_change_run.capability.json")
    payload["sandbox_required"] = False
    payload["rollback_required"] = False
    temp_repo = _make_temp_manifest_repo(payload, root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="local")

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "effect_bearing_capability_requires_sandbox" in admission.errors
    assert "effect_bearing_capability_requires_rollback" in admission.errors


def test_capability_manifest_contract_rejects_scalar_array_fields() -> None:
    payload = _temp_payload("software_dev_change_run.capability.json")
    payload["allowed_environments"] = "local"

    try:
        CapabilityManifest.from_mapping(payload)
    except ValueError as exc:
        assert "allowed_environments must be an array" in str(exc)
        assert "policy_refs" not in str(exc)
        assert "evidence_refs" not in str(exc)
    else:
        raise AssertionError("scalar allowed_environments must be rejected")


def test_capability_manifest_registry_blocks_production_hot_reload_for_effects(tmp_path: Path) -> None:
    payload = _temp_payload("software_dev_change_run.capability.json")
    payload["allowed_environments"] = ["local", "pilot", "production"]
    temp_repo = _make_temp_manifest_repo(payload, root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="production", hot_reload=True)

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "production_hot_reload_denied_for_effect_bearing_capability" in admission.errors
    assert "production_environment_requires_C6_or_C7_maturity" in admission.errors


def test_capability_manifest_registry_enforces_hot_reload_metadata_environment(
    tmp_path: Path,
) -> None:
    payload = _temp_payload("software_dev_change_run.capability.json")
    payload["allowed_environments"] = ["local", "pilot", "production"]
    payload["maturity"] = "C6"
    payload["effect_bearing"] = False
    payload["sandbox_required"] = False
    payload["rollback_required"] = False
    payload["metadata"]["hot_reload_allowed_environments"] = ["local", "pilot"]
    payload["metadata"]["production_hot_reload_allowed"] = False
    temp_repo = _make_temp_manifest_repo(payload, root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="production", hot_reload=True)

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "hot_reload_environment_not_allowed:production" in admission.errors
    assert "production_hot_reload_denied_by_manifest_metadata" in admission.errors
    assert registry.manifest_count == 0


def test_capability_manifest_registry_requires_hot_reload_metadata(
    tmp_path: Path,
) -> None:
    payload = _temp_payload("software_dev_change_run.capability.json")
    payload["metadata"].pop("hot_reload_allowed_environments")
    temp_repo = _make_temp_manifest_repo(payload, root=tmp_path)
    manifest_path = temp_repo / "capabilities" / "software_dev" / "manifests" / "software_dev_change_run.capability.json"
    registry = CapabilityManifestRegistry(repo_root=temp_repo, clock=_clock)

    admission = registry.admit_path(manifest_path, environment="local", hot_reload=True)

    assert admission.status is CapabilityManifestAdmissionStatus.REJECTED
    assert "hot_reload_allowed_environments_required" in admission.errors
    assert registry.manifest_count == 0


def _clock() -> str:
    return "2026-05-13T00:00:00+00:00"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _temp_payload(name: str) -> dict:
    return deepcopy(_load_json(MANIFEST_DIR / name))


def _make_temp_manifest_repo(payload: dict, *, root: Path) -> Path:
    temp_repo = root
    manifest_dir = temp_repo / "capabilities" / "software_dev" / "manifests"
    schema_dir = temp_repo / "schemas" / "software_dev"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{payload['capability_id'].replace('.', '_')}.capability.json"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (schema_dir / "change_run.input.schema.json").write_text(
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}) + "\n",
        encoding="utf-8",
    )
    (schema_dir / "software_change_receipt.output.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "urn:mullusi:schema:software-change-receipt:1",
                "type": "object",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return temp_repo
