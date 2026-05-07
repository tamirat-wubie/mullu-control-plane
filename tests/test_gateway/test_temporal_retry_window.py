"""Gateway temporal retry window tests.

Purpose: verify retry receipts are runtime-owned, retry-after-aware,
cooldown-aware, max-attempt-aware, expiry-aware, source-bound, and
schema-backed before repeated dispatch.
Governance scope: retry timing, tenant scope, command scope, evidence refs,
high-risk source binding, and non-terminal temporal retry window receipts.
Dependencies: gateway.temporal_retry_window and temporal retry window receipt
schema.
Invariants:
  - Eligible retries may dispatch only after retry-after and cooldown checks.
  - Early retries defer with retry-after timing.
  - Exhausted and expired retry windows fail closed.
  - Scope mismatches and terminal failures block dispatch.
  - Low-risk policies may mark retry control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_retry_window import (
    RetryAttemptSnapshot,
    RetryWindowPolicy,
    RetryWindowRequest,
    TemporalRetryWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_retry_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for retry window tests."""

    def now_utc(self) -> str:
        return NOW


def test_retry_window_allows_eligible_retry_after_cooldown() -> None:
    receipt = TemporalRetryWindow(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "retry_allowed"
    assert receipt.retry_state == "eligible"
    assert receipt.attempt_number == 2
    assert receipt.max_attempts == 4
    assert receipt.attempts_remaining == 2
    assert receipt.retry_after_seconds == 0
    assert receipt.cooldown_remaining_seconds == 0
    assert receipt.retry_after_due_at == "2026-05-05T13:15:00+00:00"
    assert "retry_admission" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_retry_window_defers_before_retry_after_due_time() -> None:
    receipt = TemporalRetryWindow(FixedClock()).evaluate(
        _request(snapshot=replace(_snapshot(), next_retry_at="2026-05-05T15:00:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "retry_deferred"
    assert receipt.retry_state == "cooldown"
    assert receipt.retry_after_seconds == 1800
    assert receipt.cooldown_remaining_seconds == 1800
    assert receipt.retry_after_due_at == "2026-05-05T15:00:00+00:00"
    assert receipt.deferral_reasons == ["retry_after_not_elapsed"]
    assert "retry_after_receipt" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False


def test_retry_window_blocks_exhausted_attempt_budget() -> None:
    receipt = TemporalRetryWindow(FixedClock()).evaluate(
        _request(snapshot=replace(_snapshot(), attempt_number=2, failure_count=4))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "retry_exhausted"
    assert receipt.retry_state == "max_attempts_reached"
    assert receipt.attempt_number == 2
    assert receipt.failure_count == 4
    assert receipt.attempts_remaining == 0
    assert receipt.retry_after_seconds == 0
    assert receipt.blocked_reasons == []
    assert "retry_exhaustion_receipt" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False


def test_retry_window_blocks_expired_or_terminal_retry_state() -> None:
    expired_receipt = TemporalRetryWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                first_attempt_at="2026-05-05T12:00:00+00:00",
                expires_at="2026-05-05T14:00:00+00:00",
            )
        )
    )
    terminal_receipt = TemporalRetryWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                terminal_failure=True,
                last_failure_reason="provider_declared_non_retryable",
            )
        )
    )

    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(expired_receipt)) == []
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(terminal_receipt)) == []
    assert expired_receipt.status == "retry_expired"
    assert expired_receipt.retry_state == "expired"
    assert "retry_expiry_block" in expired_receipt.required_controls
    assert terminal_receipt.status == "blocked"
    assert terminal_receipt.retry_state == "terminal_failure"
    assert "terminal_failure_recorded" in terminal_receipt.blocked_reasons
    assert terminal_receipt.metadata["dispatch_allowed"] is False


def test_retry_window_blocks_scope_mismatch_missing_evidence_sources_and_bad_floor() -> None:
    receipt = TemporalRetryWindow(FixedClock()).evaluate(
        _request(
            action_type="non_retryable_action",
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            snapshot=replace(
                _snapshot(),
                tenant_id="tenant-other",
                command_id="command-other",
                next_retry_at="2026-05-05T13:01:00+00:00",
                evidence_refs=[],
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.retry_state == "wrong_scope"
    assert "action_type_not_retryable" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "snapshot_tenant_mismatch" in receipt.blocked_reasons
    assert "snapshot_command_mismatch" in receipt.blocked_reasons
    assert "attempt_evidence_refs_required" in receipt.blocked_reasons
    assert "next_retry_before_policy_floor" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_retry_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalRetryWindow(FixedClock()).evaluate(
        RetryWindowRequest(
            request_id="retry-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="read_summary",
            risk_level="low",
            policy=replace(_policy(), requires_retry_window=False, high_risk_requires_retry_window=False),
            evidence_refs=[],
            snapshot=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.retry_state == "not_required"
    assert receipt.retry_window_required is False
    assert receipt.attempt_id == ""
    assert receipt.retry_after_seconds == 0
    assert receipt.max_attempts == 0
    assert receipt.attempts_remaining == 0
    assert receipt.blocked_reasons == []
    assert receipt.deferral_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["retry_checked"] is False


def _request(
    *,
    action_type: str = "finance_packet_retry",
    snapshot: RetryAttemptSnapshot | None = None,
    policy: RetryWindowPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_dispatch_window_receipt_id: str = "temporal-dispatch-window-receipt-0123456789abcdef",
    source_rate_limit_window_receipt_id: str = "temporal-rate-limit-window-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> RetryWindowRequest:
    return RetryWindowRequest(
        request_id="retry-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type=action_type,
        risk_level="high",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://retry/policy-1"],
        snapshot=snapshot if snapshot is not None else _snapshot(),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_dispatch_window_receipt_id=source_dispatch_window_receipt_id,
        source_rate_limit_window_receipt_id=source_rate_limit_window_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> RetryWindowPolicy:
    return RetryWindowPolicy(
        policy_id="retry-policy-1",
        tenant_id="tenant-1",
        scope_id="finance-worker",
        retryable_action_types=["finance_packet_retry", "read_summary"],
        max_attempts=4,
        retry_after_seconds=900,
        cooldown_seconds=600,
        max_retry_window_seconds=14400,
        requires_retry_window=True,
        high_risk_requires_retry_window=True,
    )


def _snapshot() -> RetryAttemptSnapshot:
    return RetryAttemptSnapshot(
        attempt_id="retry-attempt-2",
        tenant_id="tenant-1",
        command_id="command-1",
        first_attempt_at="2026-05-05T12:00:00+00:00",
        last_attempt_at="2026-05-05T13:00:00+00:00",
        next_retry_at="2026-05-05T13:15:00+00:00",
        expires_at="2026-05-05T16:00:00+00:00",
        attempt_number=2,
        failure_count=2,
        terminal_failure=False,
        previous_attempt_id="retry-attempt-1",
        last_failure_reason="provider_timeout",
        evidence_refs=["proof://retry/attempt-2"],
    )
