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
    _parse_github_secret_names,
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
    inventory_by_name = {item["name"]: item for item in packet["preflight_summary"]["signal_inventory"]}
    recommended_default_names = {item["name"] for item in packet["recommended_runtime_defaults"]}

    assert packet["status"] == "awaiting_operator_authority"
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert packet["provider_setup_authorized"] is False
    assert packet["external_provider_mutation_performed"] is False
    assert packet["github_secret_mutation_performed"] is False
    assert packet["credential_values_disclosed"] is False
    assert packet["ready_for_live_probe"] is False
    assert "operator_approval_ref" in packet["blocked_until"]
    assert "gmail_oauth_adapter_mode_missing" in packet["blocked_until"]
    assert "gmail_oauth_operation_family_missing_or_unsupported" in packet["blocked_until"]
    assert "gmail_oauth_scope_missing" in packet["blocked_until"]
    assert packet["preflight_environment_basis"] == "observed_environment_without_defaults"
    assert packet["preflight_summary"]["blocker_count"] == 11
    assert recommended_default_names == {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
        "EMAIL_CALENDAR_CONNECTOR_ID",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY",
        "GMAIL_SCOPE_ID",
    }
    assert inventory_by_name["MULLU_EMAIL_CALENDAR_WORKER_ADAPTER"]["env_present"] is False
    assert inventory_by_name["MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY"]["env_present"] is False
    assert inventory_by_name["GMAIL_SCOPE_ID"]["env_present"] is False
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


def test_cli_uses_github_repo_inventory_for_live_probe_handoff(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    for name in (
        *preflight.NON_SECRET_CONFIG_SIGNAL_NAMES,
        *preflight.ACCESS_TOKEN_SIGNAL_NAMES,
        *preflight.DURABLE_SECRET_SIGNAL_NAMES,
        *preflight.WITNESS_REF_SIGNAL_NAMES,
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        preflight,
        "collect_github_secret_names",
        lambda repo: set(preflight.DURABLE_SECRET_SIGNAL_NAMES),
    )
    monkeypatch.setattr(
        preflight,
        "collect_github_variable_values",
        lambda repo: {
            "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
            "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
            "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
            "GMAIL_SCOPE_ID": "https://www.googleapis.com/auth/gmail.readonly",
            "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
            "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
            "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
            "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh",
            "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "witness:gmail-revocation",
        },
    )

    exit_code = main(
        [
            "--github-repo",
            "owner/repo",
            "--operator-approval-ref",
            "approval:gmail-live-probe-20260613",
            "--output",
            str(output_path),
            "--json",
            "--require-live-probe",
        ]
    )
    captured = capsys.readouterr()
    packet = json.loads(captured.out)

    assert exit_code == 0
    assert packet["status"] == "ready_for_live_probe"
    assert packet["solver_outcome"] == "SolvedVerified"
    assert packet["preflight_summary"]["status"] == "passed"
    assert packet["blocked_until"] == []
    assert packet["credential_values_disclosed"] is False
    assert packet["repository"] == "owner/repo"
    assert all("owner/repo" in binding["store_command"] for binding in packet["runtime_bindings"] if binding["store_command"])


def test_runtime_bindings_route_secrets_and_witness_refs_separately() -> None:
    packet = produce_durable_gmail_oauth_operator_handoff({})
    bindings = {binding["name"]: binding for binding in packet["runtime_bindings"]}

    for name in preflight.NON_SECRET_CONFIG_SIGNAL_NAMES:
        assert bindings[name]["classification"] == "non_secret_config"
        assert bindings[name]["store_command"] == ""
        assert bindings[name]["value_must_not_be_committed"] is True
    for name in preflight.DURABLE_SECRET_SIGNAL_NAMES:
        assert bindings[name]["classification"] == "secret"
        assert bindings[name]["store_command"].startswith(f"gh secret set {name} ")
        assert "gh variable set" not in bindings[name]["store_command"]
    for name in preflight.WITNESS_REF_SIGNAL_NAMES:
        assert bindings[name]["classification"] == "witness_ref"
        assert bindings[name]["store_command"].startswith(f"gh variable set {name} ")
        assert "gh secret set" not in bindings[name]["store_command"]


def test_writer_rejects_secret_marker_without_creating_file(tmp_path: Path) -> None:
    output_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff(_configured_env())
    packet["operator_approval_ref"] = "refresh_token=must-not-write"

    with pytest.raises(ValueError) as raised:
        write_durable_gmail_oauth_operator_handoff(packet, output_path)

    assert "prohibited secret marker" in str(raised.value)
    assert "refresh_token=" in str(raised.value)
    assert not output_path.exists()


def test_handoff_rejects_uppercase_secret_shaped_approval_ref() -> None:
    with pytest.raises(ValueError) as raised:
        produce_durable_gmail_oauth_operator_handoff(
            _configured_env(),
            operator_approval_ref="CLIENT_SECRET=must-not-serialize",
        )

    assert "prohibited secret marker" in str(raised.value)
    assert "client_secret=" in str(raised.value)


def test_parse_github_secret_names_rejects_values_and_malformed_names() -> None:
    with pytest.raises(ValueError) as secret_value_error:
        _parse_github_secret_names(["GMAIL_REFRESH_TOKEN=refresh_token=must-not-accept"])
    with pytest.raises(ValueError) as malformed_name_error:
        _parse_github_secret_names(["gmail_refresh_token"])
    with pytest.raises(ValueError) as unicode_name_error:
        _parse_github_secret_names(["GMAIL_ሚ"])

    assert "refresh_token=" in str(secret_value_error.value)
    assert "uppercase identifier" in str(malformed_name_error.value)
    assert "uppercase identifier" in str(unicode_name_error.value)


def test_handoff_rejects_malformed_repository_slug() -> None:
    with pytest.raises(ValueError) as raised:
        produce_durable_gmail_oauth_operator_handoff(
            _configured_env(),
            repository="owner/repo; gh secret list",
        )

    assert "owner/repo slug" in str(raised.value)
