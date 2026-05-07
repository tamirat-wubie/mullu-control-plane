"""Gateway temporal kernel tests.

Purpose: verify runtime-owned time gates execution through deadlines,
freshness, budget windows, schedules, causal order, and monotonic witnesses.
Governance scope: temporal policy admission, receipt schema compatibility,
runtime clock ownership, and non-terminal temporal decisions.
Dependencies: gateway.temporal_kernel and temporal operation receipt schema.
Invariants:
  - Wall-clock time is injected by the runtime clock.
  - Monotonic time measures duration only.
  - Future schedules defer without dispatch.
  - Expired approval denies execution.
  - Stale evidence escalates high-risk action.
  - Missing causal prerequisites deny execution.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_kernel import TemporalKernel, TemporalOperationRequest
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_operation_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic clock for temporal policy tests."""

    def __init__(self) -> None:
        self._monotonic_values = [1_000, 1_750]

    def now_utc(self) -> str:
        return NOW

    def monotonic_ns(self) -> int:
        return self._monotonic_values.pop(0)


def test_temporal_kernel_allows_due_fresh_schema_valid_receipt() -> None:
    receipt = TemporalKernel(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "allow"
    assert receipt.receipt_id.startswith("temporal-receipt-")
    assert receipt.runtime_now_utc == NOW
    assert receipt.duration_ns == 750
    assert receipt.metadata["runtime_owns_time_truth"] is True
    assert receipt.metadata["monotonic_used_for_duration"] is True
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.terminal_closure_required is True


def test_temporal_kernel_defers_future_execution_without_terminal_closure() -> None:
    receipt = TemporalKernel(FixedClock()).evaluate(
        replace(_request(), execute_at="2026-05-05T14:00:00+00:00")
    )

    assert receipt.status == "defer"
    assert receipt.temporal_violations == []
    assert "scheduled_for_future" in receipt.deferral_reasons
    assert "schedule_due" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_temporal_kernel_denies_expired_approval() -> None:
    receipt = TemporalKernel(FixedClock()).evaluate(
        replace(
            _request(),
            approval_received_at="2026-05-05T10:00:00+00:00",
            approval_valid_seconds=3600,
            approval_expires_at="",
        )
    )

    assert receipt.status == "deny"
    assert "approval_expired" in receipt.temporal_violations
    assert "approval_validity" in receipt.required_controls
    assert receipt.approval_received_at == "2026-05-05T10:00:00+00:00"
    assert receipt.approval_expires_at == "2026-05-05T11:00:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.receipt_hash


def test_temporal_kernel_escalates_stale_evidence() -> None:
    receipt = TemporalKernel(FixedClock()).evaluate(
        replace(
            _request(),
            evidence_observed_at="2026-05-05T12:00:00+00:00",
            freshness_seconds=1800,
            evidence_fresh_until="",
        )
    )

    assert receipt.status == "escalate"
    assert receipt.temporal_violations == []
    assert "evidence_stale" in receipt.temporal_warnings
    assert receipt.evidence_fresh_until == "2026-05-05T12:30:00+00:00"
    assert "evidence_freshness" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False


def test_temporal_kernel_denies_missing_causal_precondition_and_budget_window() -> None:
    receipt = TemporalKernel(FixedClock()).evaluate(
        replace(
            _request(),
            budget_period_start="2026-05-04T00:00:00+00:00",
            budget_period_end="2026-05-05T12:00:00+00:00",
            causal_preconditions=["approval_received", "budget_reserved"],
            satisfied_preconditions=["approval_received"],
        )
    )

    assert receipt.status == "deny"
    assert "budget_window_expired" in receipt.temporal_violations
    assert "causal_preconditions_missing" in receipt.temporal_violations
    assert receipt.missing_preconditions == ["budget_reserved"]
    assert "budget_window" in receipt.required_controls
    assert "causal_order" in receipt.required_controls


def _request() -> TemporalOperationRequest:
    return TemporalOperationRequest(
        request_id="temporal-request-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        requested_at="2026-05-05T12:50:00+00:00",
        execute_at="2026-05-05T12:55:00+00:00",
        expires_at="2026-05-05T15:00:00+00:00",
        approval_received_at="2026-05-05T12:30:00+00:00",
        approval_expires_at="2026-05-05T14:30:00+00:00",
        evidence_observed_at="2026-05-05T12:45:00+00:00",
        evidence_fresh_until="2026-05-05T13:30:00+00:00",
        budget_period_start="2026-05-05T00:00:00+00:00",
        budget_period_end="2026-05-06T00:00:00+00:00",
        causal_preconditions=["approval_received", "budget_reserved"],
        satisfied_preconditions=["approval_received", "budget_reserved"],
        evidence_refs=["approval:manager-1", "evidence:price-check-1"],
        timezone_name="America/New_York",
        original_time_text="send after approval before 11 AM",
    )
