"""Purpose: verify the fixture-only software-development capability pack.

Governance scope: software-development capability capsule, registry admission,
governed read models, sandbox/approval boundaries, and default-pack isolation.
Dependencies: gateway capability fabric loader and governed capability contracts.
Invariants:
  - Software-development fixtures are not loaded by default.
  - The named software-development loader installs only that domain.
  - Read-only powers do not grant execution or mutation authority.
  - Effectful powers require approval, sandboxing, receipts, and recovery.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.capability_fabric import (
    build_software_dev_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
    load_software_dev_capability_entries,
    load_software_dev_domain_capsule,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
SOFTWARE_DEV_CAPSULE_PATH = ROOT / "capsules" / "software_dev.json"
SOFTWARE_DEV_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "software_dev" / "capability_pack.json"
CAPABILITY_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "capability_registry_entry.schema.json"


def test_software_dev_fixture_pack_is_not_loaded_by_default() -> None:
    default_capsules = load_default_domain_capsules()
    default_capabilities = load_default_capability_entries()

    assert all(capsule.domain != "software_dev" for capsule in default_capsules)
    assert all(entry.domain != "software_dev" for entry in default_capabilities)
    assert SOFTWARE_DEV_CAPSULE_PATH.exists()
    assert SOFTWARE_DEV_CAPABILITY_PACK_PATH.exists()


def test_software_dev_capability_entries_are_schema_valid() -> None:
    schema = _load_schema(CAPABILITY_REGISTRY_SCHEMA_PATH)
    payload = _load_json(SOFTWARE_DEV_CAPABILITY_PACK_PATH)
    entries = payload["capabilities"]

    assert len(entries) == 6
    assert all(_validate_schema_instance(schema, entry) == [] for entry in entries)
    assert all(CapabilityRegistryEntry.from_mapping(entry).domain == "software_dev" for entry in entries)


def test_software_dev_named_loader_installs_only_software_dev_domain() -> None:
    capsule = load_software_dev_domain_capsule()
    entries = load_software_dev_capability_entries()
    gate = _software_dev_gate(require_production_ready=False)
    read_model = gate.read_model()

    assert capsule.domain == "software_dev"
    assert len(entries) == 6
    assert all(entry.domain == "software_dev" for entry in entries)
    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 6
    assert read_model["domains"] == ({"domain": "software_dev", "capability_ids": tuple(sorted(capsule.capability_refs))},)


def test_software_dev_capsule_references_exact_pack_capabilities() -> None:
    capsule = DomainCapsule.from_mapping(_load_json(SOFTWARE_DEV_CAPSULE_PATH))
    capabilities = _software_dev_entries()
    capability_ids = tuple(entry.capability_id for entry in capabilities)

    assert capsule.domain == "software_dev"
    assert capsule.certification_status.value == "certified"
    assert capsule.capability_refs == capability_ids
    assert len(set(capability_ids)) == len(capability_ids)


def test_software_dev_pack_installs_through_explicit_capability_fabric() -> None:
    gate = _software_dev_gate(require_production_ready=False)
    read_model = gate.read_model()
    capabilities = {item["capability_id"]: item for item in read_model["capabilities"]}
    governed = {item["capability_id"]: item for item in read_model["governed_capability_records"]}
    repo_decision = gate.admit(command_id="cmd-repo-map", intent_name="software_dev.repo_map.read")
    change_decision = gate.admit(command_id="cmd-change", intent_name="software_dev.change.run")
    direct_deploy_decision = gate.admit(command_id="cmd-deploy", intent_name="software_dev.deploy.production")

    assert repo_decision.status.value == "accepted"
    assert repo_decision.capability_id == "software_dev.repo_map.read"
    assert change_decision.status.value == "accepted"
    assert change_decision.capability_id == "software_dev.change.run"
    assert direct_deploy_decision.status.value == "rejected"
    assert read_model["capability_count"] == 6
    assert set(capabilities) == set(governed)
    assert read_model["domains"] == ({"domain": "software_dev", "capability_ids": tuple(sorted(capabilities))},)


def test_software_dev_governed_records_bind_read_and_effect_boundaries() -> None:
    gate = _software_dev_gate(require_production_ready=False)
    governed = {item["capability_id"]: item for item in gate.read_model()["governed_capability_records"]}
    repo_record = governed["software_dev.repo_map.read"]
    change_record = governed["software_dev.change.run"]
    pr_record = governed["software_dev.pr_candidate.prepare"]

    assert repo_record["read_only"] is True
    assert repo_record["world_mutating"] is False
    assert repo_record["requires_approval"] is False
    assert repo_record["requires_sandbox"] is False
    assert repo_record["allowed_tools"] == ["code_intelligence.build_repo_map"]
    assert change_record["read_only"] is False
    assert change_record["world_mutating"] is True
    assert change_record["requires_approval"] is True
    assert change_record["requires_sandbox"] is True
    assert change_record["rollback_or_compensation_required"] is True
    assert change_record["allowed_networks"] == []
    assert "production_deployment_started" in change_record["forbidden_effects"]
    assert pr_record["requires_approval"] is True
    assert pr_record["requires_sandbox"] is True
    assert pr_record["allowed_networks"] == []
    assert "git_push_executed" in pr_record["forbidden_effects"]


def test_software_dev_pack_blocks_production_ready_overclaim() -> None:
    gate = _software_dev_gate(require_production_ready=True)
    change_decision = gate.admit(command_id="cmd-change-prod", intent_name="software_dev.change.run")
    repo_decision = gate.admit(command_id="cmd-repo-prod", intent_name="software_dev.repo_map.read")

    assert change_decision.status.value == "rejected"
    assert change_decision.capability_id == "software_dev.change.run"
    assert "capability is not production-ready" in change_decision.reason
    assert "effect_bearing_production_requires_live_write" in change_decision.reason
    assert repo_decision.status.value == "rejected"
    assert repo_decision.capability_id == "software_dev.repo_map.read"
    assert "capability is not production-ready" in repo_decision.reason


def _software_dev_gate(*, require_production_ready: bool):
    return build_software_dev_capability_admission_gate(
        clock=lambda: "2026-05-13T00:00:00+00:00",
        require_production_ready=require_production_ready,
    )


def _software_dev_entries() -> tuple[CapabilityRegistryEntry, ...]:
    return tuple(
        CapabilityRegistryEntry.from_mapping(item)
        for item in _load_json(SOFTWARE_DEV_CAPABILITY_PACK_PATH)["capabilities"]
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
