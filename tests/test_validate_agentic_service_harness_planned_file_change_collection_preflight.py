"""Test planned file-change collection preflight validation.

Purpose: verify planned file-change collection remains preflight-only,
authority-bound, cleanup-gated, redacted, and effect-denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_planned_file_change_collection_preflight.
Invariants:
  - The preflight binds to workspace sandbox and branch-write authority sources.
  - Branch creation, file writes, actual diff collection, approval grant,
    cleanup execution, mutation routes, secret-like payloads, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_planned_file_change_collection_preflight as validator


def test_planned_file_change_collection_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_planned_file_change_collection_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.workspace_sandbox_preflight_ref == validator.EXPECTED_WORKSPACE_SANDBOX_REF
    assert validation.branch_write_authority_binding_ref == validator.EXPECTED_BRANCH_WRITE_AUTHORITY_REF


def test_planned_file_change_collection_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__workspace_write_authority_granted=True,
        scope__branch_write_authority_collected=True,
        scope__planned_file_change_collection_admitted=True,
        scope__actual_file_change_collection_started=True,
        authority_gates__operator_approval_collected=True,
        authority_gates__collection_admitted=True,
        effect_denials__files_written=True,
        effect_denials__actual_diff_collected=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _workspace_preflight(), _branch_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.workspace_write_authority_granted must be false" in serialized_errors
    assert "scope.branch_write_authority_collected must be false" in serialized_errors
    assert "scope.planned_file_change_collection_admitted must be false" in serialized_errors
    assert "scope.actual_file_change_collection_started must be false" in serialized_errors
    assert "authority_gates.operator_approval_collected must be false" in serialized_errors
    assert "authority_gates.collection_admitted must be false" in serialized_errors
    assert "effect_denials.files_written must be false" in serialized_errors
    assert "effect_denials.actual_diff_collected must be false" in serialized_errors


def test_planned_file_change_collection_rejects_missing_refs() -> None:
    payload = validator.build_mutated_preflight(
        collection_contract__forbidden_action_classes=["write_files"],
        collection_contract__allowed_file_change_kinds=["schema_patch"],
        collection_contract__required_before_collection_refs=[
            "examples/agentic_service_harness_workspace_sandbox_preflight.foundation.json"
        ],
        collection_contract__required_validation_refs=[
            "scripts/validate_agentic_service_harness_planned_file_change_collection_preflight.py"
        ],
        authority_gates__blocked_reason_refs=["blocked://branch-write-authority/not-collected"],
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _workspace_preflight(), _branch_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "collection_contract.forbidden_action_classes missing required ref" in serialized_errors
    assert "collection_contract.allowed_file_change_kinds missing required ref" in serialized_errors
    assert "collection_contract.required_before_collection_refs missing required ref" in serialized_errors
    assert "collection_contract.required_validation_refs missing required ref" in serialized_errors
    assert "authority_gates.blocked_reason_refs missing required ref" in serialized_errors


def test_planned_file_change_collection_rejects_path_and_redaction_drift() -> None:
    payload = validator.build_mutated_preflight(
        path_policy__path_allowlist=["/"],
        path_policy__absolute_paths_allowed=True,
        path_policy__parent_traversal_allowed=True,
        path_policy__secret_paths_allowed=True,
        redaction_policy__secret_redaction_required=False,
        redaction_policy__diff_redaction_required=False,
        redaction_policy__credential_value_serialization_allowed=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _workspace_preflight(), _branch_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "path_policy.path_allowlist must match workspace sandbox preflight" in serialized_errors
    assert "path_policy.absolute_paths_allowed must be false" in serialized_errors
    assert "path_policy.parent_traversal_allowed must be false" in serialized_errors
    assert "path_policy.secret_paths_allowed must be false" in serialized_errors
    assert "redaction_policy.secret_redaction_required must match workspace sandbox preflight" in serialized_errors
    assert "redaction_policy.secret_redaction_required must be true" in serialized_errors
    assert "redaction_policy.diff_redaction_required must be true" in serialized_errors
    assert "redaction_policy.credential_value_serialization_allowed must be false" in serialized_errors


def test_planned_file_change_collection_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/file-changes should never be admitted",
    )
    payload["collection_contract"]["access_token_envelope"] = {"redacted": True}
    payload["collection_contract"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _workspace_preflight(), _branch_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_planned_file_change_collection_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "planned-file-change-collection-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["workspace_sandbox_preflight_ref"] == validator.EXPECTED_WORKSPACE_SANDBOX_REF
    assert file_payload["branch_write_authority_binding_ref"] == validator.EXPECTED_BRANCH_WRITE_AUTHORITY_REF


def _workspace_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_WORKSPACE_SANDBOX_EXAMPLES[0].read_text(encoding="utf-8"))


def _branch_authority() -> dict[str, object]:
    return json.loads(validator.DEFAULT_BRANCH_WRITE_AUTHORITY_EXAMPLES[0].read_text(encoding="utf-8"))
