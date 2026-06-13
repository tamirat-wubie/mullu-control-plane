"""Tests for TeamOps shared inbox live-probe authority production.

Purpose: prove TeamOps probe authority blocks by default and admits only a
future read-only probe when handoff readiness and probe approval are present.
Governance scope: TeamOps shared inbox authority, external-effect separation,
approval reference redaction, and no live probe execution.
Dependencies: scripts.produce_team_ops_shared_inbox_live_probe_authority.
Invariants:
  - Missing or blocked handoff evidence remains AwaitingEvidence.
  - Ready handoff evidence still requires a separate probe approval reference.
  - Admitted authority does not execute Gmail or send external messages.
  - Secret-shaped approval references are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.produce_team_ops_shared_inbox_live_probe_authority import (
    main,
    produce_team_ops_shared_inbox_live_probe_authority,
    write_team_ops_shared_inbox_live_probe_authority,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)


def test_missing_handoff_blocks_without_external_effects(tmp_path: Path) -> None:
    authority = produce_team_ops_shared_inbox_live_probe_authority(
        handoff_path=tmp_path / "missing_handoff.json",
    )
    serialized = json.dumps(authority, sort_keys=True)

    assert authority["status"] == "awaiting_handoff_readiness"
    assert authority["solver_outcome"] == "AwaitingEvidence"
    assert authority["handoff_validation_ok"] is False
    assert authority["handoff_ready_for_live_probe"] is False
    assert authority["probe_authorized"] is False
    assert authority["read_only_probe_allowed"] is False
    assert authority["live_probe_executed"] is False
    assert authority["external_provider_call_performed"] is False
    assert authority["external_mailbox_write_performed"] is False
    assert authority["external_message_sent"] is False
    assert "team_ops_handoff_missing" in authority["blocked_until"]
    assert "client_secret=" not in serialized


def test_ready_handoff_without_probe_approval_blocks_authority(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    authority = produce_team_ops_shared_inbox_live_probe_authority(handoff_path=handoff_path)

    assert authority["status"] == "awaiting_probe_authority"
    assert authority["solver_outcome"] == "AwaitingEvidence"
    assert authority["handoff_validation_ok"] is True
    assert authority["handoff_ready_for_live_probe"] is True
    assert authority["probe_authorized"] is False
    assert authority["read_only_probe_allowed"] is False
    assert authority["handoff_summary"]["blocker_count"] == 0
    assert "probe_approval_ref" in authority["blocked_until"]
    assert authority["allowed_probe"]["read_only"] is True
    assert authority["allowed_probe"]["external_send_allowed"] is False


def test_ready_handoff_with_probe_approval_admits_read_only_probe(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    authority = produce_team_ops_shared_inbox_live_probe_authority(
        handoff_path=handoff_path,
        probe_approval_ref="approval:teamops-read-probe-20260613",
        query="newer_than:2d",
        max_message_count=12,
    )

    assert authority["status"] == "admitted_for_read_only_probe"
    assert authority["solver_outcome"] == "SolvedVerified"
    assert authority["handoff_validation_ok"] is True
    assert authority["handoff_ready_for_live_probe"] is True
    assert authority["probe_authorized"] is True
    assert authority["probe_approval_ref"].startswith("ref:")
    assert authority["read_only_probe_allowed"] is True
    assert authority["blocked_until"] == []
    assert authority["allowed_probe"]["query"] == "newer_than:2d"
    assert authority["allowed_probe"]["max_message_count"] == 12
    assert authority["live_probe_executed"] is False
    assert authority["external_message_sent"] is False


def test_probe_authority_rejects_secret_shaped_approval_ref(tmp_path: Path) -> None:
    handoff_path = _write_ready_handoff(tmp_path)

    with pytest.raises(ValueError):
        produce_team_ops_shared_inbox_live_probe_authority(
            handoff_path=handoff_path,
            probe_approval_ref="client_secret=must-not-serialize",
        )


def test_probe_authority_writer_and_cli_emit_blocked_receipt(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    output_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    write_team_ops_shared_inbox_operator_handoff(
        produce_team_ops_shared_inbox_operator_handoff({}),
        handoff_path,
    )
    authority = produce_team_ops_shared_inbox_live_probe_authority(handoff_path=handoff_path)

    written_path = write_team_ops_shared_inbox_live_probe_authority(authority, output_path)
    exit_code = main(["--handoff", str(handoff_path), "--output", str(output_path), "--json"])
    require_admitted_exit_code = main(
        ["--handoff", str(handoff_path), "--output", str(output_path), "--require-admitted"]
    )
    captured = capsys.readouterr()
    disk_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written_path == output_path
    assert exit_code == 0
    assert require_admitted_exit_code == 2
    assert disk_payload["status"] == "awaiting_handoff_readiness"
    assert stdout_payload["authority_id"] == disk_payload["authority_id"]
    assert disk_payload["read_only_probe_allowed"] is False
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
        operator_approval_ref="approval:teamops-shared-inbox-live-probe-20260613",
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
