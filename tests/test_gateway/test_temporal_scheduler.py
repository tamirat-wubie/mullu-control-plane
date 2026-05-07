"""Gateway temporal scheduler tests.

Purpose: verify scheduled command wakeups are idempotent, lease-bound,
retry-aware, approval-rechecked, and schema-backed.
Governance scope: scheduler due checks, missed-run receipts, retry windows,
lease acquisition, high-risk reapproval evidence, and non-terminal receipts.
Dependencies: gateway.temporal_scheduler and temporal scheduler receipt schema.
Invariants:
  - Due commands acquire leases before dispatch.
  - Future commands defer without leases.
  - Expired commands emit missed-run receipts.
  - Retries respect retry_after and max_attempts.
  - High-risk scheduled commands require approval and temporal recheck proof.
  - Existing active leases block duplicate execution.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_scheduler import ScheduledCommand, TemporalScheduler
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_scheduler_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for scheduler tests."""

    def now_utc(self) -> str:
        return NOW


def test_scheduler_due_command_acquires_schema_valid_lease() -> None:
    receipt = TemporalScheduler(clock=FixedClock(), lease_ttl_seconds=120).evaluate(_command())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "leased"
    assert receipt.lease_acquired is True
    assert receipt.lease_id.startswith("temporal-lease-")
    assert receipt.lease_expires_at == "2026-05-05T13:02:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.terminal_closure_required is True
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_scheduler_future_command_defers_without_lease() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(_command(), execute_at="2026-05-05T13:30:00+00:00")
    )

    assert receipt.status == "deferred"
    assert "scheduled_for_future" in receipt.deferral_reasons
    assert receipt.lease_acquired is False
    assert receipt.lease_id == ""
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.blocked_reasons == []


def test_scheduler_expired_command_emits_missed_run_receipt() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(_command(), expires_at="2026-05-05T12:59:00+00:00")
    )

    assert receipt.status == "missed"
    assert "command_expired_before_execution" in receipt.missed_reasons
    assert receipt.metadata["missed_run_receipt"] is True
    assert receipt.lease_acquired is False
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.receipt_hash


def test_scheduler_retry_waits_until_retry_after_window() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(
            _command(),
            attempt_count=1,
            max_attempts=3,
            last_attempt_at="2026-05-05T12:50:00+00:00",
            retry_after="2026-05-05T13:10:00+00:00",
        )
    )

    assert receipt.status == "retry_wait"
    assert "retry_window_not_due" in receipt.retry_reasons
    assert "retry_window" in receipt.required_controls
    assert receipt.attempt_count == 1
    assert receipt.max_attempts == 3
    assert receipt.metadata["retry_window_checked"] is True


def test_scheduler_blocks_high_risk_missing_recheck_evidence() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(_command(), approval_ref="", temporal_receipt_ref="")
    )

    assert receipt.status == "blocked"
    assert "approval_recheck_required" in receipt.blocked_reasons
    assert "temporal_policy_recheck_required" in receipt.blocked_reasons
    assert "approval_recheck" in receipt.required_controls
    assert "temporal_policy_recheck" in receipt.required_controls
    assert receipt.lease_acquired is False


def test_scheduler_blocks_missing_execute_at_idempotency_and_recurrence_rule() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(
            _command(),
            risk_level="medium",
            execute_at="",
            idempotency_key="",
            recurring=True,
            recurrence_rule="",
        )
    )

    assert receipt.status == "blocked"
    assert "execute_at_required" in receipt.blocked_reasons
    assert "idempotency_key_required" in receipt.blocked_reasons
    assert "recurrence_rule_required" in receipt.blocked_reasons
    assert "recurrence_rule" in receipt.required_controls
    assert receipt.lease_acquired is False
    assert receipt.metadata["idempotency_required"] is True


def test_scheduler_blocks_existing_active_lease() -> None:
    receipt = TemporalScheduler(clock=FixedClock()).evaluate(
        replace(
            _command(),
            lease_id="temporal-lease-existing",
            lease_owner="worker-a",
            lease_expires_at="2026-05-05T13:05:00+00:00",
        )
    )

    assert receipt.status == "blocked"
    assert "active_lease_exists" in receipt.blocked_reasons
    assert "duplicate_execution_prevention" in receipt.required_controls
    assert receipt.lease_id == "temporal-lease-existing"
    assert receipt.lease_acquired is False
    assert receipt.metadata["dispatch_allowed"] is False


def _command() -> ScheduledCommand:
    return ScheduledCommand(
        schedule_id="schedule-1",
        command_id="command-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        action_type="vendor_payment",
        risk_level="high",
        requested_at="2026-05-05T12:30:00+00:00",
        execute_at="2026-05-05T12:55:00+00:00",
        expires_at="2026-05-05T14:00:00+00:00",
        idempotency_key="idem-1",
        evidence_refs=["evidence:schedule:1", "approval:manager-1"],
        approval_ref="approval:manager-1",
        temporal_receipt_ref="temporal-receipt-1234567890abcdef",
    )
