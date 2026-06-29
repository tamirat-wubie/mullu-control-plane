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
from mcoi_runtime.core.capability_unlock_ladder import (
    UNLOCK_LADDER_ID,
    default_capability_unlock_ladder,
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

    assert len(entries) == 11
    assert all(_validate_schema_instance(schema, entry) == [] for entry in entries)
    assert all(CapabilityRegistryEntry.from_mapping(entry).domain == "software_dev" for entry in entries)


def test_software_dev_input_schema_refs_are_materialized_and_strict() -> None:
    entries = _software_dev_entries()
    schema_refs = tuple(entry.input_schema_ref for entry in entries)
    output_refs = tuple(entry.output_schema_ref for entry in entries)

    assert len(schema_refs) == 11
    assert all(ref.startswith("schemas/software_dev/") for ref in schema_refs)
    assert all((ROOT / ref).exists() for ref in schema_refs)
    assert all(ref.startswith("urn:mullusi:schema:") for ref in output_refs)
    for ref in schema_refs:
        schema = _load_schema(ROOT / ref)
        assert schema["additionalProperties"] is False
        assert schema["$id"].startswith("urn:mullusi:schema:software-dev:")


def test_software_dev_output_schema_refs_are_materialized_and_strict() -> None:
    output_refs = tuple(entry.output_schema_ref for entry in _software_dev_entries())
    schemas_by_id = _software_dev_output_schemas_by_id()

    assert len(output_refs) == 11
    assert len(schemas_by_id) == 11
    assert set(output_refs) == set(schemas_by_id)
    for schema_id, schema in schemas_by_id.items():
        assert schema_id.startswith("urn:mullusi:schema:")
        assert schema["additionalProperties"] is False
        assert schema["$id"] == schema_id


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
    actions_payload = deepcopy(payloads["schemas/software_dev/github_actions_failure_diagnosis.input.schema.json"])
    repo_status_payload = deepcopy(payloads["schemas/software_dev/github_repo_status_summary.input.schema.json"])
    patch_plan_payload = deepcopy(payloads["schemas/software_dev/github_patch_plan.input.schema.json"])
    issue_draft_payload = deepcopy(payloads["schemas/software_dev/github_issue_draft.input.schema.json"])
    release_readiness_payload = deepcopy(payloads["schemas/software_dev/github_release_readiness.input.schema.json"])
    issue_draft_missing_evidence_payload = deepcopy(issue_draft_payload)

    context_payload["affected_files"] = ["../secrets.py"]
    change_payload["command_policy"]["network_allowed"] = True
    pr_payload["local_git_push_allowed"] = True
    actions_payload["write_authority_granted"] = True
    repo_status_payload["write_authority_granted"] = True
    patch_plan_payload["write_authority_granted"] = True
    issue_draft_payload["write_authority_granted"] = True
    release_readiness_payload["write_authority_granted"] = True
    issue_draft_missing_evidence_payload["evidence_refs"] = []

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
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_actions_failure_diagnosis.input.schema.json"),
        actions_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_repo_status_summary.input.schema.json"),
        repo_status_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_patch_plan.input.schema.json"),
        patch_plan_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_issue_draft.input.schema.json"),
        issue_draft_payload,
    )
    assert _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_release_readiness.input.schema.json"),
        release_readiness_payload,
    )
    issue_draft_evidence_errors = _validate_schema_instance(
        _load_schema(SOFTWARE_DEV_SCHEMA_DIR / "github_issue_draft.input.schema.json"),
        issue_draft_missing_evidence_payload,
    )
    assert issue_draft_evidence_errors
    assert issue_draft_missing_evidence_payload["evidence_refs"] == []
    assert issue_draft_missing_evidence_payload["write_authority_granted"] is False


def test_software_dev_output_schemas_accept_representative_receipts() -> None:
    payloads = _representative_software_dev_output_payloads()
    schemas_by_id = _software_dev_output_schemas_by_id()

    assert set(payloads) == {entry.output_schema_ref for entry in _software_dev_entries()}
    assert set(payloads) == set(schemas_by_id)
    for schema_id, payload in payloads.items():
        assert _validate_schema_instance(schemas_by_id[schema_id], payload) == []
        assert payload
        assert payload.get("metadata", {}) or schema_id == "urn:mullusi:schema:repo-map:1"


def test_software_dev_output_schemas_reject_effect_overclaims() -> None:
    payloads = _representative_software_dev_output_payloads()
    schemas_by_id = _software_dev_output_schemas_by_id()
    repo_payload = deepcopy(payloads["urn:mullusi:schema:repo-map:1"])
    app_graph_payload = deepcopy(payloads["urn:mullusi:schema:app-task-graph:1"])
    pr_payload = deepcopy(payloads["urn:mullusi:schema:pr-candidate:1"])
    actions_payload = deepcopy(payloads["urn:mullusi:schema:github-actions-failure-diagnosis-receipt:1"])
    repo_status_payload = deepcopy(payloads["urn:mullusi:schema:github-repo-status-summary-receipt:1"])
    patch_plan_payload = deepcopy(payloads["urn:mullusi:schema:github-patch-plan-receipt:1"])
    issue_draft_payload = deepcopy(payloads["urn:mullusi:schema:github-issue-draft-receipt:1"])
    release_readiness_payload = deepcopy(payloads["urn:mullusi:schema:github-release-readiness-receipt:1"])

    repo_payload["files"] = ["C:\\secrets.py"]
    app_graph_payload["metadata"]["direct_deployment_allowed"] = True
    pr_payload["metadata"]["local_git_push_allowed"] = True
    actions_payload["write_authority_granted"] = True
    repo_status_payload["policy_decision"] = "allow"
    patch_plan_payload["policy_decision"] = "allow"
    issue_draft_payload["policy_decision"] = "allow"
    release_readiness_payload["policy_decision"] = "allow"

    assert _validate_schema_instance(schemas_by_id["urn:mullusi:schema:repo-map:1"], repo_payload)
    assert _validate_schema_instance(schemas_by_id["urn:mullusi:schema:app-task-graph:1"], app_graph_payload)
    assert _validate_schema_instance(schemas_by_id["urn:mullusi:schema:pr-candidate:1"], pr_payload)
    assert _validate_schema_instance(
        schemas_by_id["urn:mullusi:schema:github-actions-failure-diagnosis-receipt:1"],
        actions_payload,
    )
    assert _validate_schema_instance(
        schemas_by_id["urn:mullusi:schema:github-repo-status-summary-receipt:1"],
        repo_status_payload,
    )
    assert _validate_schema_instance(
        schemas_by_id["urn:mullusi:schema:github-patch-plan-receipt:1"],
        patch_plan_payload,
    )
    assert _validate_schema_instance(
        schemas_by_id["urn:mullusi:schema:github-issue-draft-receipt:1"],
        issue_draft_payload,
    )
    assert _validate_schema_instance(
        schemas_by_id["urn:mullusi:schema:github-release-readiness-receipt:1"],
        release_readiness_payload,
    )


def test_software_dev_pr_candidate_local_commands_are_git_local_only() -> None:
    payload = _representative_software_dev_output_payloads()["urn:mullusi:schema:pr-candidate:1"]
    schema = _software_dev_output_schemas_by_id()["urn:mullusi:schema:pr-candidate:1"]
    push_payload = deepcopy(payload)
    cli_payload = deepcopy(payload)
    metadata_payload = deepcopy(payload)

    push_payload["commit_candidate"]["local_commands"][0]["command"] = ["git", "push", "origin", "feature/x"]
    cli_payload["commit_candidate"]["local_commands"][0]["command"] = ["gh", "pr", "create"]
    del metadata_payload["commit_candidate"]["local_commands"][0]["metadata"]["push_allowed"]

    push_errors = _validate_schema_instance(schema, push_payload)
    cli_errors = _validate_schema_instance(schema, cli_payload)
    metadata_errors = _validate_schema_instance(schema, metadata_payload)

    assert any("$.commit_candidate.local_commands[0].command[1]" in error for error in push_errors)
    assert any("$.commit_candidate.local_commands[0].command[0]" in error for error in cli_errors)
    assert any("$.commit_candidate.local_commands[0].metadata: missing required fields ['push_allowed']" in error for error in metadata_errors)


def test_software_dev_named_loader_installs_only_software_dev_domain() -> None:
    capsule = load_software_dev_domain_capsule()
    entries = load_software_dev_capability_entries()
    gate = _software_dev_gate(require_production_ready=False)
    read_model = gate.read_model()

    assert capsule.domain == "software_dev"
    assert len(entries) == 11
    assert all(entry.domain == "software_dev" for entry in entries)
    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 11
    assert read_model["domains"] == ({"domain": "software_dev", "capability_ids": tuple(sorted(capsule.capability_refs))},)
    assert read_model["capability_manifest_registry_configured"] is False
    assert read_model["capability_manifest_registry"]["manifest_count"] == 0
    assert read_model["capability_manifest_coverage_status"] == "not_configured"
    assert read_model["capability_manifest_coverage"] == ()


def test_software_dev_named_loader_projects_manifest_registry_when_configured() -> None:
    gate = build_software_dev_capability_admission_gate(
        clock=lambda: "2026-05-13T00:00:00+00:00",
        require_production_ready=False,
        manifest_environment="local",
    )
    read_model = gate.read_model()
    manifest_registry = read_model["capability_manifest_registry"]
    manifests = {
        manifest["capability_id"]: manifest
        for manifest in manifest_registry["manifests"]
    }

    assert read_model["capability_manifest_registry_configured"] is True
    assert read_model["capability_manifest_coverage_status"] == "complete"
    assert read_model["capability_manifest_covered_count"] == 11
    assert read_model["capability_manifest_missing_count"] == 0
    assert len(read_model["capability_manifest_coverage"]) == 11
    assert manifest_registry["manifest_count"] == 11
    assert manifest_registry["admission_count"] == 11
    assert manifest_registry["capability_abi_coverage_status"] == "complete"
    assert set(manifest_registry["capability_ids"]) == {
        entry.capability_id for entry in load_software_dev_capability_entries()
    }
    assert manifests["software_dev.change.run"]["sandbox_required"] is True
    assert manifests["software_dev.change.run"]["rollback_required"] is True
    assert manifests["software_dev.repo_map.read"]["effect_bearing"] is False


def test_software_dev_pack_declares_reusable_unlock_ladder_profiles() -> None:
    entries = _load_json(SOFTWARE_DEV_CAPABILITY_PACK_PATH)["capabilities"]
    expected_levels = _expected_unlock_levels()
    ladder_by_level = {level.level: level for level in default_capability_unlock_ladder()}

    assert len(entries) == 11
    assert set(expected_levels) == {entry["capability_id"] for entry in entries}
    for entry in entries:
        capability_id = entry["capability_id"]
        profile = entry["metadata"]["unlock_ladder"]
        ladder_level = ladder_by_level[expected_levels[capability_id]]

        assert profile["ladder_id"] == UNLOCK_LADDER_ID
        assert profile["level"] == expected_levels[capability_id]
        assert profile["level_id"] == ladder_level.level_id
        assert tuple(profile["gate_template_ids"]) == ladder_level.required_gate_ids


def test_software_dev_manifests_declare_same_unlock_profiles_as_pack() -> None:
    pack_profiles = {
        entry["capability_id"]: entry["metadata"]["unlock_ladder"]
        for entry in _load_json(SOFTWARE_DEV_CAPABILITY_PACK_PATH)["capabilities"]
    }
    manifest_paths = tuple(sorted((ROOT / "capabilities" / "software_dev" / "manifests").glob("*.json")))

    assert len(manifest_paths) == 11
    assert set(pack_profiles) == set(_expected_unlock_levels())
    for manifest_path in manifest_paths:
        manifest = _load_json(manifest_path)
        capability_id = manifest["capability_id"]

        assert manifest["metadata"]["unlock_ladder"] == pack_profiles[capability_id]
        assert manifest["metadata"]["unlock_ladder"]["ladder_id"] == UNLOCK_LADDER_ID
        assert manifest["metadata"]["unlock_ladder"]["level_id"].startswith("L")


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
    actions_decision = gate.admit(
        command_id="cmd-actions-failure",
        intent_name="software_dev.github_actions_failure.diagnose_read_only",
    )
    repo_status_decision = gate.admit(
        command_id="cmd-repo-status",
        intent_name="software_dev.github_repo_status.summarize_read_only",
    )
    patch_plan_decision = gate.admit(
        command_id="cmd-patch-plan",
        intent_name="software_dev.github_patch_plan.draft",
    )
    issue_draft_decision = gate.admit(
        command_id="cmd-issue-draft",
        intent_name="software_dev.github_issue.draft",
    )
    release_readiness_decision = gate.admit(
        command_id="cmd-release-readiness",
        intent_name="software_dev.github_release.readiness",
    )
    change_decision = gate.admit(command_id="cmd-change", intent_name="software_dev.change.run")
    direct_deploy_decision = gate.admit(command_id="cmd-deploy", intent_name="software_dev.deploy.production")

    assert repo_decision.status.value == "accepted"
    assert repo_decision.capability_id == "software_dev.repo_map.read"
    assert actions_decision.status.value == "accepted"
    assert actions_decision.capability_id == "software_dev.github_actions_failure.diagnose_read_only"
    assert repo_status_decision.status.value == "accepted"
    assert repo_status_decision.capability_id == "software_dev.github_repo_status.summarize_read_only"
    assert patch_plan_decision.status.value == "accepted"
    assert patch_plan_decision.capability_id == "software_dev.github_patch_plan.draft"
    assert issue_draft_decision.status.value == "accepted"
    assert issue_draft_decision.capability_id == "software_dev.github_issue.draft"
    assert release_readiness_decision.status.value == "accepted"
    assert release_readiness_decision.capability_id == "software_dev.github_release.readiness"
    assert change_decision.status.value == "accepted"
    assert change_decision.capability_id == "software_dev.change.run"
    assert direct_deploy_decision.status.value == "rejected"
    assert read_model["capability_count"] == 11
    assert set(capabilities) == set(governed)
    assert read_model["domains"] == ({"domain": "software_dev", "capability_ids": tuple(sorted(capabilities))},)


def test_software_dev_governed_records_bind_read_and_effect_boundaries() -> None:
    gate = _software_dev_gate(require_production_ready=False)
    governed = {item["capability_id"]: item for item in gate.read_model()["governed_capability_records"]}
    repo_record = governed["software_dev.repo_map.read"]
    actions_record = governed["software_dev.github_actions_failure.diagnose_read_only"]
    repo_status_record = governed["software_dev.github_repo_status.summarize_read_only"]
    patch_plan_record = governed["software_dev.github_patch_plan.draft"]
    issue_draft_record = governed["software_dev.github_issue.draft"]
    release_readiness_record = governed["software_dev.github_release.readiness"]
    change_record = governed["software_dev.change.run"]
    pr_record = governed["software_dev.pr_candidate.prepare"]

    assert repo_record["read_only"] is True
    assert repo_record["world_mutating"] is False
    assert repo_record["requires_approval"] is False
    assert repo_record["requires_sandbox"] is False
    assert repo_record["allowed_tools"] == ["code_intelligence.build_repo_map"]
    assert actions_record["read_only"] is True
    assert actions_record["world_mutating"] is False
    assert actions_record["requires_approval"] is False
    assert actions_record["allowed_tools"] == ["connector_worker.github_read"]
    assert actions_record["allowed_networks"] == ["api.github.com"]
    assert "workflow_rerun_triggered" in actions_record["forbidden_effects"]
    assert repo_status_record["read_only"] is True
    assert repo_status_record["world_mutating"] is False
    assert repo_status_record["requires_approval"] is False
    assert repo_status_record["allowed_tools"] == ["connector_worker.github_read"]
    assert repo_status_record["allowed_networks"] == ["api.github.com"]
    assert "repository_mutated" in repo_status_record["forbidden_effects"]
    assert patch_plan_record["read_only"] is False
    assert patch_plan_record["world_mutating"] is False
    assert patch_plan_record["requires_approval"] is False
    assert patch_plan_record["allowed_tools"] == ["mullusi.local_patch_plan_draft"]
    assert patch_plan_record["allowed_networks"] == []
    assert "repository_mutated" in patch_plan_record["forbidden_effects"]
    assert issue_draft_record["read_only"] is False
    assert issue_draft_record["world_mutating"] is False
    assert issue_draft_record["requires_approval"] is False
    assert issue_draft_record["allowed_tools"] == ["mullusi.local_github_issue_draft"]
    assert issue_draft_record["allowed_networks"] == []
    assert "github_issue_created" in issue_draft_record["forbidden_effects"]
    assert release_readiness_record["read_only"] is False
    assert release_readiness_record["world_mutating"] is False
    assert release_readiness_record["requires_approval"] is False
    assert release_readiness_record["allowed_tools"] == ["mullusi.local_release_readiness_assessment"]
    assert release_readiness_record["allowed_networks"] == []
    assert "github_release_created" in release_readiness_record["forbidden_effects"]
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


def _expected_unlock_levels() -> dict[str, int]:
    return {
        "software_dev.repo_map.read": 0,
        "software_dev.github_actions_failure.diagnose_read_only": 2,
        "software_dev.github_repo_status.summarize_read_only": 2,
        "software_dev.github_patch_plan.draft": 1,
        "software_dev.github_issue.draft": 1,
        "software_dev.github_release.readiness": 1,
        "software_dev.context_bundle.build": 2,
        "software_dev.gate_plan.select": 2,
        "software_dev.change.run": 4,
        "software_dev.app_task_graph.plan": 2,
        "software_dev.pr_candidate.prepare": 5,
    }


def _software_dev_output_schemas_by_id() -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    for schema_path in sorted(SOFTWARE_DEV_SCHEMA_DIR.glob("*.output.schema.json")):
        schema = _load_schema(schema_path)
        schema_id = schema["$id"]
        assert schema_id not in schemas
        schemas[schema_id] = schema
    return schemas


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
        "schemas/software_dev/github_actions_failure_diagnosis.input.schema.json": {
            "capability_id": "software_dev.github_actions_failure.diagnose_read_only",
            "request_id": "req-actions-failure",
            "repository_ref": "repo:mullu-control-plane",
            "workflow_run_id": 777,
            "workspace_ref": "workspace:local-sandbox",
            "requested_evidence_kinds": ["workflow_run", "jobs", "failed_job_logs"],
            "max_failed_job_logs": 3,
            "write_authority_granted": False,
            "metadata": metadata,
        },
        "schemas/software_dev/github_repo_status_summary.input.schema.json": {
            "capability_id": "software_dev.github_repo_status.summarize_read_only",
            "request_id": "req-repo-status",
            "repository_ref": "repo:mullu-control-plane",
            "workspace_ref": "workspace:local-sandbox",
            "requested_evidence_kinds": ["repository", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs"],
            "max_items_per_kind": 10,
            "write_authority_granted": False,
            "metadata": metadata,
        },
        "schemas/software_dev/github_patch_plan.input.schema.json": {
            "capability_id": "software_dev.github_patch_plan.draft",
            "request_id": "req-patch-plan",
            "repository_ref": "repo:mullu-control-plane",
            "workspace_ref": "workspace:local-sandbox",
            "objective": "Draft a patch plan for a failing gateway test.",
            "evidence_refs": ["github-actions-failure-receipt:abc123"],
            "evidence_summaries": ["Gateway Workroom test failed after route addition."],
            "verification_expectations": ["python -m pytest tests/test_gateway/test_github_operations_workroom.py -q"],
            "write_authority_granted": False,
            "metadata": metadata,
        },
        "schemas/software_dev/github_issue_draft.input.schema.json": {
            "capability_id": "software_dev.github_issue.draft",
            "request_id": "req-issue-draft",
            "repository_ref": "repo:mullu-control-plane",
            "workspace_ref": "workspace:local-sandbox",
            "problem_summary": "Draft a GitHub issue from patch-plan evidence without creating it.",
            "evidence_refs": ["github-patch-plan-receipt:abc123"],
            "acceptance_criteria": ["issue draft is local only", "no GitHub write authority is granted"],
            "suggested_labels": ["governance", "github-workroom"],
            "write_authority_granted": False,
            "metadata": metadata,
        },
        "schemas/software_dev/github_release_readiness.input.schema.json": {
            "capability_id": "software_dev.github_release.readiness",
            "repo": "tamiratl/mullu-control-plane",
            "release_objective": "Assess release readiness for the GitHub Operations Workroom MVP.",
            "candidate_ref": "release-candidate:2026-06-29",
            "evidence_refs": ["github-repo-status-receipt:abc123"],
            "ci_status_refs": ["ci:82-checks-pass"],
            "change_summary_refs": ["pr:2397"],
            "risk_refs": ["security-review:bounded"],
            "rollback_refs": ["rollback:revert-pr"],
            "known_blockers": [],
            "assumptions": ["Release readiness remains prepare-only."],
            "write_authority_granted": False,
            "metadata": {"fixture": "software_dev_capability_pack", "release_execution_allowed": False},
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
                "denied_git_subcommands": [
                    "archive",
                    "clone",
                    "credential",
                    "daemon",
                    "fetch",
                    "ls-remote",
                    "p4",
                    "pull",
                    "push",
                    "remote",
                    "request-pull",
                    "send-email",
                    "submodule",
                    "svn",
                ],
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


def _representative_software_dev_output_payloads() -> dict[str, dict]:
    metadata = {"fixture": "software_dev_capability_pack"}
    symbol = {
        "name": "build_repo_map",
        "kind": "function",
        "file_path": "mcoi/mcoi_runtime/core/code_intelligence.py",
        "line_start": 35,
        "line_end": 120,
        "imports": ["ast", "pathlib"],
        "referenced_by": ["tests/test_code_intelligence.py"],
        "metadata": {"detector": "python_ast"},
    }
    risk = {
        "file_path": "schemas/software_dev/repo_map.output.schema.json",
        "risk": "medium",
        "score": 35,
        "reasons": ["schema contract change", "proof matrix witness update"],
    }
    return {
        "urn:mullusi:schema:repo-map:1": {
            "repository": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "files": [
                "mcoi/mcoi_runtime/core/code_intelligence.py",
                "tests/test_code_intelligence.py",
            ],
            "symbols": [symbol],
            "test_map": {
                "source_to_tests": {
                    "mcoi/mcoi_runtime/core/code_intelligence.py": ["tests/test_code_intelligence.py"],
                },
                "test_to_sources": {
                    "tests/test_code_intelligence.py": ["mcoi/mcoi_runtime/core/code_intelligence.py"],
                },
            },
            "dependency_edges": [
                ["mcoi/mcoi_runtime/core/code_intelligence.py", "tests/test_code_intelligence.py"],
            ],
            "risk_assessments": [risk],
        },
        "urn:mullusi:schema:github-actions-failure-diagnosis-receipt:1": {
            "receipt_id": "github-actions-failure-receipt:abc123",
            "repository": "repo:mullu-control-plane",
            "workflow_run_id": 777,
            "status": "diagnosed",
            "failure_summary": "Workflow failed in Python Tests; first signal: ERROR test failed",
            "suspected_failed_jobs": ["Python Tests"],
            "evidence_refs": ["github-live-read://tamiratl/mullu-control-plane/actions/runs/777"],
            "payload_hashes": {
                "workflow_run": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "jobs": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "job_log:9001": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            },
            "actions_blocked": [
                "rerun_workflow_without_explicit_approval",
                "cancel_workflow_without_explicit_approval",
                "dispatch_workflow_without_explicit_approval",
                "post_github_comment_without_write_admission",
                "mutate_repository_without_write_admission",
            ],
            "recommended_next_action": "prepare_patch_plan_from_failed_job_signal_without_mutating_github",
            "write_authority_granted": False,
            "metadata": metadata,
        },
        "urn:mullusi:schema:github-repo-status-summary-receipt:1": {
            "receipt_id": "github-repo-status-receipt:abc123",
            "event_id": "github-repo-status-admission:abc123",
            "actor_id": "operator:tamirat",
            "surface": "github_operations_workroom",
            "intent": "SUMMARIZE_GITHUB_REPOSITORY_STATUS",
            "target_object": "github_repository:tamiratl/mullu-control-plane",
            "risk_class": "class_0_observe",
            "evidence_used": ["github-live-read://tamiratl/mullu-control-plane/repository"],
            "policy_decision": "allow_read_only",
            "actions_taken": ["performed_get_only_github_repo_reads", "hashed_payloads", "summarized_repository_status"],
            "actions_blocked": [
                "create_issue_without_explicit_approval",
                "post_github_comment_without_write_admission",
                "mutate_repository_without_write_admission",
            ],
            "assumptions": ["Access token scope is limited to oauth:github.read."],
            "verification_result": "Read-only repository status evidence collected, hash-bound, and summarized.",
            "final_judgment": "Repository has 1 open pull requests, 1 open issues, and 1 recent commits in bounded read-only evidence.",
            "memory_update": "store",
            "timestamp": "2026-06-28T12:00:00+00:00",
            "metadata": metadata,
            "partial_failure_reasons": [],
        },
        "urn:mullusi:schema:github-patch-plan-receipt:1": {
            "receipt_id": "github-patch-plan-receipt:abc123",
            "event_id": "operator-github-patch-plan-draft:abc123",
            "actor_id": "operator:tamirat",
            "surface": "github_operations_workroom",
            "intent": "DRAFT_GITHUB_PATCH_PLAN",
            "target_object": "github_repository:tamiratl/mullu-control-plane",
            "risk_class": "class_1_prepare",
            "evidence_used": ["github-actions-failure-receipt:abc123"],
            "policy_decision": "allow_draft_only",
            "actions_taken": ["drafted_patch_plan", "emitted_causal_receipt"],
            "actions_blocked": [
                "edit_repository_without_patch_approval",
                "create_branch_without_explicit_approval",
                "create_pull_request_without_explicit_approval",
                "post_github_comment_without_write_admission",
                "create_issue_without_explicit_approval",
                "claim_fix_complete_without_verification",
            ],
            "assumptions": ["Patch planning does not edit repository files or write to GitHub."],
            "verification_result": "Patch plan drafted from bounded evidence; no repository or GitHub write was performed.",
            "final_judgment": "Draft patch plan for tamiratl/mullu-control-plane: fix failing gateway test.",
            "memory_update": "store",
            "timestamp": "2026-06-28T12:00:00+00:00",
            "metadata": metadata,
            "partial_failure_reasons": [],
        },
        "urn:mullusi:schema:github-issue-draft-receipt:1": {
            "receipt_id": "github-issue-draft-receipt:abc123",
            "event_id": "operator-github-issue-draft:abc123",
            "actor_id": "operator:tamirat",
            "surface": "github_operations_workroom",
            "intent": "DRAFT_GITHUB_ISSUE",
            "target_object": "github_repository:tamiratl/mullu-control-plane",
            "risk_class": "class_1_prepare",
            "evidence_used": ["github-patch-plan-receipt:abc123"],
            "policy_decision": "allow_draft_only",
            "actions_taken": ["drafted_github_issue", "emitted_causal_receipt"],
            "actions_blocked": [
                "create_github_issue_without_explicit_approval",
                "apply_github_labels_without_write_admission",
                "assign_github_issue_without_write_admission",
                "post_github_comment_without_write_admission",
                "mutate_repository_without_write_admission",
                "claim_issue_created_without_live_receipt",
            ],
            "assumptions": ["Issue drafting does not create GitHub issues or write to GitHub."],
            "verification_result": "GitHub issue drafted from bounded evidence; no GitHub write was performed.",
            "final_judgment": "Draft a GitHub issue from patch-plan evidence without creating it.",
            "memory_update": "store",
            "timestamp": "2026-06-29T12:00:00+00:00",
            "metadata": metadata,
            "partial_failure_reasons": [],
        },
        "urn:mullusi:schema:github-release-readiness-receipt:1": {
            "receipt_id": "github-release-readiness-receipt:abc123",
            "intent": "ASSESS_GITHUB_RELEASE_READINESS",
            "target_object": "github_repository:tamiratl/mullu-control-plane:release_candidate:release-candidate:2026-06-29",
            "risk_class": "class_1_prepare",
            "evidence_used": ["github-repo-status-receipt:abc123", "ci:82-checks-pass", "pr:2397", "rollback:revert-pr"],
            "policy_decision": "allow_draft_only",
            "actions_taken": ["assessed_release_readiness", "emitted_causal_receipt"],
            "actions_blocked": [
                "create_git_tag_without_release_approval",
                "create_github_release_without_release_approval",
                "deploy_release_without_deployment_witness",
                "publish_package_without_external_obligation_approval",
                "trigger_workflow_without_explicit_approval",
                "merge_or_mutate_repository_without_write_admission",
                "claim_release_ready_without_required_evidence",
            ],
            "assumptions": ["Release readiness assessment does not execute release actions."],
            "verification_result": "Release readiness assessed from bounded evidence; no tag, release, deployment, workflow, merge, or GitHub write was performed.",
            "final_judgment": "Release candidate release-candidate:2026-06-29 has bounded evidence for a local readiness recommendation.",
            "memory_update": "store",
            "partial_failure_reasons": [],
            "write_authority_granted": False,
            "metadata": {
                "release_execution_allowed": False,
                "write_authority_granted": False,
            },
        },
        "urn:mullusi:schema:code-context-bundle:1": {
            "bundle_id": "context:abc123",
            "repository": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "task_summary": "Add governed output schema coverage for software-dev capability receipts",
            "selected_files": [
                {
                    "file_path": "schemas/software_dev/repo_map.output.schema.json",
                    "reason": "output schema under test",
                    "distance": 0,
                },
            ],
            "selected_symbols": [symbol],
            "selected_tests": ["tests/test_software_dev_capability_pack.py"],
            "dependency_edges": [
                ["schemas/software_dev/repo_map.output.schema.json", "tests/test_software_dev_capability_pack.py"],
            ],
            "acceptance_criteria": ["output URNs resolve", "overclaims reject", "proof matrix remains current"],
            "risk_assessments": [risk],
            "estimate": {
                "token_estimate": 1200,
                "cost_microusd_estimate": 40,
                "estimation_method": "deterministic_character_count_v1",
            },
            "evidence_refs": ["proof://software_dev/output-schema/context-bundle"],
            "metadata": metadata,
        },
        "urn:mullusi:schema:software-gate-plan:1": {
            "plan_id": "gate-plan:abc123",
            "repository": "repo:mullu-control-plane",
            "commit_sha": "abc123",
            "mode": "patch_test_review",
            "blast_radius": "module",
            "affected_files": ["schemas/software_dev/software_gate_plan.output.schema.json"],
            "gates": [
                {
                    "gate_id": "schema_contract_tests",
                    "tier": "fast",
                    "command": ["python", "-m", "pytest", "tests/test_software_dev_capability_pack.py", "-q"],
                    "reason": "validate software-dev schema contract witnesses",
                    "target_refs": ["tests/test_software_dev_capability_pack.py"],
                    "order": 0,
                    "required": True,
                    "metadata": {"network_allowed": False},
                },
            ],
            "skipped_gate_ids": [],
            "full_suite_required": False,
            "evidence_refs": ["proof://software_dev/output-schema/gate-plan"],
            "metadata": metadata,
        },
        "urn:mullusi:schema:software-change-receipt:1": {
            "receipt_id": "software-change:receipt-1",
            "request_id": "req-change",
            "stage": "terminal_closed",
            "cause": "all requested gates passed",
            "outcome": "SolvedVerified",
            "target_refs": ["schemas/software_dev/software_change_receipt.output.schema.json"],
            "constraint_refs": ["sandbox_profile:workspace_network_none", "rollback_required:true"],
            "evidence_refs": ["gate:schema_contract_tests"],
            "created_at": "2026-05-13T00:00:00+00:00",
            "metadata": {"network_enabled": False, "rollback_required": True},
        },
        "urn:mullusi:schema:app-task-graph:1": {
            "graph_id": "app-task-graph:invoice-dashboard",
            "app_name": "Invoice Dashboard",
            "tasks": [
                {
                    "task_id": "task-data-model",
                    "title": "Create invoice data model",
                    "kind": "data_model",
                    "affected_files": ["app/models/invoice.py"],
                    "acceptance_criteria": ["invoice fields are typed", "tenant id is required"],
                    "dependencies": [],
                    "quality_gates": ["unit_tests", "typecheck"],
                    "risk": "medium",
                    "review_required": True,
                    "metadata": {"software_mode": "patch_test_review"},
                },
                {
                    "task_id": "task-model-tests",
                    "title": "Add invoice model tests",
                    "kind": "tests",
                    "affected_files": ["tests/test_invoice_model.py"],
                    "acceptance_criteria": ["model tests cover validation failure", "model tests cover tenant scope"],
                    "dependencies": ["task-data-model"],
                    "quality_gates": ["unit_tests"],
                    "risk": "low",
                    "review_required": True,
                    "metadata": {"software_mode": "patch_test_review"},
                },
            ],
            "root_task_ids": ["task-data-model"],
            "terminal_task_ids": ["task-model-tests"],
            "evidence_refs": ["proof://software_dev/output-schema/app-task-graph"],
            "metadata": {
                "direct_deployment_allowed": False,
                "commit_candidate_allowed": False,
                "fixture": "software_dev_capability_pack",
            },
        },
        "urn:mullusi:schema:pr-candidate:1": {
            "candidate_id": "pr-candidate:invoice-dashboard",
            "status": "approval_required",
            "repository": "repo:invoice-service",
            "branch_candidate": {
                "branch_name": "mullu/app-builder-invoice-dashboard-abc123",
                "base_branch": "main",
                "create_command": {
                    "command_id": "git-create-branch",
                    "purpose": "create local review branch candidate",
                    "command": ["git", "switch", "-c", "mullu/app-builder-invoice-dashboard-abc123", "main"],
                    "requires_clean_worktree": True,
                    "metadata": {"push_allowed": False},
                },
                "rollback_command": {
                    "command_id": "git-rollback-branch",
                    "purpose": "return to base branch without pushing",
                    "command": ["git", "switch", "main"],
                    "requires_clean_worktree": False,
                    "metadata": {"push_allowed": False},
                },
            },
            "commit_candidate": {
                "commit_message": "Add invoice dashboard governed candidate",
                "affected_files": ["app/models/invoice.py", "tests/test_invoice_model.py"],
                "receipt_refs": ["software-change:receipt-1"],
                "quality_gate_refs": ["gate:schema_contract_tests"],
                "local_commands": [
                    {
                        "command_id": "git-add-candidate",
                        "purpose": "stage local candidate files",
                        "command": ["git", "add", "app/models/invoice.py", "tests/test_invoice_model.py"],
                        "requires_clean_worktree": False,
                        "metadata": {"push_allowed": False},
                    },
                    {
                        "command_id": "git-commit-candidate",
                        "purpose": "create local commit candidate",
                        "command": ["git", "commit", "-m", "Add invoice dashboard governed candidate"],
                        "requires_clean_worktree": False,
                        "metadata": {"push_allowed": False},
                    },
                ],
            },
            "review_packet": {
                "packet_id": "review-packet:invoice-dashboard",
                "title": "Invoice Dashboard governed candidate",
                "summary": "Prepares invoice model and tests for human review.",
                "affected_files": ["app/models/invoice.py", "tests/test_invoice_model.py"],
                "quality_gate_refs": ["gate:schema_contract_tests"],
                "receipt_refs": ["software-change:receipt-1"],
                "risk_flags": ["approval_required_before_pr_open"],
                "rollback_plan": ["switch back to main", "delete local candidate branch after review"],
                "markdown_body": "## Summary\n\nAdds invoice model and tests with governed receipts.",
                "metadata": {"approval_required": True},
            },
            "open_intent": {
                "intent_id": "github-pr-open:intent-1",
                "repository": "repo:invoice-service",
                "title": "Invoice Dashboard governed candidate",
                "body": "Prepared PR candidate. Opening requires human approval.",
                "base_branch": "main",
                "head_branch": "mullu/app-builder-invoice-dashboard-abc123",
                "capability_id": "github.open_pull_request",
                "approval_request_id": "approval:pr-open-review",
                "requires_approval": True,
                "world_mutating": True,
                "execution_allowed": False,
                "approval_decision_id": "",
                "metadata": {"approval_required": True},
            },
            "evidence_refs": ["proof://software_dev/output-schema/pr-candidate"],
            "metadata": {
                "local_git_push_allowed": False,
                "github_open_requires_approval": True,
                "fixture": "software_dev_capability_pack",
            },
        },
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
