"""Tests for TeamOps shared inbox approval queue receipt validation.

Purpose: prove TeamOps approval queue receipts are schema-backed, redacted,
no-send, and strictly separated from approval decisions.
Governance scope: TeamOps approval queue evidence, no-effect enforcement,
readiness validation, and validation receipt emission.
Dependencies: scripts.validate_team_ops_shared_inbox_approval_queue_receipt.
Invariants:
  - Blocked approval queue receipts remain valid non-ready evidence.
  - Ready queue receipts require a pending obligation and no approval decision.
  - Effect drift, raw content leakage, and secret markers fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_approval_queue_receipt import (
    main,
    validate_team_ops_shared_inbox_approval_queue_receipt,
    write_team_ops_shared_inbox_approval_queue_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_approval_queue_receipt.schema.json"


def test_team_ops_shared_inbox_approval_queue_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.routing_receipt_ready is False
    assert validation.blocked_until == ("observation_routing_receipt_not_ready",)


def test_team_ops_shared_inbox_approval_queue_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps approval queue receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_approval_queue_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.proof_state == "Pass"
    assert validation.approval_queue_id == "team_ops.external_send_approval"
    assert validation.approval_state == "pending"
    assert validation.blocked_until == ()


def test_team_ops_shared_inbox_approval_queue_validation_rejects_effect_drift(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    payload = _ready_receipt() | {
        "external_message_sent": True,
        "approval_decision_performed_by_producer": True,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "external_message_sent must be false" in validation.errors
    assert "approval_decision_performed_by_producer must be false" in validation.errors


def test_team_ops_shared_inbox_approval_queue_validation_rejects_raw_fields(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    payload = _ready_receipt() | {
        "subject": "raw subject",
        "sender_email": "operator@example.invalid",
        "message_body": "raw body",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "$: unexpected property 'subject'" in validation.errors
    assert "receipt must not serialize raw field: subject" in validation.errors
    assert "receipt must not serialize raw field: sender_email" in validation.errors
    assert "receipt must not serialize raw field: message_body" in validation.errors


def test_team_ops_shared_inbox_approval_queue_validation_rejects_missing_request(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    payload = _ready_receipt() | {"approval_request_ref": ""}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires approval_request_ref" in validation.errors


def test_team_ops_shared_inbox_approval_queue_validation_rejects_approval_decision_claim(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    payload = _ready_receipt() | {"approval_decision_ref": "approval-decision:123"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "approval queue receipt must not claim approval decision evidence" in validation.errors


def test_team_ops_shared_inbox_approval_queue_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    payload = _blocked_receipt() | {"recovery_actions": ["bind client_secret=must-not-serialize"]}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_approval_queue_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt_validation.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_approval_queue_receipt_validation(validation, output_path)
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


def test_team_ops_shared_inbox_approval_queue_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "secret-approval-queue-receipt-path.json"

    validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_path == "secret-approval-queue-receipt-path.json"
    assert validation.errors == ("TeamOps approval queue receipt file missing",)
    assert str(tmp_path) not in json.dumps(validation.as_dict(), sort_keys=True)


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "routing_receipt_valid": True,
        "routing_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "approval_queue_id": "",
        "approval_request_ref": "",
        "required_approver_role": "team_ops_owner",
        "approval_state": "missing",
        "approval_queue_obligation_bound": False,
        "evidence_refs": [],
        "blocked_until": ["observation_routing_receipt_not_ready"],
        "recovery_actions": ["close TeamOps observation routing evidence before creating approval queue obligations"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "routing_receipt_valid": True,
        "routing_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "required_approver_role": "team_ops_owner",
        "approval_state": "pending",
        "approval_queue_obligation_bound": True,
        "evidence_refs": ["approval_queue_obligation:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-approval-queue-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_observation_routing_receipt_ref": ".change_assurance/team_ops_shared_inbox_observation_routing_receipt.json",
        "source_observation_routing_receipt_id": "teamops-shared-inbox-observation-routing-receipt-aaaaaaaaaaaaaaaa",
        "queued_at": "2026-06-14T00:00:00+00:00",
        "approval_decision_ref": "",
        "approval_required_before_external_send": True,
        "draft_response_required": True,
        "external_send_allowed": False,
        "approval_decision_performed_by_producer": False,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_approval_queue_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
