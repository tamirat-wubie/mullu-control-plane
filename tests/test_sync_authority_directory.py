"""Static authority directory sync tests.

Purpose: verify deterministic static directory normalization and receipts.
Governance scope: source hashing, ownership/policy/escalation normalization,
duplicate rejection, and persistence of sync evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.authority_obligation_mesh import InMemoryAuthorityObligationMeshStore
import scripts.sync_authority_directory as sync_authority_directory
from scripts.sync_authority_directory import (
    apply_static_authority_directory,
    main,
    mark_receipt_persisted,
    sync_static_authority_directory,
    write_normalized_batch,
    write_sync_receipt,
)


def test_static_authority_directory_sync_normalizes_json_source(tmp_path) -> None:
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")

    batch, receipt = sync_static_authority_directory(source)

    assert batch["tenant_id"] == "tenant-1"
    assert batch["source_hash"].startswith("sha256:")
    assert batch["ownership_bindings"][0]["tenant_id"] == "tenant-1"
    assert batch["approval_policies"][0]["required_roles"] == ["financial_admin"]
    assert receipt.applied_ownership_count == 1
    assert receipt.applied_approval_policy_count == 1
    assert receipt.applied_escalation_policy_count == 1
    assert receipt.apply_mode == "dry_run"
    assert receipt.persisted is False
    assert receipt.rejected_record_count == 0
    assert "authority:ownership_read_model" in receipt.evidence_refs


def test_static_authority_directory_sync_parses_bounded_yaml_source(tmp_path) -> None:
    source = tmp_path / "authority-directory.yaml"
    source.write_text(
        "\n".join([
            "tenant_id: tenant-1",
            "source_system: static_yaml",
            "source_ref: file://authority-directory.yaml",
            "ownership_bindings:",
            "  - resource_ref: financial.send_payment",
            "    owner_team: finance_ops",
            "    primary_owner_id: finance-manager-1",
            "    fallback_owner_id: tenant-owner-1",
            "    escalation_team: executive_ops",
            "approval_policies:",
            "  - policy_id: payment-high-risk",
            "    capability: financial.send_payment",
            "    risk_tier: high",
            "    required_roles: [financial_admin]",
            "    required_approver_count: 2",
            "    separation_of_duty: true",
            "    timeout_seconds: 300",
            "    escalation_policy_id: finance-escalation",
            "escalation_policies:",
            "  - policy_id: finance-escalation",
            "    notify_after_seconds: 300",
            "    escalate_after_seconds: 900",
            "    incident_after_seconds: 3600",
            "    fallback_owner_id: tenant-owner-1",
            "    escalation_team: executive_ops",
        ]),
        encoding="utf-8",
    )

    batch, receipt = sync_static_authority_directory(source)

    assert batch["batch_id"].startswith("directory-batch-")
    assert batch["approval_policies"][0]["separation_of_duty"] is True
    assert batch["approval_policies"][0]["required_approver_count"] == 2
    assert batch["escalation_policies"][0]["tenant_id"] == "tenant-1"
    assert receipt.receipt_id.startswith("authority-directory-sync-")
    assert receipt.source_ref == "file://authority-directory.yaml"
    assert receipt.rejected_records == ()


def test_static_authority_directory_sync_rejects_duplicate_policy_keys(tmp_path) -> None:
    payload = _directory_payload()
    payload["approval_policies"].append(dict(payload["approval_policies"][0]))
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    batch, receipt = sync_static_authority_directory(source)

    assert len(batch["approval_policies"]) == 1
    assert receipt.applied_approval_policy_count == 1
    assert receipt.rejected_record_count == 1
    assert receipt.rejected_records[0]["record_type"] == "approval_policy"
    assert receipt.rejected_records[0]["reason"] == "duplicate_key"


def test_static_authority_directory_apply_writes_accepted_records_to_store(tmp_path) -> None:
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")
    batch, receipt = sync_static_authority_directory(source)
    store = InMemoryAuthorityObligationMeshStore()

    apply_static_authority_directory(batch, store)

    assert receipt.rejected_record_count == 0
    assert store.load_ownership("tenant-1", "financial.send_payment") is not None
    assert store.load_approval_policy("tenant-1", "financial.send_payment", "high") is not None
    assert store.load_escalation_policy("tenant-1", "finance-escalation") is not None
    assert len(store.list_ownership()) == 1
    assert len(store.list_approval_policies()) == 1
    assert len(store.list_escalation_policies()) == 1


def test_static_authority_directory_apply_receipt_marks_persisted(tmp_path) -> None:
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")
    batch, receipt = sync_static_authority_directory(source)
    store = InMemoryAuthorityObligationMeshStore()

    apply_static_authority_directory(batch, store)
    persisted = mark_receipt_persisted(receipt)

    assert persisted.receipt_id == receipt.receipt_id
    assert persisted.apply_mode == "apply"
    assert persisted.persisted is True
    assert persisted.applied_ownership_count == receipt.applied_ownership_count
    assert persisted.rejected_records == receipt.rejected_records


def test_static_authority_directory_apply_omits_rejected_duplicate_policy(tmp_path) -> None:
    payload = _directory_payload()
    duplicate = dict(payload["approval_policies"][0])
    duplicate["required_approver_count"] = 99
    payload["approval_policies"].append(duplicate)
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    batch, receipt = sync_static_authority_directory(source)
    store = InMemoryAuthorityObligationMeshStore()

    apply_static_authority_directory(batch, store)
    policy = store.load_approval_policy("tenant-1", "financial.send_payment", "high")

    assert receipt.rejected_record_count == 1
    assert policy is not None
    assert policy.required_approver_count == 2
    assert len(store.list_approval_policies()) == 1


def test_static_authority_directory_sync_writes_receipt_and_cli_output(tmp_path, capsys) -> None:
    source = tmp_path / "authority-directory.json"
    output = tmp_path / "receipt.json"
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")
    _batch, receipt = sync_static_authority_directory(source)

    written = write_sync_receipt(receipt, output)
    exit_code = main([str(source), "--receipt-output", str(output)])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert written == output
    assert exit_code == 0
    assert "authority directory sync receipt written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["applied_ownership_count"] == 1


def test_static_authority_directory_sync_writes_replayable_normalized_batch(tmp_path, capsys) -> None:
    source = tmp_path / "authority-directory.json"
    batch_output = tmp_path / "normalized-batch.json"
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")
    batch, _receipt = sync_static_authority_directory(source)

    written = write_normalized_batch(batch, batch_output)
    exit_code = main([str(source), "--batch-output", str(batch_output)])
    captured = capsys.readouterr()
    loaded = json.loads(batch_output.read_text(encoding="utf-8"))

    assert written == batch_output
    assert exit_code == 0
    assert "authority directory normalized batch written" in captured.out
    assert loaded["tenant_id"] == "tenant-1"
    assert loaded["ownership_bindings"][0]["tenant_id"] == "tenant-1"
    assert loaded["approval_policies"][0]["policy_id"] == "payment-high-risk"


def test_static_authority_directory_cli_apply_persists_records_and_receipt(tmp_path, capsys, monkeypatch) -> None:
    source = tmp_path / "authority-directory.json"
    output = tmp_path / "receipt.json"
    store = InMemoryAuthorityObligationMeshStore()
    source.write_text(json.dumps(_directory_payload()), encoding="utf-8")
    monkeypatch.setattr(sync_authority_directory, "build_authority_obligation_mesh_store_from_env", lambda: store)

    exit_code = main([str(source), "--receipt-output", str(output), "--apply"])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "authority directory sync receipt written" in captured.out
    assert loaded["apply_mode"] == "apply"
    assert loaded["persisted"] is True
    assert store.load_ownership("tenant-1", "financial.send_payment") is not None
    assert store.load_approval_policy("tenant-1", "financial.send_payment", "high") is not None
    assert store.load_escalation_policy("tenant-1", "finance-escalation") is not None


def test_static_authority_directory_sync_resolves_relative_source_ref(tmp_path, monkeypatch) -> None:
    payload = _directory_payload()
    payload.pop("source_ref")
    source = tmp_path / "authority-directory.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    batch, receipt = sync_static_authority_directory(Path("authority-directory.json"))

    assert batch["source_ref"].startswith("file:///")
    assert batch["source_ref"].endswith("authority-directory.json")
    assert receipt.source_ref == batch["source_ref"]
    assert receipt.source_hash == batch["source_hash"]


def test_static_authority_directory_cli_reports_bounded_parser_error(tmp_path, capsys) -> None:
    source = tmp_path / "authority-directory.yaml"
    output = tmp_path / "receipt.json"
    source.write_text("tenant_id: tenant-1\nraw-secret-token\n", encoding="utf-8")

    exit_code = main([str(source), "--receipt-output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "authority directory sync failed: unsupported static directory YAML line" in captured.err
    assert "raw-secret-token" not in captured.err
    assert captured.out == ""
    assert not output.exists()


def _directory_payload() -> dict:
    return {
        "tenant_id": "tenant-1",
        "source_system": "static_yaml",
        "source_ref": "file://authority-directory.yaml",
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
