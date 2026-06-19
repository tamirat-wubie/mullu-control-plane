"""Tests for read-only worker runtime enablement evidence request status ledgers.

Purpose: prove runtime enablement evidence request status ledgers remain
read-only and do not submit, accept, reject, authorize, enable, dispatch,
invoke, emit, append, close, or claim success.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.
Invariants:
  - Status ledger records unresolved evidence status only.
  - Runtime authority and evidence authority remain denied.
  - Secret serialization remains denied.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_evidence_request_status_ledger,
    main,
    validate_runtime_enablement_evidence_request_status_ledger,
    write_runtime_enablement_evidence_request_status_ledger_validation,
)


def test_runtime_enablement_status_ledger_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_evidence_request_status_ledger()
    records = fixture["status_records"]

    assert fixture == generated
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["ledger_state"] == "request_status_only"
    assert fixture["status_ledger_is_not_evidence"] is True
    assert fixture["status_ledger_is_not_runtime_enablement"] is True
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_dispatch_performed"] is False
    assert fixture["worker_invocation_performed"] is False
    assert fixture["secret_values_serialized"] is False
    assert len(records) == 12
    assert fixture["summary"]["awaiting_evidence_count"] == 12
    assert fixture["summary"]["submitted_evidence_count"] == 0
    assert records[0]["status"] == "awaiting_evidence"


def test_runtime_enablement_status_ledger_validator_writes_receipt(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "runtime_enablement_status_ledger_validation.json"
    validation = validate_runtime_enablement_evidence_request_status_ledger()

    written = write_runtime_enablement_evidence_request_status_ledger_validation(
        validation,
        output_path,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.status_record_count == 12
    assert validation.awaiting_evidence_count == 12
    assert validation.submitted_evidence_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_status_ledger_rejects_submission_overclaim(
    tmp_path: Path,
) -> None:
    ledger_path = _write_mutated_ledger(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["evidence_submitted"] = True
    payload["submitted_evidence_refs"] = ["evidence://submitted"]
    payload["status_records"][0]["evidence_submitted"] = True
    payload["status_records"][0]["submitted_evidence_refs"] = ["evidence://submitted"]
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_evidence_request_status_ledger(
        ledger_path=ledger_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "evidence_submitted must be false" in serialized_errors
    assert "submitted_evidence_refs must remain empty" in serialized_errors
    assert "status record evidence_submitted must be false" in serialized_errors
    assert "status record submitted_evidence_refs must remain empty" in serialized_errors


def test_runtime_enablement_status_ledger_rejects_runtime_authority_drift(
    tmp_path: Path,
) -> None:
    ledger_path = _write_mutated_ledger(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["runtime_enablement_allowed"] = True
    payload["runtime_dispatch_performed"] = True
    payload["status_records"][0]["runtime_enablement_allowed"] = True
    payload["status_records"][0]["runtime_dispatch_allowed"] = True
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_evidence_request_status_ledger(
        ledger_path=ledger_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_performed must be false" in serialized_errors
    assert "status record runtime_enablement_allowed must be false" in serialized_errors
    assert "status record runtime_dispatch_allowed must be false" in serialized_errors
    assert "summary.runtime_enablement_count" in serialized_errors


def test_runtime_enablement_status_ledger_rejects_missing_record(
    tmp_path: Path,
) -> None:
    ledger_path = _write_mutated_ledger(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["status_records"] = payload["status_records"][:-1]
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_evidence_request_status_ledger(
        ledger_path=ledger_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "status_records must contain twelve records" in serialized_errors
    assert "ledger does not match generated" in serialized_errors


def test_runtime_enablement_status_ledger_cli_json(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "runtime_enablement_status_ledger_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["status_record_count"] == 12
    assert captured.err == ""


def _write_mutated_ledger(tmp_path: Path) -> Path:
    ledger_path = tmp_path / "runtime_enablement_status_ledger.json"
    ledger_path.write_text(
        json.dumps(build_runtime_enablement_evidence_request_status_ledger()),
        encoding="utf-8",
    )
    return ledger_path
