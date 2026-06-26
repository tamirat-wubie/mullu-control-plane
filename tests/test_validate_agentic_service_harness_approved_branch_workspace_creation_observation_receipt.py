"""Test approved branch workspace creation observation receipt validation.

Purpose: verify the workspace observation receipt records only a confined
workspace-create effect and denies later harness effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt.
Invariants:
  - Source authority binding remains valid before observation is accepted.
  - Workspace creation observation does not imply file writes or adapter work.
  - Branch push, PR creation, receipt append, mutation routes, secrets, and
    terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt as validator,
)


def test_approved_branch_workspace_creation_observation_receipt_passes() -> None:
    validation = (
        validator.validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt()
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_authority_binding_ok is True
    assert validation.source_authority_binding_ref == validator.EXPECTED_SOURCE_AUTHORITY_REF


def test_approved_branch_workspace_creation_observation_receipt_rejects_missing_observation() -> None:
    payload = validator.build_mutated_observation_receipt(
        workspace_creation_observed=False,
        workspace_created=False,
        observation__source_authority_binding_satisfied=False,
        observation__workspace_path_confined=False,
        effect_boundary__workspace_created=False,
    )

    errors: list[str] = []
    validator._validate_observation_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "workspace_creation_observed must be true" in serialized_errors
    assert "workspace_created must be true" in serialized_errors
    assert "observation.source_authority_binding_satisfied must be true" in serialized_errors
    assert "observation.workspace_path_confined must be true" in serialized_errors
    assert "effect_boundary.workspace_created must be true" in serialized_errors


def test_approved_branch_workspace_creation_observation_receipt_rejects_later_effects() -> None:
    payload = validator.build_mutated_observation_receipt(
        terminal_closure=True,
        effect_boundary__filesystem_written=True,
        effect_boundary__branch_pushed=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__adapter_executed=True,
        effect_boundary__receipt_store_appended=True,
        authority_denials__filesystem_write_enabled=True,
        authority_denials__branch_push_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_observation_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "terminal_closure must be false" in serialized_errors
    assert "effect_boundary.filesystem_written must be false" in serialized_errors
    assert "effect_boundary.branch_pushed must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.adapter_executed must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors
    assert "authority_denials.filesystem_write_enabled must be false" in serialized_errors
    assert "authority_denials.branch_push_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_approved_branch_workspace_creation_observation_receipt_rejects_missing_next_evidence_refs() -> None:
    payload = validator.build_mutated_observation_receipt(
        required_next_evidence__before_filesystem_write=["evidence://workspace/post-create-observation"],
        required_next_evidence__before_adapter_execution=["approval://adapter-execution/operator-decision"],
        required_next_evidence__before_receipt_append=["evidence://receipt-store-append-preflight"],
        required_next_evidence__before_pull_request_creation=["evidence://github-pr-admission-preflight"],
        required_next_evidence__before_terminal_closure=["evidence://cleanup-receipt-after-workspace-use"],
    )

    errors: list[str] = []
    validator._validate_observation_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_next_evidence.before_filesystem_write missing required ref" in serialized_errors
    assert "required_next_evidence.before_adapter_execution missing required ref" in serialized_errors
    assert "required_next_evidence.before_receipt_append missing required ref" in serialized_errors
    assert "required_next_evidence.before_pull_request_creation missing required ref" in serialized_errors
    assert "required_next_evidence.before_terminal_closure missing required ref" in serialized_errors


def test_approved_branch_workspace_creation_observation_receipt_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_observation_receipt(
        next_action="POST /api/harness/workspace/write should not be encoded here",
    )
    payload["observation"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_observation_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_approved_branch_workspace_creation_observation_receipt_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "workspace-observation-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_authority_binding_ok"] is True


def _source_authority() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_AUTHORITY_EXAMPLES[0].read_text(encoding="utf-8"))
