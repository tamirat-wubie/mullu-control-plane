"""Gateway temporal SLA tests.

Purpose: verify SLA deadlines, business windows, warning escalation, breach
detection, and receipt schema compatibility.
Governance scope: runtime clock ownership, business-time calculation,
business-window dispatch, escalation evidence, and non-terminal receipts.
Dependencies: gateway.temporal_sla and temporal SLA receipt schema.
Invariants:
  - Business-time deadlines skip closed windows.
  - Approaching deadlines warn before breach.
  - Breached deadlines emit escalation reasons.
  - Normal dispatch is held outside business windows.
  - Invalid SLA evidence or scope blocks use.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_sla import BusinessWindow, SlaCase, SlaPolicy, TemporalSla, TemporalSlaRequest
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_sla_receipt.schema.json"
NOW = "2026-05-05T13:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for SLA tests."""

    def __init__(self, now: str = NOW) -> None:
        self._now = now

    def now_utc(self) -> str:
        return self._now


def test_temporal_sla_allows_on_track_schema_valid_receipt() -> None:
    receipt = TemporalSla(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "on_track"
    assert receipt.receipt_id.startswith("temporal-sla-receipt-")
    assert receipt.response_deadline_at == "2026-05-05T14:00:00+00:00"
    assert receipt.response_seconds_remaining == 1800
    assert receipt.business_window_status == "inside"
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True
    assert receipt.terminal_closure_required is True


def test_temporal_sla_warns_when_response_deadline_approaches() -> None:
    receipt = TemporalSla(FixedClock("2026-05-05T13:56:00+00:00")).evaluate(_request())

    assert receipt.status == "warning"
    assert "response_deadline_approaching" in receipt.temporal_warnings
    assert "response_warning_escalation_required" in receipt.escalation_reasons
    assert "escalation" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["escalation_required"] is True


def test_temporal_sla_breaches_response_deadline() -> None:
    receipt = TemporalSla(FixedClock("2026-05-05T14:01:00+00:00")).evaluate(_request())

    assert receipt.status == "breached"
    assert "response_sla_breached" in receipt.breach_reasons
    assert "response_escalation_required" in receipt.escalation_reasons
    assert receipt.response_seconds_remaining == 0
    assert receipt.metadata["escalation_required"] is True
    assert receipt.metadata["dispatch_allowed"] is True


def test_temporal_sla_business_time_skips_closed_window() -> None:
    request = _request(
        case=replace(
            _case(),
            opened_at="2026-05-05T16:30:00+00:00",
            last_response_at="2026-05-06T09:20:00+00:00",
        ),
        policy=replace(
            _policy(),
            target_response_seconds=3600,
            target_resolution_seconds=72000,
            warning_seconds=0,
        ),
    )

    receipt = TemporalSla(FixedClock("2026-05-06T13:00:00+00:00")).evaluate(request)

    assert receipt.status == "on_track"
    assert receipt.response_deadline_at == "2026-05-06T09:30:00+00:00"
    assert receipt.response_satisfied_at == "2026-05-06T09:20:00+00:00"
    assert receipt.metadata["deadline_calculation"] == "business_time"
    assert receipt.business_window_status == "inside"
    assert receipt.breach_reasons == []


def test_temporal_sla_holds_normal_dispatch_outside_business_window() -> None:
    request = _request(
        case=replace(_case(), opened_at="2026-05-05T08:00:00+00:00"),
        policy=replace(_policy(), target_response_seconds=7200, warning_seconds=0),
    )

    receipt = TemporalSla(FixedClock("2026-05-05T08:30:00+00:00")).evaluate(request)

    assert receipt.status == "outside_business_window"
    assert receipt.business_window_status == "outside"
    assert receipt.next_business_window_start == "2026-05-05T09:00:00+00:00"
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.temporal_warnings == []
    assert receipt.breach_reasons == []


def test_temporal_sla_blocks_missing_evidence_and_high_severity_contacts() -> None:
    request = _request(
        case=replace(_case(), severity="high", evidence_refs=[]),
        policy=replace(_policy(), severity="high", escalation_contacts=[]),
    )

    receipt = TemporalSla(FixedClock()).evaluate(request)

    assert receipt.status == "blocked"
    assert "evidence_refs_required" in receipt.temporal_violations
    assert "escalation_contacts_required_for_high_severity_sla" in receipt.temporal_violations
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.breach_reasons == []
    assert receipt.receipt_hash


def _request(
    *,
    case: SlaCase | None = None,
    policy: SlaPolicy | None = None,
) -> TemporalSlaRequest:
    return TemporalSlaRequest(
        request_id="sla-request-1",
        tenant_id="tenant-a",
        actor_id="operator-a",
        action_type="support_response",
        case=case or _case(),
        policy=policy or _policy(),
    )


def _case() -> SlaCase:
    return SlaCase(
        case_id="case-1",
        tenant_id="tenant-a",
        owner_id="support-lead-a",
        severity="medium",
        opened_at="2026-05-05T13:00:00+00:00",
        evidence_refs=["audit:case-opened:1"],
    )


def _policy() -> SlaPolicy:
    return SlaPolicy(
        policy_id="sla-policy-medium",
        tenant_id="tenant-a",
        severity="medium",
        timezone_name="UTC",
        target_response_seconds=3600,
        target_resolution_seconds=7200,
        warning_seconds=300,
        business_windows=[BusinessWindow(day, "09:00:00", "17:00:00") for day in range(5)],
        holidays=[],
        escalation_contacts=["support-manager-a"],
    )
