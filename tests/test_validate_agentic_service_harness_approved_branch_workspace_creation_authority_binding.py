"""Test approved branch workspace creation authority binding validation.

Purpose: verify the workspace authority binding grants only bounded creation
authority and denies later effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding.
Invariants:
  - Source preflight remains valid before authority binding is accepted.
  - Workspace creation authority does not imply workspace creation.
  - Filesystem writes, adapter execution, connector calls, receipt append, PR
    creation, mutation routes, secrets, and terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding as validator,
)


def test_approved_branch_workspace_creation_authority_binding_passes() -> None:
    validation = (
        validator.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding()
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_preflight_ok is True
    assert validation.source_preflight_ref == validator.EXPECTED_SOURCE_PREFLIGHT_REF


def test_approved_branch_workspace_creation_authority_binding_rejects_missing_authority() -> None:
    payload = validator.build_mutated_authority_binding(
        authority_binding_collected=False,
        workspace_creation_authority_granted=False,
        effect_boundary__workspace_create_authorized=False,
        authority_binding__source_preflight_satisfied=False,
    )

    errors: list[str] = []
    validator._validate_authority_binding_semantics(payload, _source_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_binding_collected must be true" in serialized_errors
    assert "workspace_creation_authority_granted must be true" in serialized_errors
    assert "effect_boundary.workspace_create_authorized must be true" in serialized_errors
    assert "authority_binding.source_preflight_satisfied must be true" in serialized_errors


def test_approved_branch_workspace_creation_authority_binding_rejects_effect_overclaim() -> None:
    payload = validator.build_mutated_authority_binding(
        workspace_created=True,
        effect_boundary__workspace_created=True,
        effect_boundary__filesystem_written=True,
        effect_boundary__branch_pushed=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__adapter_executed=True,
        authority_denials__filesystem_write_enabled=True,
        authority_denials__branch_push_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_authority_binding_semantics(payload, _source_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "workspace_created must be false" in serialized_errors
    assert "effect_boundary.filesystem_written must be false" in serialized_errors
    assert "effect_boundary.branch_pushed must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.adapter_executed must be false" in serialized_errors
    assert "authority_denials.filesystem_write_enabled must be false" in serialized_errors
    assert "authority_denials.branch_push_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_approved_branch_workspace_creation_authority_binding_rejects_missing_evidence_refs() -> None:
    payload = validator.build_mutated_authority_binding(
        required_evidence__before_authority_binding=["approval://operator/branch-workspace-create"],
        required_evidence__before_workspace_create=["evidence://workspace-path-confinement"],
        required_evidence__before_terminal_closure=["evidence://branch-workspace-create-observed"],
    )

    errors: list[str] = []
    validator._validate_authority_binding_semantics(payload, _source_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_evidence.before_authority_binding missing required ref" in serialized_errors
    assert "required_evidence.before_workspace_create missing required ref" in serialized_errors
    assert "required_evidence.before_terminal_closure missing required ref" in serialized_errors


def test_approved_branch_workspace_creation_authority_binding_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_authority_binding(
        next_action="POST /api/harness/workspace/create should not be encoded here",
    )
    payload["authority_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_authority_binding_semantics(payload, _source_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_approved_branch_workspace_creation_authority_binding_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "workspace-authority-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_preflight_ok"] is True


def _source_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_PREFLIGHT_EXAMPLES[0].read_text(encoding="utf-8"))
