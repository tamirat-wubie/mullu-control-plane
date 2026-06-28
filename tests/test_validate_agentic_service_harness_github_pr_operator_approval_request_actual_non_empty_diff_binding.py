"""Test GitHub PR approval request actual non-empty diff binding validation.

Purpose: verify the PR approval request is bound to actual non-empty diff
admission evidence while remaining read-only, uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.
Invariants:
  - Approval request binding consumes actual non-empty diff admission evidence.
  - Operator response and PR creation remain blocked.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding
    as validator,
)


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_passes() -> None:
    validation = (
        validator.validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding()
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_operator_approval_request_ref == validator.EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_authority_drift() -> None:
    payload = validator.build_mutated_approval_request_actual_non_empty_diff_binding(
        approval_request_diff_binding__operator_response_collected=True,
        approval_request_diff_binding__operator_approval_granted=True,
        approval_request_diff_binding__pull_request_creation_authorized=True,
        authority_denials__operator_response_collected=True,
        authority_denials__operator_approval_granted=True,
        effect_boundary__operator_response_recorded=True,
        effect_boundary__pull_request_opened=True,
    )

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_admission(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "approval_request_diff_binding.operator_response_collected must be false" in serialized_errors
    assert "approval_request_diff_binding.operator_approval_granted must be false" in serialized_errors
    assert "approval_request_diff_binding.pull_request_creation_authorized must be false" in serialized_errors
    assert "authority_denials.operator_response_collected must be false" in serialized_errors
    assert "authority_denials.operator_approval_granted must be false" in serialized_errors
    assert "effect_boundary.operator_response_recorded must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_ref_drift() -> None:
    payload = validator.build_mutated_approval_request_actual_non_empty_diff_binding(
        approval_request_diff_binding__changed_file_count=2,
        approval_request_diff_binding__changed_file_refs=["evidence://wrong-file"],
        approval_request_diff_binding__diff_refs=["evidence://wrong-diff"],
        approval_request_diff_binding__redacted_output_ref="witness://wrong-output",
    )

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_admission(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "approval_request_diff_binding.changed_file_count expected" in serialized_errors
    assert "approval_request_diff_binding.changed_file_refs expected" in serialized_errors
    assert "approval_request_diff_binding.diff_refs expected" in serialized_errors
    assert "approval_request_diff_binding.redacted_output_ref expected" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_missing_gate_refs() -> None:
    payload = validator.build_mutated_approval_request_actual_non_empty_diff_binding(
        approval_request_diff_binding__required_before_pr_refs=[
            "examples/agentic_service_harness_github_pr_operator_approval_request.foundation.json"
        ],
        approval_request_diff_binding__blocked_reason_refs=[
            "blocked://operator-response/not-collected"
        ],
    )

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_admission(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "required_before_pr_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "witness://github-pr-terminal-closure-certificate" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_witness_drift() -> None:
    payload = validator.build_mutated_approval_request_actual_non_empty_diff_binding(
        remaining_witnesses=[
            {
                "witness_kind": "operator_response_record",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://operator-approval-for-pr-admission",
                "blocks_pr_admission": False,
                "authority_granted": True,
            }
        ]
    )

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_admission(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors
    assert "remaining_witnesses.0.authority_granted must be false" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_source_drift() -> None:
    source_approval_request = _source_approval_request()
    source_actual_diff_admission = _source_actual_diff_admission()
    source_approval_request["request_id"] = "wrong"
    source_actual_diff_admission["binding_id"] = "wrong"

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        validator.build_mutated_approval_request_actual_non_empty_diff_binding(),
        source_approval_request,
        source_actual_diff_admission,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "GitHub PR operator approval request source: request_id expected" in serialized_errors
    assert "GitHub PR actual non-empty diff admission source: binding_id expected" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_rejects_mutation_route_and_secret() -> None:
    payload = validator.build_mutated_approval_request_actual_non_empty_diff_binding(
        approval_request_diff_binding__requested_evidence_ref="POST /api/github/pr-approval"
    )
    payload["approval_request_diff_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_approval_request_actual_diff_binding_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_admission(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_operator_approval_request_actual_non_empty_diff_binding_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-operator-approval-request-actual-diff-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert (
        file_payload["source_actual_non_empty_diff_admission_binding_ref"]
        == validator.EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF
    )


def _source_approval_request() -> dict[str, object]:
    return json.loads(validator.DEFAULT_OPERATOR_APPROVAL_REQUEST_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_actual_diff_admission() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ACTUAL_DIFF_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))
