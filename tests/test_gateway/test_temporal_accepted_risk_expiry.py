"""Gateway temporal accepted-risk expiry tests.

Purpose: verify accepted-risk expiry receipts are runtime-owned, scope-aware,
source-bound, evidence-backed, and schema-backed before dispatch.
Governance scope: accepted-risk lifecycle, expiry, tenant and command scope,
review obligation, evidence refs, high-risk source receipt binding, and
non-terminal accepted-risk expiry receipts.
Dependencies: gateway.temporal_accepted_risk_expiry and temporal
accepted-risk expiry receipt schema.
Invariants:
  - Active accepted risk may authorize dispatch only before expiry.
  - Expired accepted risk cannot authorize dispatch.
  - Revoked, future-dated, wrong-scope, or evidence-missing records fail closed.
  - High-risk accepted-risk reuse binds temporal and causal source receipts.
  - Low-risk policies may mark accepted-risk expiry control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_accepted_risk_expiry import (
    AcceptedRiskGrant,
    TemporalAcceptedRiskExpiry,
    TemporalAcceptedRiskPolicy,
    TemporalAcceptedRiskRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_accepted_risk_expiry_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for accepted-risk tests."""

    def now_utc(self) -> str:
        return NOW


def test_accepted_risk_expiry_allows_high_risk_active_unexpired_record() -> None:
    receipt = TemporalAcceptedRiskExpiry(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "risk_active"
    assert receipt.risk_state == "active"
    assert receipt.risk_id == "accepted-risk-1"
    assert receipt.scope == "effect_reconciliation"
    assert receipt.disposition == "active"
    assert receipt.accepted_age_seconds == 1800
    assert receipt.seconds_until_expiry == 5400
    assert receipt.accepted_risk_evidence_refs == ["proof://accepted-risk/evidence-1"]
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["source_receipts_checked"] is True
    assert receipt.terminal_closure_required is True


def test_accepted_risk_expiry_blocks_expired_record() -> None:
    receipt = TemporalAcceptedRiskExpiry(FixedClock()).evaluate(
        _request(accepted_risk=replace(_risk(), expires_at="2026-05-05T14:00:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "expired"
    assert receipt.risk_state == "expired"
    assert receipt.seconds_until_expiry == 0
    assert receipt.accepted_age_seconds == 1800
    assert "accepted_risk_expired" in receipt.blocked_reasons
    assert "accepted_risk_dispatch_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["expiry_checked"] is True


def test_accepted_risk_expiry_blocks_wrong_scope_missing_evidence_and_sources() -> None:
    receipt = TemporalAcceptedRiskExpiry(FixedClock()).evaluate(
        _request(
            accepted_risk=replace(
                _risk(),
                tenant_id="tenant-other",
                command_id="command-other",
                action_type="refund_payment",
                scope="provider_uncertainty",
                evidence_refs=[],
                source_terminal_closure_id="",
            ),
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_causal_order_receipt_id="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.risk_state == "wrong_scope"
    assert "accepted_risk_tenant_mismatch" in receipt.blocked_reasons
    assert "accepted_risk_command_mismatch" in receipt.blocked_reasons
    assert "accepted_risk_action_type_mismatch" in receipt.blocked_reasons
    assert "accepted_risk_scope_not_allowed" in receipt.blocked_reasons
    assert "accepted_risk_evidence_refs_required" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_causal_order_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_terminal_closure_required_for_high_risk" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["source_receipts_checked"] is False


def test_accepted_risk_expiry_blocks_future_or_stale_accepted_risk() -> None:
    receipt = TemporalAcceptedRiskExpiry(FixedClock()).evaluate(
        _request(
            accepted_risk=replace(
                _risk(),
                accepted_at="2026-05-05T15:00:00+00:00",
                expires_at="2026-05-05T16:00:00+00:00",
            ),
            policy=replace(_policy(), max_acceptance_age_seconds=100),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.risk_state == "future"
    assert receipt.accepted_age_seconds == 0
    assert receipt.seconds_until_expiry == 5400
    assert "accepted_risk_future" in receipt.blocked_reasons
    assert "accepted_risk_too_old" not in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.warning_reasons == []


def test_accepted_risk_expiry_marks_low_risk_action_not_required() -> None:
    receipt = TemporalAcceptedRiskExpiry(FixedClock()).evaluate(
        TemporalAcceptedRiskRequest(
            request_id="accepted-risk-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            policy=replace(_policy(), requires_accepted_risk_check=False),
            evidence_refs=[],
            accepted_risk=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.risk_state == "not_required"
    assert receipt.accepted_risk_required is False
    assert receipt.risk_id == ""
    assert receipt.accepted_age_seconds == 0
    assert receipt.seconds_until_expiry == 0
    assert receipt.blocked_reasons == []
    assert receipt.warning_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["accepted_risk_checked"] is False


def _request(
    *,
    accepted_risk: AcceptedRiskGrant | None = None,
    policy: TemporalAcceptedRiskPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_causal_order_receipt_id: str = "temporal-causal-order-receipt-0123456789abcdef",
) -> TemporalAcceptedRiskRequest:
    return TemporalAcceptedRiskRequest(
        request_id="accepted-risk-expiry-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://accepted-risk/policy-1"],
        accepted_risk=accepted_risk if accepted_risk is not None else _risk(),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_causal_order_receipt_id=source_causal_order_receipt_id,
        source_reapproval_receipt_id="temporal-reapproval-receipt-0123456789abcdef",
    )


def _policy() -> TemporalAcceptedRiskPolicy:
    return TemporalAcceptedRiskPolicy(
        policy_id="accepted-risk-policy-1",
        tenant_id="tenant-1",
        allowed_scopes=["effect_reconciliation", "verification_gap"],
        allowed_action_types=["vendor_payment"],
        max_acceptance_age_seconds=7200,
        requires_accepted_risk_check=True,
        high_risk_requires_accepted_risk_check=True,
    )


def _risk() -> AcceptedRiskGrant:
    return AcceptedRiskGrant(
        risk_id="accepted-risk-1",
        tenant_id="tenant-1",
        command_id="command-1",
        action_type="vendor_payment",
        scope="effect_reconciliation",
        disposition="active",
        accepted_at="2026-05-05T14:00:00+00:00",
        expires_at="2026-05-05T16:00:00+00:00",
        case_id="case-1",
        owner_id="risk-owner-1",
        accepted_by="approver-1",
        review_obligation_id="review-obligation-1",
        evidence_refs=["proof://accepted-risk/evidence-1"],
        execution_id="execution-1",
        reconciliation_id="reconciliation-1",
        source_terminal_closure_id="terminal-closure-accepted-risk-0123456789abcdef",
    )
