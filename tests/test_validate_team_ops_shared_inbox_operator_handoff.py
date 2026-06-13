"""Tests for TeamOps shared inbox operator handoff validation.

Purpose: prove TeamOps shared inbox handoff packets are schema-backed,
redacted, and explicit about observed evidence versus recommendations.
Governance scope: TeamOps assistant authority, shared inbox scope, external-send
approval, secret redaction, and presence-only runtime signals.
Dependencies: scripts.validate_team_ops_shared_inbox_operator_handoff.
Invariants:
  - Blocked handoffs remain valid while evidence is missing.
  - Live-probe readiness requires provider authority and passed preflights.
  - Secret-shaped values, external-message drift, and default-as-evidence drift
    fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    produce_team_ops_shared_inbox_operator_handoff,
)
from scripts.validate_team_ops_shared_inbox_operator_handoff import (
    main,
    validate_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_operator_handoff.schema.json"


def test_team_ops_shared_inbox_operator_handoff_accepts_blocked_packet(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    handoff_path.write_text(json.dumps(produce_team_ops_shared_inbox_operator_handoff({})), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.ok is True
    assert validation.status == "awaiting_operator_authority"
    assert validation.ready_for_live_probe is False
    assert validation.blocker_count >= 1
    assert validation.errors == ()


def test_team_ops_shared_inbox_operator_handoff_accepts_ready_packet(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    secret_names = (
        set(gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES)
        | set(gmail_preflight.WITNESS_REF_SIGNAL_NAMES)
        | set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES)
    )
    handoff_path.write_text(
        json.dumps(
            produce_team_ops_shared_inbox_operator_handoff(
                _configured_env(),
                github_secret_names=secret_names,
                operator_approval_ref="approval:teamops-live-probe-20260613",
            )
        ),
        encoding="utf-8",
    )

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_live_probe=True,
    )

    assert validation.ok is True
    assert validation.status == "ready_for_live_probe"
    assert validation.ready_for_live_probe is True
    assert validation.blocker_count == 0
    assert validation.errors == ()


def test_team_ops_shared_inbox_operator_handoff_rejects_default_as_evidence_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    packet = produce_team_ops_shared_inbox_operator_handoff({})
    packet["preflight_environment_basis"] = "recommended_defaults_applied"
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("preflight_environment_basis" in error for error in validation.errors)


def test_team_ops_shared_inbox_operator_handoff_rejects_live_probe_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    packet = produce_team_ops_shared_inbox_operator_handoff({})
    packet["ready_for_live_probe"] = True
    packet["status"] = "ready_for_live_probe"
    packet["solver_outcome"] = "SolvedVerified"
    packet["blocked_until"] = []
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "ready_for_live_probe requires provider_setup_authorized" in validation.errors
    assert "ready_for_live_probe requires passed Gmail OAuth preflight summary" in validation.errors
    assert "ready_for_live_probe requires passed TeamOps preflight summary" in validation.errors


def test_team_ops_shared_inbox_operator_handoff_rejects_external_message_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    packet = produce_team_ops_shared_inbox_operator_handoff({})
    packet["external_message_sent"] = True
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "external_message_sent must be false" in validation.errors


def test_team_ops_shared_inbox_operator_handoff_rejects_secret_marker(tmp_path: Path) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    packet = produce_team_ops_shared_inbox_operator_handoff({})
    packet["operator_approval_ref"] = "client_secret=must-not-serialize"
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_shared_inbox_operator_handoff_cli_writes_validation(tmp_path: Path, capsys) -> None:
    handoff_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    output_path = tmp_path / "team_ops_shared_inbox_operator_handoff_validation.json"
    handoff_path.write_text(json.dumps(produce_team_ops_shared_inbox_operator_handoff({})), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_team_ops_shared_inbox_operator_handoff_validation(validation, output_path)
    exit_code = main(
        [
            "--handoff",
            str(handoff_path),
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
    assert payload["ready_for_live_probe"] is False
    assert stdout_payload["status"] == "awaiting_operator_authority"
    assert captured.err == ""


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
