"""Purpose: verify durable Gmail OAuth runtime preflight evidence handling.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight.
Invariants:
  - Missing durable OAuth evidence remains AwaitingEvidence.
  - Gmail search does not overclaim compatibility with gmail.metadata.
  - Secret-shaped values are not serialized into preflight reports.
"""

from __future__ import annotations

import json

import pytest

from scripts import validate_durable_gmail_oauth_runtime_preflight as preflight


def _ready_env() -> dict[str, str]:
    return {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "https://www.googleapis.com/auth/gmail.readonly",
        "GMAIL_OAUTH_CLIENT_ID": "client-id-secret-shaped-value",
        "GMAIL_OAUTH_CLIENT_SECRET": "client_secret=must-not-leak",
        "GMAIL_REFRESH_TOKEN": "refresh_token=must-not-leak",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation-recovery",
    }


def test_empty_preflight_stays_awaiting_evidence_and_redacted() -> None:
    report = preflight.build_preflight_report({})

    assert report["status"] == "awaiting_evidence"
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["ready_for_live_probe"] is False
    assert report["production_ready_claimed"] is False
    assert report["credential_values_disclosed"] is False
    assert report["blocker_count"] >= 10
    assert any(finding["rule_id"] == "gmail_oauth_adapter_mode_missing" for finding in report["findings"])


def test_read_only_search_accepts_exact_least_privilege_scope() -> None:
    report = preflight.build_preflight_report(_ready_env())
    scope_analysis = report["scope_analysis"]

    assert report["status"] == "passed"
    assert report["solver_outcome"] == "SolvedVerified"
    assert report["ready_for_live_probe"] is True
    assert report["blocker_count"] == 0
    assert scope_analysis["recognized_scopes"] == [preflight.GMAIL_READONLY_SCOPE]
    assert scope_analysis["scope_sensitivity"] == "restricted"
    assert scope_analysis["least_privilege_satisfied"] is True
    assert scope_analysis["metadata_scope_search_compatible"] is True


def test_report_does_not_serialize_secret_values() -> None:
    environment = _ready_env()
    report = preflight.build_preflight_report(environment)
    serialized_report = json.dumps(report, sort_keys=True)

    assert "client_secret=must-not-leak" not in serialized_report
    assert "refresh_token=must-not-leak" not in serialized_report
    assert "client-id-secret-shaped-value" not in serialized_report
    assert "witness:gmail-client" not in serialized_report
    assert report["credential_values_disclosed"] is False
    assert report["secret_value_markers_present"] is False


def test_metadata_scope_is_rejected_for_current_search_path() -> None:
    environment = _ready_env()
    environment["GMAIL_SCOPE_ID"] = "gmail.metadata"

    report = preflight.build_preflight_report(environment)
    finding_ids = {finding["rule_id"] for finding in report["findings"]}

    assert report["status"] == "awaiting_evidence"
    assert report["ready_for_live_probe"] is False
    assert report["scope_analysis"]["recognized_scopes"] == [preflight.GMAIL_METADATA_SCOPE]
    assert report["scope_analysis"]["metadata_scope_search_compatible"] is False
    assert "gmail_oauth_metadata_scope_incompatible_with_search" in finding_ids
    assert "gmail_oauth_scope_not_least_privilege" in finding_ids


def test_full_mail_scope_is_rejected_as_overbroad() -> None:
    environment = _ready_env()
    environment["GMAIL_SCOPE_ID"] = "https://mail.google.com/"

    report = preflight.build_preflight_report(environment)
    finding_ids = {finding["rule_id"] for finding in report["findings"]}

    assert report["status"] == "awaiting_evidence"
    assert report["ready_for_live_probe"] is False
    assert report["scope_analysis"]["recognized_scopes"] == [preflight.GMAIL_FULL_MAIL_SCOPE]
    assert report["scope_analysis"]["least_privilege_satisfied"] is False
    assert "gmail_oauth_full_mail_scope_prohibited" in finding_ids
    assert "gmail_oauth_scope_not_least_privilege" in finding_ids


def test_github_secret_inventory_names_can_satisfy_presence_only_signals() -> None:
    environment = {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "production",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }
    secret_names = set(preflight.DURABLE_SECRET_SIGNAL_NAMES) | set(preflight.WITNESS_REF_SIGNAL_NAMES)

    report = preflight.build_preflight_report(environment, github_secret_names=secret_names)
    github_present = {
        item["name"]
        for item in report["signal_inventory"]
        if item["github_secret_present"] is True
    }

    assert report["status"] == "passed"
    assert report["ready_for_live_probe"] is True
    assert report["blocker_count"] == 0
    assert preflight.GMAIL_READONLY_SCOPE in report["scope_analysis"]["recognized_scopes"]
    assert set(preflight.DURABLE_SECRET_SIGNAL_NAMES).issubset(github_present)
    assert set(preflight.WITNESS_REF_SIGNAL_NAMES).issubset(github_present)


def test_parse_github_secret_list_reads_names_only() -> None:
    output = """NAME UPDATED
EMAIL_CALENDAR_CONNECTOR_TOKEN about 1 minute ago
GMAIL_REFRESH_TOKEN about 1 minute ago
invalid-secret-name about 1 minute ago
"""

    secret_names = preflight.parse_github_secret_list(output)

    assert "EMAIL_CALENDAR_CONNECTOR_TOKEN" in secret_names
    assert "GMAIL_REFRESH_TOKEN" in secret_names
    assert "invalid-secret-name" not in secret_names
    assert len(secret_names) == 2


def test_parse_github_variable_list_reads_allowed_non_secret_values() -> None:
    output = """NAME\tVALUE\tUPDATED
EMAIL_CALENDAR_CONNECTOR_ID\tgmail\t2026-06-12T02:03:38Z
GMAIL_SCOPE_ID\thttps://www.googleapis.com/auth/gmail.readonly\t2026-06-12T02:03:37Z
GMAIL_OAUTH_CLIENT_SECRET\tclient_secret=must-not-read\t2026-06-12T02:03:37Z
MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY\tread_only_search\t2026-06-12T02:03:37Z
MULLU_EMAIL_CALENDAR_WORKER_ADAPTER\tgoogle\t2026-06-12T02:03:37Z
MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF\twitness:gmail-consent\t2026-06-12T02:03:37Z
"""

    variable_values = preflight.parse_github_variable_list(output)

    assert variable_values["EMAIL_CALENDAR_CONNECTOR_ID"] == "gmail"
    assert variable_values["GMAIL_SCOPE_ID"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert variable_values["MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY"] == "read_only_search"
    assert variable_values["MULLU_EMAIL_CALENDAR_WORKER_ADAPTER"] == "google"
    assert variable_values["MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF"] == "witness:gmail-consent"
    assert "GMAIL_OAUTH_CLIENT_SECRET" not in variable_values


def test_parse_github_variable_list_rejects_secret_marker_in_allowed_variable() -> None:
    output = "GMAIL_SCOPE_ID\tclient_secret=must-not-store\t2026-06-12T02:03:37Z\n"

    with pytest.raises(ValueError) as raised:
        preflight.parse_github_variable_list(output)

    assert "GMAIL_SCOPE_ID" in str(raised.value)
    assert "client_secret=" in str(raised.value)


def test_parse_github_variable_list_rejects_uppercase_secret_marker() -> None:
    output = "GMAIL_SCOPE_ID\tCLIENT_SECRET=must-not-store\t2026-06-12T02:03:37Z\n"

    with pytest.raises(ValueError) as raised:
        preflight.parse_github_variable_list(output)

    assert "GMAIL_SCOPE_ID" in str(raised.value)
    assert "client_secret=" in str(raised.value)


def test_empty_local_overlay_does_not_mask_github_inventory() -> None:
    github_values = {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "https://www.googleapis.com/auth/gmail.readonly",
    }
    local_values = {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "",
        "GMAIL_SCOPE_ID": "   ",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_message",
    }

    merged = preflight.merge_non_empty_overlay(github_values, local_values)

    assert merged["MULLU_EMAIL_CALENDAR_WORKER_ADAPTER"] == "google"
    assert merged["GMAIL_SCOPE_ID"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert merged["MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY"] == "read_only_message"


def test_github_repo_inventory_cli_uses_variables_and_secret_names(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    output_path = tmp_path / "durable_gmail_oauth_runtime_preflight.json"
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

    exit_code = preflight.main(
        [
            "--github-repo",
            "owner/repo",
            "--output",
            str(output_path),
            "--json",
            "--require-ready",
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(captured.out)

    assert exit_code == 0
    assert report["status"] == "passed"
    assert report["ready_for_live_probe"] is True
    assert report["blocker_count"] == 0
    assert report["credential_values_disclosed"] is False


def test_require_ready_cli_returns_nonzero_when_blocked(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    for name in (
        *preflight.NON_SECRET_CONFIG_SIGNAL_NAMES,
        *preflight.ACCESS_TOKEN_SIGNAL_NAMES,
        *preflight.DURABLE_SECRET_SIGNAL_NAMES,
        *preflight.WITNESS_REF_SIGNAL_NAMES,
    ):
        monkeypatch.delenv(name, raising=False)

    exit_code = preflight.main(["--json", "--require-ready"])
    captured = capsys.readouterr()
    report = json.loads(captured.out)

    assert exit_code == 1
    assert report["status"] == "awaiting_evidence"
    assert report["ready_for_live_probe"] is False
    assert report["credential_values_disclosed"] is False


def test_runtime_preflight_cli_writes_redacted_receipt(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    output_path = tmp_path / "durable_gmail_oauth_runtime_preflight.json"
    for name, value in _ready_env().items():
        monkeypatch.setenv(name, value)

    exit_code = preflight.main(["--output", str(output_path), "--json", "--require-ready"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    disk_payload = json.loads(output_path.read_text(encoding="utf-8"))
    serialized_disk_payload = json.dumps(disk_payload, sort_keys=True)

    assert exit_code == 0
    assert disk_payload == stdout_payload
    assert disk_payload["ready_for_live_probe"] is True
    assert disk_payload["credential_values_disclosed"] is False
    assert "client_secret=must-not-leak" not in serialized_disk_payload
    assert "refresh_token=must-not-leak" not in serialized_disk_payload
    assert str(tmp_path) not in serialized_disk_payload


def test_runtime_preflight_writer_persists_redacted_receipt(tmp_path) -> None:
    output_path = tmp_path / "durable_gmail_oauth_runtime_preflight.json"
    report = preflight.build_preflight_report(_ready_env())

    written = preflight.write_durable_gmail_oauth_runtime_preflight(report, output_path)
    disk_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert disk_payload["status"] == "passed"
    assert disk_payload["ready_for_live_probe"] is True
    assert "client_secret=must-not-leak" not in json.dumps(disk_payload, sort_keys=True)


def test_runtime_preflight_writer_rejects_secret_marker(tmp_path) -> None:
    output_path = tmp_path / "durable_gmail_oauth_runtime_preflight.json"
    unsafe_report = {"receipt_id": "durable_gmail_oauth_runtime_preflight", "leak": "client_secret=must-not-write"}

    with pytest.raises(ValueError) as raised:
        preflight.write_durable_gmail_oauth_runtime_preflight(unsafe_report, output_path)

    assert "prohibited secret marker" in str(raised.value)
    assert "client_secret=" in str(raised.value)
    assert not output_path.exists()


def test_runtime_preflight_writer_rejects_uppercase_secret_marker(tmp_path) -> None:
    output_path = tmp_path / "durable_gmail_oauth_runtime_preflight.json"
    unsafe_report = {"receipt_id": "durable_gmail_oauth_runtime_preflight", "leak": "CLIENT_SECRET=must-not-write"}

    with pytest.raises(ValueError) as raised:
        preflight.write_durable_gmail_oauth_runtime_preflight(unsafe_report, output_path)

    assert "prohibited secret marker" in str(raised.value)
    assert "client_secret=" in str(raised.value)
    assert not output_path.exists()


def test_runtime_preflight_detects_uppercase_secret_marker_leakage() -> None:
    marker = preflight.matched_secret_marker("CLIENT_SECRET=must-not-scope")

    assert marker == "client_secret="
    assert preflight.matched_secret_marker("REFRESH_TOKEN=must-not-scope") == "refresh_token="
    assert preflight.matched_secret_marker("witness:gmail-consent") == ""


def test_non_secret_runtime_signal_with_secret_marker_fails_closed() -> None:
    environment = _ready_env()
    environment["MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF"] = "CLIENT_SECRET=must-not-witness"

    report = preflight.build_preflight_report(environment)
    finding_ids = {finding["rule_id"] for finding in report["findings"]}

    assert report["status"] == "awaiting_evidence"
    assert report["ready_for_live_probe"] is False
    assert "gmail_oauth_non_secret_signal_contains_secret_marker" in finding_ids
    assert report["credential_values_disclosed"] is False
