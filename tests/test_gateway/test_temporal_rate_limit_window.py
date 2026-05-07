"""Gateway temporal rate-limit window tests.

Purpose: verify rate-limit receipts are runtime-owned, token-aware,
tenant-scoped, endpoint-scoped, retry-after-aware, source-bound, and
schema-backed before dispatch.
Governance scope: rate-limit window bounds, token projection, burst limits,
tenant scope, endpoint scope, identity scope, evidence refs, high-risk source
binding, and non-terminal temporal rate-limit window receipts.
Dependencies: gateway.temporal_rate_limit_window and temporal rate-limit
window receipt schema.
Invariants:
  - Active windows with sufficient tokens may admit dispatch.
  - Exhausted windows throttle with retry-after timing.
  - Future windows defer until the window start.
  - Scope mismatches and stale snapshots fail closed.
  - Low-risk policies may mark rate-limit control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_rate_limit_window import (
    RateLimitWindowPolicy,
    RateLimitWindowRequest,
    RateLimitWindowSnapshot,
    TemporalRateLimitWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_rate_limit_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for rate-limit window tests."""

    def now_utc(self) -> str:
        return NOW


def test_rate_limit_window_allows_active_window_with_sufficient_tokens() -> None:
    receipt = TemporalRateLimitWindow(FixedClock()).evaluate(_request(tokens_requested=3))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "within_limit"
    assert receipt.rate_limit_state == "available"
    assert receipt.remaining_tokens == 10
    assert receipt.tokens_requested == 3
    assert receipt.projected_remaining_tokens == 7
    assert receipt.deficit_tokens == 0
    assert receipt.retry_after_seconds == 0
    assert "rate_limit_admission" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_rate_limit_window_throttles_exhausted_window_with_retry_after() -> None:
    receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        _request(
            tokens_requested=4,
            snapshot=replace(_snapshot(), remaining_tokens=1, consumed_tokens=59, denied_count=3),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "throttled"
    assert receipt.rate_limit_state == "exhausted"
    assert receipt.remaining_tokens == 1
    assert receipt.projected_remaining_tokens == 0
    assert receipt.deficit_tokens == 3
    assert receipt.retry_after_seconds == 3
    assert "rate_limit_throttle_receipt" in receipt.required_controls
    assert "retry_after_receipt" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["retry_after_required"] is True


def test_rate_limit_window_defers_future_window_until_start() -> None:
    receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                window_start="2026-05-05T15:00:00+00:00",
                window_end="2026-05-05T16:00:00+00:00",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "deferred"
    assert receipt.rate_limit_state == "future"
    assert receipt.retry_after_seconds == 1800
    assert receipt.reset_at == "2026-05-05T15:00:00+00:00"
    assert receipt.deferral_reasons == ["rate_limit_window_not_started"]
    assert "rate_limit_defer" in receipt.required_controls
    assert receipt.blocked_reasons == []
    assert receipt.metadata["dispatch_allowed"] is False


def test_rate_limit_window_blocks_scope_mismatch_missing_evidence_sources_and_burst() -> None:
    receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        _request(
            endpoint="/api/v1/payments",
            tokens_requested=11,
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            snapshot=replace(
                _snapshot(),
                tenant_id="tenant-other",
                scope_id="scope-other",
                endpoint="/api/v1/other",
                identity_id="operator-other",
                evidence_refs=[],
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.rate_limit_state == "wrong_scope"
    assert "endpoint_not_allowed" in receipt.blocked_reasons
    assert "burst_limit_exceeded" in receipt.blocked_reasons
    assert "snapshot_tenant_mismatch" in receipt.blocked_reasons
    assert "snapshot_scope_mismatch" in receipt.blocked_reasons
    assert "snapshot_endpoint_mismatch" in receipt.blocked_reasons
    assert "snapshot_identity_mismatch" in receipt.blocked_reasons
    assert "snapshot_evidence_refs_required" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_rate_limit_window_blocks_expired_or_invalid_snapshot() -> None:
    expired_receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                window_start="2026-05-05T13:00:00+00:00",
                window_end="2026-05-05T14:00:00+00:00",
            )
        )
    )
    invalid_receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                window_start="2026-05-05T15:00:00+00:00",
                window_end="2026-05-05T14:00:00+00:00",
            )
        )
    )

    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(expired_receipt)) == []
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(invalid_receipt)) == []
    assert expired_receipt.status == "blocked"
    assert expired_receipt.rate_limit_state == "expired"
    assert "rate_limit_snapshot_expired" in expired_receipt.blocked_reasons
    assert invalid_receipt.status == "blocked"
    assert invalid_receipt.rate_limit_state == "invalid"
    assert "snapshot_window_invalid" in invalid_receipt.blocked_reasons
    assert invalid_receipt.metadata["dispatch_allowed"] is False


def test_rate_limit_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalRateLimitWindow(FixedClock()).evaluate(
        RateLimitWindowRequest(
            request_id="rate-limit-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="read_summary",
            risk_level="low",
            endpoint="/api/v1/summary",
            identity_id="operator-1",
            tokens_requested=1,
            policy=replace(_policy(), requires_rate_limit_window=False),
            evidence_refs=[],
            snapshot=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.rate_limit_state == "not_required"
    assert receipt.rate_limit_required is False
    assert receipt.bucket_key == ""
    assert receipt.retry_after_seconds == 0
    assert receipt.max_tokens == 0
    assert receipt.projected_remaining_tokens == 0
    assert receipt.blocked_reasons == []
    assert receipt.deferral_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["rate_limit_checked"] is False


def _request(
    *,
    endpoint: str = "/api/v1/finance/approval-packets",
    tokens_requested: int = 2,
    snapshot: RateLimitWindowSnapshot | None = None,
    policy: RateLimitWindowPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_dispatch_window_receipt_id: str = "temporal-dispatch-window-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> RateLimitWindowRequest:
    return RateLimitWindowRequest(
        request_id="rate-limit-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="finance_packet_read",
        risk_level="high",
        endpoint=endpoint,
        identity_id="operator-1",
        tokens_requested=tokens_requested,
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://rate-limit/policy-1"],
        snapshot=snapshot if snapshot is not None else _snapshot(endpoint=endpoint),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_dispatch_window_receipt_id=source_dispatch_window_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> RateLimitWindowPolicy:
    return RateLimitWindowPolicy(
        policy_id="rate-limit-policy-1",
        tenant_id="tenant-1",
        scope_id="finance-api",
        endpoint_patterns=["/api/v1/finance/*", "/api/v1/summary"],
        max_tokens=60,
        refill_rate_per_second="1",
        burst_limit=10,
        window_seconds=3600,
        requires_rate_limit_window=True,
        high_risk_requires_rate_limit_window=True,
    )


def _snapshot(*, endpoint: str = "/api/v1/finance/approval-packets") -> RateLimitWindowSnapshot:
    return RateLimitWindowSnapshot(
        snapshot_id="rate-limit-snapshot-1",
        tenant_id="tenant-1",
        scope_id="finance-api",
        bucket_key="tenant-1:operator-1:/api/v1/finance/approval-packets",
        endpoint=endpoint,
        identity_id="operator-1",
        window_start="2026-05-05T14:00:00+00:00",
        window_end="2026-05-05T15:00:00+00:00",
        observed_at="2026-05-05T14:29:00+00:00",
        remaining_tokens=10,
        consumed_tokens=50,
        denied_count=2,
        evidence_refs=["proof://rate-limit/snapshot-1"],
    )
