"""Test GitHub PR branch-write authority binding validation.

Purpose: verify the PR branch-write authority binding remains read-only,
uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_branch_write_authority_binding.
Invariants:
  - Missing branch-write authority never grants branch or PR effects.
  - Remaining witnesses block PR admission.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_branch_write_authority_binding as validator


def test_github_pr_branch_write_authority_binding_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_branch_write_authority_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_response_witness_ref == validator.EXPECTED_SOURCE_RESPONSE_WITNESS_REF


def test_github_pr_branch_write_authority_binding_rejects_collected_authority() -> None:
    payload = validator.build_mutated_branch_write_authority_binding(
        authority_binding_collected=True,
        authority_granted=True,
        branch_write_binding__response_witness_satisfied=True,
        branch_write_binding__branch_write_authority_collected=True,
        branch_write_binding__pr_creation_authorized_after_binding=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_branch_write_authority_binding_semantics(payload, _source_response_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_binding_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "branch_write_binding.response_witness_satisfied must be false" in serialized_errors
    assert "branch_write_binding.branch_write_authority_collected must be false" in serialized_errors
    assert "branch_write_binding.pr_creation_authorized_after_binding must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_branch_write_authority_binding_rejects_effect_authority() -> None:
    payload = validator.build_mutated_branch_write_authority_binding(
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_branch_write_authority_binding_semantics(payload, _source_response_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_branch_write_authority_binding_rejects_witness_drift() -> None:
    payload = validator.build_mutated_branch_write_authority_binding(
        remaining_witnesses=[
            {
                "witness_kind": "uao_pr_admission",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://uao-pr-admission",
                "blocks_pr_admission": False,
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_branch_write_authority_binding_semantics(payload, _source_response_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors


def test_github_pr_branch_write_authority_binding_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_branch_write_authority_binding(
        requested_evidence_ref="POST /api/github/branch-write-authority",
    )
    payload["branch_write_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_branch_write_authority_binding_semantics(payload, _source_response_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_branch_write_authority_binding_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-branch-write-authority-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_response_witness_ref"] == validator.EXPECTED_SOURCE_RESPONSE_WITNESS_REF


def _source_response_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_RESPONSE_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
