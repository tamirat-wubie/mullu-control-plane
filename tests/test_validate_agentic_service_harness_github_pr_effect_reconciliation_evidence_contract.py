"""Test GitHub PR effect reconciliation evidence contract validation.

Purpose: verify the PR effect reconciliation evidence contract remains
read-only, uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract.
Invariants:
  - Live evidence collection is required but not claimed.
  - Terminal closure is not authorized by the contract.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract as validator


def test_github_pr_effect_reconciliation_evidence_contract_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_effect_reconciliation_witness_ref == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF


def test_github_pr_effect_reconciliation_evidence_contract_rejects_live_evidence_overclaim() -> None:
    payload = validator.build_mutated_effect_reconciliation_evidence_contract(
        effect_reconciliation_collected=True,
        authority_granted=True,
        effect_reconciliation_evidence_contract__live_evidence_collected=True,
        effect_reconciliation_evidence_contract__terminal_closure_authorized_after_collection=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_evidence_contract_semantics(payload, _source_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "effect_reconciliation_evidence_contract.live_evidence_collected must be false" in serialized_errors
    assert "effect_reconciliation_evidence_contract.terminal_closure_authorized_after_collection must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_effect_reconciliation_evidence_contract_rejects_effect_authority() -> None:
    payload = validator.build_mutated_effect_reconciliation_evidence_contract(
        authority_denials__pull_request_merge_enabled=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__pull_request_merged=True,
        effect_boundary__branch_deleted=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_evidence_contract_semantics(payload, _source_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.pull_request_merged must be false" in serialized_errors
    assert "effect_boundary.branch_deleted must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_effect_reconciliation_evidence_contract_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_evidence_contract(remaining_witnesses=[])

    errors: list[str] = []
    validator._validate_effect_reconciliation_evidence_contract_semantics(payload, _source_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must require exactly the live effect reconciliation evidence witness" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"] == []


def test_github_pr_effect_reconciliation_evidence_contract_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_effect_reconciliation_evidence_contract(
        requested_evidence_ref="POST /api/github/effect-reconciliation evidence",
    )
    payload["effect_reconciliation_evidence_contract"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_effect_reconciliation_evidence_contract_semantics(payload, _source_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_effect_reconciliation_evidence_contract_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-effect-reconciliation-evidence-contract-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_effect_reconciliation_witness_ref"] == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF


def _source_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_EFFECT_RECONCILIATION_EXAMPLES[0].read_text(encoding="utf-8"))
