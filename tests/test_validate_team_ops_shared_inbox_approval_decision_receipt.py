"""Tests for TeamOps shared inbox approval decision receipt validation.

Purpose: prove TeamOps approval decision receipts are schema-backed, redacted,
effect-free, and strictly separated from send execution.
Governance scope: TeamOps decision evidence, no-effect enforcement, readiness
validation, role matching, and validation receipt emission.
Dependencies: scripts.validate_team_ops_shared_inbox_approval_decision_receipt.
Invariants:
  - Blocked decision receipts remain valid non-ready evidence.
  - Ready decision receipts require a matching approver role and decision evidence.
  - Effect drift, raw content leakage, and secret markers fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_approval_decision_receipt import (
    main,
    validate_team_ops_shared_inbox_approval_decision_receipt,
    write_team_ops_shared_inbox_approval_decision_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_approval_decision_receipt.schema.json"


def test_team_ops_shared_inbox_approval_decision_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.approval_queue_receipt_ready is False
    assert validation.provider_observation_receipt_valid is False
    assert validation.external_send_authorized_by_decision is False
    assert validation.blocked_until == ("approval_queue_receipt_not_ready",)


def test_team_ops_shared_inbox_approval_decision_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps approval decision receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_accepts_approved_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    receipt_path.write_text(json.dumps(_approved_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.decision == "approved"
    assert validation.provider_observation_receipt_valid is True
    assert validation.approval_state == "approved"
    assert validation.external_send_authorized_by_decision is True
    assert validation.next_action == "prepare separate TeamOps send-preparation receipt before any external send"


def test_team_ops_shared_inbox_approval_decision_validation_accepts_denied_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    receipt_path.write_text(json.dumps(_approved_receipt() | {"decision": "denied", "approval_state": "denied", "external_send_authorized_by_decision": False}), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.decision == "denied"
    assert validation.approval_state == "denied"
    assert validation.external_send_authorized_by_decision is False
    assert validation.next_action == "close TeamOps shared inbox request without external send"


def test_team_ops_shared_inbox_approval_decision_validation_rejects_effect_drift(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {
        "external_message_sent": True,
        "draft_created_by_producer": True,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "external_message_sent must be false" in validation.errors
    assert "draft_created_by_producer must be false" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_raw_fields(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {
        "subject": "raw subject",
        "decision_text": "raw approval text",
        "message_body": "raw body",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "$: unexpected property 'subject'" in validation.errors
    assert "receipt must not serialize raw field: subject" in validation.errors
    assert "receipt must not serialize raw field: decision_text" in validation.errors
    assert "receipt must not serialize raw field: message_body" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_missing_evidence(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {"decision_evidence_ref": ""}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires decision_evidence_ref" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_missing_provider_observation(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires provider_observation_receipt_ref" in validation.errors
    assert "passed receipt requires provider_observation_receipt_id" in validation.errors
    assert "passed receipt requires provider_observation_receipt_valid=true" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_role_mismatch(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {"approver_role": "security_reviewer"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires approver_role to match required_approver_role" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_bad_authorization(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _approved_receipt() | {"decision": "denied", "approval_state": "denied", "external_send_authorized_by_decision": True}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "external_send_authorized_by_decision must match approved decision only" in validation.errors


def test_team_ops_shared_inbox_approval_decision_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    payload = _blocked_receipt() | {"recovery_actions": ["bind client_secret=must-not-serialize"]}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_approval_decision_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt_validation.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_approval_decision_receipt_validation(validation, output_path)
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
    assert payload["valid"] is True
    assert payload["ready"] is False
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def test_team_ops_shared_inbox_approval_decision_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "secret-approval-decision-receipt-path.json"

    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_path == "secret-approval-decision-receipt-path.json"
    assert validation.errors == ("TeamOps approval decision receipt file missing",)
    assert str(tmp_path) not in json.dumps(validation.as_dict(), sort_keys=True)


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "approval_queue_receipt_valid": True,
        "approval_queue_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "approval_queue_id": "",
        "approval_request_ref": "",
        "required_approver_role": "",
        "approver_ref": "",
        "approver_role": "",
        "decision": "",
        "approval_state": "missing",
        "decision_evidence_ref": "",
        "decision_reason_ref": "",
        "operator_decision_evidence_recorded": False,
        "external_send_authorized_by_decision": False,
        "evidence_refs": [],
        "blocked_until": ["approval_queue_receipt_not_ready"],
        "recovery_actions": ["close TeamOps approval queue evidence before recording an approval decision"],
    }


def _approved_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "approval_queue_receipt_valid": True,
        "approval_queue_receipt_ready": True,
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "required_approver_role": "team_ops_owner",
        "approver_ref": "principal:team-ops-owner",
        "approver_role": "team_ops_owner",
        "decision": "approved",
        "approval_state": "approved",
        "decision_evidence_ref": "approval-decision:aaaaaaaaaaaaaaaa",
        "decision_reason_ref": "approval-reason:aaaaaaaaaaaaaaaa",
        "operator_decision_evidence_recorded": True,
        "external_send_authorized_by_decision": True,
        "evidence_refs": ["approval-decision:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-approval-decision-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_approval_queue_receipt_ref": ".change_assurance/team_ops_shared_inbox_approval_queue_receipt.json",
        "source_approval_queue_receipt_id": "teamops-shared-inbox-approval-queue-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "decided_at": "2026-06-14T00:00:00+00:00",
        "approval_decision_performed_by_producer": False,
        "requires_separate_send_receipt": True,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "raw_decision_text_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
