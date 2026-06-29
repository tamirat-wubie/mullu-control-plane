"""Test GitHub PR operator approval request command preview binding validation.

Purpose: verify operator approval request evidence is bound to the PR creation
command preview without granting command execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.
Invariants:
  - Command preview remains redacted and non-executing.
  - Operator approval request evidence is bound before execution consideration.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding as validator,
)


def test_github_pr_operator_approval_request_command_preview_binding_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_command_preview_ref == validator.EXPECTED_SOURCE_COMMAND_PREVIEW_REF
    assert (
        validation.source_operator_approval_request_actual_non_empty_diff_binding_ref
        == validator.EXPECTED_SOURCE_OPERATOR_APPROVAL_BINDING_REF
    )


def test_github_pr_operator_approval_request_command_preview_binding_rejects_authority_drift() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(
        scope__execution_admitted=True,
        scope__pr_creation_enabled=True,
        approval_command_preview_binding__command_execution_admitted=True,
        approval_command_preview_binding__pull_request_creation_enabled=True,
        authority_denials__command_execution_admitted=True,
        effect_boundary__command_executed=True,
        effect_boundary__pull_request_opened=True,
    )

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        _source_command_preview(),
        _source_operator_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "scope.execution_admitted must be false" in serialized_errors
    assert "scope.pr_creation_enabled must be false" in serialized_errors
    assert "approval_command_preview_binding.command_execution_admitted must be false" in serialized_errors
    assert "approval_command_preview_binding.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.command_execution_admitted must be false" in serialized_errors
    assert "effect_boundary.command_executed must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_source_drift() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(scope__repository_slug="wrong/repo")
    source_command_preview = _source_command_preview()
    source_command_preview["command_preview_contract"]["preview_id"] = "wrong-preview"
    source_command_preview["execution_decision"]["execution_admitted"] = True
    source_operator_approval_binding = _source_operator_approval_binding()
    source_operator_approval_binding["approval_request_diff_binding"]["operator_response_collected"] = True

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        source_command_preview,
        source_operator_approval_binding,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "scope.repository_slug expected" in serialized_errors
    assert "GitHub PR command preview source: command_preview_contract.preview_id expected" in serialized_errors
    assert "GitHub PR command preview source: execution_decision.execution_admitted expected False" in serialized_errors
    assert (
        "GitHub PR operator approval request actual-diff binding source: "
        "approval_request_diff_binding.operator_response_collected expected False"
    ) in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_execution_evidence_drift() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding()
    source_command_preview = _source_command_preview()
    source_operator_approval_binding = _source_operator_approval_binding()
    evidence = payload["command_preview_execution_admission_evidence"]
    assert isinstance(evidence, dict)

    mutations = {
        "source_command_preview_ref": "examples/wrong-preview.json",
        "source_execution_admission_ref": "examples/wrong-admission.json",
        "source_admission_id": "wrong-admission",
        "source_decision": "PR_CREATION_EXECUTION_ADMITTED",
        "source_execution_admitted": True,
        "source_execution_target_ref": "github-pr://wrong",
        "source_terminal_closure_allowed": True,
        "source_dry_run_ref": "examples/wrong-dry-run.json",
        "source_dry_run_receipt_recorded": False,
        "source_command_preview_bound": False,
        "source_redacted_command_preview": "gh pr create --title raw",
        "source_operator_decision_ref": "operator-decision://wrong",
        "source_decision_value": "deny_terminal_certificate",
        "source_pull_request_creation_enabled": True,
        "source_repository_write_enabled": True,
        "source_receipt_store_append_enabled": True,
        "source_mutation_route_enabled": True,
        "source_secret_values_serialized": True,
        "source_adapter_executed": True,
        "source_connector_calls_observed": True,
        "source_terminal_closure": True,
        "source_success_claim_allowed": True,
        "command_preview_execution_admission_bound": False,
        "operator_approval_request_consumes_execution_admission_evidence": False,
        "operator_approval_request_remains_request_only": False,
        "contains_secret_values": True,
    }

    for key, value in mutations.items():
        mutated = json.loads(json.dumps(payload))
        mutated["command_preview_execution_admission_evidence"][key] = value
        errors: list[str] = []

        validator._validate_approval_command_preview_binding_semantics(
            mutated,
            source_command_preview,
            source_operator_approval_binding,
            errors,
            f"mutated-{key}",
        )
        serialized_errors = "\n".join(errors)

        assert f"command_preview_execution_admission_evidence.{key}" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_command_shape_drift() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(
        approval_command_preview_binding__redacted_command_preview="gh pr create --base main --head live --title raw"
    )
    payload["approval_command_preview_binding"]["argument_vector_template"] = ["gh", "pr", "create", "--fill"]

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        _source_command_preview(),
        _source_operator_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "approval_command_preview_binding.redacted_command_preview expected" in serialized_errors
    assert "approval_command_preview_binding.argument_vector_template expected" in serialized_errors
    assert "must retain placeholders" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_execution_admission_evidence_drift() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(
        command_preview_execution_admission_evidence__source_decision="wrong-decision",
        command_preview_execution_admission_evidence__source_execution_admitted=True,
        command_preview_execution_admission_evidence__source_redacted_command_preview="gh pr create --fill",
        command_preview_execution_admission_evidence__command_preview_execution_admission_bound=False,
        command_preview_execution_admission_evidence__operator_approval_request_consumes_execution_admission_evidence=False,
        command_preview_execution_admission_evidence__contains_secret_values=True,
    )

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        _source_command_preview(),
        _source_operator_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "command_preview_execution_admission_evidence.source_decision expected" in serialized_errors
    assert "command_preview_execution_admission_evidence.source_execution_admitted expected False" in serialized_errors
    assert "command_preview_execution_admission_evidence.source_redacted_command_preview expected" in serialized_errors
    assert (
        "command_preview_execution_admission_evidence.command_preview_execution_admission_bound expected True"
        in serialized_errors
    )
    assert (
        "command_preview_execution_admission_evidence.operator_approval_request_consumes_execution_admission_evidence "
        "expected True"
    ) in serialized_errors
    assert "command_preview_execution_admission_evidence.contains_secret_values expected False" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(
        approval_command_preview_binding__placeholder_refs=["placeholder://branch-ref"],
        approval_command_preview_binding__required_before_execution_refs=[
            validator.EXPECTED_SOURCE_COMMAND_PREVIEW_REF
        ],
        approval_command_preview_binding__blocked_reason_refs=[
            "blocked://pr-creation/command-preview-only"
        ],
    )

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        _source_command_preview(),
        _source_operator_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "approval_command_preview_binding.placeholder_refs missing required ref" in serialized_errors
    assert "approval_command_preview_binding.required_before_execution_refs missing required ref" in serialized_errors
    assert "approval_command_preview_binding.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_rejects_mutation_and_secret_like_payload() -> None:
    payload = validator.build_mutated_approval_request_command_preview_binding(
        next_action="POST /api/github/pulls should remain denied",
    )
    payload["approval_command_preview_binding"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_approval_command_preview_binding_semantics(
        payload,
        _source_command_preview(),
        _source_operator_approval_binding(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_operator_approval_request_command_preview_binding_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-operator-approval-request-command-preview-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_command_preview_ref"] == validator.EXPECTED_SOURCE_COMMAND_PREVIEW_REF


def _source_command_preview() -> dict[str, object]:
    return json.loads(validator.DEFAULT_COMMAND_PREVIEW_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_operator_approval_binding() -> dict[str, object]:
    return json.loads(validator.DEFAULT_OPERATOR_APPROVAL_BINDING_EXAMPLES[0].read_text(encoding="utf-8"))
