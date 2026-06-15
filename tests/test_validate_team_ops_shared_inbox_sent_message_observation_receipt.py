"""Tests for TeamOps sent-message observation receipt validation.

Purpose: prove the TeamOps sent-message observation validator rejects raw
payloads, local effect claims, inconsistent hashes, missing replay evidence,
and missing provider-observation closure evidence.
Governance scope: TeamOps external-send closure evidence, duplicate-action
protection, replay binding, redaction, and no-local-provider-effect checks.
Dependencies: scripts.validate_team_ops_shared_inbox_sent_message_observation_receipt.
Invariants:
  - Ready observation receipts require two matching redacted provider observations.
  - Replay and duplicate-absence evidence are mandatory before closure readiness.
  - Raw message/provider fields and producer effect claims are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_sent_message_observation_receipt import (
    main,
    validate_team_ops_shared_inbox_sent_message_observation_receipt,
    write_team_ops_shared_inbox_sent_message_observation_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_sent_message_observation_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def test_team_ops_sent_message_observation_validator_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.blocked_until == ("send_execution_receipt_not_ready",)
    assert validation.errors == ()


def test_team_ops_sent_message_observation_validator_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.status == "blocked"
    assert "TeamOps sent-message observation receipt ready must be true" in validation.errors
    assert validation.next_action == "record ready TeamOps send-execution evidence before observing sent-message closure"


def test_team_ops_sent_message_observation_validator_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.proof_state == "Pass"
    assert validation.observation_count == 2
    assert validation.duplicate_absence_observed is True
    assert validation.deterministic_replay_observed is True
    assert validation.workflow_closure_ready is True
    assert validation.next_action == "prepare TeamOps shared inbox terminal closure review packet"


def test_team_ops_sent_message_observation_validator_rejects_local_provider_claim(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"provider_call_performed_by_producer": True}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "provider_call_performed_by_producer must be false" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_sent_message_observation_validator_rejects_raw_provider_field(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"provider_message_id": "raw-provider-id"}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize raw field: provider_message_id" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_sent_message_observation_validator_rejects_missing_replay(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"replay_ref": "", "replay_hash": ""}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires replay_ref" in validation.errors
    assert "passed receipt requires replay_hash sha256 hex" in validation.errors
    assert len(validation.errors) >= 2


def test_team_ops_sent_message_observation_validator_rejects_bad_replay_hash(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"replay_hash": "not-a-sha"}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed receipt requires replay_hash sha256 hex" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_sent_message_observation_validator_rejects_hash_mismatch(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"second_observation_hash": HEX_C}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "second_observation_hash must match provider_message_hash" in validation.errors
    assert validation.sent_message_observation_ready is True


def test_team_ops_sent_message_observation_validator_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    receipt = _ready_receipt() | {"first_observation_ref": "client_secret=blocked"}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "receipt must not serialize secret marker: client_secret=" in validation.errors
    assert "client_secret=blocked" not in json.dumps(validation.as_dict(), sort_keys=True)


def test_team_ops_sent_message_observation_validator_cli_writes_validation(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt_validation.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    written = write_team_ops_shared_inbox_sent_message_observation_receipt_validation(validation, output_path)
    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def test_team_ops_sent_message_observation_validator_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "missing_team_ops_shared_inbox_sent_message_observation_receipt.json"

    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_id == ""
    assert validation.errors == ("TeamOps sent-message observation receipt file missing",)
    assert validation.next_action == "regenerate TeamOps sent-message observation receipt"


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "send_execution_receipt_valid": True,
        "send_execution_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "send_execution_ref": "",
        "dispatch_receipt_ref": "",
        "provider_message_ref": "",
        "provider_message_hash": "",
        "sent_message_observation_state": "missing",
        "sent_message_observation_ready": False,
        "first_observation_ref": "",
        "first_observation_hash": "",
        "second_observation_ref": "",
        "second_observation_hash": "",
        "observation_count": 0,
        "provider_state_consistent": False,
        "provider_message_hash_matches_execution": False,
        "duplicate_absence_observed": False,
        "replay_ref": "",
        "replay_hash": "",
        "deterministic_replay_observed": False,
        "workflow_closure_ready": False,
        "evidence_refs": [],
        "blocked_until": ["send_execution_receipt_not_ready"],
        "recovery_actions": ["record ready TeamOps send-execution evidence before observing sent-message closure"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "send_execution_receipt_valid": True,
        "send_execution_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "send_execution_ref": "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_ref": "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider_message_ref": "provider-message:aaaaaaaaaaaaaaaa",
        "provider_message_hash": HEX_A,
        "sent_message_observation_state": "observed",
        "sent_message_observation_ready": True,
        "first_observation_ref": "sent-observation:first",
        "first_observation_hash": HEX_A,
        "second_observation_ref": "sent-observation:second",
        "second_observation_hash": HEX_A,
        "observation_count": 2,
        "provider_state_consistent": True,
        "provider_message_hash_matches_execution": True,
        "duplicate_absence_observed": True,
        "replay_ref": "sent-message-replay:aaaaaaaaaaaaaaaa",
        "replay_hash": HEX_B,
        "deterministic_replay_observed": True,
        "workflow_closure_ready": True,
        "evidence_refs": [
            "sent-observation:first",
            "sent-observation:second",
            "sent-message-replay:aaaaaaaaaaaaaaaa",
            "duplicate-check:aaaaaaaaaaaaaaaa",
        ],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-sent-message-observation-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_send_execution_receipt_ref": ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
        "source_send_execution_receipt_id": "teamops-shared-inbox-send-execution-receipt-aaaaaaaaaaaaaaaa",
        "observed_at": "2026-06-14T00:00:00+00:00",
        "observation_performed_by_producer": False,
        "external_message_sent_by_producer": False,
        "external_mailbox_write_performed_by_producer": False,
        "provider_mutation_performed_by_producer": False,
        "provider_call_performed_by_producer": False,
        "draft_created_by_producer": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "raw_provider_payload_serialized": False,
        "no_secret_values_serialized": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
