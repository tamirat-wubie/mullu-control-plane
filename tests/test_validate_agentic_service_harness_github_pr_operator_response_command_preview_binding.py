"""Test GitHub PR operator response command preview binding validation.

Purpose: verify the operator response witness is bound to the command-preview
approval binding without granting PR command execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_operator_response_command_preview_binding.
Invariants:
  - Operator response remains uncollected and AwaitingEvidence.
  - Command preview remains redacted and non-executing.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_operator_response_command_preview_binding as validator


def test_github_pr_operator_response_command_preview_binding_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_operator_response_command_preview_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_operator_response_witness_ref == validator.EXPECTED_SOURCE_OPERATOR_RESPONSE_REF
    assert (
        validation.source_operator_approval_request_command_preview_binding_ref
        == validator.EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF
    )


def test_github_pr_operator_response_command_preview_binding_rejects_authority_drift() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(
        scope__execution_admitted=True,
        response_command_preview_binding__operator_response_collected=True,
        response_command_preview_binding__command_execution_admitted=True,
        response_command_preview_binding__pull_request_creation_enabled=True,
        authority_denials__command_execution_admitted=True,
        effect_boundary__command_executed=True,
        effect_boundary__pull_request_opened=True,
    )

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        _source_operator_response(),
        _source_command_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "scope.execution_admitted must be false" in serialized_errors
    assert "response_command_preview_binding.operator_response_collected must be false" in serialized_errors
    assert "response_command_preview_binding.command_execution_admitted must be false" in serialized_errors
    assert "response_command_preview_binding.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.command_execution_admitted must be false" in serialized_errors
    assert "effect_boundary.command_executed must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors


def test_github_pr_operator_response_command_preview_binding_rejects_source_drift() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(scope__repository_slug="wrong/repo")
    source_operator_response = _source_operator_response()
    source_operator_response["response_witness_id"] = "wrong-response"
    source_operator_response["response_record_collected"] = True
    source_command_approval_binding = _source_command_approval_binding()
    source_command_approval_binding["approval_command_preview_binding"]["operator_response_collected"] = True

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        source_operator_response,
        source_command_approval_binding,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "scope.repository_slug expected" in serialized_errors
    assert "GitHub PR operator response witness source: response_witness_id expected" in serialized_errors
    assert "GitHub PR operator response witness source: response_record_collected expected False" in serialized_errors
    assert (
        "GitHub PR command-preview approval binding source: "
        "approval_command_preview_binding.operator_response_collected expected False"
    ) in serialized_errors


def test_github_pr_operator_response_command_preview_binding_rejects_command_shape_drift() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(
        response_command_preview_binding__redacted_command_preview="gh pr create --base main --head live --title raw"
    )
    payload["response_command_preview_binding"]["argument_vector_template"] = ["gh", "pr", "create", "--fill"]

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        _source_operator_response(),
        _source_command_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "response_command_preview_binding.redacted_command_preview expected" in serialized_errors
    assert "response_command_preview_binding.argument_vector_template expected" in serialized_errors
    assert "must retain placeholders" in serialized_errors


def test_github_pr_operator_response_command_preview_binding_rejects_approval_request_evidence_drift() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(
        command_preview_approval_request_evidence__source_approval_request_id="wrong-approval-request",
        command_preview_approval_request_evidence__source_operator_response_collected=True,
        command_preview_approval_request_evidence__source_command_preview_execution_admission_bound=False,
        command_preview_approval_request_evidence__source_operator_approval_request_remains_request_only=False,
        command_preview_approval_request_evidence__operator_response_consumes_approval_request_evidence=False,
        command_preview_approval_request_evidence__operator_response_remains_uncollected=False,
        command_preview_approval_request_evidence__source_contains_secret_values=True,
    )

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        _source_operator_response(),
        _source_command_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "command_preview_approval_request_evidence.source_approval_request_id expected" in serialized_errors
    assert (
        "command_preview_approval_request_evidence.source_operator_response_collected expected False"
        in serialized_errors
    )
    assert (
        "command_preview_approval_request_evidence.source_command_preview_execution_admission_bound expected True"
        in serialized_errors
    )
    assert (
        "command_preview_approval_request_evidence.source_operator_approval_request_remains_request_only expected True"
        in serialized_errors
    )
    assert (
        "command_preview_approval_request_evidence.operator_response_consumes_approval_request_evidence expected True"
        in serialized_errors
    )
    assert (
        "command_preview_approval_request_evidence.operator_response_remains_uncollected expected True"
        in serialized_errors
    )
    assert "command_preview_approval_request_evidence.source_contains_secret_values expected False" in serialized_errors


def test_github_pr_operator_response_command_preview_binding_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(
        response_command_preview_binding__placeholder_refs=["placeholder://branch-ref"],
        response_command_preview_binding__required_before_execution_refs=[
            validator.EXPECTED_SOURCE_OPERATOR_RESPONSE_REF
        ],
        response_command_preview_binding__blocked_reason_refs=[
            "blocked://operator-response/not-collected"
        ],
    )

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        _source_operator_response(),
        _source_command_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "response_command_preview_binding.placeholder_refs missing required ref" in serialized_errors
    assert "response_command_preview_binding.required_before_execution_refs missing required ref" in serialized_errors
    assert "response_command_preview_binding.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_operator_response_command_preview_binding_rejects_mutation_and_secret_like_payload() -> None:
    payload = validator.build_mutated_operator_response_command_preview_binding(
        next_action="POST /api/github/pulls should remain denied",
    )
    payload["response_command_preview_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_response_command_preview_binding_semantics(
        payload,
        _source_operator_response(),
        _source_command_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_operator_response_command_preview_binding_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-operator-response-command-preview-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_operator_response_witness_ref"] == validator.EXPECTED_SOURCE_OPERATOR_RESPONSE_REF


def _source_operator_response() -> dict[str, object]:
    return json.loads(validator.DEFAULT_OPERATOR_RESPONSE_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_command_approval_binding() -> dict[str, object]:
    return json.loads(validator.DEFAULT_COMMAND_APPROVAL_BINDING_EXAMPLES[0].read_text(encoding="utf-8"))
