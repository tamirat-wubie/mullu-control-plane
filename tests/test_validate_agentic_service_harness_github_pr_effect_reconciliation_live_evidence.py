"""Test GitHub PR effect reconciliation live evidence validation.

Purpose: verify live effect reconciliation evidence is collected, read-only,
and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence.
Invariants:
  - Reconciled GitHub observations do not grant terminal closure.
  - Mutation authority and secret-like payloads fail closed.
  - Source evidence-contract binding remains explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence as validator


def test_github_pr_effect_reconciliation_live_evidence_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_evidence_contract_ref == validator.EXPECTED_SOURCE_CONTRACT_REF


def test_github_pr_effect_reconciliation_live_evidence_rejects_terminal_closure_overclaim() -> None:
    payload = validator.build_mutated_live_evidence(
        terminal_closure=True,
        reconciliation_result__terminal_closure_authorized=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_live_evidence_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "terminal_closure must be false" in serialized_errors
    assert "reconciliation_result.terminal_closure_authorized must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert len(errors) >= 3


def test_github_pr_effect_reconciliation_live_evidence_rejects_unreconciled_state() -> None:
    payload = validator.build_mutated_live_evidence(
        observed_pull_request__state="OPEN",
        observed_pull_request__head_branch_exists_after_merge=True,
        observed_checks__bucket="fail",
        observed_checks__failed_count=1,
        reconciliation_result__branch_state_reconciled=False,
    )

    errors: list[str] = []
    validator._validate_live_evidence_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "observed_pull_request.state expected 'MERGED'" in serialized_errors
    assert "observed_pull_request.head_branch_exists_after_merge must be false" in serialized_errors
    assert "observed_checks.bucket expected 'pass'" in serialized_errors
    assert "observed_checks.failed_count expected 0" in serialized_errors
    assert "reconciliation_result.branch_state_reconciled must be true" in serialized_errors


def test_github_pr_effect_reconciliation_live_evidence_rejects_mutation_authority() -> None:
    payload = validator.build_mutated_live_evidence(
        authority_granted=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__repository_written_by_witness=True,
        effect_boundary__connector_called_by_witness=True,
    )

    errors: list[str] = []
    validator._validate_live_evidence_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_granted must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "effect_boundary.repository_written_by_witness must be false" in serialized_errors
    assert "effect_boundary.connector_called_by_witness must be false" in serialized_errors


def test_github_pr_effect_reconciliation_live_evidence_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_live_evidence(
        evidence_ref="POST /api/github/effect-reconciliation evidence",
    )
    payload["observed_pull_request"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_live_evidence_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_effect_reconciliation_live_evidence_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-effect-reconciliation-live-evidence-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_evidence_contract_ref"] == validator.EXPECTED_SOURCE_CONTRACT_REF


def _source_contract() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CONTRACT_EXAMPLES[0].read_text(encoding="utf-8"))
