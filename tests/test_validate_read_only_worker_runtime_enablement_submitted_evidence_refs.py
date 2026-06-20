"""Tests for read-only worker runtime enablement submitted evidence refs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_submitted_evidence_refs import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_submitted_evidence_refs,
    main,
    validate_runtime_enablement_submitted_evidence_refs,
    write_runtime_enablement_submitted_evidence_refs_validation,
)


def test_runtime_enablement_submitted_evidence_refs_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_submitted_evidence_refs()

    assert fixture == generated
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["submission_state"] == "repo_refs_submitted_for_review"
    assert fixture["review_state"] == "not_evaluated"
    assert fixture["evidence_submitted"] is True
    assert fixture["evidence_accepted"] is False
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_dispatch_performed"] is False
    assert fixture["worker_invocation_performed"] is False
    assert len(fixture["submitted_records"]) == 12
    assert fixture["summary"]["records_with_repo_ref_count"] == 12
    assert fixture["summary"]["records_awaiting_operator_evidence_count"] == 0
    assert fixture["summary"]["accepted_evidence_count"] == 0


def test_runtime_enablement_submitted_evidence_refs_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_enablement_submitted_evidence_refs_validation.json"
    validation = validate_runtime_enablement_submitted_evidence_refs()

    written = write_runtime_enablement_submitted_evidence_refs_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.submitted_record_count == 12
    assert validation.records_with_repo_ref_count == 12
    assert validation.awaiting_operator_evidence_count == 0
    assert validation.submitted_evidence_ref_count == 12
    assert validation.accepted_evidence_count == 0
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_submitted_evidence_refs_rejects_authority_overclaim(tmp_path: Path) -> None:
    evidence_refs_path = _write_mutated_evidence_refs(tmp_path)
    payload = json.loads(evidence_refs_path.read_text(encoding="utf-8"))
    payload["authority_granted"] = True
    payload["runtime_enablement_allowed"] = True
    payload["submitted_records"][0]["authority_granted"] = True
    payload["submitted_records"][0]["runtime_enablement_allowed"] = True
    evidence_refs_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_submitted_evidence_refs(evidence_refs_path=evidence_refs_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "authority_granted must be false" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "submitted record authority_granted must be false" in serialized_errors
    assert "submitted record runtime_enablement_allowed must be false" in serialized_errors


def test_runtime_enablement_submitted_evidence_refs_rejects_acceptance_drift(tmp_path: Path) -> None:
    evidence_refs_path = _write_mutated_evidence_refs(tmp_path)
    payload = json.loads(evidence_refs_path.read_text(encoding="utf-8"))
    payload["evidence_accepted"] = True
    payload["accepted_evidence_refs"] = ["examples/read_only_worker_runtime_runner_registration_witness.foundation.json"]
    payload["submitted_records"][1]["accepted"] = True
    payload["submitted_records"][1]["candidate_ref_satisfies_required_name"] = True
    evidence_refs_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_submitted_evidence_refs(evidence_refs_path=evidence_refs_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "submitted record accepted must be false" in serialized_errors
    assert "submitted record candidate_ref_satisfies_required_name must be false" in serialized_errors


def test_runtime_enablement_submitted_evidence_refs_rejects_operator_ref_authority_overclaim(tmp_path: Path) -> None:
    evidence_refs_path = _write_mutated_evidence_refs(tmp_path)
    payload = json.loads(evidence_refs_path.read_text(encoding="utf-8"))
    approval_record = next(
        record
        for record in payload["submitted_records"]
        if record["input_kind"] == "operator_runtime_enablement_approval"
    )
    approval_record["authority_granted"] = True
    approval_record["runtime_enablement_allowed"] = True
    approval_record["candidate_ref_satisfies_required_name"] = True
    evidence_refs_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_submitted_evidence_refs(evidence_refs_path=evidence_refs_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "submitted record authority_granted must be false" in serialized_errors
    assert "submitted record runtime_enablement_allowed must be false" in serialized_errors
    assert "submitted record candidate_ref_satisfies_required_name must be false" in serialized_errors


def test_runtime_enablement_submitted_evidence_refs_rejects_missing_record(tmp_path: Path) -> None:
    evidence_refs_path = _write_mutated_evidence_refs(tmp_path)
    payload = json.loads(evidence_refs_path.read_text(encoding="utf-8"))
    payload["submitted_records"] = payload["submitted_records"][:-1]
    evidence_refs_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_submitted_evidence_refs(evidence_refs_path=evidence_refs_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "submitted_records must contain twelve records" in serialized_errors
    assert "submitted evidence refs do not match generated" in serialized_errors


def test_runtime_enablement_submitted_evidence_refs_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_enablement_submitted_evidence_refs_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["submitted_record_count"] == 12
    assert stdout_payload["records_with_repo_ref_count"] == 12
    assert captured.err == ""


def _write_mutated_evidence_refs(tmp_path: Path) -> Path:
    evidence_refs_path = tmp_path / "runtime_enablement_submitted_evidence_refs.json"
    evidence_refs_path.write_text(json.dumps(build_runtime_enablement_submitted_evidence_refs()), encoding="utf-8")
    return evidence_refs_path
