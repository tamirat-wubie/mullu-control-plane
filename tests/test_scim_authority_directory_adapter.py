"""SCIM authority directory adapter tests.

Purpose: verify SCIM export conversion into normalized authority directory JSON.
Governance scope: explicit mapping rules, source hashes, rejected references,
and compatibility with the static authority directory sync adapter.
"""

from __future__ import annotations

import json

from scripts.scim_authority_directory_adapter import (
    convert_scim_authority_directory,
    main,
    write_scim_authority_directory,
)
from scripts.sync_authority_directory import sync_static_authority_directory


def test_scim_authority_directory_adapter_emits_syncable_directory(tmp_path) -> None:
    scim_export = tmp_path / "scim.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    scim_export.write_text(json.dumps(_scim_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    payload = convert_scim_authority_directory(
        tenant_id="tenant-1",
        scim_export_path=scim_export,
        mapping_path=mapping,
        source_ref="scim://workspace/export/2026-04-29T12:00:00Z",
    )
    written = write_scim_authority_directory(payload, output)
    batch, receipt = sync_static_authority_directory(written)

    assert payload["source_system"] == "scim_export"
    assert payload["source_hash"].startswith("sha256:")
    assert payload["people"][0]["identity_id"] == "finance-manager-1"
    assert payload["teams"][0]["team_id"] == "group-finance"
    assert payload["role_assignments"][0]["role"] == "financial_admin"
    assert batch["ownership_bindings"][0]["resource_ref"] == "financial.send_payment"
    assert batch["approval_policies"][0]["required_approver_count"] == 2
    assert receipt.rejected_record_count == 0


def test_scim_authority_directory_adapter_rejects_missing_owner_reference(tmp_path) -> None:
    scim_export = tmp_path / "scim.json"
    mapping = tmp_path / "mapping.json"
    payload = _mapping_payload()
    payload["ownership_bindings"][0]["primary_owner_id"] = "missing-user"
    scim_export.write_text(json.dumps(_scim_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(payload), encoding="utf-8")

    directory = convert_scim_authority_directory(
        tenant_id="tenant-1",
        scim_export_path=scim_export,
        mapping_path=mapping,
    )

    assert directory["ownership_bindings"] == ()
    assert directory["approval_policies"][0]["policy_id"] == "payment-high-risk"
    assert directory["rejected_records"][0]["record_type"] == "ownership_binding"
    assert directory["rejected_records"][0]["reason"] == "owner_not_found"


def test_scim_authority_directory_adapter_cli_writes_output(tmp_path, capsys) -> None:
    scim_export = tmp_path / "scim.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    scim_export.write_text(json.dumps(_scim_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--scim-export", str(scim_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "SCIM authority directory written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["ownership_bindings"][0]["owner_team"] == "finance_ops"


def test_scim_authority_directory_adapter_reports_bounded_errors(tmp_path, capsys) -> None:
    scim_export = tmp_path / "scim.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    scim_export.write_text("[", encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--scim-export", str(scim_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "SCIM authority directory failed: scim_export must be JSON" in captured.err
    assert captured.out == ""
    assert not output.exists()


def _scim_payload() -> dict:
    return {
        "Users": [
            {
                "id": "finance-manager-1",
                "userName": "finance.manager@example.com",
                "displayName": "Finance Manager",
                "active": True,
            },
            {
                "id": "tenant-owner-1",
                "userName": "owner@example.com",
                "displayName": "Tenant Owner",
                "active": True,
            },
        ],
        "Groups": [
            {
                "id": "group-finance",
                "displayName": "finance_ops",
                "members": [{"value": "finance-manager-1"}],
            },
            {
                "id": "group-executive",
                "displayName": "executive_ops",
                "members": [{"value": "tenant-owner-1"}],
            },
        ],
    }


def _mapping_payload() -> dict:
    return {
        "role_assignments": [{
            "group": "finance_ops",
            "role": "financial_admin",
        }],
        "ownership_bindings": [{
            "resource_ref": "financial.send_payment",
            "owner_team": "finance_ops",
            "primary_owner_id": "finance-manager-1",
            "fallback_owner_id": "tenant-owner-1",
            "escalation_team": "executive_ops",
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
            "fallback_owner_id": "tenant-owner-1",
            "escalation_team": "executive_ops",
        }],
    }
