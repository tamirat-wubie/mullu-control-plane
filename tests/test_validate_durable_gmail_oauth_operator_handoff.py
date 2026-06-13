"""Tests for durable Gmail OAuth operator handoff validation.

Purpose: prove durable Gmail OAuth handoff packets are schema-backed,
redacted, and explicit about observed evidence versus recommendations.
Governance scope: OAuth operator authority, secret redaction, live-probe
admission, and presence-only runtime signals.
Dependencies: scripts.validate_durable_gmail_oauth_operator_handoff.
Invariants:
  - Blocked handoffs remain valid while evidence is missing.
  - Live-probe readiness requires provider authority and passed preflight.
  - Secret-shaped values and default-as-evidence drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_runtime_preflight as preflight
from scripts.produce_durable_gmail_oauth_operator_handoff import produce_durable_gmail_oauth_operator_handoff
from scripts.validate_durable_gmail_oauth_operator_handoff import (
    main,
    validate_durable_gmail_oauth_operator_handoff,
    write_durable_gmail_oauth_operator_handoff_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "durable_gmail_oauth_operator_handoff.schema.json"


def test_durable_gmail_oauth_operator_handoff_accepts_blocked_packet(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    handoff_path.write_text(json.dumps(produce_durable_gmail_oauth_operator_handoff({})), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.ok is True
    assert validation.status == "awaiting_operator_authority"
    assert validation.ready_for_live_probe is False
    assert validation.blocker_count >= 1
    assert validation.errors == ()


def test_durable_gmail_oauth_operator_handoff_accepts_ready_packet(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    secret_names = set(preflight.DURABLE_SECRET_SIGNAL_NAMES) | set(preflight.WITNESS_REF_SIGNAL_NAMES)
    handoff_path.write_text(
        json.dumps(
            produce_durable_gmail_oauth_operator_handoff(
                _configured_env(),
                github_secret_names=secret_names,
                operator_approval_ref="approval:gmail-oauth-live-probe-20260611",
            )
        ),
        encoding="utf-8",
    )

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_live_probe=True,
    )

    assert validation.ok is True
    assert validation.status == "ready_for_live_probe"
    assert validation.ready_for_live_probe is True
    assert validation.blocker_count == 0
    assert validation.errors == ()


def test_durable_gmail_oauth_operator_handoff_rejects_default_as_evidence_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff({})
    packet["preflight_environment_basis"] = "recommended_defaults_applied"
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("preflight_environment_basis" in error for error in validation.errors)


def test_durable_gmail_oauth_operator_handoff_rejects_live_probe_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff({})
    packet["ready_for_live_probe"] = True
    packet["status"] = "ready_for_live_probe"
    packet["solver_outcome"] = "SolvedVerified"
    packet["blocked_until"] = []
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "ready_for_live_probe requires provider_setup_authorized" in validation.errors
    assert "ready_for_live_probe requires passed preflight summary" in validation.errors


def test_durable_gmail_oauth_operator_handoff_rejects_secret_marker(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff({})
    packet["operator_approval_ref"] = "CLIENT_SECRET=must-not-serialize"
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("secret marker" in error for error in validation.errors)


def test_durable_gmail_oauth_operator_handoff_rejects_duplicate_contract_entries(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff({})
    packet["recommended_runtime_defaults"].append(dict(packet["recommended_runtime_defaults"][0]))
    packet["provider_console_actions"].append(dict(packet["provider_console_actions"][0]))
    packet["runtime_bindings"].append(dict(packet["runtime_bindings"][0]))
    packet["runtime_bindings"].append(
        {
            "name": "UNSUPPORTED_RUNTIME_BINDING",
            "classification": "non_secret_config",
            "store_command": "",
            "value_must_not_be_committed": True,
        }
    )
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("recommended_runtime_defaults must not duplicate names" in error for error in validation.errors)
    assert any("provider_console_actions must not duplicate action ids" in error for error in validation.errors)
    assert any("runtime_bindings must not duplicate names" in error for error in validation.errors)
    assert any("runtime bindings include unsupported names" in error for error in validation.errors)


def test_durable_gmail_oauth_operator_handoff_rejects_binding_command_drift(tmp_path: Path) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    packet = produce_durable_gmail_oauth_operator_handoff({})
    bindings = {binding["name"]: binding for binding in packet["runtime_bindings"]}
    bindings["MULLU_EMAIL_CALENDAR_WORKER_ADAPTER"]["store_command"] = "gh variable set SHOULD_NOT_EXIST"
    bindings["GMAIL_REFRESH_TOKEN"]["store_command"] = "gh variable set GMAIL_REFRESH_TOKEN --repo owner/repo --body <secret>"
    bindings["GMAIL_OAUTH_CLIENT_SECRET"]["store_command"] = "gh secret set GMAIL_OAUTH_CLIENT_SECRET --repo owner/repo --body <secret>"
    bindings["MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF"]["store_command"] = "gh secret set MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF"
    bindings["MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF"]["store_command"] = "gh variable set MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF --repo owner/repo"
    handoff_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER must not include a store command" in validation.errors
    assert "GMAIL_REFRESH_TOKEN must include a secret store command template" in validation.errors
    assert "GMAIL_REFRESH_TOKEN secret store command must not inline a value" in validation.errors
    assert "GMAIL_OAUTH_CLIENT_SECRET secret store command must not inline a value" in validation.errors
    assert (
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF must include a witness ref variable command template"
        in validation.errors
    )
    assert (
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF witness ref command must use the witness-ref placeholder"
        in validation.errors
    )


def test_durable_gmail_oauth_operator_handoff_cli_writes_validation(tmp_path: Path, capsys) -> None:
    handoff_path = tmp_path / "durable_gmail_oauth_operator_handoff.json"
    output_path = tmp_path / "durable_gmail_oauth_operator_handoff_validation.json"
    handoff_path.write_text(json.dumps(produce_durable_gmail_oauth_operator_handoff({})), encoding="utf-8")
    validation = validate_durable_gmail_oauth_operator_handoff(
        handoff_path=handoff_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_durable_gmail_oauth_operator_handoff_validation(validation, output_path)
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
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }
