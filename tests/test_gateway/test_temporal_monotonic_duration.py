"""Gateway temporal monotonic-duration tests.

Purpose: verify monotonic-duration receipts are runtime-owned, bound-checked,
cooldown-aware, source-bound, and schema-backed before dispatch.
Governance scope: monotonic clock readings, timeout and cooldown bounds,
high-risk source receipts, evidence refs, and non-terminal duration receipts.
Dependencies: gateway.temporal_monotonic_duration and temporal monotonic
duration receipt schema.
Invariants:
  - Elapsed duration is measured from monotonic clock readings.
  - Duration limits block dispatch when exceeded.
  - Cooldown and retry lower bounds defer dispatch until elapsed.
  - Regressed monotonic readings fail closed.
  - Low-risk policies may mark monotonic duration control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_monotonic_duration import (
    TemporalMonotonicDuration,
    TemporalMonotonicDurationPolicy,
    TemporalMonotonicDurationRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_monotonic_duration_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall and monotonic clock provider for duration tests."""

    def __init__(self, *monotonic_values: int) -> None:
        self._monotonic_values = list(monotonic_values)

    def now_utc(self) -> str:
        return NOW

    def monotonic_ns(self) -> int:
        if not self._monotonic_values:
            raise AssertionError("monotonic_value_missing")
        return self._monotonic_values.pop(0)


def test_monotonic_duration_allows_high_risk_dispatch_inside_latency_bound() -> None:
    receipt = TemporalMonotonicDuration(FixedClock(1_000, 4_000)).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "within_duration"
    assert receipt.duration_state == "within"
    assert receipt.duration_ns == 3_000
    assert receipt.monotonic_started_ns == 1_000
    assert receipt.monotonic_finished_ns == 4_000
    assert receipt.max_duration_ns == 10_000
    assert receipt.remaining_ns == 0
    assert receipt.overage_ns == 0
    assert receipt.metadata["monotonic_used_for_duration"] is True
    assert receipt.metadata["wall_clock_not_used_for_duration"] is True
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True
    assert receipt.terminal_closure_required is True


def test_monotonic_duration_blocks_when_timeout_limit_is_exceeded() -> None:
    receipt = TemporalMonotonicDuration(FixedClock(1_000, 12_500)).evaluate(
        _request(policy=replace(_policy(), duration_kind="timeout", max_duration_ns=10_000))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.duration_state == "over_limit"
    assert receipt.duration_ns == 11_500
    assert receipt.overage_ns == 1_500
    assert receipt.remaining_ns == 0
    assert "duration_limit_exceeded" in receipt.blocked_reasons
    assert "duration_dispatch_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["duration_limit_checked"] is True


def test_monotonic_duration_defers_cooldown_until_lower_bound_elapsed() -> None:
    receipt = TemporalMonotonicDuration(FixedClock(5_000, 8_000)).evaluate(
        _request(
            policy=TemporalMonotonicDurationPolicy(
                policy_id="duration-policy-cooldown",
                tenant_id="tenant-1",
                duration_kind="cooldown",
                min_elapsed_ns=10_000,
                max_duration_ns=20_000,
            ),
            source_scheduler_receipt_id="scheduler-receipt-0123456789abcdef",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "deferred"
    assert receipt.duration_state == "cooldown_wait"
    assert receipt.duration_ns == 3_000
    assert receipt.remaining_ns == 7_000
    assert receipt.overage_ns == 0
    assert receipt.deferral_reasons == ["duration_window_not_elapsed"]
    assert receipt.metadata["defer_required"] is True
    assert receipt.metadata["cooldown_checked"] is True
    assert receipt.metadata["dispatch_allowed"] is False


def test_monotonic_duration_blocks_regressed_clock_scope_evidence_and_missing_sources() -> None:
    receipt = TemporalMonotonicDuration(FixedClock(12_000, 11_000)).evaluate(
        _request(
            policy=replace(
                _policy(),
                tenant_id="tenant-other",
                duration_kind="retry_delay",
                min_elapsed_ns=1_000,
            ),
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_scheduler_receipt_id="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.duration_state == "invalid"
    assert receipt.duration_ns == 0
    assert "policy_tenant_mismatch" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_scheduler_receipt_required_for_high_risk_cooldown" in receipt.blocked_reasons
    assert "monotonic_clock_regressed" in receipt.blocked_reasons
    assert "duration_dispatch_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_duration_checked"] is True


def test_monotonic_duration_marks_low_risk_action_not_required() -> None:
    receipt = TemporalMonotonicDuration(FixedClock(20_000, 21_000)).evaluate(
        TemporalMonotonicDurationRequest(
            request_id="duration-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            policy=TemporalMonotonicDurationPolicy(
                policy_id="duration-policy-low",
                tenant_id="tenant-1",
                duration_kind="latency",
                requires_monotonic_duration=False,
            ),
            evidence_refs=[],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.duration_state == "not_required"
    assert receipt.duration_required is False
    assert receipt.duration_ns == 1_000
    assert receipt.blocked_reasons == []
    assert receipt.deferral_reasons == []
    assert receipt.remaining_ns == 0
    assert receipt.overage_ns == 0
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["duration_limit_checked"] is False
    assert receipt.metadata["high_risk_duration_checked"] is False


def _request(
    *,
    policy: TemporalMonotonicDurationPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_scheduler_receipt_id: str = "",
    source_causal_order_receipt_id: str = "temporal-causal-order-receipt-0123456789abcdef",
) -> TemporalMonotonicDurationRequest:
    return TemporalMonotonicDurationRequest(
        request_id="duration-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://duration/policy-1"],
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_scheduler_receipt_id=source_scheduler_receipt_id,
        source_causal_order_receipt_id=source_causal_order_receipt_id,
    )


def _policy() -> TemporalMonotonicDurationPolicy:
    return TemporalMonotonicDurationPolicy(
        policy_id="duration-policy-1",
        tenant_id="tenant-1",
        duration_kind="latency",
        min_elapsed_ns=1_000,
        max_duration_ns=10_000,
        requires_monotonic_duration=True,
        high_risk_requires_monotonic_duration=True,
    )
