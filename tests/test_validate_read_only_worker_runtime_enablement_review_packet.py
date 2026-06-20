"""Tests for read-only worker runtime enablement review packets.

Purpose: prove review packets do not accept evidence or grant runtime
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_review_packet.
Invariants:
  - Review is not evidence acceptance.
  - Reviewed repo-local refs do not satisfy runtime input names.
  - Evidence acceptance and runtime admission remain future blockers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_review_packet import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_review_packet,
    main,
    validate_runtime_enablement_review_packet,
    write_runtime_enablement_review_packet_validation,
)


def test_runtime_enablement_review_packet_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_review_packet()

    assert fixture == generated
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["review_packet_state"] == "reviewed_all_inputs_not_accepted"
    assert fixture["review_state"] == "reviewed_not_accepted"
    assert fixture["evidence_accepted"] is False
    assert fixture["authority_granted"] is False
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["worker_invocation_performed"] is False
    assert fixture["summary"]["review_record_count"] == 12
    assert fixture["summary"]["reviewed_repo_ref_count"] == 12
    assert fixture["summary"]["missing_input_count"] == 0
    assert fixture["summary"]["accepted_evidence_count"] == 0


def test_runtime_enablement_review_packet_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_enablement_review_packet_validation.json"
    validation = validate_runtime_enablement_review_packet()

    written = write_runtime_enablement_review_packet_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.review_record_count == 12
    assert validation.reviewed_repo_ref_count == 12
    assert validation.missing_input_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_review_packet_rejects_acceptance_overclaim(tmp_path: Path) -> None:
    review_packet_path = _write_mutated_review_packet(tmp_path)
    payload = json.loads(review_packet_path.read_text(encoding="utf-8"))
    payload["evidence_accepted"] = True
    payload["accepted_evidence_refs"] = ["examples/read_only_worker_runtime_runner_registration_witness.foundation.json"]
    payload["review_records"][1]["accepted"] = True
    review_packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_review_packet(review_packet_path=review_packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "review record accepted must be false" in serialized_errors
    assert "summary.accepted_evidence_count" in serialized_errors


def test_runtime_enablement_review_packet_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    review_packet_path = _write_mutated_review_packet(tmp_path)
    payload = json.loads(review_packet_path.read_text(encoding="utf-8"))
    payload["authority_granted"] = True
    payload["runtime_enablement_allowed"] = True
    payload["review_records"][0]["authority_granted"] = True
    payload["review_records"][0]["runtime_enablement_allowed"] = True
    review_packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_review_packet(review_packet_path=review_packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "authority_granted must be false" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "review record authority_granted must be false" in serialized_errors
    assert "review record runtime_enablement_allowed must be false" in serialized_errors


def test_runtime_enablement_review_packet_rejects_candidate_satisfaction_drift(tmp_path: Path) -> None:
    review_packet_path = _write_mutated_review_packet(tmp_path)
    payload = json.loads(review_packet_path.read_text(encoding="utf-8"))
    payload["review_records"][0]["candidate_ref_satisfies_required_name"] = True
    review_packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_review_packet(review_packet_path=review_packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "review record candidate_ref_satisfies_required_name must be false" in serialized_errors
    assert "runtime enablement review packet does not match generated" in serialized_errors
    assert validation.runtime_enablement_allowed is False


def test_runtime_enablement_review_packet_rejects_missing_record(tmp_path: Path) -> None:
    review_packet_path = _write_mutated_review_packet(tmp_path)
    payload = json.loads(review_packet_path.read_text(encoding="utf-8"))
    payload["review_records"] = payload["review_records"][:-1]
    review_packet_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_review_packet(review_packet_path=review_packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "review_records must contain twelve records" in serialized_errors
    assert "runtime enablement review packet does not match generated" in serialized_errors


def test_runtime_enablement_review_packet_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_enablement_review_packet_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["review_record_count"] == 12
    assert stdout_payload["reviewed_repo_ref_count"] == 12
    assert captured.err == ""


def _write_mutated_review_packet(tmp_path: Path) -> Path:
    review_packet_path = tmp_path / "runtime_enablement_review_packet.json"
    review_packet_path.write_text(json.dumps(build_runtime_enablement_review_packet()), encoding="utf-8")
    return review_packet_path
