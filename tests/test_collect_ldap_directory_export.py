"""LDAP directory export collector tests.

Purpose: verify live LDAP users/groups collection without network access.
Governance scope: ldapsearch command boundaries, bind-password handling, LDIF
parsing, JSON persistence, and credential-safe failure reporting.
"""

from __future__ import annotations

import json
import subprocess

from scripts.collect_ldap_directory_export import (
    _bounded_error_reason,
    collect_ldap_directory_export,
    main,
    write_ldap_export,
)


def test_collect_ldap_directory_export_invokes_ldapsearch_for_users_and_groups(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, check, capture_output, text, timeout):
        commands.append(command)
        assert check is True
        assert capture_output is True
        assert text is True
        assert timeout == 30
        if "(objectClass=person)" in command:
            return subprocess.CompletedProcess(command, 0, stdout=_users_ldif(), stderr="")
        if "(objectClass=groupOfNames)" in command:
            return subprocess.CompletedProcess(command, 0, stdout=_groups_ldif(), stderr="")
        raise AssertionError(f"unexpected LDAP command: {command}")

    monkeypatch.setattr("subprocess.run", fake_run)

    payload = collect_ldap_directory_export(
        ldap_uri="ldaps://directory.example.com",
        bind_dn="cn=reader,dc=example,dc=com",
        bind_password=" secret-password ",
        user_base_dn="ou=people,dc=example,dc=com",
        group_base_dn="ou=groups,dc=example,dc=com",
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    assert payload["source_system"] == "ldap_search"
    assert payload["directory_ref"] == "directory.example.com"
    assert payload["source_ref"] == "ldap://directory.example.com/export/2026-04-29T12:00:00+00:00"
    assert payload["summary"]["user_count"] == 1
    assert payload["summary"]["group_count"] == 1
    assert payload["users"][0]["dn"] == "uid=finance-manager,ou=people,dc=example,dc=com"
    assert payload["groups"][0]["members"] == ("uid=finance-manager,ou=people,dc=example,dc=com",)
    assert "-y" in commands[0]
    assert "secret-password" not in commands[0]
    assert all("secret-password" not in item for command in commands for item in command)


def test_collect_ldap_directory_export_rejects_non_ldap_uri() -> None:
    try:
        collect_ldap_directory_export(
            ldap_uri="https://directory.example.com",
            bind_dn="cn=reader,dc=example,dc=com",
            bind_password="secret-password",
            user_base_dn="ou=people,dc=example,dc=com",
            group_base_dn="ou=groups,dc=example,dc=com",
            clock=lambda: "2026-04-29T12:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "ldap_uri must be ldap or ldaps"
        assert "https" not in str(exc)
        assert "secret-password" not in str(exc)
    else:
        raise AssertionError("expected non-LDAP URI to be rejected")


def test_collect_ldap_directory_export_writes_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("subprocess.run", _fake_run_empty_directory)
    payload = collect_ldap_directory_export(
        ldap_uri="ldap://directory.example.com",
        bind_dn="cn=reader,dc=example,dc=com",
        bind_password="secret-password",
        user_base_dn="ou=people,dc=example,dc=com",
        group_base_dn="ou=groups,dc=example,dc=com",
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    written = write_ldap_export(payload, tmp_path / "ldap-export.json")
    loaded = json.loads(written.read_text(encoding="utf-8"))

    assert written.name == "ldap-export.json"
    assert loaded["summary"]["user_count"] == 0
    assert loaded["summary"]["group_count"] == 0
    assert loaded["users"] == []
    assert loaded["groups"] == []


def test_collect_ldap_directory_export_cli_writes_output(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("subprocess.run", _fake_run_empty_directory)
    output = tmp_path / "ldap-export.json"

    exit_code = main([
        "--ldap-uri", "ldaps://directory.example.com",
        "--bind-dn", "cn=reader,dc=example,dc=com",
        "--bind-password", "secret-password",
        "--user-base-dn", "ou=people,dc=example,dc=com",
        "--group-base-dn", "ou=groups,dc=example,dc=com",
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "LDAP directory export written" in captured.out
    assert loaded["source_system"] == "ldap_search"
    assert "secret-password" not in captured.out


def test_collect_ldap_directory_export_reports_bounded_dependency_error(tmp_path, monkeypatch, capsys) -> None:
    def fake_run(command, check, capture_output, text, timeout):
        raise FileNotFoundError("ldapsearch missing secret-password")

    monkeypatch.setattr("subprocess.run", fake_run)

    exit_code = main([
        "--ldap-uri", "ldaps://directory.example.com",
        "--bind-dn", "cn=reader,dc=example,dc=com",
        "--bind-password", "secret-password",
        "--user-base-dn", "ou=people,dc=example,dc=com",
        "--group-base-dn", "ou=groups,dc=example,dc=com",
        "--output", str(tmp_path / "ldap-export.json"),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "LDAP directory export failed: ldapsearch dependency unavailable" in captured.err
    assert "secret-password" not in captured.err
    assert captured.out == ""


def test_ldap_directory_export_bounds_unrecognized_error_reason() -> None:
    reason = _bounded_error_reason(ValueError("secret-ldap-directory-token"))

    assert reason == "invalid_ldap_directory_export"
    assert "secret-ldap-directory-token" not in reason
    assert reason != "secret-ldap-directory-token"


def _fake_run_empty_directory(command, check, capture_output, text, timeout):
    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def _users_ldif() -> str:
    return """dn: uid=finance-manager,ou=people,dc=example,dc=com
uid: finance-manager
cn: Finance Manager
mail: finance.manager@example.com

"""


def _groups_ldif() -> str:
    return """dn: cn=finance_ops,ou=groups,dc=example,dc=com
cn: finance_ops
member: uid=finance-manager,ou=people,dc=example,dc=com

"""
