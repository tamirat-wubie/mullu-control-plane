"""Test GitHub PR CI gate before ready-for-review witness validation.

Purpose: verify the PR CI gate witness remains read-only, uncollected,
and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness.
Invariants:
  - Missing CI gate evidence never grants ready-for-review or PR effects.
  - Effect reconciliation remains as the only terminal closure witness.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness as validator


def test_github_pr_ci_gate_before_ready_for_review_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert (
        validation.source_repository_effect_rollback_plan_witness_ref
        == validator.EXPECTED_SOURCE_ROLLBACK_PLAN_WITNESS_REF
    )


def test_github_pr_ci_gate_before_ready_for_review_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_ci_gate_before_ready_for_review_witness(
        ci_gate_collected=True,
        authority_granted=True,
        ci_gate__repository_effect_rollback_plan_satisfied=True,
        ci_gate__ci_gate_before_ready_for_review_collected=True,
        ci_gate__ready_for_review_authorized_after_ci_gate=True,
        ci_gate__pull_request_creation_authorized_after_ci_gate=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_ci_gate_before_ready_for_review_witness_semantics(
        payload,
        _source_rollback_plan_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "ci_gate_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "ci_gate.repository_effect_rollback_plan_satisfied must be false" in serialized_errors
    assert "ci_gate.ci_gate_before_ready_for_review_collected must be false" in serialized_errors
    assert "ci_gate.ready_for_review_authorized_after_ci_gate must be false" in serialized_errors
    assert "ci_gate.pull_request_creation_authorized_after_ci_gate must be false" in serialized_errors


def test_github_pr_ci_gate_before_ready_for_review_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_ci_gate_before_ready_for_review_witness(
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__ready_for_review_enabled=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__ready_for_review_marked=True,
        effect_boundary__repository_written=True,
    )

    errors: list[str] = []
    validator._validate_ci_gate_before_ready_for_review_witness_semantics(
        payload,
        _source_rollback_plan_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.ready_for_review_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.ready_for_review_marked must be false" in serialized_errors


def test_github_pr_ci_gate_before_ready_for_review_witness_rejects_witness_drift() -> None:
    payload = validator.build_mutated_ci_gate_before_ready_for_review_witness(
        remaining_witnesses=[
            {
                "witness_kind": "ci_gate_before_ready_for_review",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://ci-gate-before-ready-for-review",
                "blocks_terminal_closure": False,
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_ci_gate_before_ready_for_review_witness_semantics(
        payload,
        _source_rollback_plan_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_terminal_closure must be true" in serialized_errors


def test_github_pr_ci_gate_before_ready_for_review_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_ci_gate_before_ready_for_review_witness(
        requested_evidence_ref="POST /api/github/ready-for-review authority",
    )
    payload["ci_gate"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_ci_gate_before_ready_for_review_witness_semantics(
        payload,
        _source_rollback_plan_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_ci_gate_before_ready_for_review_witness_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-ci-gate-before-ready-for-review-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert (
        file_payload["source_repository_effect_rollback_plan_witness_ref"]
        == validator.EXPECTED_SOURCE_ROLLBACK_PLAN_WITNESS_REF
    )


def _source_rollback_plan_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_ROLLBACK_PLAN_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
