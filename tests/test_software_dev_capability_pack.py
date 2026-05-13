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

from copy import deepcopy
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
SOFTWARE_DEV_SCHEMA_DIR = ROOT / "schemas" / "software_dev"
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


def test_software_dev_input_schema_refs_are_materialized_and_strict() -> None:
    entries = _software_dev_entries()
    schema_refs = tuple(entry.input_schema_ref for entry in entries)
    output_refs = tuple(entry.output_schema_ref for entry in entries)

    assert len(schema_refs) == 6
    assert all(ref.startswith("schemas/software_dev/") for ref in schema_refs)
    assert all((ROOT / ref).exists() for ref in schema_refs)
    assert all(ref.startswith("urn:mullusi:schema:") for ref in output_refs)
    for ref in schema_refs:
        schema = _load_schema(ROOT / ref)
        assert schema["additionalProperties"] is False
        assert schema["$id"].startswith("urn:mullusi:schema:software-dev:")


def test_software_dev_input_schemas_accept_representative_requests() -> None:
    payloads = _representative_software_dev_schema_payloads()

    assert set(payloads) == {entry.input_schema_ref for entry in _software_dev_entries()}
    for schema_ref, payload in payloads.items():
        schema = _load_schema(ROOT / schema_ref)
        assert _validate_schema_instance(schema, payload) == []
        assert payload["capability_id"].startswith("software_dev.")
        assert payload["metadata"]["fixture"] == "software_dev_capability_pack"


def test_software_dev_input_schemas_reject_boundary_violations() -> None:
    payloads = _representative_software_dev_schema_payloads()
    context_payload = deepcopy(payloads["schemas/software_dev/context_bundle.input.schema.json"])
    change_payload = deepcopy(payloads["schemas/software_dev/change_run.input.schema.json"])
    pr_payload = deepcopy(payloads["schemas/software_dev/pr_candidate.input.schema.json"])

    context_payload["affected_files"] = ["../secrets.py"]
    change_payload["command_policy"]["network_allowed"] = True
    pr_payload["local_git_push_allowed"] = True

    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "context_bundle.input.schema.json"),
        context_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "change_run.input.schema.json"),
        change_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "pr_candidate.input.schema.json"),
        pr_payload,
    )


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


def _representative_software_dev_schema_payloads() -> dict[str, dict]:
    metadata = {"fixture": "software_dev_capability_pack"}
    return {
        "schemas/software_dev/repo_map_read.input.schema.json": {
            "capability_id": "software_dev.repo_map.read",
            "request_id": "req-repo-map",
            "repository_ref": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "workspace_ref": "workspace:local-sandbox",
            "include_patterns": ["mcoi/**/*.py", "tests/**/*.py"],
            "exclude_patterns": [".tmp_test_outputs/**"],
            "max_file_count": 5000,
            "metadata": metadata,
        },
        "schemas/software_dev/context_bundle.input.schema.json": {
            "capability_id": "software_dev.context_bundle.build",
            "request_id": "req-context",
            "repository_ref": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "repo_map_ref": "repo-map:abc123",
            "task_summary": "Add governed schema coverage for software-dev capability inputs",
            "affected_files": ["tests/test_software_dev_capability_pack.py"],
            "acceptance_criteria": ["schema refs resolve", "boundary violations reject", "pack stays explicit"],
            "max_symbol_count": 40,
            "max_test_count": 20,
            "max_dependency_edges": 60,
            "target_model": "coding",
            "metadata": metadata,
        },
        "schemas/software_dev/gate_plan.input.schema.json": {
            "capability_id": "software_dev.gate_plan.select",
            "request_id": "req-gates",
            "repository_ref": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "repo_map_ref": "repo-map:abc123",
            "work_kind": "feature",
            "mode": "patch_test_review",
            "summary": "Plan validation gates for software-dev schema contracts",
            "affected_files": ["schemas/software_dev/change_run.input.schema.json"],
            "acceptance_criteria": ["schemas are valid", "tests pass", "proof matrix remains current"],
            "quality_gates": ["unit_tests", "lint", "security_scan"],
            "blast_radius": "module",
            "rollback_required": True,
            "reviewer_required": True,
            "metadata": metadata,
        },
        "schemas/software_dev/change_run.input.schema.json": {
            "capability_id": "software_dev.change.run",
            "request_id": "req-change",
            "software_request_id": "swreq-schema-coverage",
            "repository_ref": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "target_branch": "feature/software-dev-schema-coverage",
            "context_bundle_ref": "context:abc123",
            "gate_plan_ref": "gate-plan:abc123",
            "approval_ref": "approval:developer-reviewer",
            "workspace_snapshot_ref": "snapshot:before-change",
            "rollback_snapshot_ref": "snapshot:rollback",
            "work_kind": "feature",
            "mode": "patch_test_review",
            "summary": "Run governed schema contract update",
            "affected_files": ["schemas/software_dev/change_run.input.schema.json"],
            "acceptance_criteria": ["schemas are strict", "network remains disabled", "rollback evidence is bound"],
            "quality_gates": ["unit_tests", "security_scan", "review"],
            "max_self_debug_iterations": 2,
            "rollback_required": True,
            "sandbox_profile": "workspace_network_none",
            "command_policy": {
                "network_allowed": False,
                "allowed_executables": ["python", "pytest", "ruff", "mypy", "git"],
                "denied_executables": ["sh", "bash", "cmd", "powershell", "curl", "wget"],
                "denied_git_subcommands": ["push", "pull", "fetch", "clone", "remote", "submodule", "credential"],
                "max_timeout_seconds": 300,
                "max_output_bytes": 1048576,
            },
            "metadata": metadata,
        },
        "schemas/software_dev/app_task_graph.input.schema.json": {
            "capability_id": "software_dev.app_task_graph.plan",
            "request_id": "req-app-graph",
            "repository_ref": "repo:invoice-service",
            "target_branch": "feature/invoice-dashboard",
            "product_spec": {
                "app_name": "Invoice Dashboard",
                "users": ["finance operator", "accounting manager"],
                "jobs_to_be_done": ["review invoices", "flag overdue invoices"],
                "core_flows": ["list invoices", "create invoice", "mark invoice paid"],
                "non_goals": ["production deployment", "payment processing"],
                "security_requirements": ["tenant scoped access", "role based approval"],
            },
            "max_task_count": 12,
            "direct_deployment_allowed": False,
            "commit_candidate_allowed": False,
            "metadata": metadata,
        },
        "schemas/software_dev/pr_candidate.input.schema.json": {
            "capability_id": "software_dev.pr_candidate.prepare",
            "request_id": "req-pr-candidate",
            "repository_ref": "repo:invoice-service",
            "base_branch": "main",
            "candidate_branch": "mullu/app-builder-invoice-dashboard-abc123",
            "title": "Invoice Dashboard governed candidate",
            "app_task_graph_ref": "app-task-graph:invoice-dashboard",
            "software_receipt_refs": ["software-change:receipt-1"],
            "quality_gate_refs": ["gate-plan:abc123"],
            "approval_request_ref": "approval:pr-open-review",
            "local_git_push_allowed": False,
            "open_pull_request_allowed": False,
            "production_deployment_allowed": False,
            "metadata": metadata,
        },
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
