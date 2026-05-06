"""Gateway temporal dispatch-window tests.

Purpose: verify runtime dispatch-window receipts are timezone-owned,
window-gated, blackout-aware, holiday-aware, source-bound, and schema-backed
before worker dispatch.
Governance scope: allowed windows, blackout windows, tenant timezone, high-risk
source receipt binding, evidence refs, deferral receipts, and non-terminal
dispatch-window receipts.
Dependencies: gateway.temporal_dispatch_window and temporal dispatch-window
receipt schema.
Invariants:
  - In-window high-risk actions can dispatch when source receipts are present.
  - Outside-window actions defer to the next allowed local window.
  - Active blackout windows defer dispatch even inside an allowed window.
  - Invalid policy, tenant, source, or evidence state blocks dispatch.
  - Low-risk policies may explicitly mark window control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_dispatch_window import (
    DispatchAllowedWindow,
    DispatchBlackoutWindow,
    DispatchWindowPolicy,
    DispatchWindowRequest,
    TemporalDispatchWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_dispatch_window_receipt.schema.json"
NOW_IN_WINDOW = "2026-05-05T14:30:00+00:00"
NOW_OUTSIDE_WINDOW = "2026-05-05T23:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for dispatch-window tests."""

    def __init__(self, now: str) -> None:
        self._now = now

    def now_utc(self) -> str:
        return self._now


def test_dispatch_window_allows_high_risk_action_inside_allowed_window() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_IN_WINDOW)).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "within_window"
    assert receipt.allowed_window_status == "inside"
    assert receipt.active_allowed_window_start == "2026-05-05T13:00:00+00:00"
    assert receipt.active_allowed_window_end == "2026-05-05T21:00:00+00:00"
    assert receipt.local_date == "2026-05-05"
    assert receipt.active_blackout_ids == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.terminal_closure_required is True


def test_dispatch_window_defers_outside_allowed_window_to_next_business_window() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_OUTSIDE_WINDOW)).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "deferred"
    assert receipt.allowed_window_status == "outside"
    assert receipt.deferral_reasons == ["outside_allowed_dispatch_window"]
    assert receipt.next_allowed_window_start == "2026-05-06T13:00:00+00:00"
    assert receipt.next_allowed_window_end == "2026-05-06T21:00:00+00:00"
    assert receipt.defer_until == "2026-05-06T13:00:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["defer_required"] is True


def test_dispatch_window_defers_active_blackout_inside_allowed_window() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_IN_WINDOW)).evaluate(
        _request(
            policy=replace(
                _policy(),
                blackout_windows=[
                    DispatchBlackoutWindow(
                        blackout_id="blackout-provider-maintenance",
                        starts_at="2026-05-05T14:00:00+00:00",
                        ends_at="2026-05-05T15:00:00+00:00",
                        reason="provider_maintenance",
                        action_types=["vendor_payment"],
                        risk_levels=["high"],
                    )
                ],
            )
        )
    )

    assert receipt.status == "deferred"
    assert receipt.allowed_window_status == "inside"
    assert receipt.active_blackout_ids == ["blackout-provider-maintenance"]
    assert receipt.deferral_reasons == ["blackout_window_active"]
    assert receipt.defer_until == "2026-05-05T15:00:00+00:00"
    assert "dispatch_block" in receipt.required_controls
    assert receipt.metadata["blackout_window_checked"] is True


def test_dispatch_window_defers_holiday_to_next_business_window() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_IN_WINDOW)).evaluate(
        _request(policy=replace(_policy(), holidays=["2026-05-05"]))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "deferred"
    assert receipt.holiday_status == "closed"
    assert receipt.allowed_window_status == "outside"
    assert "holiday_closed" in receipt.deferral_reasons
    assert "outside_allowed_dispatch_window" in receipt.deferral_reasons
    assert receipt.next_allowed_window_start == "2026-05-06T13:00:00+00:00"
    assert receipt.defer_until == "2026-05-06T13:00:00+00:00"


def test_dispatch_window_blocks_invalid_high_risk_policy_state() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_IN_WINDOW)).evaluate(
        _request(
            evidence_refs=[],
            source_schedule_receipt_id="",
            source_reapproval_receipt_id="",
            policy=replace(
                _policy(),
                tenant_id="tenant-other",
                allowed_windows=[replace(_business_window(1), end_time="08:00")],
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "policy_tenant_mismatch" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_schedule_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "allowed_window_range_invalid" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False


def test_dispatch_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalDispatchWindow(FixedClock(NOW_IN_WINDOW)).evaluate(
        DispatchWindowRequest(
            request_id="dispatch-window-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            policy=DispatchWindowPolicy(
                policy_id="policy-low-optional",
                tenant_id="tenant-1",
                timezone_name="America/New_York",
                allowed_windows=[],
                requires_allowed_window=False,
                high_risk_requires_allowed_window=True,
            ),
            evidence_refs=["proof://policy/low-window-optional"],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.allowed_window_required is False
    assert receipt.allowed_window_status == "not_required"
    assert receipt.deferral_reasons == []
    assert receipt.blocked_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_window_checked"] is False


def _request(
    *,
    policy: DispatchWindowPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_schedule_receipt_id: str = "scheduler-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> DispatchWindowRequest:
    return DispatchWindowRequest(
        request_id="dispatch-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://policy/dispatch-window-1"],
        source_schedule_receipt_id=source_schedule_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
        source_temporal_receipt_id="temporal-receipt-0123456789abcdef",
    )


def _policy() -> DispatchWindowPolicy:
    return DispatchWindowPolicy(
        policy_id="dispatch-window-policy-1",
        tenant_id="tenant-1",
        timezone_name="America/New_York",
        allowed_windows=[_business_window(weekday) for weekday in range(0, 5)],
        holidays=[],
        requires_allowed_window=True,
        high_risk_requires_allowed_window=True,
    )


def _business_window(weekday: int) -> DispatchAllowedWindow:
    return DispatchAllowedWindow(
        weekday=weekday,
        start_time="09:00",
        end_time="17:00",
        label="business-hours",
    )
