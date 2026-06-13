"""Tests for TeamOps shared inbox operator handoff production.

Purpose: prove the TeamOps operator handoff exposes shared inbox connector
blockers without executing external effects or serializing secret values.
Governance scope: TeamOps assistant authority, Gmail scope evidence, shared
inbox witness evidence, external-send approval, and presence-only runtime
signals.
Dependencies: scripts.produce_team_ops_shared_inbox_operator_handoff.
Invariants:
  - Bare handoff generation remains AwaitingEvidence.
  - Operator approval does not imply live-probe readiness.
  - Presence-only GitHub secret names can satisfy preflight signals.
  - Secret-shaped values are rejected from serialized packets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_durable_gmail_oauth_runtime_preflight as gmail_preflight
from scripts.produce_team_ops_shared_inbox_operator_handoff import (
    TEAM_OPS_OPERATOR_ACTION_IDS,
    TEAM_OPS_WITNESS_REF_SIGNAL_NAMES,
    main,
    produce_team_ops_shared_inbox_operator_handoff,
    write_team_ops_shared_inbox_operator_handoff,
)


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


def test_team_ops_default_handoff_waits_for_operator_authority_and_redacts_values() -> None:
    packet = produce_team_ops_shared_inbox_operator_handoff({})
    serialized_packet = json.dumps(packet, sort_keys=True)
    recommended_defaults = {item["name"]: item for item in packet["recommended_runtime_defaults"]}
    gmail_finding_ids = set(packet["gmail_oauth_preflight_summary"]["finding_rule_ids"])
    team_ops_finding_ids = set(packet["team_ops_preflight_summary"]["finding_rule_ids"])

    assert packet["status"] == "awaiting_operator_authority"
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert packet["provider_setup_authorized"] is False
    assert packet["preflight_environment_basis"] == "observed_environment_without_defaults"
    assert packet["external_provider_mutation_performed"] is False
    assert packet["github_secret_mutation_performed"] is False
    assert packet["external_message_sent"] is False
    assert packet["credential_values_disclosed"] is False
    assert packet["ready_for_live_probe"] is False
    assert packet["capability_boundary"]["external_send_requires_approval"] is True
    assert packet["capability_boundary"]["plan_only"] is True
    assert packet["gmail_oauth_preflight_summary"]["status"] == "awaiting_evidence"
    assert packet["team_ops_preflight_summary"]["status"] == "awaiting_evidence"
    assert "gmail_oauth_adapter_mode_missing" in gmail_finding_ids
    assert "team_ops_profile_missing_or_unsupported" in team_ops_finding_ids
    assert "team_ops_witness_ref_missing" in team_ops_finding_ids
    assert recommended_defaults["MULLU_TEAM_OPS_ASSISTANT_PROFILE"]["recommended_value"] == "team_ops.default"
    assert recommended_defaults["MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY"]["recommended_value"] == "approval_required"
    assert "operator_approval_ref" in packet["blocked_until"]
    assert "GMAIL_OAUTH_CLIENT_SECRET" in serialized_packet
    assert "client_secret=" not in serialized_packet
    assert "refresh_token=" not in serialized_packet


def test_team_ops_operator_approval_allows_provider_setup_not_live_probe() -> None:
    packet = produce_team_ops_shared_inbox_operator_handoff(
        _configured_env(),
        operator_approval_ref="approval:teamops-shared-inbox-setup-20260613",
    )
    action_ids = {action["action_id"] for action in packet["operator_actions"]}
    binding_names = {binding["name"] for binding in packet["runtime_bindings"]}

    assert packet["status"] == "ready_for_provider_setup"
    assert packet["provider_setup_authorized"] is True
    assert packet["ready_for_provider_setup"] is True
    assert packet["ready_for_live_probe"] is False
    assert packet["external_message_sent"] is False
    assert packet["scope_decision"]["minimum_scopes"] == [
        gmail_preflight.GMAIL_READONLY_SCOPE,
        gmail_preflight.GMAIL_SEND_SCOPE,
    ]
    assert packet["scope_decision"]["external_send_requires_approval"] is True
    assert action_ids == set(TEAM_OPS_OPERATOR_ACTION_IDS)
    assert set(gmail_preflight.DURABLE_SECRET_SIGNAL_NAMES).issubset(binding_names)
    assert set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES).issubset(binding_names)


def test_team_ops_presence_only_secret_inventory_admits_live_probe_with_approval() -> None:
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

    assert packet["status"] == "ready_for_live_probe"
    assert packet["solver_outcome"] == "SolvedVerified"
    assert packet["ready_for_live_probe"] is True
    assert packet["ready_for_provider_setup"] is False
    assert packet["external_message_sent"] is False
    assert packet["gmail_oauth_preflight_summary"]["status"] == "passed"
    assert packet["team_ops_preflight_summary"]["status"] == "passed"
    assert packet["blocked_until"] == []
    present_secret_names = {
        item["name"]
        for item in packet["team_ops_preflight_summary"]["signal_inventory"]
        if item["github_secret_present"] is True
    }
    assert set(TEAM_OPS_WITNESS_REF_SIGNAL_NAMES).issubset(present_secret_names)


def test_team_ops_handoff_rejects_secret_shaped_approval_ref() -> None:
    with pytest.raises(ValueError):
        produce_team_ops_shared_inbox_operator_handoff(
            _configured_env(),
            operator_approval_ref="refresh_token=must-not-serialize",
        )


def test_team_ops_writer_and_cli_emit_redacted_blocked_packet(  # type: ignore[no-untyped-def]
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_path = tmp_path / "team_ops_shared_inbox_operator_handoff.json"
    packet = produce_team_ops_shared_inbox_operator_handoff(_configured_env())
    written_path = write_team_ops_shared_inbox_operator_handoff(packet, output_path)

    for name, value in _configured_env().items():
        monkeypatch.setenv(name, value)
    exit_code = main(["--output", str(output_path), "--json"])
    require_ready_exit_code = main(["--output", str(output_path), "--require-live-probe"])
    captured = capsys.readouterr()
    disk_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written_path == output_path
    assert exit_code == 0
    assert require_ready_exit_code == 2
    assert disk_payload["status"] == "awaiting_operator_authority"
    assert stdout_payload["handoff_id"] == disk_payload["handoff_id"]
    assert disk_payload["credential_values_disclosed"] is False
    assert "client_secret=" not in json.dumps(disk_payload, sort_keys=True)
    assert "refresh_token=" not in json.dumps(stdout_payload, sort_keys=True)
