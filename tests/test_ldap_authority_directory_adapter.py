"""LDAP authority directory adapter tests.

Purpose: verify LDAP users/groups export conversion into normalized authority
directory JSON.
Governance scope: explicit mapping rules, source hashes, rejected references,
and compatibility with the static authority directory sync adapter.
"""

from __future__ import annotations

import json

from scripts.ldap_authority_directory_adapter import (
    convert_ldap_authority_directory,
    main,
    write_ldap_authority_directory,
)
from scripts.sync_authority_directory import sync_static_authority_directory


def test_ldap_authority_directory_adapter_emits_syncable_directory(tmp_path) -> None:
    ldap_export = tmp_path / "ldap.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    ldap_export.write_text(json.dumps(_ldap_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    payload = convert_ldap_authority_directory(
        tenant_id="tenant-1",
        ldap_export_path=ldap_export,
        mapping_path=mapping,
        source_ref="ldap://directory.example.com/groups/export/2026-04-29T12:00:00Z",
    )
    written = write_ldap_authority_directory(payload, output)
    batch, receipt = sync_static_authority_directory(written)

    assert payload["source_system"] == "ldap_export"
    assert payload["source_hash"].startswith("sha256:")
    assert payload["people"][0]["identity_id"] == "uid=finance-manager,ou=people,dc=example,dc=com"
    assert payload["teams"][0]["team_id"] == "cn=finance_ops,ou=groups,dc=example,dc=com"
    assert payload["role_assignments"][0]["role"] == "financial_admin"
    assert batch["ownership_bindings"][0]["resource_ref"] == "financial.send_payment"
    assert batch["approval_policies"][0]["required_approver_count"] == 2
    assert receipt.rejected_record_count == 0


def test_ldap_authority_directory_adapter_rejects_missing_dn_reference(tmp_path) -> None:
    ldap_export = tmp_path / "ldap.json"
    mapping = tmp_path / "mapping.json"
    payload = _mapping_payload()
    payload["ownership_bindings"][0]["primary_owner_id"] = "uid=missing,ou=people,dc=example,dc=com"
    ldap_export.write_text(json.dumps(_ldap_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(payload), encoding="utf-8")

    directory = convert_ldap_authority_directory(
        tenant_id="tenant-1",
        ldap_export_path=ldap_export,
        mapping_path=mapping,
    )

    assert directory["ownership_bindings"] == ()
    assert directory["approval_policies"][0]["policy_id"] == "payment-high-risk"
    assert directory["rejected_records"][0]["record_type"] == "ownership_binding"
    assert directory["rejected_records"][0]["reason"] == "owner_not_found"


def test_ldap_authority_directory_adapter_cli_writes_output(tmp_path, capsys) -> None:
    ldap_export = tmp_path / "ldap.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    ldap_export.write_text(json.dumps(_ldap_payload()), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--ldap-export", str(ldap_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "LDAP authority directory written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["ownership_bindings"][0]["owner_team"] == "cn=finance_ops,ou=groups,dc=example,dc=com"


def test_ldap_authority_directory_adapter_reports_bounded_errors(tmp_path, capsys) -> None:
    ldap_export = tmp_path / "ldap.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "authority-directory.json"
    ldap_export.write_text(json.dumps({"directory_ref": "directory.example.com", "users": [], "groups": {}}), encoding="utf-8")
    mapping.write_text(json.dumps(_mapping_payload()), encoding="utf-8")

    exit_code = main([
        "--tenant-id", "tenant-1",
        "--ldap-export", str(ldap_export),
        "--mapping", str(mapping),
        "--output", str(output),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "LDAP authority directory failed: LDAP groups must be a list" in captured.err
    assert captured.out == ""
    assert not output.exists()


def _ldap_payload() -> dict:
    return {
        "directory_ref": "directory.example.com",
        "users": [
            {
                "dn": "uid=finance-manager,ou=people,dc=example,dc=com",
                "uid": "finance-manager",
                "cn": "Finance Manager",
                "mail": "finance.manager@example.com",
                "active": True,
            },
            {
                "dn": "uid=tenant-owner,ou=people,dc=example,dc=com",
                "uid": "tenant-owner",
                "cn": "Tenant Owner",
                "mail": "tenant.owner@example.com",
                "active": True,
            },
        ],
        "groups": [
            {
                "dn": "cn=finance_ops,ou=groups,dc=example,dc=com",
                "cn": "finance_ops",
                "display_name": "Finance Ops",
                "members": ["uid=finance-manager,ou=people,dc=example,dc=com"],
            },
            {
                "dn": "cn=executive_ops,ou=groups,dc=example,dc=com",
                "cn": "executive_ops",
                "display_name": "Executive Ops",
                "members": ["uid=tenant-owner,ou=people,dc=example,dc=com"],
            },
        ],
    }


def _mapping_payload() -> dict:
    return {
        "role_assignments": [{
            "group_dn": "cn=finance_ops,ou=groups,dc=example,dc=com",
            "role": "financial_admin",
        }],
        "ownership_bindings": [{
            "resource_ref": "financial.send_payment",
            "owner_team": "cn=finance_ops,ou=groups,dc=example,dc=com",
            "primary_owner_id": "uid=finance-manager,ou=people,dc=example,dc=com",
            "fallback_owner_id": "uid=tenant-owner,ou=people,dc=example,dc=com",
            "escalation_team": "cn=executive_ops,ou=groups,dc=example,dc=com",
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
            "fallback_owner_id": "uid=tenant-owner,ou=people,dc=example,dc=com",
            "escalation_team": "cn=executive_ops,ou=groups,dc=example,dc=com",
        }],
    }
