"""Test GitHub PR creation dry-run receipt validation.

Purpose: verify the harness GitHub PR creation path remains dry-run-only after
binding admission preflight and terminal certificate read-model evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_creation_dry_run_receipt.
Invariants:
  - PR creation dry-run never opens pull requests or creates branches.
  - Source admission preflight and terminal certificate read model remain non-authorizing.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_creation_dry_run_receipt as validator


def test_github_pr_creation_dry_run_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_creation_dry_run_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_pr_admission_preflight_ref == validator.EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF
    assert validation.terminal_certificate_read_model_ref == validator.EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF


def test_github_pr_creation_dry_run_receipt_rejects_authority_drift() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(
        scope__pr_creation_enabled=True,
        simulated_pr_creation__runtime_pr_creation_executed=True,
        simulated_pr_creation__pull_request_opened=True,
        simulated_pr_creation__branch_created=True,
        simulated_pr_creation__repository_written=True,
        execution_admission_gate__execution_admitted=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, _source_preflight(), _read_model(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.pr_creation_enabled must be false" in serialized_errors
    assert "simulated_pr_creation.runtime_pr_creation_executed must be false" in serialized_errors
    assert "simulated_pr_creation.pull_request_opened must be false" in serialized_errors
    assert "simulated_pr_creation.branch_created must be false" in serialized_errors
    assert "simulated_pr_creation.repository_written must be false" in serialized_errors
    assert "execution_admission_gate.execution_admitted must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors


def test_github_pr_creation_dry_run_receipt_rejects_source_refs_drift() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(
        source_pr_admission_preflight_ref="examples/missing-pr-admission-preflight.json",
        source_terminal_closure_certificate_read_model_ref="examples/missing-certificate-read-model.json",
    )
    payload["receipt_refs"]["github_pr_admission_preflight_example"] = "examples/missing.json"
    payload["receipt_refs"]["terminal_closure_certificate_read_model_example"] = "examples/missing.json"

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, _source_preflight(), _read_model(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_pr_admission_preflight_ref expected" in serialized_errors
    assert "source_terminal_closure_certificate_read_model_ref expected" in serialized_errors
    assert "receipt_refs.github_pr_admission_preflight_example expected" in serialized_errors
    assert "receipt_refs.terminal_closure_certificate_read_model_example expected" in serialized_errors


def test_github_pr_creation_dry_run_receipt_rejects_source_preflight_drift() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(scope__repository_slug="wrong/repo")
    source_preflight = _source_preflight()
    source_preflight["approval_admission_gate"]["decision"] = "PR_ADMITTED"
    source_preflight["approval_admission_gate"]["pr_admitted"] = True
    source_preflight["source_terminal_closure_certificate_read_model_ref"] = "examples/missing-read-model.json"

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, source_preflight, _read_model(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.repository_slug expected" in serialized_errors
    assert "approval_admission_gate.decision expected" in serialized_errors
    assert "approval_admission_gate.pr_admitted expected False" in serialized_errors
    assert "source_terminal_closure_certificate_read_model_ref expected" in serialized_errors
    assert "simulated_pr_creation.source_admission_decision expected 'PR_ADMITTED'" in serialized_errors
    assert "simulated_pr_creation.source_pr_admitted expected True" in serialized_errors


def test_github_pr_creation_dry_run_receipt_rejects_read_model_source_drift() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(scope__repository_connection_id="repo-wrong")
    read_model = _read_model()
    read_model["projection_scope"]["projection_only"] = False
    read_model["authority_denials"]["pull_request_creation_enabled"] = True
    read_model["effect_boundary"]["repository_written_by_read_model"] = True
    read_model["operator_view"]["contains_secret_values"] = True

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, _source_preflight(), read_model, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.repository_connection_id expected" in serialized_errors
    assert "projection_scope.projection_only expected True" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled expected False" in serialized_errors
    assert "effect_boundary.repository_written_by_read_model expected False" in serialized_errors
    assert "operator_view.contains_secret_values expected False" in serialized_errors


def test_github_pr_creation_dry_run_receipt_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(
        dry_run_contract__forbidden_action_classes=["open_pr"],
        dry_run_contract__required_source_refs=[validator.EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF],
        dry_run_contract__required_gate_refs=["gate://harness/no-pr-creation"],
        dry_run_contract__dry_run_obligations_checked=["obligation://record-pr-creation-dry-run-receipt"],
        dry_run_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_github_pr_creation_dry_run_receipt.py"
        ],
        execution_admission_gate__required_before_execution_refs=["evidence://uao-pr-execution-admission"],
        execution_admission_gate__blocked_reason_refs=["blocked://pr-creation/dry-run-only"],
    )

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, _source_preflight(), _read_model(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "dry_run_contract.forbidden_action_classes missing required ref" in serialized_errors
    assert "dry_run_contract.required_source_refs missing required ref" in serialized_errors
    assert "dry_run_contract.required_gate_refs missing required ref" in serialized_errors
    assert "dry_run_contract.dry_run_obligations_checked missing required ref" in serialized_errors
    assert "dry_run_contract.validation_refs missing required ref" in serialized_errors
    assert "execution_admission_gate.required_before_execution_refs missing required ref" in serialized_errors
    assert "execution_admission_gate.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_creation_dry_run_receipt_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_pr_creation_dry_run(
        next_action="POST /api/github/pulls should never be admitted",
    )
    payload["simulated_pr_creation"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_pr_creation_dry_run_semantics(payload, _source_preflight(), _read_model(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_creation_dry_run_receipt_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-creation-dry-run-receipt-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert (
        file_payload["source_pr_admission_preflight_ref"]
        == validator.EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF
    )
    assert (
        file_payload["terminal_certificate_read_model_ref"]
        == validator.EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF
    )


def _source_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_EXAMPLES[0].read_text(encoding="utf-8"))


def _read_model() -> dict[str, object]:
    return json.loads(validator.DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_EXAMPLES[0].read_text(encoding="utf-8"))
