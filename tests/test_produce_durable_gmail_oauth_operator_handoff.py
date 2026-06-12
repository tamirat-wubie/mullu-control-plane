"""Tests for durable Gmail OAuth operator handoff production.

Purpose: prove the operator handoff exposes provider setup blockers without
executing external effects or serializing secret values.
Governance scope: OAuth evidence boundary, secret redaction, presence-only
runtime signals, and live-probe admission.
Dependencies: scripts.produce_durable_gmail_oauth_operator_handoff.
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

from scripts import validate_durable_gmail_oauth_runtime_preflight as preflight
from scripts.produce_durable_gmail_oauth_operator_handoff import (
    PROVIDER_ACTION_IDS,
    main,
    produce_durable_gmail_oauth_operator_handoff,
    write_durable_gmail_oauth_operator_handoff,
)


def _configured_env() -> dict[str, str]:
    return {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }


def test_default_handoff_waits_for_operator_authority_and_redacts_values() -> None:
    packet = produce_durable_gmail_oauth_operator_handoff({})
    serialized_packet = json.dumps(packet, sort_keys=True)

    assert packet["status"] == "awaiting_operator_authority"
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert packet["provider_setup_authorized"] is False
    assert packet["external_provider_mutation_performed"] is False
    assert packet["github_secret_mutation_performed"] is False
    assert packet["credential_values_disclosed"] is False
    assert packet["ready_for_live_probe"] is False
    assert "operator_approval_ref" in packet["blocked_until"]
    assert "GMAIL_OAUTH_CLIENT_SECRET" in serialized_packet
    assert "client_secret=" not in serialized_packet
    assert "refresh_token=" not in serialized_packet


def test_operator_approval_allows_provider_setup_not_live_probe() -> None:
    packet = produce_durable_gmail_oauth_operator_handoff(
        _configured_env(),
        operator_approval_ref="approval:gmail-oauth-setup-20260611",
    )
    action_ids = {action["action_id"] for action in packet["provider_console_actions"]}
    binding_names = {binding["name"] for binding in packet["runtime_bindings"]}

    assert packet["status"] == "ready_for_provider_setup"
    assert packet["provider_setup_authorized"] is True
    assert packet["ready_for_provider_setup"] is True
    assert packet["ready_for_live_probe"] is False
    assert packet["preflight_summary"]["status"] == "awaiting_evidence"
    assert packet["scope_decision"]["minimum_scopes"] == [preflight.GMAIL_READONLY_SCOPE]
    assert packet["scope_decision"]["scope_sensitivity"] == "restricted"
    assert action_ids == set(PROVIDER_ACTION_IDS)
    assert set(preflight.DURABLE_SECRET_SIGNAL_NAMES).issubset(binding_names)
    assert set(preflight.WITNESS_REF_SIGNAL_NAMES).issubset(binding_names)


def test_presence_only_secret_inventory_admits_live_probe_with_approval() -> None:
    secret_names = set(preflight.DURABLE_SECRET_SIGNAL_NAMES) | set(preflight.WITNESS_REF_SIGNAL_NAMES)
    packet = produce_durable_gmail_oauth_operator_handoff(
        _configured_env(),
        github_secret_names=secret_names,
        operator_approval_ref="approval:gmail-oauth-live-probe-20260611",
    )

    assert packet["status"] == "ready_for_live_probe"
    assert packet["solver_outcome"] == "SolvedVerified"
    assert packet["ready_for_live_probe"] is True
    assert packet["ready_for_provider_setup"] is False
    assert packet["preflight_summary"]["status"] == "passed"
    assert packet["preflight_summary"]["blocker_count"] == 0
    assert packet["blocked_until"] == []
    present_secret_names = {
        item["name"]
        for item in packet["preflight_summary"]["signal_inventory"]
        if item["github_secret_present"] is True
    }
    assert set(preflight.DURABLE_SECRET_SIGNAL_NAMES).issubset(present_secret_names)
    assert set(preflight.WITNESS_REF_SIGNAL_NAMES).issubset(present_secret_names)


def test_handoff_rejects_secret_shaped_approval_ref() -> None:
    with pytest.raises(ValueError):
        produce_durable_gmail_oauth_operator_handoff(
            _configured_env(),
            operator_approval_ref="client_secret=must-not-serialize",
        )


def test_writer_and_cli_emit_redacted_blocked_packet(  # type: ignore[no-untyped-def]
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff(_configured_env())
    written_path = write_durable_gmail_oauth_operator_handoff(packet, output_path)

    for name, value in _configured_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GMAIL_OAUTH_CLIENT_SECRET", raising=False)
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
