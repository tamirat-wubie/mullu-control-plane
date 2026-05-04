"""Workspace groups authority directory adapter tests.

Purpose: verify workspace users/groups export conversion into normalized
authority directory JSON.
Governance scope: explicit mapping rules, source hashes, rejected references,
and compatibility with the static authority directory sync adapter.
"""

from __future__ import annotations

import json

from scripts.workspace_groups_authority_directory_adapter import (
    _bounded_error_reason,
    convert_workspace_groups_authority_directory,
    main,
    write_workspace_groups_authority_directory,
)
from scripts.sync_authority_directory import sync_static_authority_directory


def test_workspace_groups_authority_directory_adapter_emits_syncable_directory(tmp_path) -> None:
    workspace_export = tmp_path / "workspace-groups.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    workspace_export.write_text(json.dumps(_workspace_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    payload = convert_workspace_groups_authority_directory(
        tenant_id="tenant-1",
        workspace_export_path=workspace_export,
        mapping_path=mapping,
        source_ref="workspace://example.com/groups/export/2026-04-29T12:00:00Z",
    )
    written = write_workspace_groups_authority_directory(payload, output)
    batch, receipt = sync_static_authority_directory(written)

    assert payload["source_system"] == "workspace_groups_export"
    assert payload["source_hash"].startswith("sha256:")
    assert payload["people"][0]["identity_id"] == "finance.manager@example.com"
    assert payload["teams"][0]["team_id"] == "finance-ops@example.com"
    assert payload["role_assignments"][0]["role"] == "financial_admin"
    assert batch["ownership_bindings"][0]["resource_ref"] == "financial.send_payment"
    assert batch["approval_policies"][0]["required_approver_count"] == 2
    assert receipt.rejected_record_count == 0


def test_workspace_groups_authority_directory_adapter_rejects_missing_owner_reference(tmp_path) -> None:
    workspace_export = tmp_path / "workspace-groups.json"
    mapping = tmp_path / "mapping.json"
    payload = _mapping_payload()
    payload["ownership_bindings"][0]["primary_owner_id"] = "missing@example.com"
    workspace_export.write_text(json.dumps(_workspace_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(payload), encoding="utf-8")

    directory = convert_workspace_groups_authority_directory(
        tenant_id="tenant-1",
        workspace_export_path=workspace_export,
        mapping_path=mapping,
    )

    assert directory["ownership_bindings"] == ()
    assert directory["approval_policies"][0]["policy_id"] == "payment-high-risk"
    assert directory["rejected_records"][0]["record_type"] == "ownership_binding"
    assert directory["rejected_records"][0]["reason"] == "owner_not_found"


def test_workspace_groups_authority_directory_adapter_cli_writes_output(tmp_path, capsys) -> None:
    workspace_export = tmp_path / "workspace-groups.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    workspace_export.write_text(json.dumps(_workspace_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--workspace-export", str(workspace_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Workspace groups authority directory written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["ownership_bindings"][0]["owner_team"] == "finance-ops@example.com"


def test_workspace_groups_authority_directory_adapter_reports_bounded_errors(tmp_path, capsys) -> None:
    workspace_export = tmp_path / "workspace-groups.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    workspace_export.write_text(json.dumps({"domain": "example.com", "users": [], "groups": {}}), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--workspace-export", str(workspace_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Workspace groups authority directory failed: workspace groups must be a list" in captured.err
    assert captured.out == ""
    assert not output.exists()


def test_workspace_groups_authority_directory_bounds_unrecognized_error_reason() -> None:
    reason = _bounded_error_reason(ValueError("secret-workspace-authority-token"))

    assert reason == "invalid_workspace_groups_authority_directory"
    assert "secret-workspace-authority-token" not in reason
    assert reason != "secret-workspace-authority-token"


def _workspace_payload() -> dict:
    return {
        "domain": "example.com",
        "users": [
            {
                "email": "finance.manager@example.com",
                "name": "Finance Manager",
                "active": True,
            },
            {
                "email": "tenant.owner@example.com",
                "name": "Tenant Owner",
                "active": True,
            },
        ],
        "groups": [
            {
                "email": "finance-ops@example.com",
                "name": "Finance Ops",
                "members": ["finance.manager@example.com"],
            },
            {
                "email": "executive-ops@example.com",
                "name": "Executive Ops",
                "members": ["tenant.owner@example.com"],
            },
        ],
    }


def _mapping_payload() -> dict:
    return {
        "role_assignments": [{
            "group_email": "finance-ops@example.com",
            "role": "financial_admin",
        }],
        "ownership_bindings": [{
            "resource_ref": "financial.send_payment",
            "owner_team": "finance-ops@example.com",
            "primary_owner_id": "finance.manager@example.com",
            "fallback_owner_id": "tenant.owner@example.com",
            "escalation_team": "executive-ops@example.com",
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
            "fallback_owner_id": "tenant.owner@example.com",
            "escalation_team": "executive-ops@example.com",
        }],
    }
