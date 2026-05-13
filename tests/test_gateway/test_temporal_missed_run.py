"""Gateway temporal missed-run tests.

Purpose: verify governed receipts for late, expired, duplicate-dispatched, and
blocked scheduled commands.
Governance scope: runtime-owned time truth, scheduler receipt linkage, high-risk
source controls, evidence anchors, and terminal-closure separation.
Dependencies: gateway.temporal_missed_run and temporal missed-run schema.
Invariants:
  - Missed scheduled work cannot be silent when policy requires a receipt.
  - Late-within-grace work remains dispatch-eligible only after receipt proof.
  - High-risk missed work requires upstream temporal and reapproval receipts.
"""

from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from gateway.temporal_missed_run import (
    MissedRunPolicy,
    MissedRunRequest,
    MissedRunSnapshot,
    evaluate_temporal_missed_run,
    receipt_to_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "temporal_missed_run_receipt.schema.json"
NOW = datetime(2026, 5, 5, 13, 0, tzinfo=timezone.utc)


def _schema_validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _policy(**overrides):
    values = {
        "policy_id": "missed-run-policy-001",
        "tenant_id": "tenant-a",
        "scope_id": "scheduler:tenant-a",
        "max_lateness_seconds": 3600,
        "grace_seconds": 300,
    }
    values.update(overrides)
    return MissedRunPolicy(**values)


def _snapshot(**overrides):
    values = {
        "schedule_id": "schedule-001",
        "tenant_id": "tenant-a",
        "command_id": "cmd-001",
        "action_type": "vendor_payment",
        "execute_at": "2026-05-05T12:00:00Z",
        "observed_at": "2026-05-05T13:00:00Z",
        "expires_at": "2026-05-05T12:30:00Z",
        "attempt_count": 0,
        "max_attempts": 3,
        "scheduler_receipt_id": "temporal-scheduler-receipt-abc123",
        "evidence_refs": ["proof://scheduler/due-check"],
    }
    values.update(overrides)
    return MissedRunSnapshot(**values)


def _request(**overrides):
    values = {
        "request_id": "missed-run-request-001",
        "tenant_id": "tenant-a",
        "actor_id": "worker-001",
        "command_id": "cmd-001",
        "action_type": "vendor_payment",
        "risk_level": "high",
        "policy": _policy(),
        "snapshot": _snapshot(),
        "evidence_refs": ["proof://temporal/scheduler-window"],
        "source_temporal_receipt_id": "temporal-policy-receipt-abc123",
        "source_scheduler_receipt_id": "temporal-scheduler-receipt-abc123",
        "source_reapproval_receipt_id": "temporal-reapproval-receipt-abc123",
    }
    values.update(overrides)
    return MissedRunRequest(**values)


def _validate(receipt):
    payload = receipt_to_dict(receipt)
    errors = sorted(_schema_validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []
    return payload


def test_expired_command_emits_missed_run_receipt():
    receipt = evaluate_temporal_missed_run(_request(), runtime_now_utc=NOW)

    payload = _validate(receipt)

    assert payload["status"] == "missed"
    assert payload["missed_run_state"] == "missed_expired"
    assert payload["lateness_seconds"] == 3600
    assert "command_expired_before_execution" in payload["missed_reasons"]
    assert payload["metadata"]["dispatch_allowed"] is False
    assert payload["terminal_closure_required"] is True


def test_late_within_grace_remains_dispatch_eligible():
    request = _request(
        risk_level="medium",
        snapshot=_snapshot(
            execute_at="2026-05-05T12:57:00Z",
            expires_at="2026-05-05T13:30:00Z",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "late_within_grace"
    assert payload["missed_run_state"] == "late_allowed"
    assert payload["lateness_seconds"] == 180
    assert payload["missed_reasons"] == []
    assert payload["metadata"]["dispatch_allowed"] is True
    assert payload["metadata"]["recovery_required"] is False


def test_recovery_due_when_late_but_not_expired():
    request = _request(
        risk_level="medium",
        policy=_policy(max_lateness_seconds=7200, grace_seconds=60),
        snapshot=_snapshot(
            execute_at="2026-05-05T12:00:00Z",
            expires_at="2026-05-05T14:00:00Z",
            attempt_count=1,
            max_attempts=3,
            recurring=True,
            recurrence_rule="FREQ=DAILY;INTERVAL=1",
        ),
        source_temporal_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "recovery_due"
    assert payload["missed_run_state"] == "recovery_allowed"
    assert payload["missed_reasons"] == ["missed_run_recovery_due"]
    assert "queue_recovery_review" in payload["recovery_actions"]
    assert "retry_if_governance_allows" in payload["recovery_actions"]
    assert payload["metadata"]["recovery_required"] is True


def test_duplicate_dispatched_run_requires_terminal_receipt():
    request = _request(
        snapshot=_snapshot(
            already_dispatched=True,
            terminal_receipt_id="terminal-receipt-001",
            expires_at="2026-05-05T14:00:00Z",
        )
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "duplicate_dispatched"
    assert payload["missed_run_state"] == "already_dispatched"
    assert payload["already_dispatched"] is True
    assert payload["terminal_receipt_id"] == "terminal-receipt-001"
    assert payload["missed_reasons"] == []
    assert payload["metadata"]["dispatch_allowed"] is False


def test_high_risk_missed_run_blocks_without_required_sources_and_evidence():
    request = _request(
        evidence_refs=[],
        source_temporal_receipt_id="",
        source_scheduler_receipt_id="",
        source_reapproval_receipt_id="",
        snapshot=_snapshot(
            tenant_id="tenant-b",
            command_id="cmd-other",
            action_type="refund",
            observed_at="2026-05-05T13:30:00Z",
            scheduler_receipt_id="temporal-scheduler-receipt-different",
            evidence_refs=[],
        ),
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["missed_run_state"] == "wrong_scope"
    assert "snapshot_tenant_mismatch" in payload["blocked_reasons"]
    assert "source_temporal_receipt_required_for_high_risk" in payload["blocked_reasons"]
    assert "source_reapproval_receipt_required_for_high_risk" in payload["blocked_reasons"]
    assert "observed_at_in_future" in payload["blocked_reasons"]


def test_invalid_temporal_order_blocks():
    request = _request(
        snapshot=_snapshot(
            execute_at="2026-05-05T12:00:00Z",
            observed_at="2026-05-05T11:59:00Z",
            expires_at="2026-05-05T11:30:00Z",
            last_attempt_at="2026-05-05T13:30:00Z",
        )
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["missed_run_state"] == "invalid"
    assert "observed_before_execute_at" in payload["blocked_reasons"]
    assert "expires_at_before_execute_at" in payload["blocked_reasons"]
    assert "last_attempt_at_in_future" in payload["blocked_reasons"]


def test_low_risk_policy_can_mark_receipt_not_required():
    request = _request(
        risk_level="low",
        policy=_policy(
            requires_missed_run_receipt=False,
            high_risk_requires_missed_run_receipt=False,
        ),
        snapshot=None,
        evidence_refs=[],
        source_temporal_receipt_id="",
        source_scheduler_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "not_required"
    assert payload["missed_run_state"] == "not_required"
    assert payload["missed_run_required"] is False
    assert payload["schedule_id"] == ""
    assert payload["required_controls"] == []
    assert payload["metadata"]["missed_run_checked"] is False


def test_optional_policy_still_blocks_on_tenant_mismatch():
    request = _request(
        risk_level="low",
        policy=_policy(
            tenant_id="tenant-b",
            requires_missed_run_receipt=False,
            high_risk_requires_missed_run_receipt=False,
        ),
        snapshot=None,
        evidence_refs=[],
        source_temporal_receipt_id="",
        source_scheduler_receipt_id="",
        source_reapproval_receipt_id="",
    )

    receipt = evaluate_temporal_missed_run(request, runtime_now_utc=NOW)
    payload = _validate(receipt)

    assert payload["status"] == "blocked"
    assert payload["missed_run_state"] == "wrong_scope"
    assert payload["missed_run_required"] is True
    assert payload["blocked_reasons"] == ["policy_tenant_mismatch"]
    assert payload["metadata"]["dispatch_allowed"] is False


def test_runtime_now_must_be_timezone_aware():
    request = _request()

    with pytest.raises(ValueError, match="runtime_now_utc must be timezone-aware"):
        evaluate_temporal_missed_run(request, runtime_now_utc=datetime(2026, 5, 5, 13, 0))
