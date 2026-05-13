"""Gateway temporal resolution tests.

Purpose: verify bounded temporal phrases resolve through runtime-owned time,
tenant timezone policy, ambiguity controls, business calendars, and schema
contracts before scheduling or dispatch.
Governance scope: phrase resolution, original text preservation, high-risk
clarification, evidence refs, business-day calculation, and non-terminal
temporal resolution receipts.
Dependencies: gateway.temporal_resolution and temporal resolution receipt
schema.
Invariants:
  - Runtime time is injected, not guessed from the phrase.
  - Tenant timezone controls local phrase resolution.
  - Ambiguous high-risk phrases require clarification.
  - Unsupported phrases do not produce executable timestamps.
  - Business-day calculations skip weekends and holidays.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gateway.temporal_resolution import (
    TemporalResolutionPolicy,
    TemporalResolutionRequest,
    evaluate_temporal_resolution,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_resolution_receipt.schema.json"
NOW = datetime(2026, 5, 4, 13, 10, tzinfo=timezone.utc)


def test_temporal_resolution_resolves_relative_duration_from_runtime_now() -> None:
    receipt = evaluate_temporal_resolution(_request(original_text="in 3 hours"), runtime_now_utc=NOW)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "resolved"
    assert receipt.resolution_state == "relative_duration"
    assert receipt.resolved_execute_at == "2026-05-04T16:10:00+00:00"
    assert receipt.local_resolved_time == "2026-05-04T12:10:00-04:00"
    assert receipt.metadata["runtime_owns_time_truth"] is True


def test_temporal_resolution_resolves_tomorrow_explicit_time_in_tenant_timezone() -> None:
    receipt = evaluate_temporal_resolution(_request(original_text="tomorrow at 9am"), runtime_now_utc=NOW)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "resolved"
    assert receipt.resolution_state == "tomorrow_explicit"
    assert receipt.resolved_execute_at == "2026-05-05T13:00:00+00:00"
    assert receipt.local_resolved_time == "2026-05-05T09:00:00-04:00"
    assert receipt.ambiguity_level == "none"


def test_temporal_resolution_low_risk_ambiguous_tomorrow_uses_safe_default() -> None:
    receipt = evaluate_temporal_resolution(
        _request(original_text="tomorrow morning", risk_level="low", source_clock_sample_id=""),
        runtime_now_utc=NOW,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "resolved"
    assert receipt.resolution_state == "tomorrow_defaulted"
    assert receipt.safe_default_execute_at == "2026-05-05T13:00:00+00:00"
    assert "ambiguous_time_defaulted" in receipt.warning_reasons
    assert receipt.metadata["safe_default_used"] is True


def test_temporal_resolution_high_risk_ambiguous_tomorrow_requires_clarification() -> None:
    receipt = evaluate_temporal_resolution(_request(original_text="tomorrow morning"), runtime_now_utc=NOW)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "needs_clarification"
    assert receipt.clarification_required is True
    assert receipt.resolved_execute_at == ""
    assert receipt.safe_default_execute_at == "2026-05-05T13:00:00+00:00"
    assert "operator_clarification" in receipt.required_controls


def test_temporal_resolution_business_days_skip_weekend_and_holiday() -> None:
    friday = datetime(2026, 5, 8, 14, 0, tzinfo=timezone.utc)
    receipt = evaluate_temporal_resolution(
        _request(
            original_text="within 2 business days",
            risk_level="medium",
            source_clock_sample_id="",
            policy=replace(_policy(), holidays=["2026-05-11"]),
        ),
        runtime_now_utc=friday,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "resolved"
    assert receipt.resolution_state == "business_day"
    assert receipt.business_day_count == 2
    assert receipt.resolved_execute_at == "2026-05-13T21:00:00+00:00"
    assert receipt.business_calendar_used is True


def test_temporal_resolution_end_of_day_uses_tenant_business_close() -> None:
    receipt = evaluate_temporal_resolution(
        _request(original_text="before end of day", risk_level="medium", source_clock_sample_id=""),
        runtime_now_utc=NOW,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "resolved"
    assert receipt.resolution_state == "end_of_day"
    assert receipt.resolved_execute_at == "2026-05-04T21:00:00+00:00"
    assert receipt.local_resolved_time == "2026-05-04T17:00:00-04:00"
    assert "business_day_end_defaulted" in receipt.warning_reasons


def test_temporal_resolution_unsupported_phrase_fails_closed() -> None:
    receipt = evaluate_temporal_resolution(
        _request(original_text="when ready", risk_level="low", source_clock_sample_id=""),
        runtime_now_utc=NOW,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "unsupported"
    assert receipt.resolution_state == "unsupported"
    assert receipt.resolved_execute_at == ""
    assert receipt.safe_default_execute_at == ""
    assert receipt.metadata["temporal_phrase_resolved"] is False


def test_temporal_resolution_blocks_missing_evidence_and_scope_mismatch() -> None:
    receipt = evaluate_temporal_resolution(
        _request(evidence_refs=[], policy=replace(_policy(), tenant_id="tenant-other")),
        runtime_now_utc=NOW,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "policy_tenant_mismatch" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_clock_sample_required_for_high_risk" not in receipt.blocked_reasons
    assert receipt.metadata["temporal_phrase_resolved"] is False


def test_temporal_resolution_requires_timezone_aware_runtime_now() -> None:
    with pytest.raises(ValueError, match="runtime_now_utc_timezone_required"):
        evaluate_temporal_resolution(
            _request(original_text="in 1 hour"),
            runtime_now_utc=datetime(2026, 5, 4, 13, 10),
        )


def _request(
    *,
    original_text: str = "tomorrow at 9am",
    risk_level: str = "high",
    evidence_refs: list[str] | None = None,
    source_clock_sample_id: str = "clock-sample-0123456789abcdef",
    policy: TemporalResolutionPolicy | None = None,
) -> TemporalResolutionRequest:
    return TemporalResolutionRequest(
        request_id="temporal-resolution-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level=risk_level,
        original_text=original_text,
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://clock/runtime-now"],
        source_clock_sample_id=source_clock_sample_id,
        source_temporal_receipt_id="temporal-receipt-0123456789abcdef",
    )


def _policy() -> TemporalResolutionPolicy:
    return TemporalResolutionPolicy(
        policy_id="temporal-resolution-policy-1",
        tenant_id="tenant-1",
        timezone_name="America/New_York",
        default_morning_time="09:00",
        default_due_time="09:00",
        business_day_start_time="09:00",
        business_day_end_time="17:00",
        business_weekdays=[0, 1, 2, 3, 4],
    )
