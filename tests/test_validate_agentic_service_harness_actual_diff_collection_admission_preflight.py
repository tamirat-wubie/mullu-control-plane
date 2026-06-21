"""Test actual diff collection admission preflight validation.

Purpose: verify actual diff collection remains blocked until authority, cleanup,
redaction, UAO, and receipt-store write path evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_actual_diff_collection_admission_preflight.
Invariants:
  - The preflight binds to the actual file-change summary receipt.
  - Non-empty diffs, raw diffs, receipt-store append, mutation routes,
    secret-like payloads, workflow cycles, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_actual_diff_collection_admission_preflight as validator


def test_actual_diff_collection_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_actual_diff_collection_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.actual_summary_ref == validator.EXPECTED_ACTUAL_SUMMARY_REF


def test_actual_diff_collection_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__actual_diff_collection_allowed=True,
        admission_gates__branch_write_authority_collected=True,
        admission_gates__workspace_write_authority_granted=True,
        admission_gates__cleanup_receipt_emitted=True,
        admission_gates__uao_diff_collection_admission_verified=True,
        admission_gates__receipt_store_write_path_verified=True,
        admission_gates__actual_diff_collection_allowed=True,
        effect_boundary__actual_diff_collected=True,
        effect_boundary__receipt_store_appended=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _actual_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.actual_diff_collection_allowed must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_collected must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_granted must be false" in serialized_errors
    assert "admission_gates.cleanup_receipt_emitted must be false" in serialized_errors
    assert "admission_gates.uao_diff_collection_admission_verified must be false" in serialized_errors
    assert "admission_gates.receipt_store_write_path_verified must be false" in serialized_errors
    assert "effect_boundary.actual_diff_collected must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors


def test_actual_diff_collection_rejects_non_empty_diff_plan() -> None:
    payload = validator.build_mutated_preflight(
        diff_collection_plan__candidate_changed_file_count=1,
        diff_collection_plan__changed_file_refs=["evidence://changed-file/src-app"],
        diff_collection_plan__diff_refs=["evidence://diff/src-app"],
        diff_collection_plan__non_empty_diff_allowed=True,
        diff_collection_plan__raw_diff_serialization_allowed=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _actual_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "diff_collection_plan.candidate_changed_file_count must be 0 while authority is absent" in serialized_errors
    assert "diff_collection_plan.changed_file_refs must be empty while authority is absent" in serialized_errors
    assert "diff_collection_plan.diff_refs must be empty while authority is absent" in serialized_errors
    assert "diff_collection_plan.non_empty_diff_allowed must be false" in serialized_errors
    assert "diff_collection_plan.raw_diff_serialization_allowed must be false" in serialized_errors


def test_actual_diff_collection_rejects_missing_refs_and_path_drift() -> None:
    payload = validator.build_mutated_preflight(
        admission_gates__required_before_diff_collection_refs=[
            "examples/agentic_service_harness_actual_file_change_summary_receipt.foundation.json"
        ],
        admission_gates__blocked_reason_refs=["blocked://branch-write-authority/not-collected"],
        path_policy__path_allowlist=["/"],
        redaction_policy__redaction_evidence_ref="evidence://wrong-redaction",
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _actual_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "admission_gates.required_before_diff_collection_refs missing required ref" in serialized_errors
    assert "admission_gates.blocked_reason_refs missing required ref" in serialized_errors
    assert "path_policy.path_allowlist must match actual summary" in serialized_errors
    assert "redaction_policy.redaction_evidence_ref must match actual summary" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_actual_diff_collection_rejects_workflow_cycle_and_dangling_stage() -> None:
    payload = validator.build_mutated_preflight()
    payload["workflow_stages"][0]["predecessor_stage_ids"] = ["collect_redacted_diff_bundle"]
    payload["workflow_stages"][1]["predecessor_stage_ids"] = [
        "verify_actual_summary_receipt",
        "missing_stage",
    ]

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _actual_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "dangling predecessor missing_stage" in serialized_errors
    assert "workflow stage cycle detected" in serialized_errors
    assert len(errors) >= 2


def test_actual_diff_collection_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/actual-diffs should never be admitted",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _actual_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_actual_diff_collection_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "actual-diff-collection-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["actual_summary_ref"] == validator.EXPECTED_ACTUAL_SUMMARY_REF


def _actual_summary() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ACTUAL_SUMMARY_EXAMPLES[0].read_text(encoding="utf-8"))
