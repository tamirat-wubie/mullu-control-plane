"""Tests for TeamOps shared inbox live-probe approval binding production.

Purpose: prove TeamOps probe approval references become redacted binding
receipts before read-only probe authority consumes them.
Governance scope: TeamOps shared inbox handoff readiness, approval reference
redaction, authority binding, and no live probe execution.
Dependencies: scripts.bind_team_ops_shared_inbox_live_probe_approval.
Invariants:
  - Missing or blocked handoff evidence remains AwaitingEvidence.
  - Ready handoff evidence still requires a separate probe approval reference.
  - Ready approval binding performs no Gmail or external message action.
  - Secret-shaped approval references are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.bind_team_ops_shared_inbox_live_probe_approval import (
    bind_team_ops_shared_inbox_live_probe_approval,
    main,
    write_team_ops_shared_inbox_live_probe_approval_binding,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)


def test_missing_handoff_binding_blocks_without_external_effects(tmp_path: Path) -> None:
    binding = bind_team_ops_shared_inbox_live_probe_approval(
        handoff_path=tmp_path / "missing_handoff.json",
    )
    serialized = json.dumps(binding, sort_keys=True)

    assert binding["status"] == "awaiting_handoff_readiness"
    assert binding["solver_outcome"] == "AwaitingEvidence"
    assert binding["handoff_validation_ok"] is False
    assert binding["handoff_ready_for_live_probe"] is False
    assert binding["probe_approval_ref_present"] is False
    assert binding["ready_for_authority_receipt"] is False
    assert binding["live_probe_executed"] is False
    assert binding["external_provider_call_performed"] is False
    assert binding["external_mailbox_write_performed"] is False
    assert binding["external_message_sent"] is False
    assert "team_ops_handoff_missing" in binding["blocked_until"]
    assert "probe_approval_ref" in binding["blocked_until"]
    assert "client_secret=" not in serialized


def test_ready_handoff_without_probe_approval_blocks_binding(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    binding = bind_team_ops_shared_inbox_live_probe_approval(handoff_path=handoff_path)

    assert binding["status"] == "awaiting_probe_approval"
    assert binding["solver_outcome"] == "AwaitingEvidence"
    assert binding["handoff_validation_ok"] is True
    assert binding["handoff_ready_for_live_probe"] is True
    assert binding["probe_approval_ref_present"] is False
    assert binding["ready_for_authority_receipt"] is False
    assert binding["handoff_summary"]["blocker_count"] == 0
    assert binding["probe_approval_ref"] == ""
    assert "probe_approval_ref" in binding["blocked_until"]
    assert binding["allowed_probe_summary"]["read_only"] is True
    assert binding["allowed_probe_summary"]["external_send_allowed"] is False


def test_ready_handoff_with_probe_approval_binds_authority_input(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    binding = bind_team_ops_shared_inbox_live_probe_approval(
        handoff_path=handoff_path,
        probe_approval_ref="approval:teamops-read-probe-20260614",
        query="newer_than:2d",
        max_message_count=12,
    )

    assert binding["status"] == "ready_for_authority_receipt"
    assert binding["solver_outcome"] == "SolvedVerified"
    assert binding["handoff_validation_ok"] is True
    assert binding["handoff_ready_for_live_probe"] is True
    assert binding["probe_approval_ref_present"] is True
    assert binding["probe_approval_ref"].startswith("ref:")
    assert binding["ready_for_authority_receipt"] is True
    assert binding["blocked_until"] == []
    assert binding["allowed_probe_summary"]["query"] == "newer_than:2d"
    assert binding["allowed_probe_summary"]["max_message_count"] == 12
    assert binding["approval_ref_value_serialized"] is False
    assert binding["external_message_sent"] is False


def test_approval_binding_rejects_secret_shaped_approval_ref(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    with pytest.raises(ValueError):
        bind_team_ops_shared_inbox_live_probe_approval(
            handoff_path=handoff_path,
            probe_approval_ref="refresh_token=must-not-serialize",
        )


def test_approval_binding_writer_and_cli_emit_blocked_receipt(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    output_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    write_team_ops_shared_inbox_operator_handoff(
        produce_team_ops_shared_inbox_operator_handoff({}),
        handoff_path,
    )
    binding = bind_team_ops_shared_inbox_live_probe_approval(handoff_path=handoff_path)

    written_path = write_team_ops_shared_inbox_live_probe_approval_binding(binding, output_path)
    exit_code = main(["--handoff", str(handoff_path), "--output", str(output_path), "--json"])
    require_ready_exit_code = main(
        ["--handoff", str(handoff_path), "--output", str(output_path), "--require-ready"]
    )
    captured = capsys.readouterr()
    disk_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written_path == output_path
    assert exit_code == 0
    assert require_ready_exit_code == 2
    assert disk_payload["status"] == "awaiting_handoff_readiness"
    assert stdout_payload["binding_id"] == disk_payload["binding_id"]
    assert disk_payload["ready_for_authority_receipt"] is False
    assert disk_payload["credential_values_disclosed"] is False
    assert disk_payload["external_provider_call_performed"] is False


def _write_ready_handoff(tmp_path: Path) -> Path:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    secret_names = (
        set(gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES)
        | set(gmail_preflight.WITNESS_REF_SIGNAL_NAMES)
        | set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES)
    )
    packet = produce_team_ops_shared_inbox_operator_handoff(
        _configured_env(),
        github_secret_names=secret_names,
        operator_approval_ref="approval:teamops-shared-inbox-live-probe-20260614",
    )
    write_team_ops_shared_inbox_operator_handoff(packet, handoff_path)
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
