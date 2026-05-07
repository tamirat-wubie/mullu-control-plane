"""Gateway temporal causal-order tests.

Purpose: verify causal-order receipts are runtime-owned, tenant-scoped,
source-bound, event-ordered, and schema-backed before dispatch.
Governance scope: required timestamped events, predecessor edges, tenant and
command scope, high-risk source receipts, evidence refs, and non-terminal
causal-order receipts.
Dependencies: gateway.temporal_causal_order and temporal causal-order receipt
schema.
Invariants:
  - High-risk dispatch requires complete ordered causal events.
  - Missing, future, mismatched, or predecessor-invalid events block dispatch.
  - Out-of-order timestamps block dispatch before worker execution.
  - Low-risk policies may explicitly mark causal-order control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_causal_order import (
    TemporalCausalEvent,
    TemporalCausalOrder,
    TemporalCausalOrderPolicy,
    TemporalCausalOrderRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_causal_order_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"
ORDERED_EVENT_TYPES = [
    "request_received",
    "identity_verified",
    "risk_classified",
    "temporal_checked",
    "reapproval_checked",
    "dispatch_window_checked",
    "budget_window_checked",
    "dispatch_ready",
]


class FixedClock:
    """Deterministic wall-clock provider for causal-order tests."""

    def now_utc(self) -> str:
        return NOW


def test_causal_order_allows_high_risk_dispatch_when_required_events_are_ordered() -> None:
    receipt = TemporalCausalOrder(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "order_valid"
    assert receipt.order_state == "valid"
    assert receipt.event_count == 8
    assert receipt.required_event_types == ORDERED_EVENT_TYPES
    assert receipt.ordered_event_types == ORDERED_EVENT_TYPES
    assert receipt.observed_event_types == ORDERED_EVENT_TYPES
    assert receipt.missing_event_types == []
    assert receipt.out_of_order_event_ids == []
    assert receipt.invalid_event_ids == []
    assert receipt.earliest_event_at == "2026-05-05T14:00:00+00:00"
    assert receipt.latest_event_at == "2026-05-05T14:07:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["source_receipts_checked"] is True
    assert receipt.terminal_closure_required is True


def test_causal_order_blocks_missing_required_event_type() -> None:
    receipt = TemporalCausalOrder(FixedClock()).evaluate(
        _request(events=[event for event in _events() if event.event_type != "dispatch_ready"])
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.order_state == "missing"
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.missing_event_types == ["dispatch_ready"]
    assert "required_event_missing:dispatch_ready" in receipt.blocked_reasons
    assert "causal_dispatch_block" in receipt.required_controls
    assert receipt.out_of_order_event_ids == []
    assert receipt.invalid_event_ids == []


def test_causal_order_blocks_out_of_order_runtime_timestamps() -> None:
    events = [
        replace(event, occurred_at="2026-05-05T14:04:30+00:00")
        if event.event_type == "budget_window_checked"
        else event
        for event in _events()
    ]
    receipt = TemporalCausalOrder(FixedClock()).evaluate(_request(events=events))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.order_state == "out_of_order"
    assert "evt-budget-window-checked" in receipt.out_of_order_event_ids
    assert "predecessor_order_violation:evt-budget-window-checked:evt-dispatch-window-checked" in receipt.blocked_reasons
    assert "causal_order_violation:dispatch_window_checked:budget_window_checked" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert "causal_dispatch_block" in receipt.required_controls


def test_causal_order_blocks_invalid_scope_future_event_predecessor_and_missing_sources() -> None:
    events = [
        replace(_events()[0], tenant_id="tenant-other", evidence_refs=[]),
        replace(_events()[1], command_id="command-other"),
        replace(_events()[2], occurred_at="2026-05-05T15:00:00+00:00"),
        replace(_events()[3], predecessor_event_ids=["evt-missing"]),
    ]
    receipt = TemporalCausalOrder(FixedClock()).evaluate(
        _request(
            events=events,
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_dispatch_window_receipt_id="",
            source_budget_window_receipt_id="",
            source_reapproval_receipt_id="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.order_state == "missing"
    assert "evt-request-received" in receipt.invalid_event_ids
    assert "evt-identity-verified" in receipt.invalid_event_ids
    assert "evt-risk-classified" in receipt.invalid_event_ids
    assert "evt-temporal-checked" in receipt.invalid_event_ids
    assert "event_tenant_mismatch:evt-request-received" in receipt.blocked_reasons
    assert "event_command_mismatch:evt-identity-verified" in receipt.blocked_reasons
    assert "event_future:evt-risk-classified" in receipt.blocked_reasons
    assert "event_predecessor_missing:evt-temporal-checked:evt-missing" in receipt.blocked_reasons
    assert "event_evidence_refs_required:evt-request-received" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_dispatch_window_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_budget_window_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["source_receipts_checked"] is False


def test_causal_order_marks_low_risk_action_not_required() -> None:
    receipt = TemporalCausalOrder(FixedClock()).evaluate(
        TemporalCausalOrderRequest(
            request_id="causal-order-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            policy=TemporalCausalOrderPolicy(
                policy_id="causal-order-policy-low",
                tenant_id="tenant-1",
                required_event_types=ORDERED_EVENT_TYPES,
                ordered_event_types=ORDERED_EVENT_TYPES,
                requires_causal_order=False,
            ),
            events=[],
            evidence_refs=[],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.order_state == "not_required"
    assert receipt.required_event_types == []
    assert receipt.ordered_event_types == []
    assert receipt.blocked_reasons == []
    assert receipt.missing_event_types == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["causal_order_checked"] is False
    assert receipt.metadata["high_risk_causal_order_checked"] is False


def _request(
    *,
    events: list[TemporalCausalEvent] | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_dispatch_window_receipt_id: str = "temporal-dispatch-window-receipt-0123456789abcdef",
    source_budget_window_receipt_id: str = "temporal-budget-window-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> TemporalCausalOrderRequest:
    return TemporalCausalOrderRequest(
        request_id="causal-order-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        policy=_policy(),
        events=events if events is not None else _events(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://causal-order/policy-1"],
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_dispatch_window_receipt_id=source_dispatch_window_receipt_id,
        source_budget_window_receipt_id=source_budget_window_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> TemporalCausalOrderPolicy:
    return TemporalCausalOrderPolicy(
        policy_id="causal-order-policy-1",
        tenant_id="tenant-1",
        required_event_types=ORDERED_EVENT_TYPES,
        ordered_event_types=ORDERED_EVENT_TYPES,
        requires_causal_order=True,
        high_risk_requires_causal_order=True,
    )


def _events() -> list[TemporalCausalEvent]:
    return [
        _event("evt-request-received", "request_received", "2026-05-05T14:00:00+00:00"),
        _event(
            "evt-identity-verified",
            "identity_verified",
            "2026-05-05T14:01:00+00:00",
            predecessors=["evt-request-received"],
        ),
        _event(
            "evt-risk-classified",
            "risk_classified",
            "2026-05-05T14:02:00+00:00",
            predecessors=["evt-identity-verified"],
        ),
        _event(
            "evt-temporal-checked",
            "temporal_checked",
            "2026-05-05T14:03:00+00:00",
            predecessors=["evt-risk-classified"],
            source_receipt_id="temporal-receipt-0123456789abcdef",
        ),
        _event(
            "evt-reapproval-checked",
            "reapproval_checked",
            "2026-05-05T14:04:00+00:00",
            predecessors=["evt-temporal-checked"],
            source_receipt_id="temporal-reapproval-receipt-0123456789abcdef",
        ),
        _event(
            "evt-dispatch-window-checked",
            "dispatch_window_checked",
            "2026-05-05T14:05:00+00:00",
            predecessors=["evt-reapproval-checked"],
            source_receipt_id="temporal-dispatch-window-receipt-0123456789abcdef",
        ),
        _event(
            "evt-budget-window-checked",
            "budget_window_checked",
            "2026-05-05T14:06:00+00:00",
            predecessors=["evt-dispatch-window-checked"],
            source_receipt_id="temporal-budget-window-receipt-0123456789abcdef",
        ),
        _event(
            "evt-dispatch-ready",
            "dispatch_ready",
            "2026-05-05T14:07:00+00:00",
            predecessors=["evt-budget-window-checked"],
        ),
    ]


def _event(
    event_id: str,
    event_type: str,
    occurred_at: str,
    *,
    predecessors: list[str] | None = None,
    source_receipt_id: str = "",
) -> TemporalCausalEvent:
    return TemporalCausalEvent(
        event_id=event_id,
        event_type=event_type,
        tenant_id="tenant-1",
        command_id="command-1",
        occurred_at=occurred_at,
        source_receipt_id=source_receipt_id,
        predecessor_event_ids=predecessors if predecessors is not None else [],
        evidence_refs=[f"proof://causal-order/{event_id}"],
    )
