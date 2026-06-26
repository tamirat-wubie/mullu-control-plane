"""Test observed branch workspace creation receipt validation.

Purpose: verify workspace creation observation is reconciled before later
effects can be considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_observed_branch_workspace_creation_receipt.
Invariants:
  - Source authority binding passes before observation is accepted.
  - Expected and observed effects must match.
  - Filesystem writes, branch pushes, PR creation, adapter execution, connector
    calls, receipt append, mutation routes, secrets, and terminal closure fail
    closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_observed_branch_workspace_creation_receipt as validator


def test_observed_branch_workspace_creation_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_observed_branch_workspace_creation_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_authority_binding_ok is True
    assert validation.source_authority_binding_ref == validator.EXPECTED_SOURCE_AUTHORITY_REF


def test_observed_branch_workspace_creation_receipt_rejects_effect_mismatch() -> None:
    payload = validator.build_mutated_observed_workspace_receipt(
        effect_reconciliation__observed_effect="filesystem_written",
        effect_reconciliation__reconciliation_status="MISMATCH",
        effect_reconciliation__forbidden_effects_checked=False,
    )

    errors: list[str] = []
    validator._validate_observed_workspace_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation.observed_effect expected" in serialized_errors
    assert "effect_reconciliation.reconciliation_status expected 'MATCH'" in serialized_errors
    assert "effect_reconciliation.forbidden_effects_checked must be true" in serialized_errors


def test_observed_branch_workspace_creation_receipt_rejects_downstream_effects() -> None:
    payload = validator.build_mutated_observed_workspace_receipt(
        forbidden_effects__filesystem_written=True,
        forbidden_effects__branch_pushed=True,
        forbidden_effects__pull_request_opened=True,
        forbidden_effects__adapter_executed=True,
        forbidden_effects__receipt_store_appended=True,
        forbidden_effects__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_observed_workspace_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "forbidden_effects.filesystem_written must be false" in serialized_errors
    assert "forbidden_effects.branch_pushed must be false" in serialized_errors
    assert "forbidden_effects.pull_request_opened must be false" in serialized_errors
    assert "forbidden_effects.adapter_executed must be false" in serialized_errors
    assert "forbidden_effects.receipt_store_appended must be false" in serialized_errors
    assert "forbidden_effects.terminal_closure must be false" in serialized_errors


def test_observed_branch_workspace_creation_receipt_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_observed_workspace_receipt(
        effect_reconciliation__evidence_refs=["evidence://workspace-path-confined"],
        required_next_evidence__before_filesystem_write=["evidence://filesystem-write-rollback-plan"],
        required_next_evidence__before_adapter_execution=["approval://adapter-execution/operator-decision"],
        required_next_evidence__before_receipt_append=["evidence://receipt-store-write-path"],
        required_next_evidence__before_terminal_closure=["evidence://cleanup-receipt-after-workspace-use"],
    )

    errors: list[str] = []
    validator._validate_observed_workspace_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation.evidence_refs missing required ref" in serialized_errors
    assert "required_next_evidence missing required ref" in serialized_errors


def test_observed_branch_workspace_creation_receipt_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_observed_workspace_receipt(
        next_action="POST /api/harness/workspace/write should not be encoded here",
    )
    payload["observed_workspace"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_observed_workspace_semantics(payload, _source_authority(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_observed_branch_workspace_creation_receipt_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "observed-workspace-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_authority_binding_ok"] is True


def _source_authority() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_AUTHORITY_EXAMPLES[0].read_text(encoding="utf-8"))
