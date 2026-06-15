"""Tests for TeamOps shared inbox send-preparation receipt validation.

Purpose: prove TeamOps send-preparation receipts stay redacted, no-effect, and
strictly separated from send execution.
Governance scope: TeamOps send-preparation validation, approved-decision
binding, raw-content rejection, and provider-effect denial.
Dependencies: scripts.validate_team_ops_shared_inbox_send_preparation_receipt.
Invariants:
  - Ready preparation requires approved decision carry-forward.
  - Send execution remains outside this receipt.
  - Raw fields, secret markers, bad hashes, and effect drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_send_preparation_receipt import (
    main,
    validate_team_ops_shared_inbox_send_preparation_receipt,
    write_team_ops_shared_inbox_send_preparation_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_send_preparation_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_shared_inbox_send_preparation_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.proof_state == "Unknown"
    assert validation.approval_decision_receipt_ready is False
    assert validation.send_preparation_ready is False
    assert validation.blocked_until == ("approval_decision_receipt_not_ready",)


def test_team_ops_shared_inbox_send_preparation_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps send preparation receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_send_preparation_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.decision == "approved"
    assert validation.send_preparation_state == "prepared"
    assert validation.next_action == "execute separate TeamOps send-execution receipt only after final effect preflight"


def test_team_ops_shared_inbox_send_preparation_validation_rejects_denied_decision(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {
        "decision": "denied",
        "approval_state": "denied",
        "external_send_authorized_by_decision": False,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("approved decision" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_preparation_validation_rejects_effect_drift(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {"external_message_sent": True}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("external_message_sent" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_preparation_validation_rejects_raw_fields(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {"recipient_email": "user@example.invalid"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize raw field: recipient_email" in validation.errors


def test_team_ops_shared_inbox_send_preparation_validation_rejects_missing_preparation(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {"send_preparation_ref": "", "evidence_refs": []}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("send_preparation_ref" in error for error in validation.errors)
    assert "passed receipt requires evidence_refs" in validation.errors


def test_team_ops_shared_inbox_send_preparation_validation_rejects_bad_hash(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {"recipient_hash": "not-a-sha"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("recipient_hash" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_preparation_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    payload = _ready_receipt() | {"send_preparation_ref": "client_secret="}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_preparation_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt_validation.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_send_preparation_receipt_validation(validation, output_path)
    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ready"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def test_team_ops_shared_inbox_send_preparation_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "missing.json"

    validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_id == ""
    assert "TeamOps send preparation receipt file missing" in validation.errors


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "approval_decision_receipt_valid": True,
        "approval_decision_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "approval_queue_id": "",
        "approval_request_ref": "",
        "approval_decision_ref": "",
        "approver_ref": "",
        "decision": "",
        "approval_state": "missing",
        "external_send_authorized_by_decision": False,
        "send_preparation_state": "missing",
        "send_preparation_ready": False,
        "send_preparation_ref": "",
        "prepared_message_ref": "",
        "thread_ref": "",
        "recipient_hash": "",
        "prepared_message_hash": "",
        "evidence_refs": [],
        "blocked_until": ["approval_decision_receipt_not_ready"],
        "recovery_actions": ["record an approved TeamOps approval decision before preparing send evidence"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "approval_decision_receipt_valid": True,
        "approval_decision_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "approval_decision_ref": "approval-decision:aaaaaaaaaaaaaaaa",
        "approver_ref": "principal:team-ops-owner",
        "decision": "approved",
        "approval_state": "approved",
        "external_send_authorized_by_decision": True,
        "send_preparation_state": "prepared",
        "send_preparation_ready": True,
        "send_preparation_ref": "send-preparation:aaaaaaaaaaaaaaaa",
        "prepared_message_ref": "prepared-message:aaaaaaaaaaaaaaaa",
        "thread_ref": "thread:teamops-123",
        "recipient_hash": HEX_A,
        "prepared_message_hash": HEX_B,
        "evidence_refs": ["send-preparation:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-send-preparation-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_approval_decision_receipt_ref": ".change_assurance/team_ops_shared_inbox_approval_decision_receipt.json",
        "source_approval_decision_receipt_id": "teamops-shared-inbox-approval-decision-receipt-aaaaaaaaaaaaaaaa",
        "prepared_at": "2026-06-14T00:00:00+00:00",
        "send_execution_performed_by_producer": False,
        "requires_separate_send_execution_receipt": True,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
