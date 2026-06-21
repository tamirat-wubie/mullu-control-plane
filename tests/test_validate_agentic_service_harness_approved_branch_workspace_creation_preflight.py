"""Test approved branch workspace creation preflight validation.

Purpose: verify the approval-binding preflight remains non-terminal and cannot
drift into branch creation, filesystem writes, adapter execution, or receipt
append authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight.
Invariants:
  - Source preflight validators pass before this preflight is accepted.
  - Branch workspace creation and filesystem writes remain blocked.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_approved_branch_workspace_creation_preflight as validator,
)


def test_approved_branch_workspace_creation_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_approved_branch_workspace_creation_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_validators_ok is True


def test_approved_branch_workspace_creation_preflight_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__branch_workspace_creation_admitted=True,
        scope__branch_created=True,
        scope__filesystem_write_enabled=True,
        authority_denials__branch_workspace_create_enabled=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__adapter_execution_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.branch_workspace_creation_admitted must be false" in serialized_errors
    assert "scope.branch_created must be false" in serialized_errors
    assert "scope.filesystem_write_enabled must be false" in serialized_errors
    assert "authority_denials.branch_workspace_create_enabled must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.adapter_execution_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors


def test_approved_branch_workspace_creation_preflight_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        approval_binding__required_before_create_refs=["approval://operator/branch-workspace-create"],
        approval_binding__blocked_reason_refs=["blocked://operator-approval/not-collected"],
        approval_binding__next_required_evidence_refs=["evidence://dry-run-test-runner-plan-receipt"],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "approval_binding.required_before_create_refs missing required ref" in serialized_errors
    assert "approval_binding.blocked_reason_refs missing required ref" in serialized_errors
    assert "approval_binding.next_required_evidence_refs missing required ref" in serialized_errors


def test_approved_branch_workspace_creation_preflight_rejects_approval_drift() -> None:
    payload = validator.build_mutated_preflight(
        approval_binding__approval_state="APPROVED",
        approval_binding__operator_approval_collected=True,
        approval_binding__uao_admission_collected=True,
        approval_binding__cleanup_evidence_collected=True,
        approval_binding__workspace_create_route_admitted=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "approval_binding.approval_state must be AWAITING_OPERATOR_APPROVAL" in serialized_errors
    assert "approval_binding.operator_approval_collected must be false" in serialized_errors
    assert "approval_binding.uao_admission_collected must be false" in serialized_errors
    assert "approval_binding.cleanup_evidence_collected must be false" in serialized_errors
    assert "approval_binding.workspace_create_route_admitted must be false" in serialized_errors


def test_approved_branch_workspace_creation_preflight_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/branch-workspace/create should never be admitted",
    )
    payload["approval_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_approved_branch_workspace_creation_preflight_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "approved-branch-workspace-creation-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
