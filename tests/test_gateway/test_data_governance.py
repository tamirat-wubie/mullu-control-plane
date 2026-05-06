"""Gateway data governance tests.

Purpose: verify sensitive data lifecycle gates and privacy read models.
Governance scope: classification, consent, encryption, retention, residency,
export, deletion workflow, legal hold, and schema anchoring.
Dependencies: gateway.data_governance and schemas/data_governance_snapshot.schema.json.
Invariants:
  - Sensitive persistence requires encryption and retention policy.
  - Export respects purpose and residency boundaries.
  - Legal hold blocks deletion.
  - Decisions are non-destructive lifecycle records.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.data_governance import (
    DataClassification,
    DataGovernanceRecord,
    DataGovernanceRegistry,
    DataLifecycleAction,
    DataLifecycleRequest,
    DataLifecycleVerdict,
    PrivacyBasis,
    data_governance_snapshot_to_json_dict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "data_governance_snapshot.schema.json"


def test_pii_consent_record_requires_consent_reference() -> None:
    with pytest.raises(ValueError, match="consent_ref_required_for_pii_consent"):
        _pii_record(consent_ref="")


def test_sensitive_persistence_requires_encryption_and_retention_policy() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    registry.register(_pii_record())

    no_encryption = registry.evaluate(_request(
        "req-persist-1",
        DataLifecycleAction.PERSIST,
        encryption_enabled=False,
        retention_policy_ref="retention://pii-365",
    ))
    no_retention = registry.evaluate(_request(
        "req-persist-2",
        DataLifecycleAction.PERSIST,
        encryption_enabled=True,
        retention_policy_ref="",
    ))
    allowed = registry.evaluate(_request(
        "req-persist-3",
        DataLifecycleAction.PERSIST,
        encryption_enabled=True,
        retention_policy_ref="retention://pii-365",
    ))

    assert no_encryption.verdict == DataLifecycleVerdict.DENY
    assert no_encryption.reason == "sensitive_persistence_requires_encryption"
    assert no_retention.verdict == DataLifecycleVerdict.DENY
    assert no_retention.reason == "sensitive_persistence_requires_retention_policy"
    assert allowed.verdict == DataLifecycleVerdict.ALLOW
    assert "encryption" in allowed.required_controls
    assert allowed.metadata["decision_is_not_deletion"] is True


def test_export_enforces_purpose_and_residency_review() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    registry.register(_pii_record())

    wrong_purpose = registry.evaluate(_request(
        "req-export-1",
        DataLifecycleAction.EXPORT,
        purpose="marketing",
        target_residency="us",
    ))
    cross_residency = registry.evaluate(_request(
        "req-export-2",
        DataLifecycleAction.EXPORT,
        purpose="customer_support",
        target_residency="eu",
    ))
    sensitive_same_residency = registry.evaluate(_request(
        "req-export-3",
        DataLifecycleAction.EXPORT,
        purpose="customer_support",
        target_residency="us",
    ))

    assert wrong_purpose.verdict == DataLifecycleVerdict.DENY
    assert wrong_purpose.reason == "purpose_limitation_denied"
    assert cross_residency.verdict == DataLifecycleVerdict.REVIEW
    assert cross_residency.reason == "cross_residency_export_requires_review"
    assert sensitive_same_residency.verdict == DataLifecycleVerdict.REVIEW
    assert sensitive_same_residency.reason == "sensitive_export_requires_review"


def test_legal_hold_blocks_deletion_even_after_retention_window() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    record = registry.register(_pii_record())
    held = registry.place_legal_hold(data_id=record.data_id, evidence_refs=("legal://hold-001",))

    decision = registry.evaluate(_request(
        "req-delete-1",
        DataLifecycleAction.DELETE,
        requested_at="2028-05-07T00:00:00Z",
    ))

    assert held.legal_hold is True
    assert "legal://hold-001" in held.evidence_refs
    assert decision.verdict == DataLifecycleVerdict.DENY
    assert decision.reason == "legal_hold_blocks_deletion"
    assert "legal_hold_release" in decision.required_controls


def test_deletion_before_retention_expiry_requires_review_not_deletion() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    registry.register(_pii_record())

    decision = registry.evaluate(_request(
        "req-delete-2",
        DataLifecycleAction.DELETE,
        requested_at="2026-06-01T00:00:00Z",
    ))

    assert decision.verdict == DataLifecycleVerdict.REVIEW
    assert decision.reason == "retention_window_not_expired"
    assert decision.metadata["decision_is_not_deletion"] is True


def test_public_export_can_be_allowed_with_audit_controls() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    registry.register(DataGovernanceRecord(
        data_id="pub-001",
        tenant_id="tenant-a",
        classification=DataClassification.PUBLIC,
        purpose="docs",
        source_event_id="event-002",
        created_at="2026-05-05T00:00:00Z",
        retention_until="2026-06-05T00:00:00Z",
        delete_after="2026-06-06T00:00:00Z",
        privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        data_residency="global",
        encrypted=False,
    ))

    decision = registry.evaluate(DataLifecycleRequest(
        request_id="req-public-export",
        data_id="pub-001",
        tenant_id="tenant-a",
        action=DataLifecycleAction.EXPORT,
        requested_at="2026-05-06T00:00:00Z",
        actor_id="operator",
        purpose="docs",
        target_residency="global",
    ))

    assert decision.verdict == DataLifecycleVerdict.ALLOW
    assert decision.reason == "export_controls_satisfied"
    assert decision.required_controls == ("audit_export",)


def test_data_governance_snapshot_schema_exposes_lifecycle_contract() -> None:
    registry = DataGovernanceRegistry(clock=_clock)
    registry.register(_pii_record())
    registry.evaluate(_request(
        "req-persist-1",
        DataLifecycleAction.PERSIST,
        encryption_enabled=True,
        retention_policy_ref="retention://pii-365",
    ))
    snapshot = registry.snapshot(snapshot_id="data-governance-snapshot-001")
    payload = data_governance_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:data-governance-snapshot:1"
    assert "pii" in schema["$defs"]["classification"]["enum"]
    assert schema["$defs"]["decision"]["properties"]["metadata"]["properties"]["decision_is_not_deletion"]["const"] is True
    assert payload["records"][0]["record_hash"]
    assert payload["snapshot_hash"]


def _clock() -> str:
    return "2026-05-05T12:00:00Z"


def _pii_record(*, consent_ref: str = "consent://customer-001") -> DataGovernanceRecord:
    return DataGovernanceRecord(
        data_id="mem-001",
        tenant_id="tenant-a",
        classification=DataClassification.PII,
        purpose="customer_support",
        source_event_id="trace-001",
        created_at="2026-05-05T00:00:00Z",
        retention_until="2027-05-05T00:00:00Z",
        delete_after="2027-05-06T00:00:00Z",
        privacy_basis=PrivacyBasis.CONSENT,
        data_residency="us",
        encrypted=True,
        consent_ref=consent_ref,
        evidence_refs=("trace://001",),
    )


def _request(
    request_id: str,
    action: DataLifecycleAction,
    *,
    requested_at: str = "2026-05-06T00:00:00Z",
    purpose: str = "",
    target_residency: str = "",
    encryption_enabled: bool = False,
    retention_policy_ref: str = "",
) -> DataLifecycleRequest:
    return DataLifecycleRequest(
        request_id=request_id,
        data_id="mem-001",
        tenant_id="tenant-a",
        action=action,
        requested_at=requested_at,
        actor_id="operator-1",
        purpose=purpose,
        target_residency=target_residency,
        encryption_enabled=encryption_enabled,
        retention_policy_ref=retention_policy_ref,
        evidence_refs=("request://data-lifecycle",),
    )
