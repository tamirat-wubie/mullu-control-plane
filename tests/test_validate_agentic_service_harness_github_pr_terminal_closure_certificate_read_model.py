"""Tests for GitHub PR terminal closure certificate read model.

Purpose: prove the minted certificate projection is read-only, source-bound,
and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model.
Invariants:
  - The default read model validates.
  - Source drift, missing evidence, mutation authority, new terminal authority,
    mutation routes, and credential-like values fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_CERTIFICATE_ID,
    EXPECTED_READ_MODEL_ID,
    build_mutated_terminal_closure_certificate_read_model,
    main,
    validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model,
)


def _write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "github-pr-terminal-closure-certificate-read-model.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_github_pr_terminal_closure_certificate_read_model_accepts_default_fixture() -> None:
    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.read_model_id == EXPECTED_READ_MODEL_ID
    assert validation.source_certificate_id == EXPECTED_CERTIFICATE_ID


def test_github_pr_terminal_closure_certificate_read_model_rejects_source_certificate_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model(
        source_certificate_id="terminal-closure-certificate.untrusted",
        certificate_summary__certificate_id="terminal-closure-certificate.untrusted",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert EXPECTED_CERTIFICATE_ID in serialized_errors
    assert "source_certificate_id" in serialized_errors
    assert "certificate_summary.certificate_id" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_rejects_missing_evidence_ref(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model()
    payload["certificate_summary"]["evidence_refs"].remove(
        "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json"
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_refs" in serialized_errors
    assert "operator_decision_value_record" in serialized_errors
    assert "expected" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_rejects_minting_evidence_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model(
        actual_diff_certificate_minting_evidence__source_minting_id="wrong-minting",
        actual_diff_certificate_minting_evidence__source_certificate_id="wrong-certificate",
        actual_diff_certificate_minting_evidence__source_decision_value_record_ref="examples/wrong-record.json",
        actual_diff_certificate_minting_evidence__source_decision_value_record_id="wrong-record",
        actual_diff_certificate_minting_evidence__operator_decision_ref="operator-decision://wrong",
        actual_diff_certificate_minting_evidence__decision_value="deny_terminal_certificate",
        actual_diff_certificate_minting_evidence__operator_decision_gate_satisfied=False,
        actual_diff_certificate_minting_evidence__terminal_closure_certificate_minted=False,
        actual_diff_certificate_minting_evidence__terminal_closure_authorized=False,
        actual_diff_certificate_minting_evidence__terminal_closure=False,
        actual_diff_certificate_minting_evidence__authority_scope_kind="wrong-scope",
        actual_diff_certificate_minting_evidence__actual_diff_terminal_closure_certificate_witness_ref="examples/wrong-certificate-witness.json",
        actual_diff_certificate_minting_evidence__actual_diff_operator_response_witness_ref="examples/wrong-response.json",
        actual_diff_certificate_minting_evidence__actual_non_empty_diff_receipt_ref="witness://wrong-diff",
        actual_diff_certificate_minting_evidence__changed_file_refs=["evidence://wrong-file"],
        actual_diff_certificate_minting_evidence__diff_refs=["evidence://wrong-diff"],
        actual_diff_certificate_minting_evidence__redacted_diff_bundle_ref="digest://wrong-bundle",
        actual_diff_certificate_minting_evidence__redacted_output_ref="witness://wrong-output",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "actual_diff_certificate_minting_evidence.source_minting_id expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.source_certificate_id expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.source_decision_value_record_ref expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.source_decision_value_record_id expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.operator_decision_ref expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.decision_value expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.operator_decision_gate_satisfied expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.terminal_closure_certificate_minted expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.terminal_closure_authorized expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.terminal_closure expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.authority_scope_kind expected" in serialized_errors
    assert (
        "actual_diff_certificate_minting_evidence.actual_diff_terminal_closure_certificate_witness_ref expected"
        in serialized_errors
    )
    assert (
        "actual_diff_certificate_minting_evidence.actual_diff_operator_response_witness_ref expected"
        in serialized_errors
    )
    assert "actual_diff_certificate_minting_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.changed_file_refs expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.diff_refs expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "actual_diff_certificate_minting_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_rejects_mutation_authority(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model(
        projection_scope__repository_mutation_authority_granted=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__repository_written_by_read_model=True,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "repository_mutation_authority_granted" in serialized_errors
    assert "repository_write_enabled" in serialized_errors
    assert "repository_written_by_read_model" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_rejects_new_terminal_authority(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model(
        projection_scope__new_terminal_closure_authority_granted=True,
        authority_denials__new_terminal_closure_enabled=True,
        effect_boundary__terminal_certificate_minted_by_read_model=True,
        read_model_is_not_terminal_closure=False,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "new_terminal_closure_authority_granted" in serialized_errors
    assert "new_terminal_closure_enabled" in serialized_errors
    assert "terminal_certificate_minted_by_read_model" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_rejects_mutation_route_and_secret_like_payload(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_read_model(
        next_action="POST /api/v1/harness/github-pr/terminal-certificate/read-model",
    )
    payload["operator_view"]["serialized_token_value"] = "github_pat_forbiddencredential"
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_certificate_read_model_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json", "--example", str(DEFAULT_EXAMPLES[0])])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["example_count"] == 1
    assert payload["read_model_id"] == EXPECTED_READ_MODEL_ID
