"""Test GitHub PR actual non-empty diff admission binding validation.

Purpose: verify PR admission consumes actual non-empty diff refs without
granting branch, PR, repository, connector, raw-content, receipt append, or
terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.
Invariants:
  - Redacted changed-file and diff refs match the source actual diff binding.
  - Remaining witnesses block PR admission.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding as validator


def test_github_pr_actual_non_empty_diff_admission_binding_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_pr_admission_preflight_ref == validator.EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF
    assert (
        validation.source_actual_non_empty_diff_receipt_binding_ref
        == validator.EXPECTED_SOURCE_ACTUAL_DIFF_BINDING_REF
    )


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_authority_drift() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(
        pr_admission_diff_binding__pr_admitted=True,
        pr_admission_diff_binding__pull_request_creation_authorized=True,
        authority_denials__pr_admitted=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__repository_written=True,
    )

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        _source_preflight(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "pr_admission_diff_binding.pr_admitted must be false" in serialized_errors
    assert "pr_admission_diff_binding.pull_request_creation_authorized must be false" in serialized_errors
    assert "authority_denials.pr_admitted must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_ref_drift() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(
        source_pr_admission_preflight_ref="examples/wrong.json",
        source_actual_non_empty_diff_receipt_binding_ref="examples/wrong.json",
        pr_admission_diff_binding__actual_non_empty_diff_receipt_ref="witness://wrong",
        pr_admission_diff_binding__changed_file_refs=[],
        pr_admission_diff_binding__diff_refs=["evidence://wrong"],
    )

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        _source_preflight(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "source_pr_admission_preflight_ref expected" in serialized_errors
    assert "source_actual_non_empty_diff_receipt_binding_ref expected" in serialized_errors
    assert "actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "changed_file_refs expected" in serialized_errors
    assert "diff_refs expected" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_missing_gate_refs() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(
        pr_admission_diff_binding__required_before_pr_refs=[
            "examples/agentic_service_harness_github_pr_admission_preflight.foundation.json"
        ],
        pr_admission_diff_binding__blocked_reason_refs=["blocked://pr-creation/not-admitted"],
    )

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        _source_preflight(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "required_before_pr_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_source_drift() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(scope__repository_connection_id="wrong")
    source_preflight = _source_preflight()
    source_preflight["approval_admission_gate"]["pr_admitted"] = True
    source_actual_diff_binding = _source_actual_diff_binding()
    source_actual_diff_binding["actual_non_empty_diff_binding"]["changed_file_refs"] = []
    source_actual_diff_binding["effect_boundary"]["pull_request_opened"] = True

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        source_preflight,
        source_actual_diff_binding,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "approval_admission_gate.pr_admitted expected False" in serialized_errors
    assert "scope.repository_connection_id expected" in serialized_errors
    assert "changed_file_refs expected" in serialized_errors
    assert "changed_file_refs must be non-empty" in serialized_errors
    assert "effect_boundary.pull_request_opened expected False" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_witness_drift() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(
        remaining_witnesses=[
            {
                "witness_kind": "operator_approval",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://operator-approval-for-pr-admission",
                "blocks_pr_admission": False,
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        _source_preflight(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_pr_actual_non_empty_diff_binding(
        next_action="POST /api/github/prs should never be admitted",
    )
    payload["pr_admission_diff_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_pr_actual_non_empty_diff_binding_semantics(
        payload,
        _source_preflight(),
        _source_actual_diff_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_actual_non_empty_diff_admission_binding_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-actual-non-empty-diff-admission-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_pr_admission_preflight_ref"] == validator.EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF
    assert (
        file_payload["source_actual_non_empty_diff_receipt_binding_ref"]
        == validator.EXPECTED_SOURCE_ACTUAL_DIFF_BINDING_REF
    )


def _source_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_PR_ADMISSION_PREFLIGHT_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_actual_diff_binding() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ACTUAL_DIFF_BINDING_EXAMPLES[0].read_text(encoding="utf-8"))
