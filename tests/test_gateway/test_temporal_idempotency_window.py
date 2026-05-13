"""Gateway temporal idempotency window tests.

Purpose: verify idempotency receipts are runtime-owned, scope-aware,
fingerprint-aware, replay-window-aware, committed-effect-aware, source-bound,
and schema-backed before effect dispatch.
Governance scope: idempotency timing, tenant scope, command scope, action
scope, request fingerprints, evidence refs, high-risk source binding, and
non-terminal temporal idempotency window receipts.
Dependencies: gateway.temporal_idempotency_window and temporal idempotency
window receipt schema.
Invariants:
  - New keys create bounded replay windows before dispatch.
  - Matching uncommitted replays may dispatch only inside the window.
  - Committed, expired, mismatched, and malformed replays fail closed.
  - Low-risk policies may mark idempotency control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.temporal_idempotency_window import (
    IdempotencySnapshot,
    IdempotencyWindowPolicy,
    IdempotencyWindowRequest,
    TemporalIdempotencyWindow,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_idempotency_window_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"
DEFAULT_SNAPSHOT = object()


class FixedClock:
    """Deterministic wall-clock provider for idempotency window tests."""

    def now_utc(self) -> str:
        return NOW


def test_idempotency_window_admits_new_key_with_runtime_window() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(_request(snapshot=None))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "admit_new"
    assert receipt.idempotency_state == "new_key"
    assert receipt.idempotency_key == "idem-1"
    assert receipt.first_seen_at == NOW
    assert receipt.expires_at == "2026-05-05T16:30:00+00:00"
    assert receipt.seconds_until_expiry == 7200
    assert receipt.attempt_count == 1
    assert "new_idempotency_key_admission" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_idempotency_window_admits_matching_uncommitted_replay() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "admit_replay"
    assert receipt.idempotency_state == "matching_replay"
    assert receipt.window_age_seconds == 1800
    assert receipt.seconds_until_expiry == 5400
    assert receipt.stored_request_fingerprint == "sha256:request-1"
    assert receipt.snapshot_evidence_refs == ["proof://idempotency/idem-1"]
    assert "matching_replay_admission" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["committed_effect_checked"] is True


def test_idempotency_window_blocks_duplicate_committed_effect_without_dispatch() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                effect_committed=True,
                terminal_receipt_id="terminal-closure-certificate-1",
                prior_receipt_id="temporal-idempotency-window-receipt-0123456789abcdef",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "duplicate_committed"
    assert receipt.idempotency_state == "committed"
    assert receipt.effect_committed is True
    assert receipt.terminal_receipt_id == "terminal-closure-certificate-1"
    assert "duplicate_dispatch_block" in receipt.required_controls
    assert "terminal_receipt_reuse" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["committed_effect_checked"] is True


def test_idempotency_window_blocks_expired_replay_window() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(
        _request(snapshot=replace(_snapshot(), expires_at="2026-05-05T14:30:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "idempotency_expired"
    assert receipt.idempotency_state == "expired"
    assert receipt.seconds_until_expiry == 0
    assert receipt.blocked_reasons == []
    assert "idempotency_expiry_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["idempotency_checked"] is True


def test_idempotency_window_blocks_scope_fingerprint_evidence_and_source_gaps() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(
        _request(
            idempotency_key="idem-request",
            request_fingerprint="sha256:request-current",
            action_type="finance_packet_dispatch",
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
            snapshot=replace(
                _snapshot(),
                idempotency_key="idem-other",
                tenant_id="tenant-other",
                command_id="command-other",
                action_type="finance_packet_archive",
                request_fingerprint="sha256:request-other",
                attempt_count=4,
                evidence_refs=[],
            ),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.idempotency_state == "wrong_scope"
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "snapshot_idempotency_key_mismatch" in receipt.blocked_reasons
    assert "snapshot_tenant_mismatch" in receipt.blocked_reasons
    assert "snapshot_command_mismatch" in receipt.blocked_reasons
    assert "snapshot_action_mismatch" in receipt.blocked_reasons
    assert "request_fingerprint_mismatch" in receipt.blocked_reasons
    assert "snapshot_evidence_refs_required" in receipt.blocked_reasons
    assert "max_replay_attempts_exceeded" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_idempotency_window_blocks_invalid_temporal_order() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(
        _request(
            snapshot=replace(
                _snapshot(),
                first_seen_at="2026-05-05T15:00:00+00:00",
                last_seen_at="2026-05-05T14:00:00+00:00",
                expires_at="2026-05-05T14:45:00+00:00",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.idempotency_state == "invalid"
    assert "first_seen_in_future" in receipt.blocked_reasons
    assert "idempotency_seen_order_invalid" in receipt.blocked_reasons
    assert "idempotency_window_invalid" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False


def test_idempotency_window_marks_low_risk_action_not_required() -> None:
    receipt = TemporalIdempotencyWindow(FixedClock()).evaluate(
        IdempotencyWindowRequest(
            request_id="idempotency-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="read_summary",
            risk_level="low",
            idempotency_key="",
            request_fingerprint="",
            policy=replace(
                _policy(),
                requires_idempotency_window=False,
                high_risk_requires_idempotency_window=False,
            ),
            evidence_refs=[],
            snapshot=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.idempotency_state == "not_required"
    assert receipt.idempotency_required is False
    assert receipt.idempotency_key == ""
    assert receipt.request_fingerprint == ""
    assert receipt.attempt_count == 0
    assert receipt.blocked_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["idempotency_checked"] is False


def _request(
    *,
    snapshot: IdempotencySnapshot | None | object = DEFAULT_SNAPSHOT,
    policy: IdempotencyWindowPolicy | None = None,
    action_type: str = "finance_packet_dispatch",
    idempotency_key: str = "idem-1",
    request_fingerprint: str = "sha256:request-1",
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_scheduler_receipt_id: str = "temporal-scheduler-receipt-0123456789abcdef",
    source_retry_window_receipt_id: str = "temporal-retry-window-receipt-0123456789abcdef",
    source_lease_window_receipt_id: str = "temporal-lease-window-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> IdempotencyWindowRequest:
    return IdempotencyWindowRequest(
        request_id="idempotency-window-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type=action_type,
        risk_level="high",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://idempotency/policy-1"],
        snapshot=_snapshot() if snapshot is DEFAULT_SNAPSHOT else snapshot,
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_scheduler_receipt_id=source_scheduler_receipt_id,
        source_retry_window_receipt_id=source_retry_window_receipt_id,
        source_lease_window_receipt_id=source_lease_window_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> IdempotencyWindowPolicy:
    return IdempotencyWindowPolicy(
        policy_id="idempotency-policy-1",
        tenant_id="tenant-1",
        scope_id="finance-worker",
        idempotent_action_types=["finance_packet_dispatch"],
        window_seconds=7200,
        max_replay_attempts=4,
        requires_idempotency_window=True,
        high_risk_requires_idempotency_window=True,
    )


def _snapshot() -> IdempotencySnapshot:
    return IdempotencySnapshot(
        idempotency_key="idem-1",
        tenant_id="tenant-1",
        command_id="command-1",
        action_type="finance_packet_dispatch",
        request_fingerprint="sha256:request-1",
        first_seen_at="2026-05-05T14:00:00+00:00",
        last_seen_at="2026-05-05T14:15:00+00:00",
        expires_at="2026-05-05T16:00:00+00:00",
        attempt_count=2,
        effect_committed=False,
        terminal_receipt_id="",
        prior_receipt_id="temporal-idempotency-window-receipt-0123456789abcdef",
        evidence_refs=["proof://idempotency/idem-1"],
    )
