"""Test temporary branch workspace preflight validation.

Purpose: verify the harness branch workspace preflight remains contract-only
and cannot drift into branch creation, filesystem writes, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_temporary_branch_workspace_preflight.
Invariants:
  - Workspace creation and branch writes remain blocked without approval.
  - Command/path/network/timeout/cleanup gates remain explicit.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_temporary_branch_workspace_preflight as validator


def test_temporary_branch_workspace_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_temporary_branch_workspace_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_contract_ref == validator.EXPECTED_SOURCE_CONTRACT_REF


def test_temporary_branch_workspace_preflight_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__branch_created=True,
        scope__filesystem_write_enabled=True,
        authority_denials__branch_workspace_create_enabled=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__runtime_state_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.branch_created must be false" in serialized_errors
    assert "scope.filesystem_write_enabled must be false" in serialized_errors
    assert "authority_denials.branch_workspace_create_enabled must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.runtime_state_write_enabled must be false" in serialized_errors


def test_temporary_branch_workspace_preflight_rejects_allowlist_drift() -> None:
    payload = validator.build_mutated_preflight(
        workspace_preflight__command_allowlist=["git.status"],
        workspace_preflight__path_allowlist=["."],
        workspace_preflight__network_policy="proxy_allowlist",
        workspace_preflight__timeout_seconds=900,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "workspace_preflight.command_allowlist must match source sandbox" in serialized_errors
    assert "workspace_preflight.command_allowlist must match required set" in serialized_errors
    assert "workspace_preflight.path_allowlist must match required set" in serialized_errors
    assert "workspace_preflight.timeout_seconds must match source sandbox" in serialized_errors
    assert "workspace_preflight.network_policy must match source sandbox" in serialized_errors
    assert "workspace_preflight.network_policy must be none" in serialized_errors


def test_temporary_branch_workspace_preflight_rejects_cleanup_and_ref_drift() -> None:
    payload = validator.build_mutated_preflight(
        cleanup_plan__cleanup_required=False,
        cleanup_plan__cleanup_verified=True,
        cleanup_plan__residual_state_allowed=True,
        workspace_preflight__required_before_create_refs=["approval-request://harness/gate.branchwrite"],
        workspace_preflight__blocked_reason_refs=["blocked://operator-approval/not-present"],
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "cleanup_plan.cleanup_required must be true" in serialized_errors
    assert "cleanup_plan.cleanup_verified must be false" in serialized_errors
    assert "cleanup_plan.residual_state_allowed must be false" in serialized_errors
    assert "workspace_preflight.required_before_create_refs missing required ref" in serialized_errors
    assert "workspace_preflight.blocked_reason_refs missing required ref" in serialized_errors


def test_temporary_branch_workspace_preflight_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/workspaces/create should never be admitted",
    )
    payload["workspace_preflight"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_temporary_branch_workspace_preflight_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "temporary-branch-workspace-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_contract_ref"] == validator.EXPECTED_SOURCE_CONTRACT_REF


def _source_contract() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CONTRACT.read_text(encoding="utf-8"))
