"""Test GitHub PR operator response witness validation.

Purpose: verify the PR operator response witness remains read-only, missing,
and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_operator_response_witness.
Invariants:
  - Missing operator response binds to the actual-diff approval request binding.
  - Missing operator response never grants PR creation or repository effects.
  - Remaining witnesses block PR admission.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_operator_response_witness as validator


def test_github_pr_operator_response_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_operator_response_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_approval_request_ref == validator.EXPECTED_SOURCE_APPROVAL_REQUEST_REF
    assert (
        validation.source_actual_diff_approval_request_binding_ref
        == validator.EXPECTED_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_REF
    )


def test_github_pr_operator_response_witness_rejects_collected_response() -> None:
    payload = validator.build_mutated_response_witness(
        response_record_collected=True,
        approval_satisfied=True,
        rejection_recorded=True,
        authority_granted=True,
        operator_response__response_record_collected=True,
        operator_response__pr_creation_authorized_after_response=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_response_witness_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "response_record_collected must be false" in serialized_errors
    assert "approval_satisfied must be false" in serialized_errors
    assert "rejection_recorded must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "operator_response.pr_creation_authorized_after_response must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_operator_response_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_response_witness(
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_response_witness_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_operator_response_witness_rejects_witness_drift() -> None:
    payload = validator.build_mutated_response_witness(
        remaining_witnesses=[
            {
                "witness_kind": "branch_write_authority",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://branch-write-authority-binding",
                "blocks_pr_admission": False,
                "authority_granted": False,
            }
        ],
        operator_response__required_response_kinds=["record_operator_pr_approval_witness"],
    )

    errors: list[str] = []
    validator._validate_response_witness_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors
    assert "operator_response.required_response_kinds missing required value" in serialized_errors


def test_github_pr_operator_response_witness_rejects_actual_diff_binding_drift() -> None:
    payload = validator.build_mutated_response_witness(
        source_actual_diff_approval_request_binding_ref="examples/agentic_service_harness_github_pr_operator_approval_request.foundation.json",
        operator_response__requires_actual_non_empty_diff_approval_request_binding=False,
        operator_response__actual_diff_approval_request_binding_ref="examples/agentic_service_harness_github_pr_operator_approval_request.foundation.json",
        operator_response__actual_non_empty_diff_receipt_ref="witness://wrong-diff",
        operator_response__changed_file_refs=["evidence://wrong-file"],
        operator_response__diff_refs=["evidence://wrong-diff"],
        operator_response__redacted_diff_bundle_ref="digest://wrong-bundle",
        operator_response__redacted_output_ref="witness://wrong-output",
    )

    errors: list[str] = []
    validator._validate_response_witness_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "source_actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "operator_response.requires_actual_non_empty_diff_approval_request_binding must be true" in serialized_errors
    assert "operator_response.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "operator_response.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "operator_response.changed_file_refs expected" in serialized_errors
    assert "operator_response.diff_refs expected" in serialized_errors
    assert "operator_response.redacted_diff_bundle_ref expected" in serialized_errors
    assert "operator_response.redacted_output_ref expected" in serialized_errors


def test_github_pr_operator_response_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_response_witness(
        requested_evidence_ref="POST /api/github/pr-response",
    )
    payload["operator_response"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_response_witness_semantics(
        payload,
        _source_approval_request(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_operator_response_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-operator-response-witness-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_approval_request_ref"] == validator.EXPECTED_SOURCE_APPROVAL_REQUEST_REF
    assert (
        file_payload["source_actual_diff_approval_request_binding_ref"]
        == validator.EXPECTED_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_REF
    )


def _source_approval_request() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_APPROVAL_REQUEST_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_actual_diff_binding() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_EXAMPLES[0].read_text(encoding="utf-8"))
