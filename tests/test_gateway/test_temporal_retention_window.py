"""Gateway temporal retention window tests.

Purpose: verify retention-window receipts are runtime-owned, lifecycle-aware,
tenant-scoped, legal-hold-aware, source-bound, and schema-backed before data
lifecycle action dispatch.
Governance scope: retention_until, delete_after, legal hold, tenant scope,
retention policy refs, owner refs, evidence refs, high-risk source binding,
and non-terminal temporal retention window receipts.
Dependencies: gateway.temporal_retention_window and temporal retention window
receipt schema.
Invariants:
  - Data deletion cannot run before delete_after.
  - Archive, anonymize, and review actions cannot run before retention_until.
  - Legal hold blocks lifecycle actions regardless of retention age.
  - High-risk lifecycle actions bind temporal, reapproval, and data-decision receipts.
  - Low-risk policies may mark retention-window control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_retention_window import (
    RetentionSubject,
    TemporalRetentionPolicy,
    TemporalRetentionRequest,
    TemporalRetentionWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_retention_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for retention window tests."""

    def now_utc(self) -> str:
        return NOW


def test_retention_window_defers_delete_before_delete_after() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "retention_active"
    assert receipt.retention_state == "retained"
    assert receipt.seconds_until_retention_until == 0
    assert receipt.seconds_until_delete_after == 3600
    assert receipt.seconds_until_action_due == 3600
    assert receipt.overdue_seconds == 0
    assert "retention_window_not_expired" in receipt.warning_reasons
    assert "retention_defer" in receipt.required_controls
    assert receipt.metadata["lifecycle_action_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_retention_window_allows_delete_at_due_boundary() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        _request(subject=replace(_subject(), delete_after=NOW))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "action_due"
    assert receipt.retention_state == "action_due"
    assert receipt.target_action_due_at == NOW
    assert receipt.seconds_until_action_due == 0
    assert receipt.overdue_seconds == 0
    assert receipt.warning_reasons == []
    assert "lifecycle_action_receipt" in receipt.required_controls
    assert "audit_trail" in receipt.required_controls
    assert receipt.metadata["lifecycle_action_allowed"] is True


def test_retention_window_marks_overdue_after_warning_window() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        _request(
            subject=replace(
                _subject(),
                retention_until="2026-05-05T11:00:00+00:00",
                delete_after="2026-05-05T12:00:00+00:00",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "overdue"
    assert receipt.retention_state == "overdue"
    assert receipt.seconds_until_action_due == 0
    assert receipt.overdue_seconds == 9000
    assert "retention_action_overdue" in receipt.warning_reasons
    assert "retention_overdue_review" in receipt.required_controls
    assert receipt.blocked_reasons == []
    assert receipt.metadata["lifecycle_action_allowed"] is True


def test_retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        _request(
            subject=replace(
                _subject(),
                tenant_id="tenant-other",
                legal_hold=True,
                evidence_refs=[],
            ),
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            source_data_decision_id="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.retention_state == "legal_hold"
    assert "retention_subject_tenant_mismatch" in receipt.blocked_reasons
    assert "legal_hold_blocks_lifecycle_action" in receipt.blocked_reasons
    assert "subject_evidence_refs_required" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_data_decision_required_for_high_risk" in receipt.blocked_reasons
    assert "destructive_action_reapproval_required" in receipt.blocked_reasons
    assert receipt.metadata["lifecycle_action_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_retention_window_blocks_invalid_or_future_record() -> None:
    future_receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        _request(subject=replace(_subject(), created_at="2026-05-05T15:00:00+00:00"))
    )
    invalid_receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        _request(
            subject=replace(
                _subject(),
                retention_until="2026-05-05T15:00:00+00:00",
                delete_after="2026-05-05T13:00:00+00:00",
            )
        )
    )

    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(future_receipt)) == []
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(invalid_receipt)) == []
    assert future_receipt.status == "blocked"
    assert future_receipt.retention_state == "invalid"
    assert "retention_subject_created_in_future" in future_receipt.blocked_reasons
    assert invalid_receipt.status == "blocked"
    assert invalid_receipt.retention_state == "invalid"
    assert "delete_after_precedes_retention_until" in invalid_receipt.blocked_reasons
    assert invalid_receipt.metadata["lifecycle_action_allowed"] is False


def test_retention_window_allows_archive_after_retention_until() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(_request(action_type="archive"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "action_due"
    assert receipt.retention_state == "action_due"
    assert receipt.target_action_due_at == "2026-05-05T14:00:00+00:00"
    assert receipt.seconds_until_retention_until == 0
    assert receipt.seconds_until_action_due == 0
    assert receipt.overdue_seconds == 1800
    assert receipt.warning_reasons == []
    assert receipt.metadata["lifecycle_action_allowed"] is True


def test_retention_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalRetentionWindow(FixedClock()).evaluate(
        TemporalRetentionRequest(
            request_id="retention-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="retain",
            risk_level="low",
            policy=replace(_policy(), requires_retention_check=False),
            subject=None,
            evidence_refs=[],
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.retention_state == "not_required"
    assert receipt.retention_check_required is False
    assert receipt.data_id == ""
    assert receipt.seconds_until_action_due == 0
    assert receipt.blocked_reasons == []
    assert receipt.warning_reasons == []
    assert receipt.metadata["lifecycle_action_allowed"] is True
    assert receipt.metadata["retention_checked"] is False


def _request(
    *,
    action_type: str = "delete",
    subject: RetentionSubject | None = None,
    policy: TemporalRetentionPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
    source_data_decision_id: str = "data-decision-0123456789abcdef",
) -> TemporalRetentionRequest:
    return TemporalRetentionRequest(
        request_id="retention-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type=action_type,
        risk_level="high",
        policy=policy or _policy(),
        subject=subject if subject is not None else _subject(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://retention/policy-1"],
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
        source_data_decision_id=source_data_decision_id,
    )


def _policy() -> TemporalRetentionPolicy:
    return TemporalRetentionPolicy(
        policy_id="retention-policy-1",
        tenant_id="tenant-1",
        allowed_actions=["delete", "archive", "anonymize", "review"],
        overdue_warning_seconds=3600,
        requires_retention_check=True,
        high_risk_requires_retention_check=True,
    )


def _subject() -> RetentionSubject:
    return RetentionSubject(
        data_id="data-1",
        tenant_id="tenant-1",
        classification="pii",
        purpose="customer_support",
        created_at="2026-01-01T00:00:00+00:00",
        retention_until="2026-05-05T14:00:00+00:00",
        delete_after="2026-05-05T15:30:00+00:00",
        retention_policy_ref="retention://pii-120d",
        owner_id="data-owner-1",
        evidence_refs=["proof://retention/evidence-1"],
        legal_hold=False,
        source_event_id="trace-1",
        record_hash="record-hash-0123456789abcdef",
    )
