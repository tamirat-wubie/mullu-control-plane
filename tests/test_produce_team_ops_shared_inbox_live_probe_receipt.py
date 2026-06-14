"""Tests for TeamOps shared inbox live-probe receipt production.

Purpose: prove TeamOps shared inbox live-probe receipts bind operator-input
readiness to redacted observation evidence without connector execution.
Governance scope: TeamOps read-only observation receipts, no-effect producer
claims, redaction, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_live_probe_receipt.
Invariants:
  - Blocked operator input produces blocked evidence without provider calls.
  - Admitted operator input still needs redacted observation evidence.
  - Ready receipts require digest, evidence refs, and bounded message counts.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.bind_team_ops_shared_inbox_live_probe_approval import (
    bind_team_ops_shared_inbox_live_probe_approval,
    write_team_ops_shared_inbox_live_probe_approval_binding,
)
from scripts.emit_team_ops_shared_inbox_live_probe_operator_input_request import (
    emit_team_ops_live_probe_operator_input_request,
)
from scripts.produce_team_ops_shared_inbox_live_probe_authority import (
    produce_team_ops_shared_inbox_live_probe_authority,
    write_team_ops_shared_inbox_live_probe_authority,
)
from scripts.produce_team_ops_shared_inbox_live_probe_receipt import (
    main,
    produce_team_ops_shared_inbox_live_probe_receipt,
    write_team_ops_shared_inbox_live_probe_receipt,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_live_probe_receipt.schema.json"


def test_team_ops_shared_inbox_live_probe_receipt_blocks_without_operator_input_ready(
    tmp_path: Path,
) -> None:
    operator_input_path = _write_blocked_operator_input(tmp_path)

    receipt = produce_team_ops_shared_inbox_live_probe_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.operator_input_request_valid is True
    assert receipt.operator_input_probe_allowed is False
    assert receipt.external_provider_call_performed_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("operator_input_request_not_ready",)


def test_team_ops_shared_inbox_live_probe_receipt_requires_observation_evidence(
    tmp_path: Path,
) -> None:
    operator_input_path = _write_ready_operator_input(tmp_path)

    receipt = produce_team_ops_shared_inbox_live_probe_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.operator_input_probe_allowed is True
    assert receipt.live_probe_observation_bound is False
    assert receipt.response_digest == ""
    assert receipt.evidence_refs == ()
    assert receipt.blocked_until == ("redacted_live_probe_observation_missing",)


def test_team_ops_shared_inbox_live_probe_receipt_accepts_read_only_observation(
    tmp_path: Path,
) -> None:
    operator_input_path = _write_ready_operator_input(tmp_path)

    receipt = produce_team_ops_shared_inbox_live_probe_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
        response_digest="a" * 64,
        observed_message_count=2,
        evidence_refs=("team_ops_live_probe_observation:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.connector_id == "gmail"
    assert receipt.provider_operation == "email.search"
    assert receipt.max_message_count == 12
    assert receipt.observed_message_count == 2
    assert receipt.response_digest == "a" * 64
    assert receipt.evidence_refs == ("team_ops_live_probe_observation:aaaaaaaaaaaaaaaa",)
    assert receipt.blocked_until == ()
    assert receipt.live_probe_observation_bound is True


def test_team_ops_shared_inbox_live_probe_receipt_blocks_count_over_authority(
    tmp_path: Path,
) -> None:
    operator_input_path = _write_ready_operator_input(tmp_path)

    receipt = produce_team_ops_shared_inbox_live_probe_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
        response_digest="a" * 64,
        observed_message_count=13,
        evidence_refs=("team_ops_live_probe_observation:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.blocked_until == ("observed_message_count_exceeds_authority",)
    assert receipt.live_probe_observation_bound is False


def test_team_ops_shared_inbox_live_probe_receipt_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    operator_input_path = _write_ready_operator_input(tmp_path)

    try:
        produce_team_ops_shared_inbox_live_probe_receipt(
            operator_input_path=operator_input_path,
            schema_path=SCHEMA_PATH,
            checked_at="2026-06-14T00:00:00+00:00",
            response_digest="a" * 64,
            evidence_refs=("client_secret=must-not-serialize",),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_live_probe_receipt_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    operator_input_path = _write_ready_operator_input(tmp_path)
    output_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    receipt = produce_team_ops_shared_inbox_live_probe_receipt(
        operator_input_path=operator_input_path,
        schema_path=SCHEMA_PATH,
        checked_at="2026-06-14T00:00:00+00:00",
    )

    written = write_team_ops_shared_inbox_live_probe_receipt(receipt, output_path)
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
            "--response-digest",
            "a" * 64,
            "--observed-message-count",
            "2",
            "--evidence-ref",
            "team_ops_live_probe_observation:aaaaaaaaaaaaaaaa",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["response_digest"] == "a" * 64
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _write_blocked_operator_input(tmp_path: Path) -> Path:
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    operator_input_path = tmp_path / "team_ops_shared_inbox_live_probe_operator_input_request.json"
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(handoff_path=tmp_path / "missing_handoff.json"),
        authority_path,
    )
    request = emit_team_ops_live_probe_operator_input_request(authority_path=authority_path)
    operator_input_path.write_text(json.dumps(request.as_dict()), encoding="utf-8")
    return operator_input_path


def _write_ready_operator_input(tmp_path: Path) -> Path:
    handoff_path = _write_ready_handoff(tmp_path)
    approval_binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    operator_input_path = tmp_path / "team_ops_shared_inbox_live_probe_operator_input_request.json"
    write_team_ops_shared_inbox_live_probe_approval_binding(
        bind_team_ops_shared_inbox_live_probe_approval(
            handoff_path=handoff_path,
            probe_approval_ref="approval:teamops-read-probe-20260614",
        ),
        approval_binding_path,
    )
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            approval_binding_path=approval_binding_path,
            query="newer_than:2d",
            max_message_count=12,
        ),
        authority_path,
    )
    request = emit_team_ops_live_probe_operator_input_request(authority_path=authority_path)
    operator_input_path.write_text(json.dumps(request.as_dict()), encoding="utf-8")
    return operator_input_path


def _write_ready_handoff(tmp_path: Path) -> Path:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    secret_names = (
        set(gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES)
        | set(gmail_preflight.WITNESS_REF_SIGNAL_NAMES)
        | set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES)
    )
    handoff = produce_team_ops_shared_inbox_operator_handoff(
        _configured_env(),
        github_secret_names=secret_names,
        operator_approval_ref="approval:teamops-shared-inbox-live-probe-20260614",
    )
    write_team_ops_shared_inbox_operator_handoff(handoff, handoff_path)
    return handoff_path


def _configured_env() -> dict[str, str]:
    return {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_and_send_with_approval",
        "GMAIL_SCOPE_ID": "gmail.readonly gmail.send",
        "MULLU_TEAM_OPS_ASSISTANT_PROFILE": "team_ops.default",
        "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER": "gmail",
        "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE": "shared_inbox_triage",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY": "approval_required",
    }
