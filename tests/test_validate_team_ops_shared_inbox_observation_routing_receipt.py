"""Tests for TeamOps shared inbox observation routing receipt validation.

Purpose: prove TeamOps shared inbox routing receipts are schema-backed,
redacted, no-send, and strictly gated before workflow promotion.
Governance scope: TeamOps routing evidence, no-effect enforcement, readiness
validation, assignment gating, and validation receipt emission.
Dependencies: scripts.validate_team_ops_shared_inbox_observation_routing_receipt.
Invariants:
  - Blocked routing receipts remain valid non-ready evidence.
  - Ready routing receipts require provider-observation identity, redacted hashes,
    owner assignment, and approval.
  - Effect drift, raw content leakage, and secret markers fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_observation_routing_receipt import (
    main,
    validate_team_ops_shared_inbox_observation_routing_receipt,
    write_team_ops_shared_inbox_observation_routing_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_observation_routing_receipt.schema.json"


def test_team_ops_shared_inbox_observation_routing_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.live_probe_receipt_ready is False
    assert validation.provider_observation_receipt_valid is False
    assert validation.blocked_until == ("live_probe_receipt_not_ready",)


def test_team_ops_shared_inbox_observation_routing_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps observation routing receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.proof_state == "Pass"
    assert validation.provider_observation_receipt_valid is True
    assert validation.classification == "support_request"
    assert validation.owner_queue == "support"
    assert validation.blocked_until == ()


def test_team_ops_shared_inbox_observation_routing_validation_rejects_effect_drift(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _ready_receipt() | {
        "external_message_sent": True,
        "draft_created_by_producer": True,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "external_message_sent must be false" in validation.errors
    assert "draft_created_by_producer must be false" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_rejects_raw_fields(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _ready_receipt() | {
        "subject": "raw subject",
        "sender_email": "operator@example.invalid",
        "message_body": "raw body",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "$: unexpected property 'subject'" in validation.errors
    assert "receipt must not serialize raw field: subject" in validation.errors
    assert "receipt must not serialize raw field: sender_email" in validation.errors
    assert "receipt must not serialize raw field: message_body" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_rejects_unknown_classification(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _ready_receipt() | {"classification": "unknown", "owner_queue": "triage"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires non-unknown classification" in validation.errors
    assert "passed receipt requires non-triage owner_queue" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_rejects_missing_owner(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _ready_receipt() | {"assigned_owner_ref": ""}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires assigned_owner_ref when assignment_required" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_rejects_missing_provider_observation(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _ready_receipt() | {
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires provider_observation_receipt_ref" in validation.errors
    assert "passed receipt requires provider_observation_receipt_id" in validation.errors
    assert "passed receipt requires provider_observation_receipt_valid=true" in validation.errors


def test_team_ops_shared_inbox_observation_routing_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    payload = _blocked_receipt() | {"recovery_actions": ["bind client_secret=must-not-serialize"]}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_observation_routing_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt_validation.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_observation_routing_receipt_validation(validation, output_path)
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


def test_team_ops_shared_inbox_observation_routing_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "secret-observation-routing-receipt-path.json"

    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_path == "secret-observation-routing-receipt-path.json"
    assert validation.errors == ("TeamOps observation routing receipt file missing",)
    assert str(tmp_path) not in json.dumps(validation.as_dict(), sort_keys=True)


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
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


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
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


def _base_receipt() -> dict[str, object]:
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
