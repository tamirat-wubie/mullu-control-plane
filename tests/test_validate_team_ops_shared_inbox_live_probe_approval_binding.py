"""Tests for TeamOps shared inbox live-probe approval binding validation.

Purpose: prove TeamOps approval bindings are schema-backed, redacted, and fail
closed when ready state drifts from handoff or approval evidence.
Governance scope: approval binding validation, external-effect separation,
handoff readiness binding, and validation receipt writing.
Dependencies: scripts.validate_team_ops_shared_inbox_live_probe_approval_binding.
Invariants:
  - Blocked approval bindings remain valid while evidence is missing.
  - Ready bindings require handoff readiness and redacted probe approval.
  - External-effect drift and secret marker drift fail validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.bind_team_ops_shared_inbox_live_probe_approval import (
    bind_team_ops_shared_inbox_live_probe_approval,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)
from scripts.validate_team_ops_shared_inbox_live_probe_approval_binding import (
    main,
    validate_team_ops_shared_inbox_live_probe_approval_binding,
    write_team_ops_shared_inbox_live_probe_approval_binding_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_live_probe_approval_binding.schema.json"


def test_team_ops_live_probe_approval_binding_accepts_blocked_packet(tmp_path: Path) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    binding_path.write_text(
        json.dumps(bind_team_ops_shared_inbox_live_probe_approval(handoff_path=tmp_path / "missing.json")),
        encoding="utf-8",
    )

    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.ok is True
    assert validation.status == "awaiting_handoff_readiness"
    assert validation.ready_for_authority_receipt is False
    assert validation.blocker_count >= 1
    assert validation.errors == ()


def test_team_ops_live_probe_approval_binding_accepts_ready_packet(tmp_path: Path) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    binding_path.write_text(
        json.dumps(
            bind_team_ops_shared_inbox_live_probe_approval(
                handoff_path=_write_ready_handoff(tmp_path),
                probe_approval_ref="approval:teamops-read-probe-20260614",
            )
        ),
        encoding="utf-8",
    )

    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.ok is True
    assert validation.status == "ready_for_authority_receipt"
    assert validation.ready_for_authority_receipt is True
    assert validation.blocker_count == 0
    assert validation.errors == ()


def test_team_ops_live_probe_approval_binding_rejects_ready_state_without_approval(tmp_path: Path) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    packet = bind_team_ops_shared_inbox_live_probe_approval(handoff_path=_write_ready_handoff(tmp_path))
    packet["ready_for_authority_receipt"] = True
    packet["status"] = "ready_for_authority_receipt"
    packet["solver_outcome"] = "SolvedVerified"
    packet["blocked_until"] = []
    binding_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "ready binding requires probe_approval_ref_present" in validation.errors
    assert "ready binding requires redacted probe_approval_ref" in validation.errors
    assert "status must be awaiting_probe_approval" in validation.errors


def test_team_ops_live_probe_approval_binding_rejects_external_effect_drift(tmp_path: Path) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    packet = bind_team_ops_shared_inbox_live_probe_approval(handoff_path=tmp_path / "missing.json")
    packet["external_message_sent"] = True
    packet["external_mailbox_write_performed"] = True
    packet["allowed_probe_summary"]["external_send_allowed"] = True
    binding_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "external_message_sent must be false" in validation.errors
    assert "external_mailbox_write_performed must be false" in validation.errors
    assert "allowed_probe_summary.external_send_allowed must be false" in validation.errors


def test_team_ops_live_probe_approval_binding_rejects_secret_marker(tmp_path: Path) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    packet = bind_team_ops_shared_inbox_live_probe_approval(handoff_path=tmp_path / "missing.json")
    packet["probe_approval_ref"] = "client_secret=must-not-serialize"
    binding_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_live_probe_approval_binding_cli_writes_validation(tmp_path: Path, capsys) -> None:
    binding_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding.json"
    output_path = tmp_path / "team_ops_shared_inbox_live_probe_approval_binding_validation.json"
    binding_path.write_text(
        json.dumps(bind_team_ops_shared_inbox_live_probe_approval(handoff_path=tmp_path / "missing.json")),
        encoding="utf-8",
    )
    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=binding_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_team_ops_shared_inbox_live_probe_approval_binding_validation(validation, output_path)
    exit_code = main(
        [
            "--binding",
            str(binding_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-blocked",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["ready_for_authority_receipt"] is False
    assert stdout_payload["status"] == "awaiting_handoff_readiness"
    assert captured.err == ""


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
