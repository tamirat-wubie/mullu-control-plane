"""Test GitHub PR creation command preview validation.

Purpose: verify PR creation command previews remain non-executing after binding
execution-admission evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_creation_command_preview.
Invariants:
  - Command preview never opens pull requests, pushes branches, or writes repositories.
  - Source execution admission remains bound and non-authorizing.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_creation_command_preview as validator


def test_github_pr_creation_command_preview_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_creation_command_preview()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_execution_admission_ref == validator.EXPECTED_SOURCE_EXECUTION_ADMISSION_REF


def test_github_pr_creation_command_preview_rejects_authority_drift() -> None:
    payload = validator.build_mutated_pr_creation_command_preview(
        scope__execution_admitted=True,
        scope__pr_creation_enabled=True,
        command_preview__command_executed=True,
        command_preview__pull_request_opened=True,
        command_preview__repository_written=True,
        execution_decision__execution_admitted=True,
        authority_denials__pull_request_creation_enabled=True,
    )

    errors: list[str] = []
    validator._validate_command_preview_semantics(payload, _source_execution_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.execution_admitted must be false" in serialized_errors
    assert "scope.pr_creation_enabled must be false" in serialized_errors
    assert "command_preview.command_executed must be false" in serialized_errors
    assert "command_preview.pull_request_opened must be false" in serialized_errors
    assert "command_preview.repository_written must be false" in serialized_errors
    assert "execution_decision.execution_admitted must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors


def test_github_pr_creation_command_preview_rejects_source_drift() -> None:
    payload = validator.build_mutated_pr_creation_command_preview(scope__repository_slug="wrong/repo")
    source = _source_execution_admission()
    source["execution_admission_decision"]["decision"] = "PR_EXECUTION_ADMITTED"
    source["execution_admission_decision"]["execution_admitted"] = True
    source["authority_denials"]["pull_request_creation_enabled"] = True

    errors: list[str] = []
    validator._validate_command_preview_semantics(payload, source, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.repository_slug expected" in serialized_errors
    assert "source execution admission: execution_admission_decision.decision expected" in serialized_errors
    assert "source_execution_admission_binding.source_decision expected" in serialized_errors
    assert "source_execution_admission_binding.source_execution_admitted expected True" in serialized_errors
    assert "source_execution_admission_binding.source_pull_request_creation_enabled expected True" in serialized_errors


def test_github_pr_creation_command_preview_rejects_execution_admission_evidence_drift() -> None:
    payload = validator.build_mutated_pr_creation_command_preview()
    source = _source_execution_admission()
    evidence = payload["execution_admission_evidence"]
    assert isinstance(evidence, dict)

    mutations = {
        "source_execution_admission_ref": "examples/wrong.json",
        "source_admission_id": "wrong-admission",
        "source_decision": "PR_CREATION_EXECUTION_ADMITTED",
        "source_execution_admitted": True,
        "source_execution_target_ref": "github-pr://wrong",
        "source_terminal_closure_allowed": True,
        "source_required_before_execution_refs": ["evidence://wrong"],
        "source_blocked_reason_refs": ["blocked://wrong"],
        "source_dry_run_ref": "examples/wrong-dry-run.json",
        "source_dry_run_receipt_recorded": False,
        "source_command_preview_bound": False,
        "source_command_preview_ref": "examples/wrong-preview.json",
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
        "command_preview_remains_preview_only": False,
        "contains_secret_values": True,
    }

    for key, value in mutations.items():
        mutated = json.loads(json.dumps(payload))
        mutated["execution_admission_evidence"][key] = value
        errors: list[str] = []

        validator._validate_command_preview_semantics(mutated, source, errors, f"mutated-{key}")
        serialized_errors = "\n".join(errors)

        assert f"execution_admission_evidence.{key}" in serialized_errors


def test_github_pr_creation_command_preview_rejects_command_shape_drift() -> None:
    payload = validator.build_mutated_pr_creation_command_preview(
        command_preview__redacted_command_preview="gh pr create --base main --head live --title raw --body raw"
    )
    payload["command_preview"]["argument_vector_template"] = ["gh", "pr", "create", "--fill"]

    errors: list[str] = []
    validator._validate_command_preview_semantics(payload, _source_execution_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "command_preview.redacted_command_preview expected" in serialized_errors
    assert "command_preview.argument_vector_template expected" in serialized_errors
    assert "must retain redacted placeholders" in serialized_errors


def test_github_pr_creation_command_preview_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_pr_creation_command_preview(
        command_preview_contract__forbidden_action_classes=["open_pr"],
        command_preview_contract__required_source_refs=[validator.EXPECTED_SOURCE_EXECUTION_ADMISSION_REF],
        command_preview_contract__required_gate_refs=["gate://harness/no-pr-creation"],
        command_preview_contract__preview_obligations_checked=["obligation://deny-live-pr-creation"],
        command_preview_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_github_pr_creation_command_preview.py"
        ],
        command_preview__placeholder_refs=["placeholder://branch-ref"],
        execution_decision__required_before_execution_refs=["evidence://uao-pr-execution-admission"],
        execution_decision__blocked_reason_refs=["blocked://pr-creation/command-preview-only"],
    )

    errors: list[str] = []
    validator._validate_command_preview_semantics(payload, _source_execution_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "command_preview_contract.forbidden_action_classes missing required ref" in serialized_errors
    assert "command_preview_contract.required_source_refs missing required ref" in serialized_errors
    assert "command_preview_contract.required_gate_refs missing required ref" in serialized_errors
    assert "command_preview_contract.preview_obligations_checked missing required ref" in serialized_errors
    assert "command_preview_contract.validation_refs missing required ref" in serialized_errors
    assert "command_preview.placeholder_refs missing required ref" in serialized_errors
    assert "execution_decision.required_before_execution_refs missing required ref" in serialized_errors
    assert "execution_decision.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_creation_command_preview_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_pr_creation_command_preview(
        next_action="POST /api/github/pulls should never be admitted",
    )
    payload["command_preview"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_command_preview_semantics(payload, _source_execution_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_creation_command_preview_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-creation-command-preview-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_execution_admission_ref"] == validator.EXPECTED_SOURCE_EXECUTION_ADMISSION_REF


def _source_execution_admission() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_EXECUTION_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))
