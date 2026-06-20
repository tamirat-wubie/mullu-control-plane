"""Test workspace sandbox preflight validation.

Purpose: verify the harness temporary branch workspace preflight remains
contract-only, approval-bound, cleanup-gated, and effect-denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_workspace_sandbox_preflight.
Invariants:
  - The preflight binds to the branch-write-awaiting-approval sandbox.
  - Branch creation, writes, command execution, approval grant, cleanup
    execution, mutation routes, secret-like payloads, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_workspace_sandbox_preflight as validator


def test_workspace_sandbox_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_workspace_sandbox_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_contract_ref == validator.EXPECTED_SOURCE_CONTRACT_REF


def test_workspace_sandbox_preflight_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__approval_collected=True,
        scope__authority_granted=True,
        scope__branch_workspace_created=True,
        scope__workspace_write_enabled=True,
        effect_denials__branch_created=True,
        effect_denials__files_written=True,
        effect_denials__commands_executed=True,
        effect_denials__runtime_state_written=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.approval_collected must be false" in serialized_errors
    assert "scope.authority_granted must be false" in serialized_errors
    assert "scope.branch_workspace_created must be false" in serialized_errors
    assert "scope.workspace_write_enabled must be false" in serialized_errors
    assert "effect_denials.branch_created must be false" in serialized_errors
    assert "effect_denials.files_written must be false" in serialized_errors
    assert "effect_denials.commands_executed must be false" in serialized_errors
    assert "effect_denials.runtime_state_written must be false" in serialized_errors


def test_workspace_sandbox_preflight_rejects_sandbox_control_drift() -> None:
    payload = validator.build_mutated_preflight(
        sandbox_controls__command_allowlist=["git.status"],
        sandbox_controls__path_allowlist=["/"],
        sandbox_controls__timeout_seconds=3600,
        sandbox_controls__network_policy="proxy_allowlist",
        sandbox_controls__production_mutation_allowed=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "sandbox_controls.command_allowlist must match source sandbox" in serialized_errors
    assert "sandbox_controls.path_allowlist must match source sandbox" in serialized_errors
    assert "sandbox_controls.timeout_seconds must match source sandbox" in serialized_errors
    assert "sandbox_controls.network_policy must match source sandbox" in serialized_errors
    assert "sandbox_controls.network_policy must stay none" in serialized_errors
    assert "sandbox_controls.production_mutation_allowed must be false" in serialized_errors


def test_workspace_sandbox_preflight_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_preflight(
        workspace_preflight_contract__required_source_refs=[
            "examples/agentic_service_harness.branch_write_awaiting_approval.json"
        ],
        workspace_preflight_contract__required_gate_refs=["gate://harness/no-branch-creation"],
        workspace_preflight_contract__preflight_obligations_checked=[
            "obligation://bind-command-allowlist"
        ],
        workspace_preflight_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_workspace_sandbox_preflight.py"
        ],
        cleanup_gate__required_before_workspace_write_refs=[
            "evidence://workspace-path-confinement"
        ],
        cleanup_gate__blocked_reason_refs=["blocked://workspace/write-authority-not-granted"],
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "workspace_preflight_contract.required_source_refs missing required ref" in serialized_errors
    assert "workspace_preflight_contract.required_gate_refs missing required ref" in serialized_errors
    assert "workspace_preflight_contract.preflight_obligations_checked missing required ref" in serialized_errors
    assert "workspace_preflight_contract.validation_refs missing required ref" in serialized_errors
    assert "cleanup_gate.required_before_workspace_write_refs missing required ref" in serialized_errors
    assert "cleanup_gate.blocked_reason_refs missing required ref" in serialized_errors


def test_workspace_sandbox_preflight_rejects_cleanup_and_secret_drift() -> None:
    payload = validator.build_mutated_preflight(
        cleanup_gate__cleanup_receipt_required=False,
        cleanup_gate__cleanup_receipt_emitted=True,
        cleanup_gate__cleanup_execution_allowed=True,
        next_action="POST /api/harness/workspaces should never be admitted",
    )
    payload["workspace_preflight_contract"]["serialized_token_value"] = "github_pat_forbiddencredential"
    payload["workspace_preflight_contract"]["access_token_envelope"] = {
        "redacted": True
    }

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "cleanup_gate.cleanup_receipt_required must be true" in serialized_errors
    assert "cleanup_gate.cleanup_receipt_emitted must be false" in serialized_errors
    assert "cleanup_gate.cleanup_execution_allowed must be false" in serialized_errors
    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_workspace_sandbox_preflight_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "workspace-sandbox-preflight-validation.json"

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
    return json.loads(validator.DEFAULT_SOURCE_CONTRACT_EXAMPLES[0].read_text(encoding="utf-8"))
