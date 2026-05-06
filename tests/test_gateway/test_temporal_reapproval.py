"""Gateway temporal reapproval tests.

Purpose: verify execution-time approval rechecks are runtime-owned, scoped,
role-covered, expiry-aware, revocation-aware, and schema-backed before dispatch.
Governance scope: approval age, expiry, tenant scope, execution scope, source
schedule binding, evidence refs, high-risk role coverage, and non-terminal
reapproval receipts.
Dependencies: gateway.temporal_reapproval and temporal reapproval receipt schema.
Invariants:
  - Valid high-risk approval grants can support dispatch.
  - Expired approval grants require reapproval.
  - Missing approver roles require reapproval.
  - Revoked, future, out-of-scope, wrong-tenant, or evidence-missing grants block dispatch.
  - Low-risk actions with no approval policy emit not-required receipts.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_reapproval import (
    ApprovalGrant,
    ReapprovalRequest,
    TemporalReapproval,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_reapproval_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for reapproval tests."""

    def now_utc(self) -> str:
        return NOW


def test_temporal_reapproval_approves_valid_high_risk_grants_schema_receipt() -> None:
    receipt = TemporalReapproval(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "approved"
    assert receipt.valid_approval_ids == ["approval:manager-1", "approval:finance-1"]
    assert receipt.valid_approval_count == 2
    assert receipt.approved_role_count == 2
    assert receipt.missing_approver_roles == []
    assert receipt.earliest_approval_expiry_at == "2026-05-05T14:00:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.terminal_closure_required is True


def test_temporal_reapproval_requires_fresh_approval_when_grant_expired() -> None:
    receipt = TemporalReapproval(FixedClock()).evaluate(
        _request(
            approval_grants=[
                _manager_grant(),
                replace(_finance_grant(), expires_at="2026-05-05T12:59:00+00:00"),
            ],
            reapproval_window_seconds=1800,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "reapproval_required"
    assert receipt.expired_approval_ids == ["approval:finance-1"]
    assert receipt.missing_approver_roles == ["finance-controller"]
    assert "approval:finance-1:approval_expired" in receipt.reapproval_reasons
    assert "minimum_approval_count_not_met" in receipt.reapproval_reasons
    assert receipt.reapproval_due_at == "2026-05-05T13:30:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["reapproval_required"] is True


def test_temporal_reapproval_requires_missing_role_coverage() -> None:
    receipt = TemporalReapproval(FixedClock()).evaluate(_request(approval_grants=[_manager_grant()]))

    assert receipt.status == "reapproval_required"
    assert receipt.valid_approval_ids == ["approval:manager-1"]
    assert receipt.valid_approval_count == 1
    assert receipt.approved_role_count == 1
    assert receipt.missing_approver_roles == ["finance-controller"]
    assert "missing_approver_role:finance-controller" in receipt.reapproval_reasons
    assert "minimum_approval_count_not_met" in receipt.reapproval_reasons


def test_temporal_reapproval_blocks_invalid_or_unsafe_grants() -> None:
    receipt = TemporalReapproval(FixedClock()).evaluate(
        _request(
            approval_grants=[
                replace(_manager_grant(), revoked_at="2026-05-05T12:55:00+00:00"),
                replace(_finance_grant(), tenant_id="tenant-other"),
                replace(_finance_grant("approval:wrong-scope"), approval_scope="invoice:other"),
                replace(_finance_grant("approval:future"), granted_at="2026-05-05T13:05:00+00:00"),
                replace(_finance_grant("approval:no-evidence"), evidence_refs=[]),
            ],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.revoked_approval_ids == ["approval:manager-1"]
    assert receipt.future_approval_ids == ["approval:future"]
    assert set(receipt.blocked_approval_ids) == {
        "approval:finance-1",
        "approval:wrong-scope",
        "approval:no-evidence",
    }
    assert "approval:manager-1:approval_revoked" in receipt.blocked_reasons
    assert "approval:finance-1:approval_tenant_mismatch" in receipt.blocked_reasons
    assert "approval:wrong-scope:approval_scope_mismatch" in receipt.blocked_reasons
    assert "approval:no-evidence:approval_evidence_refs_required" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False


def test_temporal_reapproval_marks_low_risk_action_not_required() -> None:
    receipt = TemporalReapproval(FixedClock()).evaluate(
        ReapprovalRequest(
            request_id="reapproval-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            execution_scope="reminder:follow-up",
            required_approver_roles=[],
            minimum_approval_count=0,
            approval_grants=[],
            max_approval_age_seconds=0,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.required_approver_roles == []
    assert receipt.approval_states == []
    assert receipt.reapproval_reasons == []
    assert receipt.blocked_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_reapproval_checked"] is False


def _request(
    *,
    approval_grants: list[ApprovalGrant] | None = None,
    reapproval_window_seconds: int = 0,
) -> ReapprovalRequest:
    return ReapprovalRequest(
        request_id="reapproval-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        execution_scope="invoice:123",
        required_approver_roles=["manager", "finance-controller"],
        minimum_approval_count=2,
        approval_grants=approval_grants or [_manager_grant(), _finance_grant()],
        max_approval_age_seconds=7200,
        reapproval_window_seconds=reapproval_window_seconds,
        source_schedule_receipt_id="scheduler-receipt-0123456789abcdef",
        source_temporal_receipt_id="temporal-receipt-0123456789abcdef",
    )


def _manager_grant() -> ApprovalGrant:
    return ApprovalGrant(
        approval_id="approval:manager-1",
        tenant_id="tenant-1",
        approver_id="user-manager-1",
        approver_role="manager",
        approval_scope="invoice:123",
        granted_at="2026-05-05T12:20:00+00:00",
        expires_at="2026-05-05T14:00:00+00:00",
        evidence_refs=["proof://approval/manager-1"],
        source_event_id="event-approval-manager-1",
    )


def _finance_grant(approval_id: str = "approval:finance-1") -> ApprovalGrant:
    return ApprovalGrant(
        approval_id=approval_id,
        tenant_id="tenant-1",
        approver_id="user-finance-1",
        approver_role="finance-controller",
        approval_scope="invoice:123",
        granted_at="2026-05-05T12:30:00+00:00",
        expires_at="2026-05-05T14:30:00+00:00",
        evidence_refs=["proof://approval/finance-1"],
        source_event_id="event-approval-finance-1",
    )
