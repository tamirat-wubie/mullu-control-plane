"""Gateway temporal budget-window tests.

Purpose: verify budget-window receipts are runtime-owned, reset-aware,
tenant-scoped, spend-projected, source-bound, and schema-backed before dispatch.
Governance scope: daily/weekly/custom reset windows, tenant timezone, spend
snapshots, high-risk source receipt binding, evidence refs, and non-terminal
budget-window receipts.
Dependencies: gateway.temporal_budget_window and temporal budget-window receipt
schema.
Invariants:
  - Active budget windows allow dispatch only when projected spend fits.
  - Tenant-local reset windows are preserved in UTC receipt fields.
  - Future budget windows defer until the period starts.
  - Over-budget, mismatched, or evidence-missing states block dispatch.
  - Low-risk policies may explicitly mark budget-window control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_budget_window import (
    BudgetSpendSnapshot,
    BudgetWindowPolicy,
    BudgetWindowRequest,
    TemporalBudgetWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_budget_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"
DAILY_PERIOD_START = "2026-05-05T04:00:00+00:00"
DAILY_PERIOD_END = "2026-05-06T04:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for budget-window tests."""

    def now_utc(self) -> str:
        return NOW


def test_budget_window_allows_high_risk_action_inside_daily_remaining_budget() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "within_budget"
    assert receipt.period_state == "active"
    assert receipt.budget_state == "sufficient"
    assert receipt.period_start == DAILY_PERIOD_START
    assert receipt.period_end == DAILY_PERIOD_END
    assert receipt.spent_amount_usd == "470.00"
    assert receipt.estimated_amount_usd == "30.00"
    assert receipt.projected_amount_usd == "500.00"
    assert receipt.available_amount_usd == "30.00"
    assert receipt.overage_amount_usd == "0.00"
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.terminal_closure_required is True


def test_budget_window_blocks_when_projected_spend_exceeds_active_limit() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(_request(estimated_amount_usd="50.00"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.budget_state == "exhausted"
    assert receipt.projected_amount_usd == "520.00"
    assert receipt.available_amount_usd == "30.00"
    assert receipt.overage_amount_usd == "20.00"
    assert "budget_limit_exceeded" in receipt.blocked_reasons
    assert "budget_dispatch_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False


def test_budget_window_preserves_weekly_tenant_local_reset_window() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(
        _request(
            policy=replace(_policy(), period_kind="weekly"),
            spend_snapshot=replace(
                _snapshot(spent_amount_usd="100.00"),
                period_start="2026-05-04T04:00:00+00:00",
                period_end="2026-05-11T04:00:00+00:00",
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "within_budget"
    assert receipt.period_kind == "weekly"
    assert receipt.period_start == "2026-05-04T04:00:00+00:00"
    assert receipt.period_end == "2026-05-11T04:00:00+00:00"
    assert receipt.projected_amount_usd == "130.00"
    assert receipt.metadata["reset_window_checked"] is True


def test_budget_window_defers_future_custom_period() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(
        _request(
            policy=BudgetWindowPolicy(
                policy_id="budget-window-policy-custom",
                tenant_id="tenant-1",
                budget_id="budget-daily-1",
                timezone_name="America/New_York",
                period_kind="custom",
                limit_amount_usd="500.00",
                custom_period_start="2026-05-05T15:00:00+00:00",
                custom_period_end="2026-05-06T15:00:00+00:00",
            ),
            spend_snapshot=replace(
                _snapshot(spent_amount_usd="0.00"),
                period_start="2026-05-05T15:00:00+00:00",
                period_end="2026-05-06T15:00:00+00:00",
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "deferred"
    assert receipt.period_state == "future"
    assert receipt.deferral_reasons == ["budget_window_not_started"]
    assert receipt.defer_until == "2026-05-05T15:00:00+00:00"
    assert receipt.metadata["defer_required"] is True
    assert receipt.metadata["dispatch_allowed"] is False


def test_budget_window_blocks_mismatched_snapshot_and_missing_sources() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(
        _request(
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            spend_snapshot=replace(
                _snapshot(evidence_refs=[]),
                tenant_id="tenant-other",
                budget_id="budget-other",
                period_end="2026-05-06T05:00:00+00:00",
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "snapshot_tenant_mismatch" in receipt.blocked_reasons
    assert "snapshot_budget_mismatch" in receipt.blocked_reasons
    assert "snapshot_evidence_refs_required" in receipt.blocked_reasons
    assert "snapshot_period_mismatch" in receipt.blocked_reasons


def test_budget_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalBudgetWindow(FixedClock()).evaluate(
        BudgetWindowRequest(
            request_id="budget-window-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            policy=replace(_policy(), requires_budget_window=False),
            estimated_amount_usd="0.00",
            evidence_refs=[],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.budget_window_required is False
    assert receipt.period_state == "not_required"
    assert receipt.budget_state == "not_required"
    assert receipt.blocked_reasons == []
    assert receipt.deferral_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_budget_checked"] is False


def _request(
    *,
    policy: BudgetWindowPolicy | None = None,
    spend_snapshot: BudgetSpendSnapshot | None = None,
    estimated_amount_usd: str = "30.00",
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> BudgetWindowRequest:
    return BudgetWindowRequest(
        request_id="budget-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        policy=policy or _policy(),
        estimated_amount_usd=estimated_amount_usd,
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://budget-window/policy-1"],
        spend_snapshot=spend_snapshot or _snapshot(),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_dispatch_window_receipt_id="temporal-dispatch-window-receipt-0123456789abcdef",
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> BudgetWindowPolicy:
    return BudgetWindowPolicy(
        policy_id="budget-window-policy-1",
        tenant_id="tenant-1",
        budget_id="budget-daily-1",
        timezone_name="America/New_York",
        period_kind="daily",
        limit_amount_usd="500.00",
        week_start_weekday=0,
        requires_budget_window=True,
        high_risk_requires_budget_window=True,
    )


def _snapshot(
    *,
    spent_amount_usd: str = "470.00",
    reserved_amount_usd: str = "0.00",
    evidence_refs: list[str] | None = None,
) -> BudgetSpendSnapshot:
    return BudgetSpendSnapshot(
        snapshot_id="budget-snapshot-1",
        tenant_id="tenant-1",
        budget_id="budget-daily-1",
        period_start=DAILY_PERIOD_START,
        period_end=DAILY_PERIOD_END,
        spent_amount_usd=spent_amount_usd,
        reserved_amount_usd=reserved_amount_usd,
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://budget-window/snapshot-1"],
        observed_at="2026-05-05T14:25:00+00:00",
    )
