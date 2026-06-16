"""Tests for TeamOps shared inbox send-execution receipt validation.

Purpose: prove TeamOps send-execution receipts stay redacted, source-bound, and
free of local provider-effect claims.
Governance scope: TeamOps send-execution validation, send-preparation binding,
raw-content rejection, and local provider-effect denial.
Dependencies: scripts.validate_team_ops_shared_inbox_send_execution_receipt.
Invariants:
  - Ready execution requires approved send-preparation carry-forward.
  - Provider evidence is refs and hashes only.
  - Raw fields, secret markers, bad hashes, and local effect drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_send_execution_receipt import (
    main,
    validate_team_ops_shared_inbox_send_execution_receipt,
    write_team_ops_shared_inbox_send_execution_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_send_execution_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64


def test_team_ops_shared_inbox_send_execution_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.proof_state == "Unknown"
    assert validation.send_preparation_receipt_ready is False
    assert validation.provider_observation_receipt_valid is False
    assert validation.send_execution_ready is False
    assert validation.external_message_sent is False
    assert validation.blocked_until == ("send_preparation_receipt_not_ready",)


def test_team_ops_shared_inbox_send_execution_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps send execution receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_send_execution_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.provider_observation_receipt_valid is True
    assert validation.decision == "approved"
    assert validation.send_execution_state == "sent"
    assert validation.external_message_sent is True
    assert validation.next_action == "verify TeamOps sent-message observation and close workflow with replay evidence"


def test_team_ops_shared_inbox_send_execution_validation_rejects_unready_preparation(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"send_preparation_receipt_ready": False}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("ready send preparation receipt" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_execution_validation_rejects_local_provider_claim(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"provider_call_performed_by_producer": True}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("provider_call_performed_by_producer" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_execution_validation_rejects_raw_fields(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"provider_message_id": "provider-raw-message-id"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize raw field: provider_message_id" in validation.errors


def test_team_ops_shared_inbox_send_execution_validation_rejects_missing_execution(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"send_execution_ref": "", "evidence_refs": []}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("send_execution_ref" in error for error in validation.errors)
    assert "passed receipt requires evidence_refs" in validation.errors


def test_team_ops_shared_inbox_send_execution_validation_rejects_missing_provider_witness(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires provider_observation_receipt_ref" in validation.errors
    assert "passed receipt requires provider_observation_receipt_id" in validation.errors
    assert "passed receipt requires provider_observation_receipt_valid=true" in validation.errors


def test_team_ops_shared_inbox_send_execution_validation_rejects_bad_hash(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"provider_message_hash": "not-a-sha"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("provider_message_hash" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_execution_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    payload = _ready_receipt() | {"send_execution_ref": "client_secret="}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_send_execution_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt_validation.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_send_execution_receipt_validation(validation, output_path)
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


def test_team_ops_shared_inbox_send_execution_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "missing.json"

    validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_id == ""
    assert "TeamOps send execution receipt file missing" in validation.errors


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "send_preparation_receipt_valid": True,
        "send_preparation_receipt_ready": False,
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
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
        "send_preparation_ref": "",
        "prepared_message_ref": "",
        "thread_ref": "",
        "recipient_hash": "",
        "prepared_message_hash": "",
        "send_execution_state": "missing",
        "send_execution_ready": False,
        "send_execution_ref": "",
        "dispatch_receipt_ref": "",
        "provider_message_ref": "",
        "dispatch_receipt_hash": "",
        "provider_message_hash": "",
        "send_execution_observed": False,
        "external_message_sent": False,
        "evidence_refs": [],
        "blocked_until": ["send_preparation_receipt_not_ready"],
        "recovery_actions": ["record ready TeamOps send-preparation evidence before admitting send execution evidence"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "send_preparation_receipt_valid": True,
        "send_preparation_receipt_ready": True,
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
        "send_preparation_ref": "send-preparation:aaaaaaaaaaaaaaaa",
        "prepared_message_ref": "prepared-message:aaaaaaaaaaaaaaaa",
        "thread_ref": "thread:teamops-123",
        "recipient_hash": HEX_A,
        "prepared_message_hash": HEX_B,
        "send_execution_state": "sent",
        "send_execution_ready": True,
        "send_execution_ref": "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_ref": "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider_message_ref": "provider-message:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_hash": HEX_C,
        "provider_message_hash": HEX_D,
        "send_execution_observed": True,
        "external_message_sent": True,
        "evidence_refs": [
            "send-execution:aaaaaaaaaaaaaaaa",
            "dispatch-receipt:aaaaaaaaaaaaaaaa",
            "provider-message:aaaaaaaaaaaaaaaa",
        ],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-send-execution-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_send_preparation_receipt_ref": ".change_assurance/team_ops_shared_inbox_send_preparation_receipt.json",
        "source_send_preparation_receipt_id": "teamops-shared-inbox-send-preparation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "executed_at": "2026-06-14T00:00:00+00:00",
        "send_execution_performed_by_producer": False,
        "external_message_sent_by_producer": False,
        "external_mailbox_write_performed_by_producer": False,
        "provider_mutation_performed_by_producer": False,
        "provider_call_performed_by_producer": False,
        "draft_created_by_producer": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "no_secret_values_serialized": True,
        "requires_sent_message_observation_receipt": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_send_execution_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
