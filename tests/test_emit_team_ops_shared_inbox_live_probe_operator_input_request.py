"""Tests for TeamOps live-probe operator input request emission.

Purpose: prove TeamOps live-probe authority receipts become public-safe
operator input requests before any read-only connector probe is run.
Governance scope: TeamOps live-probe readiness, missing-input derivation,
authority validation, external-effect blocking, and secret redaction.
Dependencies: scripts.emit_team_ops_shared_inbox_live_probe_operator_input_request.
Invariants:
  - Blocked authority produces explicit missing inputs and blocked actions.
  - Admitted authority clears inputs but still performs no connector call.
  - Invalid authority is GovernanceBlocked before operator execution.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.emit_team_ops_shared_inbox_live_probe_operator_input_request import (
    emit_team_ops_live_probe_operator_input_request,
    main,
    write_team_ops_live_probe_operator_input_request,
)
from scripts.bind_team_ops_shared_inbox_live_probe_approval import (
    bind_team_ops_shared_inbox_live_probe_approval,
    write_team_ops_shared_inbox_live_probe_approval_binding,
)
from scripts.produce_team_ops_shared_inbox_live_probe_authority import (
    produce_team_ops_shared_inbox_live_probe_authority,
    write_team_ops_shared_inbox_live_probe_authority,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_live_probe_operator_input_request.schema.json"


def test_team_ops_live_probe_operator_input_request_reports_blocked_authority(tmp_path: Path) -> None:
    authority_path = _write_blocked_authority(tmp_path)

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.request_id.startswith("teamops-shared-inbox-live-probe-input-request-")
    assert request.ready is False
    assert request.probe_allowed is False
    assert request.authority_validation_ok is True
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert {"source_handoff_receipt", "probe_approval_ref"} <= input_kinds
    assert "team_ops_shared_inbox_live_probe" in request.blocked_actions
    assert "external_message_send" in request.blocked_actions
    assert request.no_secret_values_serialized is True
    assert request.live_probe_executed is False
    assert request.external_provider_call_performed is False


def test_team_ops_live_probe_operator_input_request_allows_admitted_authority(tmp_path: Path) -> None:
    authority_path = _write_admitted_authority(tmp_path)

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready is True
    assert request.probe_allowed is True
    assert request.authority_validation_ok is True
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert request.blocked_actions == ()
    assert request.allowed_probe_summary["query"] == "newer_than:2d"
    assert request.allowed_probe_summary["max_message_count"] == 12
    assert request.live_probe_executed is False
    assert request.external_message_sent is False


def test_team_ops_live_probe_operator_input_request_blocks_invalid_authority(tmp_path: Path) -> None:
    authority_path = _write_admitted_authority(tmp_path)
    packet = json.loads(authority_path.read_text(encoding="utf-8"))
    packet["external_message_sent"] = True
    authority_path.write_text(json.dumps(packet), encoding="utf-8")

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready is False
    assert request.probe_allowed is False
    assert request.authority_validation_ok is False
    assert request.solver_outcome == "GovernanceBlocked"
    assert request.proof_state == "Fail"
    assert request.required_inputs[0].input_kind == "valid_authority_receipt"
    assert "external_provider_call" in request.blocked_actions


def test_team_ops_live_probe_operator_input_request_reports_missing_approval_binding(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    missing_binding_path = tmp_path / "missing_approval_binding.json"
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            approval_binding_path=missing_binding_path,
        ),
        authority_path,
    )

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.probe_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert "approval_binding_receipt" in input_kinds
    assert any(
        item.required_names == ("team_ops_shared_inbox_live_probe_approval_binding",)
        for item in request.required_inputs
    )
    assert request.next_action == "emit the TeamOps live-probe approval binding receipt, then rerun authority"


def test_team_ops_live_probe_operator_input_request_reports_invalid_approval_binding(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    approval_binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    approval_binding_path.write_text("[]", encoding="utf-8")
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            approval_binding_path=approval_binding_path,
        ),
        authority_path,
    )

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.probe_allowed is False
    assert request.authority_validation_ok is True
    assert "valid_approval_binding_receipt" in input_kinds
    assert any(item.current_state == "present_invalid" for item in request.required_inputs)
    assert request.next_action == "fix the TeamOps approval binding receipt validation errors, then rerun authority"


def test_team_ops_live_probe_operator_input_request_reports_not_ready_approval_binding(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)
    approval_binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    write_team_ops_shared_inbox_live_probe_approval_binding(
        bind_team_ops_shared_inbox_live_probe_approval(handoff_path=handoff_path),
        approval_binding_path,
    )
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            approval_binding_path=approval_binding_path,
        ),
        authority_path,
    )

    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.probe_allowed is False
    assert "approval_binding_readiness_evidence" in input_kinds
    assert "probe_approval_ref" in input_kinds
    assert any(
        item.next_action == "close TeamOps approval binding evidence, then rerun live-probe authority"
        for item in request.required_inputs
    )


def test_team_ops_live_probe_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    authority_path = _write_blocked_authority(tmp_path)
    output_path = tmp_path / "team_ops_live_probe_operator_input_request.json"
    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_team_ops_live_probe_operator_input_request(request, output_path)
    exit_code = main(
        [
            "--authority",
            str(authority_path),
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
    assert payload["probe_allowed"] is False
    assert payload["required_inputs"]
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def _write_blocked_authority(tmp_path: Path) -> Path:
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(handoff_path=tmp_path / "missing_handoff.json"),
        authority_path,
    )
    return authority_path


def _write_admitted_authority(tmp_path: Path) -> Path:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    _write_ready_handoff(tmp_path)
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            probe_approval_ref="approval:teamops-read-probe-20260613",
            query="newer_than:2d",
            max_message_count=12,
        ),
        authority_path,
    )
    return authority_path


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
        operator_approval_ref="approval:teamops-shared-inbox-live-probe-20260613",
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
