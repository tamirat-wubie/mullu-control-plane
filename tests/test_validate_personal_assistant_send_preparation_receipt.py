"""Tests for Personal Assistant send-preparation receipt validation.

Purpose: prove Personal Assistant send-preparation receipts stay redacted,
no-effect, and strictly separated from send execution.
Governance scope: Personal Assistant send-preparation validation,
approved-decision binding, queue precondition binding, raw-content rejection,
and provider-effect denial.
Dependencies: scripts.validate_personal_assistant_send_preparation_receipt.
Invariants:
  - Ready preparation requires approved decision carry-forward.
  - Send execution remains outside this receipt.
  - Raw fields, secret markers, bad hashes, and effect drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_personal_assistant_send_preparation_receipt import (
    main,
    validate_personal_assistant_send_preparation_receipt,
    write_personal_assistant_send_preparation_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_send_preparation_receipt.schema.json"
REHEARSAL_PACKET_PATH = ROOT / "examples" / "personal_assistant_email_send_with_approval_rehearsal_packet.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_personal_assistant_email_send_rehearsal_packet_validates_ready_without_effects() -> None:
    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=REHEARSAL_PACKET_PATH,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )
    payload = json.loads(REHEARSAL_PACKET_PATH.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert payload["workflow_id"] == "personal_assistant.email_send_with_approval"
    assert payload["send_preparation_authorized_by_decision"] is True
    assert payload["external_send_authorized_by_decision"] is False
    assert payload["send_execution_performed_by_producer"] is False
    assert payload["draft_created_by_producer"] is False
    assert payload["external_mailbox_write_performed"] is False
    assert payload["external_message_sent"] is False
    assert payload["connector_mutation_performed"] is False
    assert payload["system_of_record_write_performed"] is False
    assert payload["memory_write_performed"] is False
    assert payload["raw_message_content_serialized"] is False
    assert payload["raw_recipient_serialized"] is False
    assert payload["no_secret_values_serialized"] is True


def test_personal_assistant_send_preparation_validation_accepts_blocked_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.proof_state == "Unknown"
    assert validation.approval_decision_ready is True
    assert validation.send_preparation_ready is False
    assert validation.blocked_until == ("send_preparation_evidence_missing",)


def test_personal_assistant_send_preparation_validation_require_ready_rejects_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "Personal Assistant send preparation receipt ready must be true" in validation.errors


def test_personal_assistant_send_preparation_validation_accepts_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.decision == "approved"
    assert validation.receipt_decision == "deferred"
    assert validation.send_preparation_state == "prepared"
    assert validation.next_action == (
        "execute separate Personal Assistant send-execution receipt only after final effect preflight"
    )


def test_personal_assistant_send_preparation_validation_rejects_denied_decision(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {
        "decision": "rejected",
        "send_preparation_authorized_by_decision": False,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("approved decision" in error for error in validation.errors)


def test_personal_assistant_send_preparation_validation_rejects_effect_drift(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {"external_message_sent": True}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("external_message_sent" in error for error in validation.errors)


def test_personal_assistant_send_preparation_validation_rejects_raw_fields(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {"recipient_email": "user@example.invalid"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize raw field: recipient_email" in validation.errors


def test_personal_assistant_send_preparation_validation_rejects_missing_preparation(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {"send_preparation_ref": "", "evidence_refs": []}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("send_preparation_ref" in error for error in validation.errors)
    assert "passed receipt requires evidence_refs" in validation.errors


def test_personal_assistant_send_preparation_validation_rejects_bad_hash(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {"recipient_hash": "not-a-sha"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("recipient_hash" in error for error in validation.errors)


def test_personal_assistant_send_preparation_validation_rejects_secret_marker(tmp_path: Path) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    payload = _ready_receipt() | {"send_preparation_ref": "client_secret="}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize secret-like value" in validation.errors


def test_personal_assistant_send_preparation_validation_cli_writes_receipt(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    output_path = tmp_path / "personal_assistant_send_preparation_receipt_validation.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")
    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_personal_assistant_send_preparation_receipt_validation(validation, output_path)
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


def test_personal_assistant_send_preparation_validation_missing_path_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "missing.json"

    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_id == ""
    assert "Personal Assistant send preparation receipt file missing" in validation.errors


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "send_preparation_state": "missing",
        "send_preparation_ready": False,
        "send_preparation_ref": "",
        "prepared_message_ref": "",
        "recipient_hash": "",
        "prepared_message_hash": "",
        "send_preparation_authorized_by_decision": False,
        "evidence_refs": [],
        "blocked_until": ["send_preparation_evidence_missing"],
        "recovery_actions": ["bind redacted send-preparation, prepared-message, recipient-hash, and message-hash evidence"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "send_preparation_state": "prepared",
        "send_preparation_ready": True,
        "send_preparation_ref": "send-preparation:aaaaaaaaaaaaaaaa",
        "prepared_message_ref": "prepared-message:aaaaaaaaaaaaaaaa",
        "recipient_hash": HEX_A,
        "prepared_message_hash": HEX_B,
        "send_preparation_authorized_by_decision": True,
        "evidence_refs": ["send-preparation:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "pa_send_preparation_receipt_aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "personal_assistant.email_send_with_approval",
        "source_approval_decision_ref": "examples/personal_assistant_approval_decision_evidence.json",
        "source_decision_set_id": "pa_approval_decision_set_foundation_001",
        "source_decision_id": "pa_approval_decision_approved_001",
        "approval_decision_valid": True,
        "approval_decision_ready": True,
        "approval_id": "pa_approval_decision_approved_001",
        "request_id": "pa_request_decision_approved_001",
        "plan_id": "pa_plan_decision_approved_001",
        "decision": "approved",
        "receipt_decision": "deferred",
        "queue_precondition_sha256": HEX_A,
        "source_queue_state": "requested",
        "source_queue_receipt_id": "pa_receipt_decision_approved_001_request",
        "source_review_packet_id": "pa_approval_review_approval_review_packet_001",
        "source_review_packet_sha256": HEX_B,
        "prepared_at": "2026-06-14T00:00:00+00:00",
        "external_send_authorized_by_decision": False,
        "send_execution_performed_by_producer": False,
        "requires_separate_send_execution_receipt": True,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "connector_mutation_performed": False,
        "system_of_record_write_performed": False,
        "memory_write_performed": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_personal_assistant_send_preparation_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
