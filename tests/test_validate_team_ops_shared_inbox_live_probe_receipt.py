"""Tests for TeamOps shared inbox live-probe receipt validation.

Purpose: prove TeamOps shared inbox live-probe receipts are schema-backed,
redacted, read-only, and strictly gated before workflow promotion.
Governance scope: TeamOps observation evidence, no-effect enforcement, readiness
validation, and validation receipt emission.
Dependencies: scripts.validate_team_ops_shared_inbox_live_probe_receipt.
Invariants:
  - Blocked receipts remain valid non-ready evidence.
  - Ready receipts require redacted evidence and read-only operation.
  - Effect drift, raw query leakage, and count overflow fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_live_probe_receipt import (
    main,
    validate_team_ops_shared_inbox_live_probe_receipt,
    write_team_ops_shared_inbox_live_probe_receipt_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_live_probe_receipt.schema.json"


def test_team_ops_shared_inbox_live_probe_receipt_validation_accepts_blocked_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.operator_input_probe_allowed is False
    assert validation.blocked_until == ("operator_input_request_not_ready",)


def test_team_ops_shared_inbox_live_probe_receipt_validation_require_ready_rejects_blocked(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps shared inbox live-probe receipt ready must be true" in validation.errors


def test_team_ops_shared_inbox_live_probe_receipt_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.proof_state == "Pass"
    assert validation.operator_input_probe_allowed is True
    assert validation.blocked_until == ()


def test_team_ops_shared_inbox_live_probe_receipt_validation_rejects_effect_drift(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    payload = _ready_receipt() | {
        "external_message_sent": True,
        "provider_mutation_performed": True,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "external_message_sent must be false" in validation.errors
    assert "provider_mutation_performed must be false" in validation.errors


def test_team_ops_shared_inbox_live_probe_receipt_validation_rejects_count_over_authority(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    payload = _ready_receipt() | {"observed_message_count": 13, "max_message_count": 12}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "observed_message_count must not exceed max_message_count" in validation.errors


def test_team_ops_shared_inbox_live_probe_receipt_validation_rejects_raw_query_field(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    payload = _ready_receipt() | {"query": "newer_than:2d"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "$: unexpected property 'query'" in validation.errors
    assert "receipt must not serialize raw query" in validation.errors


def test_team_ops_shared_inbox_live_probe_receipt_validation_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    payload = _blocked_receipt() | {"recovery_actions": ["bind client_secret=must-not-serialize"]}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_live_probe_receipt_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt_validation.json"
    receipt_path.write_text(json.dumps(_blocked_receipt()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_shared_inbox_live_probe_receipt_validation(validation, output_path)
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


def test_team_ops_shared_inbox_live_probe_receipt_validation_missing_path_is_bounded(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "secret-live-probe-receipt-path.json"

    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_path == "secret-live-probe-receipt-path.json"
    assert validation.errors == ("TeamOps shared inbox live-probe receipt file missing",)
    assert str(tmp_path) not in json.dumps(validation.as_dict(), sort_keys=True)


def _blocked_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "operator_input_request_valid": True,
        "operator_input_probe_allowed": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "connector_id": "",
        "provider_operation": "",
        "observed_message_count": 0,
        "response_digest": "",
        "evidence_refs": [],
        "live_probe_observation_bound": False,
        "blocked_until": ["operator_input_request_not_ready"],
        "recovery_actions": ["close TeamOps live-probe operator inputs before binding observation evidence"],
    }


def _ready_receipt() -> dict[str, object]:
    return _base_receipt() | {
        "operator_input_request_valid": True,
        "operator_input_probe_allowed": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "connector_id": "gmail",
        "provider_operation": "email.search",
        "observed_message_count": 2,
        "response_digest": "a" * 64,
        "evidence_refs": ["team_ops_live_probe_observation:aaaaaaaaaaaaaaaa"],
        "live_probe_observation_bound": True,
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-live-probe-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_operator_input_request_ref": ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request.json",
        "source_authority_id": "teamops-live-probe-authority-aaaaaaaaaaaaaaaa",
        "checked_at": "2026-06-14T00:00:00+00:00",
        "query_hash": "b" * 64,
        "max_message_count": 12,
        "no_secret_values_serialized": True,
        "external_provider_call_performed_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "forbidden_effects_observed": False,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_live_probe_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
