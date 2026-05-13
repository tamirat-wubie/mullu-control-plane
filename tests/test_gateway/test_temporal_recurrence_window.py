"""Gateway temporal recurrence-window tests.

Purpose: verify governed receipts for recurring schedule next-occurrence
calculation, timezone preservation, completion, duplicate prevention, and
high-risk due-candidate controls.
Governance scope: runtime-owned time truth, recurrence rule parsing,
scheduler receipt linkage, evidence anchors, and non-terminal closure.
Dependencies: gateway.temporal_recurrence_window and recurrence receipt schema.
Invariants:
  - The runtime computes the next recurring occurrence.
  - Tenant local time is preserved across timezone offset changes.
  - Unsupported or mismatched recurrence candidates fail closed.
"""

from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from gateway.temporal_recurrence_window import (
    RecurrenceWindowPolicy,
    RecurrenceWindowRequest,
    RecurrenceWindowSnapshot,
    evaluate_temporal_recurrence_window,
    receipt_to_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "temporal_recurrence_window_receipt.schema.json"


def _schema_validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate(receipt):
    payload = receipt_to_dict(receipt)
    errors = sorted(_schema_validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []
    return payload


def _policy(**overrides):
    values = {
        "policy_id": "recurrence-policy-001",
        "tenant_id": "tenant-a",
        "timezone_name": "America/New_York",
    }
    values.update(overrides)
    return RecurrenceWindowPolicy(**values)


def _snapshot(**overrides):
    values = {
        "schedule_id": "schedule-001",
        "tenant_id": "tenant-a",
        "command_id": "cmd-001",
        "action_type": "vendor_payment",
        "recurrence_rule": "FREQ=DAILY;INTERVAL=1",
        "previous_execute_at": "2026-03-07T14:00:00Z",
        "candidate_execute_at": "2026-03-08T13:00:00Z",
        "occurrence_index": 1,
        "scheduler_receipt_id": "scheduler-receipt-abc123",
        "evidence_refs": ["proof://scheduler/recurrence-state"],
    }
    values.update(overrides)
    return RecurrenceWindowSnapshot(**values)


def _request(**overrides):
    values = {
        "request_id": "recurrence-request-001",
        "tenant_id": "tenant-a",
        "actor_id": "worker-001",
        "command_id": "cmd-001",
        "action_type": "vendor_payment",
        "risk_level": "high",
        "policy": _policy(),
        "snapshot": _snapshot(),
        "evidence_refs": ["proof://temporal/recurrence-window"],
        "source_scheduler_receipt_id": "scheduler-receipt-abc123",
        "source_temporal_receipt_id": "temporal-policy-receipt-abc123",
        "source_reapproval_receipt_id": "temporal-reapproval-receipt-abc123",
    }
    values.update(overrides)
    return RecurrenceWindowRequest(**values)


def test_daily_recurrence_preserves_local_time_across_dst_start():
    receipt = evaluate_temporal_recurrence_window(
        _request(),
        runtime_now_utc=datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc),
    )

    payload = _validate(receipt)

    assert payload["status"] == "next_due"
    assert payload["recurrence_state"] == "candidate_matches"
    assert payload["expected_next_execute_at"] == "2026-03-08T13:00:00Z"
    assert payload["expected_local_time"] == "2026-03-08T09:00:00-04:00"
    assert payload["candidate_local_time"] == "2026-03-08T09:00:00-04:00"
    assert payload["metadata"]["dispatch_allowed"] is True


def test_weekly_candidate_not_due_before_runtime_now():
    request = _request(
        risk_level="medium",
        snapshot=_snapshot(
            recurrence_rule="FREQ=WEEKLY;INTERVAL=1",
            previous_execute_at="2026-05-01T13:00:00Z",
            candidate_execute_at="2026-05-08T13:00:00Z",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 5, 5, 13, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "not_due"
    assert payload["recurrence_state"] == "candidate_future"
    assert "recurrence_candidate_not_due" in payload["deferral_reasons"]
    assert payload["expected_next_execute_at"] == "2026-05-08T13:00:00Z"
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["blocked_reasons"] == []


def test_mismatched_candidate_blocks_dispatch():
    request = _request(
        risk_level="medium",
        snapshot=_snapshot(candidate_execute_at="2026-03-08T14:00:00Z"),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["recurrence_state"] == "invalid"
    assert "candidate_execute_at_not_next_occurrence" in payload["blocked_reasons"]
    assert payload["expected_next_execute_at"] == "2026-03-08T13:00:00Z"
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["series_completed"] is False


def test_monthly_recurrence_clamps_end_of_month():
    request = _request(
        risk_level="medium",
        policy=_policy(timezone_name="UTC"),
        snapshot=_snapshot(
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            previous_execute_at="2026-01-31T15:00:00Z",
            candidate_execute_at="2026-02-28T15:00:00Z",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 2, 28, 15, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "next_due"
    assert payload["frequency"] == "MONTHLY"
    assert payload["expected_next_execute_at"] == "2026-02-28T15:00:00Z"
    assert payload["expected_local_time"] == "2026-02-28T15:00:00+00:00"
    assert payload["blocked_reasons"] == []
    assert payload["metadata"]["timezone_preserved"] is True


def test_count_completed_does_not_create_next_occurrence():
    request = _request(
        risk_level="medium",
        snapshot=_snapshot(
            recurrence_rule="FREQ=DAILY;INTERVAL=1;COUNT=2",
            occurrence_index=2,
            candidate_execute_at="2026-03-08T13:00:00Z",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "completed"
    assert payload["recurrence_state"] == "series_completed"
    assert payload["series_completed"] is True
    assert payload["count_limit"] == 2
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["blocked_reasons"] == []


def test_high_risk_due_candidate_requires_reapproval_source():
    request = _request(source_reapproval_receipt_id="")

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["recurrence_state"] == "invalid"
    assert "source_reapproval_receipt_required_for_high_risk_due_candidate" in payload["blocked_reasons"]
    assert "source_temporal_receipt_required_for_high_risk_due_candidate" not in payload["blocked_reasons"]
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["metadata"]["high_risk_reapproval_checked"] is True


def test_duplicate_candidate_requires_terminal_receipt():
    request = _request(
        risk_level="medium",
        snapshot=_snapshot(
            last_dispatched_at="2026-03-08T13:00:00Z",
            terminal_receipt_id="",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["recurrence_state"] == "duplicate_blocked"
    assert "candidate_already_dispatched" in payload["blocked_reasons"]
    assert "terminal_receipt_required_for_dispatched_candidate" in payload["blocked_reasons"]
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["terminal_receipt_id"] == ""


def test_optional_policy_still_blocks_on_tenant_mismatch():
    request = _request(
        risk_level="low",
        policy=_policy(
            tenant_id="tenant-b",
            requires_recurrence_receipt=False,
            high_risk_requires_reapproval_when_due=False,
        ),
        snapshot=None,
        evidence_refs=[],
        source_scheduler_receipt_id="",
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_recurrence_window(
        request,
        runtime_now_utc=datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc),
    )
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["recurrence_state"] == "wrong_scope"
    assert payload["recurrence_required"] is True
    assert payload["blocked_reasons"] == ["policy_tenant_mismatch"]
    assert payload["metadata"]["dispatch_allowed"] is False


def test_runtime_now_must_be_timezone_aware():
    with pytest.raises(ValueError, match="runtime_now_utc must be timezone-aware"):
        evaluate_temporal_recurrence_window(
            _request(),
            runtime_now_utc=datetime(2026, 3, 8, 13, 0),
        )
