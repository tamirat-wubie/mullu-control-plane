"""Test filesystem-write non-empty diff evidence candidate validation.

Purpose: verify the concrete evidence candidate records a redacted non-empty
diff without promoting write authority, receipt append, PR creation, or closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_filesystem_write_non_empty_diff_evidence_candidate.
Invariants:
  - Candidate evidence carries one changed-file ref and one redacted diff ref.
  - Raw diff bodies, raw file content, authority promotion, receipt append, PR
    creation, secret-like payloads, and terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_filesystem_write_non_empty_diff_evidence_candidate as validator


def test_filesystem_write_non_empty_diff_evidence_candidate_passes() -> None:
    validation = validator.validate_agentic_service_harness_filesystem_write_non_empty_diff_evidence_candidate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.filesystem_write_admission_ref == validator.EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF
    assert validation.non_empty_diff_file_summary_ref == validator.EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF


def test_filesystem_write_non_empty_diff_evidence_candidate_rejects_empty_payload() -> None:
    payload = validator.build_mutated_candidate(
        write_evidence_candidate__candidate_changed_file_count=0,
        write_evidence_candidate__changed_file_refs=[],
        write_evidence_candidate__diff_refs=[],
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(
        payload,
        _filesystem_preflight(),
        _file_summary_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "candidate_changed_file_count must be 1" in serialized_errors
    assert "changed_file_refs must contain exactly one ref" in serialized_errors
    assert "diff_refs must contain exactly one ref" in serialized_errors


def test_filesystem_write_non_empty_diff_evidence_candidate_rejects_authority_drift() -> None:
    payload = validator.build_mutated_candidate(
        scope__authority_promotion_allowed=True,
        authority_denials__branch_write_authority_promoted=True,
        authority_denials__filesystem_write_authority_promoted=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__pr_creation_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(
        payload,
        _filesystem_preflight(),
        _file_summary_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "scope.authority_promotion_allowed must be false" in serialized_errors
    assert "authority_denials.branch_write_authority_promoted must be false" in serialized_errors
    assert "authority_denials.filesystem_write_authority_promoted must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.pr_creation_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_filesystem_write_non_empty_diff_evidence_candidate_rejects_raw_content() -> None:
    payload = validator.build_mutated_candidate(
        write_evidence_candidate__raw_diff_body_serialized=True,
        write_evidence_candidate__raw_file_content_serialized=True,
        write_evidence_candidate__absolute_paths_allowed=True,
        write_evidence_candidate__parent_traversal_allowed=True,
        write_evidence_candidate__secret_paths_allowed=True,
        redaction_policy__raw_output_storage_allowed=True,
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(
        payload,
        _filesystem_preflight(),
        _file_summary_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "write_evidence_candidate.raw_diff_body_serialized must be false" in serialized_errors
    assert "write_evidence_candidate.raw_file_content_serialized must be false" in serialized_errors
    assert "write_evidence_candidate.absolute_paths_allowed must be false" in serialized_errors
    assert "write_evidence_candidate.parent_traversal_allowed must be false" in serialized_errors
    assert "write_evidence_candidate.secret_paths_allowed must be false" in serialized_errors
    assert "redaction_policy.raw_output_storage_allowed must be false" in serialized_errors


def test_filesystem_write_non_empty_diff_evidence_candidate_rejects_reconciliation_drift() -> None:
    payload = validator.build_mutated_candidate(
        effect_reconciliation__observed_effect="unexpected effect",
        effect_reconciliation__expected_observed_match=False,
        effect_reconciliation__forbidden_effects_checked=False,
        effect_reconciliation__unresolved_reconciliation=True,
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(
        payload,
        _filesystem_preflight(),
        _file_summary_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "expected and observed effects must match" in serialized_errors
    assert "expected_observed_match must be true" in serialized_errors
    assert "forbidden_effects_checked must be true" in serialized_errors
    assert "unresolved_reconciliation must be false" in serialized_errors


def test_filesystem_write_non_empty_diff_evidence_candidate_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_candidate(
        next_action="POST /api/harness/filesystem-write-candidate must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_candidate_semantics(
        payload,
        _filesystem_preflight(),
        _file_summary_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_filesystem_write_non_empty_diff_evidence_candidate_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "filesystem-write-non-empty-diff-evidence-candidate-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["filesystem_write_admission_ref"] == validator.EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF


def _filesystem_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))


def _file_summary_receipt() -> dict[str, object]:
    return json.loads(validator.DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_EXAMPLES[0].read_text(encoding="utf-8"))
