"""Test GitHub PR creation execution admission validation.

Purpose: verify PR creation execution admission remains blocked after binding
the dry-run receipt evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_creation_execution_admission.
Invariants:
  - Execution admission never opens pull requests or grants repository writes.
  - Source dry-run evidence remains bound and non-authorizing.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_creation_execution_admission as validator


def test_github_pr_creation_execution_admission_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_creation_execution_admission()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_dry_run_ref == validator.EXPECTED_SOURCE_DRY_RUN_REF


def test_github_pr_creation_execution_admission_rejects_authority_drift() -> None:
    payload = validator.build_mutated_pr_creation_execution_admission(
        scope__execution_admitted=True,
        scope__pr_creation_enabled=True,
        execution_admission_decision__execution_admitted=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_execution_admission_semantics(payload, _source_dry_run(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.execution_admitted must be false" in serialized_errors
    assert "scope.pr_creation_enabled must be false" in serialized_errors
    assert "execution_admission_decision.execution_admitted must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors


def test_github_pr_creation_execution_admission_rejects_source_refs_drift() -> None:
    payload = validator.build_mutated_pr_creation_execution_admission(
        source_pr_creation_dry_run_receipt_ref="examples/missing-dry-run.json",
        source_pr_admission_preflight_ref="examples/missing-preflight.json",
        source_terminal_closure_certificate_read_model_ref="examples/missing-read-model.json",
    )
    payload["receipt_refs"]["github_pr_creation_dry_run_receipt_example"] = "examples/missing.json"

    errors: list[str] = []
    validator._validate_execution_admission_semantics(payload, _source_dry_run(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_pr_creation_dry_run_receipt_ref expected" in serialized_errors
    assert "source_pr_admission_preflight_ref expected" in serialized_errors
    assert "source_terminal_closure_certificate_read_model_ref expected" in serialized_errors
    assert "receipt_refs.github_pr_creation_dry_run_receipt_example expected" in serialized_errors


def test_github_pr_creation_execution_admission_rejects_source_dry_run_drift() -> None:
    payload = validator.build_mutated_pr_creation_execution_admission(scope__repository_slug="wrong/repo")
    source_dry_run = _source_dry_run()
    source_dry_run["execution_admission_gate"]["decision"] = "PR_EXECUTION_ADMITTED"
    source_dry_run["execution_admission_gate"]["execution_admitted"] = True
    source_dry_run["simulated_pr_creation"]["pull_request_opened"] = True

    errors: list[str] = []
    validator._validate_execution_admission_semantics(payload, source_dry_run, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.repository_slug expected" in serialized_errors
    assert "source dry-run receipt: execution_admission_gate.decision expected" in serialized_errors
    assert "source dry-run receipt: execution_admission_gate.execution_admitted expected False" in serialized_errors
    assert "source_dry_run_binding.source_execution_decision expected" in serialized_errors
    assert "source_dry_run_binding.source_pull_request_opened expected True" in serialized_errors


def test_github_pr_creation_execution_admission_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_pr_creation_execution_admission(
        execution_admission_contract__forbidden_action_classes=["open_pr"],
        execution_admission_contract__required_source_refs=[validator.EXPECTED_SOURCE_DRY_RUN_REF],
        execution_admission_contract__required_gate_refs=["gate://harness/no-pr-creation"],
        execution_admission_contract__admission_obligations_checked=["obligation://deny-live-pr-creation"],
        execution_admission_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_github_pr_creation_execution_admission.py"
        ],
        execution_admission_decision__required_before_execution_refs=["evidence://uao-pr-execution-admission"],
        execution_admission_decision__blocked_reason_refs=["blocked://pr-creation/execution-admission-preflight-only"],
    )

    errors: list[str] = []
    validator._validate_execution_admission_semantics(payload, _source_dry_run(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "execution_admission_contract.forbidden_action_classes missing required ref" in serialized_errors
    assert "execution_admission_contract.required_source_refs missing required ref" in serialized_errors
    assert "execution_admission_contract.required_gate_refs missing required ref" in serialized_errors
    assert "execution_admission_contract.admission_obligations_checked missing required ref" in serialized_errors
    assert "execution_admission_contract.validation_refs missing required ref" in serialized_errors
    assert "execution_admission_decision.required_before_execution_refs missing required ref" in serialized_errors
    assert "execution_admission_decision.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_creation_execution_admission_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_pr_creation_execution_admission(
        next_action="POST /api/github/pulls should never be admitted",
    )
    payload["execution_admission_decision"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_execution_admission_semantics(payload, _source_dry_run(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_creation_execution_admission_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-creation-execution-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_dry_run_ref"] == validator.EXPECTED_SOURCE_DRY_RUN_REF


def _source_dry_run() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_DRY_RUN_EXAMPLES[0].read_text(encoding="utf-8"))
