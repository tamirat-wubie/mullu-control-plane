"""Gateway temporal evidence freshness tests.

Purpose: verify evidence freshness rechecks are runtime-owned, type-covered,
scope-bound, high-risk verified, and schema-backed before dispatch.
Governance scope: freshness windows, required evidence coverage, missing or
stale evidence refresh, tenant scope, revocation, and non-terminal receipts.
Dependencies: gateway.temporal_evidence_freshness and temporal evidence
freshness receipt schema.
Invariants:
  - Fresh required evidence can support dispatch.
  - Stale required evidence requires refresh.
  - Missing required evidence blocks dispatch as insufficient evidence.
  - Revoked, out-of-scope, or unverified high-risk evidence blocks dispatch.
  - Expiring evidence remains fresh but requires a recheck by expiry.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_evidence_freshness import (
    EvidenceFreshnessClaim,
    EvidenceFreshnessRequest,
    TemporalEvidenceFreshness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_evidence_freshness_receipt.schema.json"
NOW = "2026-05-05T13:00:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for evidence freshness tests."""

    def now_utc(self) -> str:
        return NOW


def test_evidence_freshness_allows_fresh_required_schema_receipt() -> None:
    receipt = TemporalEvidenceFreshness(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "fresh"
    assert receipt.accepted_evidence_refs == ["approval:manager-1", "price-check:quote-1"]
    assert receipt.missing_evidence_types == []
    assert receipt.earliest_fresh_until == "2026-05-05T13:45:00+00:00"
    assert receipt.recheck_due_at == "2026-05-05T13:45:00+00:00"
    assert receipt.metadata["evidence_fresh_for_dispatch"] is True
    assert receipt.terminal_closure_required is True


def test_evidence_freshness_requires_refresh_for_stale_required_type() -> None:
    receipt = TemporalEvidenceFreshness(FixedClock()).evaluate(
        _request(
            evidence_claims=[
                _approval_claim(),
                replace(
                    _price_claim(),
                    observed_at="2026-05-05T11:00:00+00:00",
                    freshness_seconds=1800,
                    fresh_until="",
                ),
            ]
        )
    )

    assert receipt.status == "refresh_required"
    assert receipt.stale_evidence_refs == ["price-check:quote-1"]
    assert receipt.stale_evidence_types == ["price-check"]
    assert receipt.refresh_due_at == "2026-05-05T14:00:00+00:00"
    assert "evidence_refresh" in receipt.required_controls
    assert receipt.metadata["refresh_required"] is True
    assert receipt.metadata["evidence_fresh_for_dispatch"] is False


def test_evidence_freshness_blocks_missing_required_evidence() -> None:
    receipt = TemporalEvidenceFreshness(FixedClock()).evaluate(
        _request(evidence_claims=[_approval_claim()])
    )

    assert receipt.status == "insufficient_evidence"
    assert receipt.accepted_evidence_refs == ["approval:manager-1"]
    assert receipt.missing_evidence_types == ["price-check"]
    assert receipt.refresh_due_at == "2026-05-05T14:00:00+00:00"
    assert "dispatch_block" in receipt.required_controls
    assert receipt.blocked_reasons == []
    assert receipt.metadata["recheck_required_before_dispatch"] is True


def test_evidence_freshness_blocks_revoked_unverified_or_wrong_tenant_evidence() -> None:
    receipt = TemporalEvidenceFreshness(FixedClock()).evaluate(
        _request(
            evidence_claims=[
                replace(_approval_claim(), verified=False),
                replace(_price_claim(), tenant_id="tenant-other"),
                replace(
                    _price_claim("price-check:revoked-quote"),
                    revoked_at="2026-05-05T12:59:00+00:00",
                ),
            ]
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval:manager-1:unverified_evidence_for_high_risk_action" in receipt.blocked_reasons
    assert "price-check:quote-1:evidence_tenant_mismatch" in receipt.blocked_reasons
    assert "price-check:revoked-quote:evidence_revoked" in receipt.blocked_reasons
    assert set(receipt.blocked_evidence_refs) == {
        "approval:manager-1",
        "price-check:quote-1",
        "price-check:revoked-quote",
    }
    assert receipt.refresh_due_at == ""
    assert receipt.metadata["evidence_fresh_for_dispatch"] is False


def test_evidence_freshness_warns_when_evidence_is_expiring_soon() -> None:
    receipt = TemporalEvidenceFreshness(FixedClock()).evaluate(
        _request(
            expiry_warning_seconds=600,
            evidence_claims=[
                _approval_claim(),
                replace(_price_claim(), fresh_until="2026-05-05T13:05:00+00:00"),
            ],
        )
    )

    assert receipt.status == "fresh"
    assert receipt.expiring_soon_evidence_refs == ["price-check:quote-1"]
    assert "price-check:quote-1:evidence_expiring_soon" in receipt.evidence_warnings
    assert receipt.earliest_fresh_until == "2026-05-05T13:05:00+00:00"
    assert receipt.recheck_due_at == "2026-05-05T13:05:00+00:00"
    assert receipt.refresh_due_at == ""
    assert receipt.evidence_states[1].status == "expiring_soon"


def _request(
    *,
    evidence_claims: list[EvidenceFreshnessClaim] | None = None,
    expiry_warning_seconds: int = 0,
) -> EvidenceFreshnessRequest:
    return EvidenceFreshnessRequest(
        request_id="evidence-freshness-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="vendor_payment",
        risk_level="high",
        required_evidence_types=["approval", "price-check"],
        evidence_claims=evidence_claims or [_approval_claim(), _price_claim()],
        refresh_window_seconds=3600,
        expiry_warning_seconds=expiry_warning_seconds,
        source_temporal_receipt_id="temporal-receipt-0123456789abcdef",
    )


def _approval_claim() -> EvidenceFreshnessClaim:
    return EvidenceFreshnessClaim(
        evidence_ref="approval:manager-1",
        evidence_type="approval",
        tenant_id="tenant-1",
        observed_at="2026-05-05T12:30:00+00:00",
        fresh_until="2026-05-05T14:00:00+00:00",
        source_event_id="event-approval-1",
        verified=True,
    )


def _price_claim(evidence_ref: str = "price-check:quote-1") -> EvidenceFreshnessClaim:
    return EvidenceFreshnessClaim(
        evidence_ref=evidence_ref,
        evidence_type="price-check",
        tenant_id="tenant-1",
        observed_at="2026-05-05T12:45:00+00:00",
        fresh_until="2026-05-05T13:45:00+00:00",
        source_event_id="event-price-check-1",
        verified=True,
    )
