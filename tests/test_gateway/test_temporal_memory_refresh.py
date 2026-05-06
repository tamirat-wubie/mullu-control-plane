"""Gateway temporal memory refresh workflow tests.

Purpose: verify stale temporal memory becomes governed refresh work with
evidence coverage, due windows, ownership, activation blocks, and schema-backed
non-terminal receipts.
Governance scope: source memory receipt status, tenant-owner scope, evidence
requirements, review readiness, supersession blocking, and refresh task
creation.
Dependencies: gateway.temporal_memory, gateway.temporal_memory_refresh, and the
temporal memory refresh receipt schema.
Invariants:
  - Usable memory does not create refresh work.
  - Stale memory creates a bounded refresh task.
  - Full evidence coverage moves refresh work to review readiness.
  - Policy or scope violations block refresh planning.
  - Superseded memory remains blocked from reactivation.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_memory import TemporalMemory, TemporalMemoryRecord, TemporalMemoryUseRequest
from gateway.temporal_memory_refresh import MemoryRefreshRequest, TemporalMemoryRefresh
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_memory_refresh_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for refresh workflow tests."""

    def now_utc(self) -> str:
        return NOW


def test_refresh_not_required_for_usable_memory_schema_receipt() -> None:
    source_receipt = TemporalMemory(FixedClock()).evaluate(_memory_use_request())
    receipt = TemporalMemoryRefresh(FixedClock()).evaluate(_refresh_request(source_receipt))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.source_memory_status == "usable"
    assert receipt.refresh_task_id == ""
    assert receipt.refresh_due_at == ""
    assert receipt.metadata["activation_blocked_until_refresh"] is False
    assert receipt.metadata["memory_refresh_task_created"] is False


def test_stale_memory_creates_bounded_refresh_task() -> None:
    source_receipt = _stale_source_receipt()
    receipt = TemporalMemoryRefresh(FixedClock()).evaluate(
        _refresh_request(
            source_receipt,
            required_evidence_types=["closure", "terminal-certificate"],
            candidate_evidence_refs=[],
        )
    )

    assert receipt.status == "refresh_required"
    assert receipt.refresh_task_id.startswith("temporal-memory-refresh-task-")
    assert receipt.refresh_due_at == "2026-05-05T14:00:00+00:00"
    assert receipt.missing_evidence_types == ["closure", "terminal-certificate"]
    assert "memory_evidence_stale" in receipt.refresh_reasons
    assert receipt.metadata["activation_blocked_until_refresh"] is True
    assert receipt.terminal_closure_required is True


def test_complete_refresh_evidence_is_ready_for_review() -> None:
    source_receipt = _stale_source_receipt()
    receipt = TemporalMemoryRefresh(FixedClock()).evaluate(
        _refresh_request(
            source_receipt,
            required_evidence_types=["closure", "terminal-certificate"],
            candidate_evidence_refs=[
                "closure:command-2",
                "terminal-certificate:command-2",
                "untrusted-note:ignored",
            ],
        )
    )

    assert receipt.status == "ready_for_review"
    assert receipt.accepted_evidence_refs == ["closure:command-2", "terminal-certificate:command-2"]
    assert receipt.rejected_evidence_refs == ["untrusted-note:ignored"]
    assert receipt.missing_evidence_types == []
    assert "operator_review" in receipt.required_controls
    assert receipt.metadata["review_required"] is True
    assert receipt.metadata["evidence_type_coverage_complete"] is True


def test_refresh_planning_blocks_invalid_policy_and_scope() -> None:
    source_receipt = _stale_source_receipt()
    receipt = TemporalMemoryRefresh(FixedClock()).evaluate(
        MemoryRefreshRequest(
            request_id="memory-refresh-invalid-1",
            tenant_id="tenant-other",
            owner_id="operator-1",
            actor_id="operator-2",
            refresh_owner_id="operator-3",
            risk_level="high",
            source_receipt=source_receipt,
            refresh_window_seconds=0,
            required_evidence_types=[],
            candidate_evidence_refs=[],
        )
    )

    assert receipt.status == "blocked"
    assert "source_memory_tenant_mismatch" in receipt.blocked_reasons
    assert "refresh_window_seconds_positive_required" in receipt.blocked_reasons
    assert "required_evidence_types_required" in receipt.blocked_reasons
    assert receipt.refresh_task_id == ""
    assert receipt.metadata["activation_blocked_until_refresh"] is True
    assert receipt.metadata["memory_refresh_task_created"] is False


def test_superseded_memory_does_not_create_refresh_task() -> None:
    source_receipt = TemporalMemory(FixedClock()).evaluate(
        _memory_use_request(replace(_memory_record(), superseded_by="mem-vendor-preference-v2"))
    )
    receipt = TemporalMemoryRefresh(FixedClock()).evaluate(_refresh_request(source_receipt))

    assert receipt.status == "superseded"
    assert receipt.source_memory_status == "superseded"
    assert receipt.refresh_task_id == ""
    assert receipt.supersession_reasons == ["memory_superseded"]
    assert "reactivation_block" in receipt.required_controls
    assert receipt.metadata["activation_blocked_until_refresh"] is True


def _refresh_request(
    source_receipt,
    *,
    required_evidence_types: list[str] | None = None,
    candidate_evidence_refs: list[str] | None = None,
) -> MemoryRefreshRequest:
    return MemoryRefreshRequest(
        request_id="memory-refresh-1",
        tenant_id="tenant-1",
        owner_id="operator-1",
        actor_id="operator-2",
        refresh_owner_id="operator-3",
        risk_level="medium",
        source_receipt=source_receipt,
        refresh_window_seconds=3600,
        required_evidence_types=required_evidence_types or ["closure"],
        candidate_evidence_refs=candidate_evidence_refs or [],
    )


def _stale_source_receipt():
    return TemporalMemory(FixedClock()).evaluate(
        _memory_use_request(
            replace(
                _memory_record(),
                last_confirmed_at="2026-05-05T11:00:00+00:00",
                freshness_seconds=1800,
            ),
            risk_level="medium",
        )
    )


def _memory_use_request(
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
        memory=memory or _memory_record(),
    )


def _memory_record() -> TemporalMemoryRecord:
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
