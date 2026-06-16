"""Tests for TeamOps shared inbox provider observation receipt production.

Purpose: prove provider observation receipts bind read-only provider evidence
without connector execution or raw payload serialization.
Governance scope: TeamOps provider observation receipts, redaction, read-only
effect bounds, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_provider_observation_receipt.
Invariants:
  - Blocked operator input produces blocked evidence without provider calls.
  - Ready operator input still needs redacted provider observation evidence.
  - Passed receipts require provider ref, response digests, and bounded counts.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_provider_observation_receipt import (
    main,
    produce_team_ops_shared_inbox_provider_observation_receipt,
    write_team_ops_shared_inbox_provider_observation_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_provider_observation_receipt.schema.json"


def test_provider_observation_receipt_blocks_without_operator_input_ready(tmp_path: Path) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=False)

    receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.operator_input_request_valid is True
    assert receipt.operator_input_probe_allowed is False
    assert receipt.provider_call_performed_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("operator_input_request_not_ready",)


def test_provider_observation_receipt_requires_redacted_evidence(tmp_path: Path) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=True)

    receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.provider_call_observed_by_operator is False
    assert receipt.read_only_observation_bound is False
    assert set(receipt.blocked_until) == {
        "provider_receipt_ref_missing",
        "provider_response_digest_missing_or_invalid",
        "redacted_response_digest_missing_or_invalid",
    }


def test_provider_observation_receipt_accepts_read_only_observation(tmp_path: Path) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=True)

    receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
        provider_receipt_ref="provider://gmail/read-only-observation/20260614",
        provider_response_digest="a" * 64,
        redacted_response_digest="b" * 64,
        observed_message_count=2,
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.connector_id == "gmail"
    assert receipt.provider_operation == "email.search"
    assert receipt.max_message_count == 12
    assert receipt.observed_message_count == 2
    assert receipt.provider_response_digest == "a" * 64
    assert receipt.redacted_response_digest == "b" * 64
    assert receipt.provider_call_observed_by_operator is True
    assert receipt.read_only_observation_bound is True
    assert receipt.blocked_until == ()


def test_provider_observation_receipt_blocks_count_over_authority(tmp_path: Path) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=True)

    receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
        provider_receipt_ref="provider://gmail/read-only-observation/20260614",
        provider_response_digest="a" * 64,
        redacted_response_digest="b" * 64,
        observed_message_count=13,
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.blocked_until == ("observed_message_count_exceeds_authority",)
    assert receipt.read_only_observation_bound is False


def test_provider_observation_receipt_rejects_secret_marker_ref(tmp_path: Path) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=True)

    try:
        produce_team_ops_shared_inbox_provider_observation_receipt(
            operator_input_path=operator_input_path,
            schema_path=SCHEMA_PATH,
            checked_at="2026-06-14T00:00:00+00:00",
            provider_receipt_ref="client_secret=must-not-serialize",
            provider_response_digest="a" * 64,
            redacted_response_digest="b" * 64,
            observed_message_count=2,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_provider_observation_receipt_cli_writes_report(tmp_path: Path, capsys) -> None:
    operator_input_path = _write_operator_input(tmp_path, probe_allowed=True)
    output_path = tmp_path / "team_ops_shared_inbox_provider_observation_receipt.json"
    receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    written = write_team_ops_shared_inbox_provider_observation_receipt(receipt, output_path)
    exit_code = main(
        [
            "--operator-input",
            str(operator_input_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--checked-at",
            "2026-06-14T00:00:00+00:00",
            "--provider-receipt-ref",
            "provider://gmail/read-only-observation/20260614",
            "--provider-response-digest",
            "a" * 64,
            "--redacted-response-digest",
            "b" * 64,
            "--observed-message-count",
            "2",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["redacted_response_digest"] == "b" * 64
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _write_operator_input(tmp_path: Path, *, probe_allowed: bool) -> Path:
    path = tmp_path / "team_ops_shared_inbox_live_probe_operator_input_request.json"
    payload = _operator_input(probe_allowed=probe_allowed)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _operator_input(*, probe_allowed: bool) -> dict[str, object]:
    ready_payload = {
        "request_id": "teamops-shared-inbox-live-probe-input-request-aaaaaaaaaaaaaaaa",
        "authority_id": "teamops-shared-inbox-live-probe-authority-aaaaaaaaaaaaaaaa",
        "ready": probe_allowed,
        "probe_allowed": probe_allowed,
        "authority_validation_ok": True,
        "solver_outcome": "SolvedVerified" if probe_allowed else "AwaitingEvidence",
        "proof_state": "Pass" if probe_allowed else "Unknown",
        "required_inputs": [] if probe_allowed else [_required_input()],
        "blocked_actions": []
        if probe_allowed
        else [
            "team_ops_shared_inbox_live_probe",
            "external_provider_call",
            "shared_inbox_message_read",
            "external_message_send",
            "team_ops_production_readiness_claim",
        ],
        "source_artifacts": {
            "team_ops_shared_inbox_live_probe_authority": (
                ".change_assurance/team_ops_shared_inbox_live_probe_authority.json"
            )
        },
        "allowed_probe_summary": {
            "probe_id": "team_ops.shared_inbox.read_only_probe",
            "capabilities_used": ["email.read", "messaging.thread.read"],
            "query": "newer_than:2d",
            "max_message_count": 12,
            "read_only": True,
            "draft_allowed": False,
            "external_send_allowed": False,
        },
        "no_secret_values_serialized": True,
        "live_probe_executed": False,
        "external_provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "next_action": "run the TeamOps shared inbox read-only live probe and validate its receipt",
    }
    return ready_payload


def _required_input() -> dict[str, object]:
    return {
        "input_id": "teamops-live-probe-input-aaaaaaaaaaaa",
        "blocker": "probe_approval_ref",
        "input_kind": "probe_approval_ref",
        "required_names": ["MULLU_TEAM_OPS_LIVE_PROBE_APPROVAL_REF"],
        "current_state": "missing",
        "evidence_source": "team_ops_shared_inbox_live_probe_authority",
        "next_action": "bind MULLU_TEAM_OPS_LIVE_PROBE_APPROVAL_REF outside this report",
    }
