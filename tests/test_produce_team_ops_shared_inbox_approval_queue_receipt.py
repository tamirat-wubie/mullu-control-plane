"""Tests for TeamOps shared inbox approval queue receipt production.

Purpose: prove TeamOps routing evidence composes into a no-send pending
approval obligation before any external communication.
Governance scope: TeamOps approval queue binding, redaction, no-effect
producer claims, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_approval_queue_receipt.
Invariants:
  - Blocked routing evidence keeps approval queue receipts blocked.
  - Ready queue receipts require a redacted approval request and evidence refs.
  - Passed queue receipts never approve, draft, send, write, or mutate providers.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_approval_queue_receipt import (
    main,
    produce_team_ops_shared_inbox_approval_queue_receipt,
    write_team_ops_shared_inbox_approval_queue_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_approval_queue_receipt.schema.json"


def test_team_ops_shared_inbox_approval_queue_blocks_without_routing_ready(
    tmp_path: Path,
) -> None:
    routing_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    routing_path.write_text(json.dumps(_blocked_routing_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_queue_receipt(
        routing_receipt_path=routing_path,
        schema_path=SCHEMA_PATH,
        queued_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.routing_receipt_valid is True
    assert receipt.routing_receipt_ready is False
    assert receipt.provider_observation_receipt_ref == ""
    assert receipt.provider_observation_receipt_id == ""
    assert receipt.provider_observation_receipt_valid is False
    assert receipt.external_send_allowed is False
    assert receipt.approval_decision_performed_by_producer is False
    assert receipt.draft_created_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("observation_routing_receipt_not_ready",)


def test_team_ops_shared_inbox_approval_queue_requires_request_evidence(
    tmp_path: Path,
) -> None:
    routing_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    routing_path.write_text(json.dumps(_ready_routing_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_queue_receipt(
        routing_receipt_path=routing_path,
        schema_path=SCHEMA_PATH,
        queued_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.routing_receipt_ready is True
    assert receipt.provider_observation_receipt_ref == (
        ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json"
    )
    assert receipt.provider_observation_receipt_valid is True
    assert receipt.approval_queue_id == "team_ops.external_send_approval"
    assert receipt.approval_request_ref == ""
    assert receipt.approval_state == "missing"
    assert receipt.approval_queue_obligation_bound is False
    assert receipt.blocked_until == ("approval_queue_evidence_missing",)


def test_team_ops_shared_inbox_approval_queue_accepts_pending_obligation(
    tmp_path: Path,
) -> None:
    routing_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    routing_path.write_text(json.dumps(_ready_routing_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_approval_queue_receipt(
        routing_receipt_path=routing_path,
        schema_path=SCHEMA_PATH,
        queued_at="2026-06-14T00:00:00+00:00",
        approval_request_ref="approval-request:teamops-123",
        required_approver_role="team_ops_manager",
        evidence_refs=("approval_queue_obligation:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.provider_observation_receipt_id == (
        "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa"
    )
    assert receipt.provider_observation_receipt_valid is True
    assert receipt.approval_queue_id == "team_ops.external_send_approval"
    assert receipt.required_approver_role == "team_ops_manager"
    assert receipt.approval_state == "pending"
    assert receipt.approval_decision_ref == ""
    assert receipt.approval_queue_obligation_bound is True
    assert receipt.external_send_allowed is False
    assert receipt.approval_decision_performed_by_producer is False
    assert receipt.draft_created_by_producer is False
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_approval_queue_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    routing_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    routing_path.write_text(json.dumps(_ready_routing_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_approval_queue_receipt(
            routing_receipt_path=routing_path,
            schema_path=SCHEMA_PATH,
            queued_at="2026-06-14T00:00:00+00:00",
            approval_request_ref="client_secret=must-not-serialize",
            evidence_refs=("approval_queue_obligation:aaaaaaaaaaaaaaaa",),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_approval_queue_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    routing_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_approval_queue_receipt.json"
    routing_path.write_text(json.dumps(_ready_routing_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_approval_queue_receipt(
        routing_receipt_path=routing_path,
        schema_path=SCHEMA_PATH,
        queued_at="2026-06-14T00:00:00+00:00",
        approval_request_ref="approval-request:teamops-123",
        evidence_refs=("approval_queue_obligation:aaaaaaaaaaaaaaaa",),
    )

    written = write_team_ops_shared_inbox_approval_queue_receipt(receipt, output_path)
    exit_code = main(
        [
            "--routing-receipt",
            str(routing_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--queued-at",
            "2026-06-14T00:00:00+00:00",
            "--approval-request-ref",
            "approval-request:teamops-123",
            "--required-approver-role",
            "team_ops_owner",
            "--evidence-ref",
            "approval_queue_obligation:aaaaaaaaaaaaaaaa",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["provider_observation_receipt_valid"] is True
    assert payload["approval_state"] == "pending"
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_routing_receipt() -> dict[str, object]:
    return _base_routing_receipt() | {
        "live_probe_receipt_valid": True,
        "live_probe_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "observation_digest": "",
        "message_digest": "",
        "thread_digest": "",
        "subject_hash": "",
        "sender_hash": "",
        "recipient_hashes": [],
        "classification": "unknown",
        "priority": "normal",
        "owner_queue": "triage",
        "assigned_owner_ref": "",
        "evidence_refs": [],
        "blocked_until": ["live_probe_receipt_not_ready"],
        "recovery_actions": ["close TeamOps read-only live-probe evidence before routing observations"],
    }


def _ready_routing_receipt() -> dict[str, object]:
    return _base_routing_receipt() | {
        "live_probe_receipt_valid": True,
        "live_probe_receipt_ready": True,
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "observation_digest": "a" * 64,
        "message_digest": "b" * 64,
        "thread_digest": "c" * 64,
        "subject_hash": "d" * 64,
        "sender_hash": "e" * 64,
        "recipient_hashes": ["f" * 64],
        "classification": "support_request",
        "priority": "high",
        "owner_queue": "support",
        "assigned_owner_ref": "principal:team-support-owner",
        "evidence_refs": ["team_ops_routing_observation:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_routing_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-observation-routing-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_live_probe_receipt_ref": ".change_assurance/team_ops_shared_inbox_live_probe_receipt.json",
        "source_live_probe_receipt_id": "teamops-shared-inbox-live-probe-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "routed_at": "2026-06-14T00:00:00+00:00",
        "assignment_required": True,
        "draft_response_required": True,
        "approval_required_before_external_send": True,
        "external_send_allowed": False,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_observation_routing_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
