"""Tests for GitHub PR terminal closure certificate minting.

Purpose: prove the terminal closure certificate mints only after explicit
approve_terminal_certificate evidence and remains bounded to the PR proof thread.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting.
Invariants:
  - The default certificate minting record validates.
  - Missing approval, missing evidence, invalid disposition, mutation authority,
    mutation routes, and credential-like values fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_CERTIFICATE_ID,
    EXPECTED_DECISION_VALUE,
    build_mutated_terminal_closure_certificate_minting,
    main,
    validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting,
)


def _write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "github-pr-terminal-closure-certificate-minting.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_github_pr_terminal_closure_certificate_minting_accepts_default_fixture() -> None:
    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.certificate_id == EXPECTED_CERTIFICATE_ID
    assert validation.source_decision_value_record_ref.endswith(
        "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json"
    )


def test_github_pr_terminal_closure_certificate_minting_rejects_denial_value(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting(
        operator_decision_value="deny_terminal_certificate",
        terminal_closure_certificate__metadata__operator_decision_value="deny_terminal_certificate",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert EXPECTED_DECISION_VALUE in serialized_errors
    assert "operator_decision_value" in serialized_errors
    assert "deny_terminal_certificate" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_rejects_unminted_certificate(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting(
        terminal_closure_certificate_minted=False,
        terminal_closure_authorized=False,
        terminal_closure=False,
        authority_scope__terminal_certificate_minting_authorized=False,
        effect_boundary__terminal_certificate_minted_by_record=False,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_minted" in serialized_errors
    assert "terminal_closure_authorized" in serialized_errors
    assert "terminal_certificate_minted_by_record" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_rejects_invalid_disposition(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting(
        terminal_closure_certificate__disposition="requires_review",
        terminal_closure_certificate__case_id="case-review-required",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "disposition" in serialized_errors
    assert "requires_review" in serialized_errors
    assert "case_id" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_rejects_missing_evidence_ref(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting()
    payload["terminal_closure_certificate"]["evidence_refs"].remove(
        "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json"
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_refs missing" in serialized_errors
    assert "operator_decision_value_record" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_rejects_mutation_authority(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting(
        authority_scope__repository_mutation_authority_granted=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__pull_request_merge_enabled=True,
        effect_boundary__repository_written_by_minting_runtime=True,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "repository_mutation_authority_granted" in serialized_errors
    assert "repository_write_enabled" in serialized_errors
    assert "pull_request_merge_enabled" in serialized_errors
    assert "repository_written_by_minting_runtime" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_rejects_mutation_route_and_secret_like_payload(
    tmp_path: Path,
) -> None:
    payload = build_mutated_terminal_closure_certificate_minting(
        next_action="POST /api/v1/harness/github-pr/terminal-closure",
    )
    payload["terminal_closure_certificate"]["metadata"]["serialized_token_value"] = "github_pat_forbiddencredential"
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_certificate_minting_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json", "--example", str(DEFAULT_EXAMPLES[0])])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["example_count"] == 1
    assert payload["certificate_id"] == EXPECTED_CERTIFICATE_ID
