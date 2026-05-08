"""Gateway temporal lease window tests.

Purpose: verify lease receipts are runtime-owned, scope-aware, expiry-aware,
renewal-aware, fencing-token-backed, source-bound, and schema-backed before
worker dispatch.
Governance scope: lease timing, tenant scope, command scope, resource scope,
worker ownership, evidence refs, high-risk source binding, and non-terminal
temporal lease window receipts.
Dependencies: gateway.temporal_lease_window and temporal lease window receipt
schema.
Invariants:
  - Active leases may dispatch only with matching scope and fencing evidence.
  - Near-expiry leases warn while preserving dispatch admission.
  - Expired, released, revoked, and malformed leases fail closed.
  - Low-risk policies may mark lease control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_lease_window import (
    LeaseSnapshot,
    LeaseWindowPolicy,
    LeaseWindowRequest,
    TemporalLeaseWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_lease_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for lease window tests."""

    def now_utc(self) -> str:
        return NOW


def test_lease_window_allows_active_scoped_lease() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "lease_active"
    assert receipt.lease_state == "active"
    assert receipt.lease_id == "lease-1"
    assert receipt.resource_id == "finance/approval/packet-1"
    assert receipt.fencing_token == "fence-token-1"
    assert receipt.sequence == 7
    assert receipt.lease_age_seconds == 1800
    assert receipt.seconds_until_expiry == 1800
    assert "lease_admission" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_lease_window_warns_when_lease_is_inside_renewal_grace_window() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(
        _request(snapshot=replace(_snapshot(), lease_expires_at="2026-05-05T14:35:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "lease_expiring"
    assert receipt.lease_state == "expiring"
    assert receipt.seconds_until_expiry == 300
    assert receipt.warning_reasons == ["lease_renewal_required"]
    assert "lease_renewal_warning" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["renewal_required"] is True


def test_lease_window_blocks_expired_lease_without_dispatch() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(
        _request(snapshot=replace(_snapshot(), lease_expires_at="2026-05-05T14:30:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "lease_expired"
    assert receipt.lease_state == "expired"
    assert receipt.seconds_until_expiry == 0
    assert receipt.blocked_reasons == []
    assert "lease_expiry_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["lease_expiry_checked"] is True


def test_lease_window_blocks_scope_mismatch_missing_evidence_fencing_and_closed_lease() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(
        _request(
            resource_id="finance/forbidden/packet-1",
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            snapshot=replace(
                _snapshot(),
                tenant_id="tenant-other",
                command_id="command-other",
                resource_id="finance/approval/packet-other",
                worker_id="worker-other",
                lease_owner_id="owner-other",
                acquired_at="2026-05-05T12:00:00+00:00",
                lease_expires_at="2026-05-05T16:00:00+00:00",
                fencing_token="",
                sequence=0,
                released=True,
                revoked=True,
                evidence_refs=[],
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.lease_state == "released"
    assert "resource_not_allowed" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "snapshot_tenant_mismatch" in receipt.blocked_reasons
    assert "snapshot_command_mismatch" in receipt.blocked_reasons
    assert "snapshot_resource_mismatch" in receipt.blocked_reasons
    assert "snapshot_worker_mismatch" in receipt.blocked_reasons
    assert "snapshot_lease_owner_mismatch" in receipt.blocked_reasons
    assert "lease_evidence_refs_required" in receipt.blocked_reasons
    assert "fencing_token_required" in receipt.blocked_reasons
    assert "fencing_sequence_positive_required" in receipt.blocked_reasons
    assert "lease_released" in receipt.blocked_reasons
    assert "lease_revoked" in receipt.blocked_reasons
    assert "lease_window_exceeds_policy" in receipt.blocked_reasons
    assert "lease_age_exceeds_policy" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_lease_window_blocks_invalid_temporal_order() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                acquired_at="2026-05-05T15:00:00+00:00",
                last_renewed_at="2026-05-05T14:00:00+00:00",
                lease_expires_at="2026-05-05T14:45:00+00:00",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.lease_state == "invalid"
    assert "lease_acquired_in_future" in receipt.blocked_reasons
    assert "lease_renewal_order_invalid" in receipt.blocked_reasons
    assert "lease_window_invalid" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False


def test_lease_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalLeaseWindow(FixedClock()).evaluate(
        LeaseWindowRequest(
            request_id="lease-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="read_summary",
            risk_level="low",
            resource_id="finance/approval/packet-1",
            worker_id="worker-1",
            lease_owner_id="owner-1",
            policy=replace(_policy(), requires_lease_window=False, high_risk_requires_lease_window=False),
            evidence_refs=[],
            snapshot=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.lease_state == "not_required"
    assert receipt.lease_required is False
    assert receipt.lease_id == ""
    assert receipt.resource_id == ""
    assert receipt.sequence == 0
    assert receipt.blocked_reasons == []
    assert receipt.warning_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["lease_checked"] is False


def _request(
    *,
    resource_id: str = "finance/approval/packet-1",
    snapshot: LeaseSnapshot | None = None,
    policy: LeaseWindowPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_scheduler_receipt_id: str = "temporal-scheduler-receipt-0123456789abcdef",
    source_retry_window_receipt_id: str = "temporal-retry-window-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> LeaseWindowRequest:
    return LeaseWindowRequest(
        request_id="lease-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="finance_packet_dispatch",
        risk_level="high",
        resource_id=resource_id,
        worker_id="worker-1",
        lease_owner_id="owner-1",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://lease/policy-1"],
        snapshot=snapshot if snapshot is not None else _snapshot(),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_scheduler_receipt_id=source_scheduler_receipt_id,
        source_retry_window_receipt_id=source_retry_window_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> LeaseWindowPolicy:
    return LeaseWindowPolicy(
        policy_id="lease-policy-1",
        tenant_id="tenant-1",
        scope_id="finance-worker",
        allowed_resource_patterns=["finance/approval/*"],
        max_lease_seconds=7200,
        renewal_grace_seconds=600,
        requires_lease_window=True,
        high_risk_requires_lease_window=True,
    )


def _snapshot() -> LeaseSnapshot:
    return LeaseSnapshot(
        lease_id="lease-1",
        tenant_id="tenant-1",
        command_id="command-1",
        resource_id="finance/approval/packet-1",
        worker_id="worker-1",
        lease_owner_id="owner-1",
        acquired_at="2026-05-05T14:00:00+00:00",
        last_renewed_at="2026-05-05T14:15:00+00:00",
        lease_expires_at="2026-05-05T15:00:00+00:00",
        fencing_token="fence-token-1",
        sequence=7,
        released=False,
        revoked=False,
        evidence_refs=["proof://lease/lease-1"],
    )
