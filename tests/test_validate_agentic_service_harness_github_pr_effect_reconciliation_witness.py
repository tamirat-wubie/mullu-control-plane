"""Test GitHub PR effect reconciliation witness validation.

Purpose: verify the PR effect reconciliation witness remains read-only,
uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_witness.
Invariants:
  - Missing effect reconciliation never grants terminal closure or merge effects.
  - Remaining witnesses are empty because this is the final missing-evidence request.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_effect_reconciliation_witness as validator


def test_github_pr_effect_reconciliation_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_effect_reconciliation_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_ci_gate_before_ready_for_review_witness_ref == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF


def test_github_pr_effect_reconciliation_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        effect_reconciliation_collected=True,
        authority_granted=True,
        effect_reconciliation__ci_gate_before_ready_for_review_satisfied=True,
        effect_reconciliation__effect_reconciliation_collected=True,
        effect_reconciliation__terminal_closure_authorized_after_reconciliation=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "effect_reconciliation.ci_gate_before_ready_for_review_satisfied must be false" in serialized_errors
    assert "effect_reconciliation.effect_reconciliation_collected must be false" in serialized_errors
    assert "effect_reconciliation.terminal_closure_authorized_after_reconciliation must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        authority_denials__pull_request_merge_enabled=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__pull_request_merged=True,
        effect_boundary__branch_deleted=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.pull_request_merged must be false" in serialized_errors
    assert "effect_boundary.branch_deleted must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        remaining_witnesses=[
            {
                "witness_kind": "effect_reconciliation",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://effect-reconciliation-before-terminal-closure",
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must be empty after effect reconciliation request" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "effect_reconciliation"


def test_github_pr_effect_reconciliation_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        requested_evidence_ref="POST /api/github/effect-reconciliation authority",
    )
    payload["effect_reconciliation"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_effect_reconciliation_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-effect-reconciliation-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_ci_gate_before_ready_for_review_witness_ref"] == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF


def _source_ci_gate_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CI_GATE_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
