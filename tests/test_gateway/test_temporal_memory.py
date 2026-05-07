"""Gateway temporal memory tests.

Purpose: verify governed memory use is time-valid, freshness-aware,
confidence-decayed, supersession-aware, scope-bound, and schema-backed.
Governance scope: temporal memory use admission, stale evidence refresh,
validity windows, supersession, confidence decay, and non-terminal receipts.
Dependencies: gateway.temporal_memory and temporal memory receipt schema.
Invariants:
  - Fresh valid memory is usable.
  - Stale memory requires evidence refresh.
  - Expired or forbidden memory is blocked.
  - Superseded memory is not usable.
  - Decayed confidence can block memory use.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_memory import TemporalMemory, TemporalMemoryRecord, TemporalMemoryUseRequest
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_memory_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for temporal memory tests."""

    def now_utc(self) -> str:
        return NOW


def test_temporal_memory_allows_fresh_valid_schema_receipt() -> None:
    receipt = TemporalMemory(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "usable"
    assert receipt.receipt_id.startswith("temporal-memory-receipt-")
    assert receipt.age_seconds == 1800
    assert receipt.stale_seconds == 0
    assert receipt.decayed_confidence == 0.995
    assert receipt.metadata["memory_usable"] is True
    assert receipt.terminal_closure_required is True


def test_temporal_memory_requires_refresh_for_stale_evidence() -> None:
    receipt = TemporalMemory(FixedClock()).evaluate(
        _request(
            replace(
                _record(),
                last_confirmed_at="2026-05-05T11:00:00+00:00",
                freshness_seconds=1800,
            ),
            risk_level="medium",
        )
    )

    assert receipt.status == "refresh_required"
    assert receipt.temporal_violations == []
    assert "memory_evidence_stale" in receipt.temporal_warnings
    assert receipt.age_seconds == 7200
    assert receipt.stale_seconds == 5400
    assert receipt.metadata["evidence_refresh_required"] is True


def test_temporal_memory_blocks_expired_forbidden_high_risk_use() -> None:
    receipt = TemporalMemory(FixedClock()).evaluate(
        _request(
            replace(
                _record(),
                allowed_use=["audit"],
                forbidden_use=["planning"],
                valid_until="2026-05-05T12:59:00+00:00",
                freshness_seconds=0,
            )
        )
    )

    assert receipt.status == "blocked"
    assert "memory_use_forbidden" in receipt.temporal_violations
    assert "memory_use_not_allowed" in receipt.temporal_violations
    assert "memory_validity_expired" in receipt.temporal_violations
    assert "freshness_window_required_for_high_risk_memory" in receipt.temporal_violations
    assert receipt.metadata["memory_usable"] is False


def test_temporal_memory_blocks_superseded_record_without_deleting_history() -> None:
    receipt = TemporalMemory(FixedClock()).evaluate(
        _request(replace(_record(), superseded_by="mem-vendor-preference-v2"))
    )

    assert receipt.status == "superseded"
    assert receipt.temporal_violations == []
    assert "memory_superseded" in receipt.supersession_reasons
    assert receipt.superseded_by == "mem-vendor-preference-v2"
    assert "supersession" in receipt.required_controls
    assert receipt.metadata["memory_usable"] is False


def test_temporal_memory_blocks_when_confidence_decays_below_minimum() -> None:
    receipt = TemporalMemory(FixedClock()).evaluate(
        _request(
            replace(
                _record(),
                confidence=0.70,
                min_confidence=0.65,
                last_confirmed_at="2026-05-01T13:00:00+00:00",
                freshness_seconds=604800,
                confidence_decay_per_day=0.03,
            )
        )
    )

    assert receipt.status == "blocked"
    assert "memory_confidence_below_minimum" in receipt.temporal_violations
    assert receipt.decayed_confidence == 0.58
    assert receipt.stale_seconds == 0
    assert receipt.metadata["confidence_decay_applied"] is True
    assert receipt.metadata["memory_usable"] is False


def _request(
    memory: TemporalMemoryRecord | None = None,
    *,
    risk_level: str = "high",
) -> TemporalMemoryUseRequest:
    return TemporalMemoryUseRequest(
        request_id="memory-use-1",
        tenant_id="tenant-1",
        owner_id="operator-1",
        action_type="vendor_payment",
        risk_level=risk_level,
        use_context="planning",
        memory=memory or _record(),
    )


def _record() -> TemporalMemoryRecord:
    return TemporalMemoryRecord(
        memory_id="mem-vendor-preference-v1",
        tenant_id="tenant-1",
        owner_id="operator-1",
        scope="preference",
        subject="vendor_payment_channel",
        value="Use vendor portal A for invoices.",
        source_event_id="event-closure-1",
        observed_at="2026-05-05T12:00:00+00:00",
        learned_at="2026-05-05T12:05:00+00:00",
        last_confirmed_at="2026-05-05T12:30:00+00:00",
        valid_from="2026-05-05T12:00:00+00:00",
        valid_until="2026-06-05T12:00:00+00:00",
        evidence_refs=["closure:command-1", "terminal-certificate:1"],
        allowed_use=["planning", "audit"],
        forbidden_use=["external_sharing"],
        confidence=1.0,
        freshness_seconds=7200,
        confidence_decay_per_day=0.24,
        min_confidence=0.5,
        sensitivity="medium",
    )
