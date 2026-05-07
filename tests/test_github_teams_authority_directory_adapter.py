"""GitHub teams authority directory adapter tests.

Purpose: verify GitHub teams export conversion into normalized authority
directory JSON.
Governance scope: explicit mapping rules, source hashes, rejected references,
and compatibility with the static authority directory sync adapter.
"""

from __future__ import annotations

import json

from scripts.github_teams_authority_directory_adapter import (
    _bounded_error_reason,
    convert_github_teams_authority_directory,
    main,
    write_github_teams_authority_directory,
)
from scripts.sync_authority_directory import sync_static_authority_directory


def test_github_teams_authority_directory_adapter_emits_syncable_directory(tmp_path) -> None:
    github_export = tmp_path / "github-teams.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    github_export.write_text(json.dumps(_github_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    payload = convert_github_teams_authority_directory(
        tenant_id="tenant-1",
        github_export_path=github_export,
        mapping_path=mapping,
        source_ref="github://mullusi/teams/export/2026-04-29T12:00:00Z",
    )
    written = write_github_teams_authority_directory(payload, output)
    batch, receipt = sync_static_authority_directory(written)

    assert payload["source_system"] == "github_teams_export"
    assert payload["source_hash"].startswith("sha256:")
    assert payload["people"][0]["identity_id"] == "finance-manager"
    assert payload["teams"][0]["team_id"] == "finance-ops"
    assert payload["role_assignments"][0]["role"] == "financial_admin"
    assert batch["ownership_bindings"][0]["resource_ref"] == "financial.send_payment"
    assert batch["approval_policies"][0]["required_approver_count"] == 2
    assert receipt.rejected_record_count == 0


def test_github_teams_authority_directory_adapter_rejects_missing_owner_reference(tmp_path) -> None:
    github_export = tmp_path / "github-teams.json"
    mapping = tmp_path / "mapping.json"
    payload = _mapping_payload()
    payload["ownership_bindings"][0]["primary_owner_id"] = "missing-login"
    github_export.write_text(json.dumps(_github_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(payload), encoding="utf-8")

    directory = convert_github_teams_authority_directory(
        tenant_id="tenant-1",
        github_export_path=github_export,
        mapping_path=mapping,
    )

    assert directory["ownership_bindings"] == ()
    assert directory["approval_policies"][0]["policy_id"] == "payment-high-risk"
    assert directory["rejected_records"][0]["record_type"] == "ownership_binding"
    assert directory["rejected_records"][0]["reason"] == "owner_not_found"


def test_github_teams_authority_directory_adapter_cli_writes_output(tmp_path, capsys) -> None:
    github_export = tmp_path / "github-teams.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    github_export.write_text(json.dumps(_github_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--github-export", str(github_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "GitHub teams authority directory written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["ownership_bindings"][0]["owner_team"] == "finance-ops"


def test_github_teams_authority_directory_adapter_reports_bounded_errors(tmp_path, capsys) -> None:
    github_export = tmp_path / "github-teams.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    github_export.write_text(json.dumps({"organization": "mullusi", "members": [], "teams": {}}), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--github-export", str(github_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "GitHub teams authority directory failed: GitHub teams must be a list" in captured.err
    assert captured.out == ""
    assert not output.exists()


def test_github_teams_authority_directory_bounds_unrecognized_error_reason() -> None:
    reason = _bounded_error_reason(ValueError("secret-github-authority-token"))

    assert reason == "invalid_github_teams_authority_directory"
    assert "secret-github-authority-token" not in reason
    assert reason != "secret-github-authority-token"


def _github_payload() -> dict:
    return {
        "organization": "mullusi",
        "members": [
            {
                "login": "finance-manager",
                "name": "Finance Manager",
            },
            {
                "login": "tenant-owner",
                "name": "Tenant Owner",
            },
        ],
        "teams": [
            {
                "slug": "finance-ops",
                "name": "Finance Ops",
                "members": ["finance-manager"],
            },
            {
                "slug": "executive-ops",
                "name": "Executive Ops",
                "members": ["tenant-owner"],
            },
        ],
    }


def _mapping_payload() -> dict:
    return {
        "role_assignments": [{
            "team_slug": "finance-ops",
            "role": "financial_admin",
        }],
        "ownership_bindings": [{
            "resource_ref": "financial.send_payment",
            "owner_team": "finance-ops",
            "primary_owner_id": "finance-manager",
            "fallback_owner_id": "tenant-owner",
            "escalation_team": "executive-ops",
        }],
        "approval_policies": [{
            "policy_id": "payment-high-risk",
            "capability": "financial.send_payment",
            "risk_tier": "high",
            "required_roles": ["financial_admin"],
            "required_approver_count": 2,
            "separation_of_duty": True,
            "timeout_seconds": 300,
            "escalation_policy_id": "finance-escalation",
        }],
        "escalation_policies": [{
            "policy_id": "finance-escalation",
            "notify_after_seconds": 300,
            "escalate_after_seconds": 900,
            "incident_after_seconds": 3600,
            "fallback_owner_id": "tenant-owner",
            "escalation_team": "executive-ops",
        }],
    }
