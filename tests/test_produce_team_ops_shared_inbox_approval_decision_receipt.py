"""Tests for TeamOps shared inbox approval decision receipt production.

Purpose: prove TeamOps approval queue obligations compose into redacted
operator decision receipts without drafting or sending.
Governance scope: TeamOps approval decisions, no-effect producer claims,
approver role binding, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_approval_decision_receipt.
Invariants:
  - Blocked queue evidence keeps decision receipts blocked.
  - Ready decisions require redacted approver and decision evidence refs.
  - Approved decisions authorize only a later separate send receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_approval_decision_receipt import (
    main,
    produce_team_ops_shared_inbox_approval_decision_receipt,
    write_team_ops_shared_inbox_approval_decision_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_approval_decision_receipt.schema.json"


def test_team_ops_shared_inbox_approval_decision_blocks_without_queue_ready(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_blocked_queue_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.approval_queue_receipt_valid is True
    assert receipt.approval_queue_receipt_ready is False
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.approval_decision_performed_by_producer is False
    assert receipt.draft_created_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("approval_queue_receipt_not_ready",)


def test_team_ops_shared_inbox_approval_decision_requires_decision_evidence(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.approval_queue_receipt_ready is True
    assert receipt.approval_queue_id == "team_ops.external_send_approval"
    assert receipt.decision == ""
    assert receipt.approval_state == "missing"
    assert receipt.operator_decision_evidence_recorded is False
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.blocked_until == ("approval_decision_evidence_missing",)


def test_team_ops_shared_inbox_approval_decision_accepts_approved_decision(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
        approver_ref="principal:team-ops-owner",
        approver_role="team_ops_owner",
        decision="approved",
        decision_evidence_ref="approval-decision:aaaaaaaaaaaaaaaa",
        decision_reason_ref="approval-reason:aaaaaaaaaaaaaaaa",
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.approval_state == "approved"
    assert receipt.operator_decision_evidence_recorded is True
    assert receipt.approval_decision_performed_by_producer is False
    assert receipt.external_send_authorized_by_decision is True
    assert receipt.requires_separate_send_receipt is True
    assert receipt.external_message_sent is False
    assert receipt.draft_created_by_producer is False
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_approval_decision_accepts_denied_no_send(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
        approver_ref="principal:team-ops-owner",
        approver_role="team_ops_owner",
        decision="denied",
        decision_evidence_ref="approval-decision:bbbbbbbbbbbbbbbb",
    )

    assert receipt.status == "passed"
    assert receipt.decision == "denied"
    assert receipt.approval_state == "denied"
    assert receipt.operator_decision_evidence_recorded is True
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_approval_decision_blocks_role_mismatch(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
        approver_ref="principal:security-reviewer",
        approver_role="security_reviewer",
        decision="approved",
        decision_evidence_ref="approval-decision:cccccccccccccccc",
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.approval_state == "invalid"
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.blocked_until == ("approver_role_mismatch",)


def test_team_ops_shared_inbox_approval_decision_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_approval_decision_receipt(
            approval_queue_receipt_path=queue_path,
            schema_path=SCHEMA_PATH,
            decided_at="2026-06-14T00:00:00+00:00",
            approver_ref="client_secret=must-not-serialize",
            approver_role="team_ops_owner",
            decision="approved",
            decision_evidence_ref="approval-decision:aaaaaaaaaaaaaaaa",
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_approval_decision_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    queue_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    queue_path.write_text(json.dumps(_ready_queue_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
        approval_queue_receipt_path=queue_path,
        schema_path=SCHEMA_PATH,
        decided_at="2026-06-14T00:00:00+00:00",
        approver_ref="principal:team-ops-owner",
        approver_role="team_ops_owner",
        decision="approved",
        decision_evidence_ref="approval-decision:aaaaaaaaaaaaaaaa",
    )

    written = write_team_ops_shared_inbox_approval_decision_receipt(receipt, output_path)
    exit_code = main(
        [
            "--approval-queue-receipt",
            str(queue_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--decided-at",
            "2026-06-14T00:00:00+00:00",
            "--approver-ref",
            "principal:team-ops-owner",
            "--approver-role",
            "team_ops_owner",
            "--decision",
            "approved",
            "--decision-evidence-ref",
            "approval-decision:aaaaaaaaaaaaaaaa",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["approval_state"] == "approved"
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_queue_receipt() -> dict[str, object]:
    return _base_queue_receipt() | {
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


def _ready_queue_receipt() -> dict[str, object]:
    return _base_queue_receipt() | {
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


def _base_queue_receipt() -> dict[str, object]:
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
