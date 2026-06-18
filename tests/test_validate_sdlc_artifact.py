"""Purpose: verify governed SDLC artifact validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_artifact.
Invariants:
  - SDLC docs, schemas, and examples validate as one linked chain.
  - Raw private reasoning fields are rejected.
  - Cross-artifact drift is reported explicitly.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts import validate_sdlc_artifact as validator


def test_current_sdlc_contract_passes() -> None:
    errors = validator.validate_contract()
    records = validator.load_example_records()

    assert errors == []
    assert len(records) == 12
    assert all(spec.schema_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert all(spec.example_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert len(validator.CANONICAL_SCHEMA_REFS) == len(records)
    assert len(validator.CANONICAL_EXAMPLE_REFS) == len(records)
    assert "scripts/validate_sdlc_pr_enforcement.py" in validator.REQUIRED_VALIDATORS
    assert "implementation_receipt" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "change_request" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "recovery_handoff" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "workspace_governance_preflight" in validator.REQUIRED_VERIFICATION_COMMANDS
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH == ".tmp/workspace-governance-preflight-receipt.json"
    assert validator.BRANCH_RULESET_WITNESS_PATH == "docs/main-protection-ruleset-witness.json"


def test_schema_artifacts_have_expected_identity() -> None:
    for spec in validator.ARTIFACT_SPECS:
        schema = validator._load_schema(spec.schema_path)
        errors = validator.validate_schema_artifact(schema, spec)

        assert errors == []
        assert schema["$id"] == spec.schema_id
        assert schema["title"] == spec.title
        assert schema["additionalProperties"] is False
        if spec.kind in validator.GATE_BOUND_ARTIFACT_KINDS:
            assert "uao_ref" in schema["required"]
            assert "causal_decision_trace_ref" in schema["required"]
            assert "receipt_ref" in schema["required"]


def test_example_chain_links_all_lifecycle_artifacts() -> None:
    records = validator.load_example_records()
    errors = validator.validate_example_chain(records)

    assert errors == []
    assert records["requirement"]["request_id"] == records["change_request"]["request_id"]
    assert records["work_plan"]["design_id"] == records["design_decision"]["design_id"]
    assert records["implementation_receipt"]["plan_id"] == records["work_plan"]["plan_id"]
    assert records["transition_receipt"]["change_id"] == records["change_request"]["request_id"]
    assert records["recovery_handoff"]["change_id"] == records["change_request"]["request_id"]
    assert records["recovery_handoff"]["terminal_closure_ref"] == records["closure_receipt"]["closure_id"]
    assert records["deployment_candidate"]["release_id"] == records["release_candidate"]["release_id"]
    assert records["change_request"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["implementation_receipt"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["transition_receipt"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["recovery_handoff"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_REF in records["closure_receipt"]["receipts"]
    assert records["deployment_candidate"]["uao_ref"] in records["closure_receipt"]["uao_refs"]
    assert set(validator.CANONICAL_SCHEMA_REFS).issubset(set(records["design_decision"]["schema_changes"]))
    assert set(validator.CANONICAL_INVENTORY_REFS).issubset(set(records["work_plan"]["expected_artifacts"]))
    assert set(validator.CANONICAL_EXAMPLE_REFS).issubset(set(records["verification_receipt"]["coverage_refs"]))
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH in records["verification_receipt"]["coverage_refs"]
    assert validator.BRANCH_RULESET_WITNESS_PATH in records["verification_receipt"]["coverage_refs"]
    assert validator.BRANCH_RULESET_WITNESS_PATH in records["implementation_receipt"]["documentation_changes"]
    assert set(validator.CANONICAL_INVENTORY_REFS).issubset(
        {changed_file["path"] for changed_file in records["implementation_receipt"]["changed_files"]}
    )
    assert validator.BRANCH_RULESET_WITNESS_PATH in {
        changed_file["path"] for changed_file in records["implementation_receipt"]["changed_files"]
    }


def test_raw_private_reasoning_field_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_design["raw_chain_of_thought"] = "private reasoning must not be serialized"

    errors = validator.validate_artifact_record("design_decision", invalid_design)

    assert any("raw_chain_of_thought is prohibited" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_design["design_id"] == "sdlc_design_uao_validator_001"


def test_gate_decision_envelope_is_required_and_prefix_checked() -> None:
    records = validator.load_example_records()
    invalid_requirement = copy.deepcopy(records["requirement"])
    invalid_release = copy.deepcopy(records["release_candidate"])
    invalid_requirement.pop("uao_ref")
    invalid_release["receipt_ref"] = "trace://wrong/release/receipt"

    requirement_errors = validator.validate_artifact_record("requirement", invalid_requirement)
    release_errors = validator.validate_artifact_record("release_candidate", invalid_release)

    assert any("uao_ref" in error for error in requirement_errors)
    assert "release_candidate: receipt_ref must use receipt:// prefix" in release_errors
    assert "release_candidate: release_receipt must match receipt_ref" in release_errors


def test_closure_must_retain_upstream_gate_refs() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["closure_receipt"]["receipts"].remove(records["change_request"]["receipt_ref"])
    invalid_records["closure_receipt"]["uao_refs"].remove(records["requirement"]["uao_ref"])
    invalid_records["closure_receipt"]["causal_decision_trace_refs"].remove(
        records["deployment_candidate"]["causal_decision_trace_ref"]
    )
    invalid_records["closure_receipt"]["receipts"].remove(records["implementation_receipt"]["receipt_ref"])
    invalid_records["closure_receipt"]["receipts"].remove(records["transition_receipt"]["receipt_ref"])
    invalid_records["closure_receipt"]["receipts"].remove(records["recovery_handoff"]["receipt_ref"])
    invalid_records["closure_receipt"]["uao_refs"].remove(records["recovery_handoff"]["uao_ref"])
    invalid_records["closure_receipt"]["causal_decision_trace_refs"].remove(
        records["recovery_handoff"]["causal_decision_trace_ref"]
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: closure must include change_request receipt_ref" in errors
    assert "example_chain: closure must include requirement uao_ref" in errors
    assert "example_chain: closure must include implementation_receipt receipt_ref" in errors
    assert "example_chain: closure must include implementation receipt" in errors
    assert "example_chain: closure must include transition_receipt receipt_ref" in errors
    assert "example_chain: closure must include recovery_handoff receipt_ref" in errors
    assert "example_chain: closure must include recovery handoff receipt" in errors
    assert "example_chain: closure must include recovery_handoff uao_ref" in errors
    assert "example_chain: closure must include recovery_handoff causal_decision_trace_ref" in errors
    assert "example_chain: closure must include deployment_candidate causal_decision_trace_ref" in errors


def test_cross_artifact_request_drift_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["requirement"]["request_id"] = "wrong_request"

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: requirement.request_id must match change request" in errors
    assert len(errors) >= 1
    assert invalid_records["change_request"]["request_id"] == "sdlc_req_uao_validator_001"


def test_work_plan_rejects_future_dependency_and_missing_validator() -> None:
    work_plan = copy.deepcopy(validator.load_example_records()["work_plan"])
    work_plan["steps"][0]["depends_on"] = [2]
    work_plan["required_validators"] = [
        item
        for item in work_plan["required_validators"]
        if item != "scripts/validate_sdlc_state_machine.py"
    ]

    errors = validator.validate_artifact_record("work_plan", work_plan)

    assert any("dependency 2 must be earlier" in error for error in errors)
    assert any("missing required validators" in error for error in errors)
    assert len(errors) >= 2


def test_inventory_closure_rejects_missing_canonical_refs() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_work_plan = copy.deepcopy(records["work_plan"])
    invalid_implementation = copy.deepcopy(records["implementation_receipt"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_design["schema_changes"].remove("schemas/sdlc_recovery_handoff_receipt.schema.json")
    invalid_work_plan["expected_artifacts"].remove("examples/sdlc/closure_uao_validator.json")
    invalid_implementation["schema_changes"].remove("schemas/sdlc_transition_receipt.schema.json")
    invalid_implementation["changed_files"] = [
        changed_file
        for changed_file in invalid_implementation["changed_files"]
        if changed_file["path"] != "examples/sdlc/deployment_candidate_uao_validator.json"
    ]
    invalid_verification["coverage_refs"].remove("examples/sdlc/security_review_uao_validator.json")

    design_errors = validator.validate_artifact_record("design_decision", invalid_design)
    work_plan_errors = validator.validate_artifact_record("work_plan", invalid_work_plan)
    implementation_errors = validator.validate_artifact_record("implementation_receipt", invalid_implementation)
    verification_errors = validator.validate_artifact_record("verification_receipt", invalid_verification)

    assert any("design_decision: schema_changes missing canonical SDLC inventory refs" in error for error in design_errors)
    assert any("work_plan: expected_artifacts missing canonical SDLC inventory refs" in error for error in work_plan_errors)
    assert any("implementation_receipt: schema_changes missing canonical SDLC inventory refs" in error for error in implementation_errors)
    assert any("implementation_receipt: changed_files missing canonical SDLC inventory refs" in error for error in implementation_errors)
    assert any("verification_receipt: coverage_refs missing canonical SDLC inventory refs" in error for error in verification_errors)
    assert len(design_errors) + len(work_plan_errors) + len(implementation_errors) + len(verification_errors) >= 5


def test_design_and_verification_require_pr_enforcement_validator() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_design["validator_changes"] = [
        item
        for item in invalid_design["validator_changes"]
        if item != "scripts/validate_sdlc_pr_enforcement.py"
    ]
    invalid_verification["commands"] = [
        item
        for item in invalid_verification["commands"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]
    invalid_verification["validator_outputs"] = [
        item
        for item in invalid_verification["validator_outputs"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]

    design_errors = validator.validate_artifact_record("design_decision", invalid_design)
    verification_errors = validator.validate_artifact_record("verification_receipt", invalid_verification)

    assert any("design_decision: missing required validators" in error for error in design_errors)
    assert any("verification_receipt: missing command sdlc_pr_enforcement_validation" in error for error in verification_errors)
    assert any("verification_receipt: missing validator outputs" in error for error in verification_errors)
    assert len(design_errors) + len(verification_errors) >= 3


def test_snet_runtime_integration_gate_validates_as_design_decision() -> None:
    design_path = Path("examples/sdlc/design_snet_runtime_integration_gate_20260613.json")
    design_record = validator.load_json_object(design_path, "SNet runtime integration gate")

    errors = validator.validate_artifact_record("design_decision", design_record)

    assert errors == []
    assert design_record["requirement_id"] == "sdlc_reqspec_snet_rsim_01_20260613"
    assert set(validator.CANONICAL_SCHEMA_REFS).issubset(set(design_record["schema_changes"]))
    assert set(validator.REQUIRED_VALIDATORS).issubset(set(design_record["validator_changes"]))
    assert design_record["security_model"]["effect_bearing_requires_receipt"] is True
    assert "mcoi/mcoi_runtime/snet/engine.py" in design_record["affected_modules"]
    assert "scripts/validate_snet_mesh_receipt.py" in design_record["validator_changes"]
    assert any("run_workspace_governance_checks.py" in item for item in design_record["test_plan"])
    assert "Admit one bounded read-only MCOI route" in design_record["architecture_summary"]
    assert "raw answer submission" in design_record["architecture_summary"]
    assert "autonomous execution" in design_record["architecture_summary"]


def test_capability_maturity_label_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_capability_maturity_labels_20260615.json")
    design_path = Path("examples/sdlc/design_capability_maturity_labels_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "capability maturity label requirement")
    design_record = validator.load_json_object(design_path, "capability maturity label design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "maturity_label" in design_record["architecture_summary"]
    assert "schemas/capability_maturity.schema.json" in design_record["schema_changes"]
    assert "tests/test_gateway/test_capability_maturity.py" in design_record["validator_changes"]
    assert "Verified must be impossible below C6" in requirement_record["constraints"]


def test_trusted_identity_header_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_trusted_identity_header_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_trusted_identity_header_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "trusted identity header boundary requirement")
    design_record = validator.load_json_object(design_path, "trusted identity header boundary design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "TrustedIdentityGatewayEvidence" in design_record["architecture_summary"]
    assert "gateway/tenant_identity.py" in requirement_record["affected_surfaces"]
    assert "no live OIDC verifier implementation" in requirement_record["non_goals"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_oidc_jwks_refresh_evidence_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_oidc_jwks_refresh_evidence_20260615.json")
    design_path = Path("examples/sdlc/design_oidc_jwks_refresh_evidence_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "OIDC JWKS refresh evidence requirement")
    design_record = validator.load_json_object(design_path, "OIDC JWKS refresh evidence design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "OidcJwksRefreshEvidence" in design_record["architecture_summary"]
    assert "gateway/tenant_identity.py" in requirement_record["affected_surfaces"]
    assert "no JWKS network fetch implementation" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_tenant_identity.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_adapter_external_effect_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_adapter_external_effect_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_adapter_external_effect_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "adapter external effect requirement")
    design_record = validator.load_json_object(design_path, "adapter external effect design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "AdapterExternalEffectEvidence" in design_record["architecture_summary"]
    assert "gateway/adapter_worker_clients.py" in requirement_record["affected_surfaces"]
    assert "no live Gmail draft or send authority claim" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_adapter_worker_clients.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_adapter_messaging_phone_dispatch_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_adapter_messaging_phone_dispatch_20260615.json")
    design_path = Path("examples/sdlc/design_adapter_messaging_phone_dispatch_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "adapter messaging phone requirement")
    design_record = validator.load_json_object(design_path, "adapter messaging phone design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "AdapterExternalEffectEvidence" in design_record["architecture_summary"]
    assert "gateway/capability_dispatch.py" in requirement_record["affected_surfaces"]
    assert "no live SMS send authority claim" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_adapter_worker_dispatch.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_github_check_run_write_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_github_check_run_write_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_github_check_run_write_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "GitHub check-run write requirement")
    design_record = validator.load_json_object(design_path, "GitHub check-run write design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "GitHubCheckRunWriter" in design_record["architecture_summary"]
    assert "gateway/github_check_run_writer.py" in requirement_record["affected_surfaces"]
    assert "no live GitHub check-run creation" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_github_check_run_writer.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_github_app_token_exchange_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_github_app_token_exchange_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_github_app_token_exchange_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "GitHub App token exchange requirement")
    design_record = validator.load_json_object(design_path, "GitHub App token exchange design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "GitHubAppTokenExchange" in design_record["architecture_summary"]
    assert "gateway/github_app_token_exchange.py" in requirement_record["affected_surfaces"]
    assert "no live GitHub App token minting" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_github_app_token_exchange.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_github_action_execution_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_github_action_execution_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_github_action_execution_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "GitHub action execution requirement")
    design_record = validator.load_json_object(design_path, "GitHub action execution design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "GitHubActionExecution" in design_record["architecture_summary"]
    assert "gateway/github_action_execution.py" in requirement_record["affected_surfaces"]
    assert "no live GitHub API call" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_github_action_execution.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_github_branch_protection_reconcile_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_github_branch_protection_reconcile_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_github_branch_protection_reconcile_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "GitHub branch-protection reconcile requirement")
    design_record = validator.load_json_object(design_path, "GitHub branch-protection reconcile design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "BranchProtectionReconciler" in design_record["architecture_summary"]
    assert "gateway/branch_protection_reconcile.py" in requirement_record["affected_surfaces"]
    assert "no live GitHub API call" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_branch_protection_reconcile.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_distributed_lease_claim_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_distributed_lease_claim_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_distributed_lease_claim_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "distributed lease claim requirement")
    design_record = validator.load_json_object(design_path, "distributed lease claim design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "DistributedLeaseClaimPlanner" in design_record["architecture_summary"]
    assert "gateway/distributed_lease_boundary.py" in requirement_record["affected_surfaces"]
    assert "no live distributed lease backend call" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_distributed_lease_boundary.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_distributed_lease_adapter_registry_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_distributed_lease_adapter_registry_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_distributed_lease_adapter_registry_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "distributed lease adapter registry requirement")
    design_record = validator.load_json_object(design_path, "distributed lease adapter registry design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "DistributedLeaseAdapterRegistryEvaluator" in design_record["architecture_summary"]
    assert "gateway/distributed_lease_adapters.py" in requirement_record["affected_surfaces"]
    assert "no live distributed lease backend call" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_distributed_lease_adapters.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_distributed_lease_execution_receipt_boundary_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_distributed_lease_execution_receipt_boundary_20260615.json")
    design_path = Path("examples/sdlc/design_distributed_lease_execution_receipt_boundary_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "distributed lease execution requirement")
    design_record = validator.load_json_object(design_path, "distributed lease execution design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "DistributedLeaseExecutionReceiptEvaluator" in design_record["architecture_summary"]
    assert "gateway/distributed_lease_execution.py" in requirement_record["affected_surfaces"]
    assert "no live distributed lease backend call" in requirement_record["non_goals"]
    assert "tests/test_gateway/test_distributed_lease_execution.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_scheduler_worker_runtime_receipt_handoff_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_scheduler_worker_runtime_receipt_handoff_20260615.json")
    design_path = Path("examples/sdlc/design_scheduler_worker_runtime_receipt_handoff_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "scheduler worker handoff requirement")
    design_record = validator.load_json_object(design_path, "scheduler worker handoff design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "SchedulerWorkerRuntimeReceiptHandoff" in design_record["architecture_summary"]
    assert "schemas/scheduler_worker_runtime_receipt_handoff.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/scheduler_worker_runtime_receipt_handoff.schema.json" in design_record["schema_changes"]
    assert "no live worker dispatch" in requirement_record["non_goals"]
    assert "scripts/validate_scheduler_worker_runtime_receipt_handoff.py" in design_record["validator_changes"]
    assert "tests/test_validate_scheduler_worker_runtime_receipt_handoff.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_scheduler_worker_runtime_receipt_emitter_dry_run_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_scheduler_worker_runtime_receipt_emitter_dry_run_20260615.json")
    design_path = Path("examples/sdlc/design_scheduler_worker_runtime_receipt_emitter_dry_run_20260615.json")
    requirement_record = validator.load_json_object(requirement_path, "scheduler worker emitter dry-run requirement")
    design_record = validator.load_json_object(design_path, "scheduler worker emitter dry-run design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "SchedulerWorkerRuntimeReceiptEmitterDryRun" in design_record["architecture_summary"]
    assert "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json" in design_record["schema_changes"]
    assert "no live worker dispatch" in requirement_record["non_goals"]
    assert "scripts/validate_scheduler_worker_runtime_receipt_emitter_dry_run.py" in design_record["validator_changes"]
    assert "tests/test_validate_scheduler_worker_runtime_receipt_emitter_dry_run.py" in design_record["validator_changes"]
    assert "scripts/validate_sdlc_security_review.py" in design_record["validator_changes"]


def test_connector_action_promotion_gate_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_connector_action_promotion_gate_20260616.json")
    design_path = Path("examples/sdlc/design_connector_action_promotion_gate_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "connector action promotion gate requirement")
    design_record = validator.load_json_object(design_path, "connector action promotion gate design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "ConnectorActionPromotionGate" in design_record["architecture_summary"]
    assert "schemas/connector_action_promotion_gate.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/connector_action_promotion_gate.schema.json" in design_record["schema_changes"]
    assert "no live connector invocation" in requirement_record["non_goals"]
    assert "scripts/validate_connector_action_promotion_gate.py" in design_record["validator_changes"]
    assert "tests/test_validate_connector_action_promotion_gate.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_readiness_waiver_review_packet_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_readiness_waiver_review_packet_20260616.json")
    design_path = Path("examples/sdlc/design_readiness_waiver_review_packet_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "readiness waiver review packet requirement")
    design_record = validator.load_json_object(design_path, "readiness waiver review packet design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "ReadinessWaiverReviewPacket" in design_record["architecture_summary"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in design_record["schema_changes"]
    assert "no deployment authority" in requirement_record["non_goals"]
    assert "scripts/validate_readiness_waiver_review_packet.py" in design_record["validator_changes"]
    assert "tests/test_validate_readiness_waiver_review_packet.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_browser_observation_receipt_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_browser_observation_receipt_20260616.json")
    design_path = Path("examples/sdlc/design_browser_observation_receipt_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "browser observation receipt requirement")
    design_record = validator.load_json_object(design_path, "browser observation receipt design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "BrowserObservationReceipt" in design_record["architecture_summary"]
    assert "schemas/browser_observation_receipt.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/browser_observation_receipt.schema.json" in design_record["schema_changes"]
    assert "no browser navigation authority" in requirement_record["non_goals"]
    assert "scripts/validate_browser_observation_receipt.py" in design_record["validator_changes"]
    assert "tests/test_validate_browser_observation_receipt.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_research_source_conflict_map_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_research_source_conflict_map_20260616.json")
    design_path = Path("examples/sdlc/design_research_source_conflict_map_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "research source conflict map requirement")
    design_record = validator.load_json_object(design_path, "research source conflict map design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "ResearchSourceConflictMap" in design_record["architecture_summary"]
    assert "schemas/research_source_conflict_map.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/research_source_conflict_map.schema.json" in design_record["schema_changes"]
    assert "no live web search" in requirement_record["non_goals"]
    assert "scripts/validate_research_source_conflict_map.py" in design_record["validator_changes"]
    assert "tests/test_validate_research_source_conflict_map.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_trusted_capture_evidence_packet_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_trusted_capture_evidence_packet_20260616.json")
    design_path = Path("examples/sdlc/design_trusted_capture_evidence_packet_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "trusted capture evidence packet requirement")
    design_record = validator.load_json_object(design_path, "trusted capture evidence packet design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "TrustedCaptureEvidencePacket" in design_record["architecture_summary"]
    assert "schemas/trusted_capture_evidence_packet.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/trusted_capture_evidence_packet.schema.json" in design_record["schema_changes"]
    assert "no live capture" in requirement_record["non_goals"]
    assert "scripts/validate_trusted_capture_evidence_packet.py" in design_record["validator_changes"]
    assert "tests/test_validate_trusted_capture_evidence_packet.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_sccml_trace_adapter_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_sccml_trace_adapter_witness_20260616.json")
    design_path = Path("examples/sdlc/design_sccml_trace_adapter_witness_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "sccml trace adapter witness requirement")
    design_record = validator.load_json_object(design_path, "sccml trace adapter witness design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "SccmlTraceAdapterWitness" in design_record["architecture_summary"]
    assert "schemas/sccml_trace_adapter_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/sccml_trace_adapter_witness.schema.json" in design_record["schema_changes"]
    assert "no live kernel execution" in requirement_record["non_goals"]
    assert "scripts/validate_sccml_trace_adapter_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_sccml_trace_adapter_witness.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_chaos_rehearsal_execution_report_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_chaos_rehearsal_execution_report_20260616.json")
    design_path = Path("examples/sdlc/design_chaos_rehearsal_execution_report_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "chaos rehearsal requirement")
    design_record = validator.load_json_object(design_path, "chaos rehearsal design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "ChaosRehearsalExecutionReport" in design_record["architecture_summary"]
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in design_record["schema_changes"]
    assert "no live chaos execution" in requirement_record["non_goals"]
    assert "scripts/validate_chaos_rehearsal_execution_report.py" in design_record["validator_changes"]
    assert "tests/test_validate_chaos_rehearsal_execution_report.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_invariant_fuzz_execution_report_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_invariant_fuzz_execution_report_20260617.json")
    design_path = Path("examples/sdlc/design_invariant_fuzz_execution_report_20260617.json")
    requirement_record = validator.load_json_object(requirement_path, "invariant fuzz requirement")
    design_record = validator.load_json_object(design_path, "invariant fuzz design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "InvariantFuzzExecutionReport" in design_record["architecture_summary"]
    assert "schemas/invariant_fuzz_execution_report.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/invariant_fuzz_execution_report.schema.json" in design_record["schema_changes"]
    assert "no canonical runtime mutation" in requirement_record["non_goals"]
    assert "scripts/validate_invariant_fuzz_execution_report.py" in design_record["validator_changes"]
    assert "tests/test_validate_invariant_fuzz_execution_report.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_world_substrate_replay_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_world_substrate_replay_witness_20260617.json")
    design_path = Path("examples/sdlc/design_world_substrate_replay_witness_20260617.json")
    requirement_record = validator.load_json_object(requirement_path, "world substrate replay witness requirement")
    design_record = validator.load_json_object(design_path, "world substrate replay witness design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "WorldSubstrateReplayWitness" in design_record["architecture_summary"]
    assert "schemas/world_substrate_replay_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/world_substrate_replay_witness.schema.json" in design_record["schema_changes"]
    assert "no live world service call" in requirement_record["non_goals"]
    assert "scripts/validate_world_substrate_replay_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_world_substrate_replay_witness.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_worker_receipt_ledger_read_model_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_worker_receipt_ledger_read_model_20260616.json")
    design_path = Path("examples/sdlc/design_worker_receipt_ledger_read_model_20260616.json")
    requirement_record = validator.load_json_object(requirement_path, "worker receipt ledger requirement")
    design_record = validator.load_json_object(design_path, "worker receipt ledger design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "WorkerReceiptLedgerReadModel" in design_record["architecture_summary"]
    assert "schemas/worker_receipt_ledger_read_model.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/worker_receipt_ledger_read_model.schema.json" in design_record["schema_changes"]
    assert "no worker dispatch" in requirement_record["non_goals"]
    assert "scripts/validate_worker_receipt_ledger_read_model.py" in design_record["validator_changes"]
    assert "tests/test_validate_worker_receipt_ledger_read_model.py" in design_record["validator_changes"]
    assert ".github/workflows/ci.yml" in design_record["validator_changes"]


def test_implementation_receipt_rejects_path_escape_and_unlisted_refs() -> None:
    implementation = copy.deepcopy(validator.load_example_records()["implementation_receipt"])
    implementation["changed_files"][0]["path"] = "../outside.py"
    implementation["validator_changes"].append("scripts/not_listed_validator.py")
    implementation["rollback_refs"] = []

    errors = validator.validate_artifact_record("implementation_receipt", implementation)

    assert any("changed file path must stay workspace-relative" in error for error in errors)
    assert any("validator_changes ref is not listed in changed_files" in error for error in errors)
    assert "implementation_receipt: rollback_refs are required" in errors


def test_transition_and_verification_must_reference_implementation_receipt() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["transition_receipt"]["required_receipt_refs"].remove(
        records["implementation_receipt"]["receipt_ref"]
    )
    invalid_records["verification_receipt"]["coverage_refs"].remove(
        "examples/sdlc/implementation_uao_validator.json"
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: transition must require implementation receipt" in errors
    assert "example_chain: verification coverage must include implementation receipt artifact" in errors
    assert len(errors) >= 2


def test_recovery_handoff_rejects_unclosed_recovery_constraints() -> None:
    recovery_handoff = copy.deepcopy(validator.load_example_records()["recovery_handoff"])
    recovery_handoff["rollback_state"] = "partial"
    recovery_handoff["incident_handoff_required"] = False
    recovery_handoff["accepted_risk_refs"] = ["risk://sdlc/accepted/001"]
    recovery_handoff["rollback_refs"] = []
    recovery_handoff["effect_boundary_refs"].append(recovery_handoff["effect_boundary_refs"][0])

    errors = validator.validate_artifact_record("recovery_handoff", recovery_handoff)

    assert "recovery_handoff: partial or blocked rollback requires incident handoff" in errors
    assert "recovery_handoff: accepted risks require incident handoff" in errors
    assert "recovery_handoff: rollback refs are required unless rollback is not_required" in errors
    assert "recovery_handoff: effect_boundary_refs must not contain duplicates" in errors
    assert any("rollback_refs" in error for error in errors)


def test_verification_must_reference_recovery_handoff_receipt() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["verification_receipt"]["coverage_refs"].remove(
        "examples/sdlc/recovery_handoff_uao_validator.json"
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: verification coverage must include recovery handoff receipt artifact" in errors
    assert len(errors) >= 1
    assert invalid_records["recovery_handoff"]["receipt_ref"] in invalid_records["closure_receipt"]["receipts"]


def test_workspace_preflight_receipt_is_required_for_terminal_closure() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["verification_receipt"]["commands"] = [
        item
        for item in invalid_records["verification_receipt"]["commands"]
        if item["name"] != "workspace_governance_preflight"
    ]
    invalid_records["verification_receipt"]["validator_outputs"] = [
        item
        for item in invalid_records["verification_receipt"]["validator_outputs"]
        if item["name"] != "workspace_governance_preflight"
    ]
    invalid_records["verification_receipt"]["coverage_refs"].remove(validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH)
    invalid_records["closure_receipt"]["receipts"].remove(validator.WORKSPACE_PREFLIGHT_RECEIPT_REF)

    verification_errors = validator.validate_artifact_record(
        "verification_receipt",
        invalid_records["verification_receipt"],
    )
    chain_errors = validator.validate_example_chain(invalid_records)

    assert "verification_receipt: missing command workspace_governance_preflight" in verification_errors
    assert any("workspace_governance_preflight" in error for error in verification_errors)
    assert (
        "example_chain: verification coverage must include workspace governance preflight receipt artifact"
        in chain_errors
    )
    assert "example_chain: closure must include workspace governance preflight receipt" in chain_errors
    assert len(verification_errors) + len(chain_errors) >= 4


def test_branch_ruleset_witness_is_required_for_pr_enforcement_closure() -> None:
    records = validator.load_example_records()
    invalid_implementation = copy.deepcopy(records["implementation_receipt"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_implementation["changed_files"] = [
        changed_file
        for changed_file in invalid_implementation["changed_files"]
        if changed_file["path"] != validator.BRANCH_RULESET_WITNESS_PATH
    ]
    invalid_implementation["documentation_changes"].remove(validator.BRANCH_RULESET_WITNESS_PATH)
    invalid_verification["coverage_refs"].remove(validator.BRANCH_RULESET_WITNESS_PATH)

    implementation_errors = validator.validate_artifact_record(
        "implementation_receipt",
        invalid_implementation,
    )
    verification_errors = validator.validate_artifact_record(
        "verification_receipt",
        invalid_verification,
    )

    assert any("changed_files missing required branch ruleset witness refs" in error for error in implementation_errors)
    assert any(
        "documentation_changes missing required branch ruleset witness refs" in error
        for error in implementation_errors
    )
    assert any("coverage_refs missing required branch ruleset witness refs" in error for error in verification_errors)
    assert len(implementation_errors) + len(verification_errors) >= 3


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "sdlc_artifact_validation_receipt"
    assert report["terminal_closure_required"] is True
    assert report["receipt_is_not_terminal_closure"] is True
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["error_count"] == 0
    assert report["check_count"] == 11
    assert any(check["name"] == "sdlc_gate_decision_envelopes" for check in report["checks"])
    assert any(check["name"] == "sdlc_inventory_closure" for check in report["checks"])
    assert any(check["name"] == "sdlc_workspace_preflight_closure" for check in report["checks"])
    assert any(check["name"] == "sdlc_recovery_handoff_retention" for check in report["checks"])
    assert any(check["name"] == "sdlc_branch_ruleset_witness_closure" for check in report["checks"])


def test_cli_text_output_reports_all_receipt_checks() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "[PASS] sdlc_workspace_preflight_closure" in output
    assert "[PASS] sdlc_recovery_handoff_retention" in output
    assert output.count("[PASS]") == validator.build_validation_report()["check_count"]
    assert output.endswith("STATUS: passed\n")


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    payload_path = tmp_path / "invalid-sdlc.json"
    payload_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(payload_path, "payload")

    assert payload_path.exists()
    assert payload_path.suffix == ".json"


def test_mfidel_substrate_conformance_receipt_requirement_and_design_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_mfidel_substrate_conformance_receipt_20260616.json")
    design_path = Path("examples/sdlc/design_mfidel_substrate_conformance_receipt_20260616.json")
    requirement = validator.load_json_object(requirement_path, "mfidel substrate requirement")
    design = validator.load_json_object(design_path, "mfidel substrate design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement)
    design_errors = validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in requirement["affected_surfaces"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_mfidel_substrate_conformance_receipt.py" in design["validator_changes"]


def test_maf_receipt_parity_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_receipt_parity_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_receipt_parity_witness_20260618.json")
    requirement_record = validator.load_json_object(requirement_path, "maf receipt parity requirement")
    design_record = validator.load_json_object(design_path, "maf receipt parity design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in design_record["schema_changes"]
    assert "scripts/validate_maf_receipt_parity_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_maf_receipt_parity_witness.py" in design_record["validator_changes"]


def test_maf_abi_cli_contract_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_abi_cli_contract_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_abi_cli_contract_witness_20260618.json")
    requirement_record = validator.load_json_object(requirement_path, "maf ABI CLI requirement")
    design_record = validator.load_json_object(design_path, "maf ABI CLI design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "schemas/maf_abi_cli_contract_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/maf_abi_cli_contract_witness.schema.json" in design_record["schema_changes"]
    assert "scripts/validate_maf_abi_cli_contract_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_maf_abi_cli_contract_witness.py" in design_record["validator_changes"]
    assert "no CLI execution" in requirement_record["non_goals"]


def test_maf_subprocess_effect_boundary_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_subprocess_effect_boundary_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_subprocess_effect_boundary_witness_20260618.json")
    requirement_record = validator.load_json_object(requirement_path, "maf subprocess requirement")
    design_record = validator.load_json_object(design_path, "maf subprocess design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "schemas/maf_subprocess_effect_boundary_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/maf_subprocess_effect_boundary_witness.schema.json" in design_record["schema_changes"]
    assert "scripts/validate_maf_subprocess_effect_boundary_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_maf_subprocess_effect_boundary_witness.py" in design_record["validator_changes"]
    assert "no subprocess execution" in requirement_record["non_goals"]


def test_maf_deterministic_fixture_parity_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_deterministic_fixture_parity_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_deterministic_fixture_parity_witness_20260618.json")
    requirement_record = validator.load_json_object(requirement_path, "maf deterministic fixture requirement")
    design_record = validator.load_json_object(design_path, "maf deterministic fixture design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "schemas/maf_deterministic_fixture_parity_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/maf_deterministic_fixture_parity_witness.schema.json" in design_record["schema_changes"]
    assert "scripts/validate_maf_deterministic_fixture_parity_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_maf_deterministic_fixture_parity_witness.py" in design_record["validator_changes"]
    assert "no raw fixture payload retention" in requirement_record["non_goals"]


def test_maf_failure_receipt_path_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_failure_receipt_path_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_failure_receipt_path_witness_20260618.json")
    requirement_record = validator.load_json_object(requirement_path, "maf failure receipt path requirement")
    design_record = validator.load_json_object(design_path, "maf failure receipt path design")

    requirement_errors = validator.validate_artifact_record("requirement", requirement_record)
    design_errors = validator.validate_artifact_record("design_decision", design_record)

    assert requirement_errors == []
    assert design_errors == []
    assert design_record["requirement_id"] == requirement_record["requirement_id"]
    assert "schemas/maf_failure_receipt_path_witness.schema.json" in requirement_record["affected_surfaces"]
    assert "schemas/maf_failure_receipt_path_witness.schema.json" in design_record["schema_changes"]
    assert "scripts/validate_maf_failure_receipt_path_witness.py" in design_record["validator_changes"]
    assert "tests/test_validate_maf_failure_receipt_path_witness.py" in design_record["validator_changes"]
    assert "no raw failure payload retention" in requirement_record["non_goals"]
