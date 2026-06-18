"""Test GitHub PR UAO admission witness validation.

Purpose: verify the PR UAO PR admission witness remains read-only,
uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_uao_admission_witness.
Invariants:
  - Missing UAO PR admission never grants branch or PR effects.
  - Remaining witnesses block PR admission.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_uao_admission_witness as validator


def test_github_pr_uao_admission_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_uao_admission_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_branch_write_binding_ref == validator.EXPECTED_SOURCE_BRANCH_WRITE_BINDING_REF


def test_github_pr_uao_admission_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_uao_admission_witness(
        authority_binding_collected=True,
        authority_granted=True,
        uao_admission__response_witness_satisfied=True,
        uao_admission__uao_pr_admission_collected=True,
        uao_admission__pr_creation_authorized_after_binding=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_uao_admission_witness_semantics(payload, _source_branch_write_binding(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_binding_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "uao_admission.response_witness_satisfied must be false" in serialized_errors
    assert "uao_admission.uao_pr_admission_collected must be false" in serialized_errors
    assert "uao_admission.pr_creation_authorized_after_binding must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_uao_admission_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_uao_admission_witness(
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_uao_admission_witness_semantics(payload, _source_branch_write_binding(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_uao_admission_witness_rejects_witness_drift() -> None:
    payload = validator.build_mutated_uao_admission_witness(
        remaining_witnesses=[
            {
                "witness_kind": "repository_effect_rollback_plan",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://repository-effect-rollback-plan",
                "blocks_pr_admission": False,
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_uao_admission_witness_semantics(payload, _source_branch_write_binding(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors


def test_github_pr_uao_admission_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_uao_admission_witness(
        requested_evidence_ref="POST /api/github/UAO PR admission-authority",
    )
    payload["uao_admission"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_uao_admission_witness_semantics(payload, _source_branch_write_binding(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_uao_admission_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-uao-pr-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_branch_write_binding_ref"] == validator.EXPECTED_SOURCE_BRANCH_WRITE_BINDING_REF


def _source_branch_write_binding() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_BRANCH_WRITE_BINDING_EXAMPLES[0].read_text(encoding="utf-8"))
