"""Purpose: verify audit-chain verifier bounded failure semantics.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, PRS.
Dependencies: mcoi_runtime.governance.audit.trail.
Invariants:
  - Verification failures use documented failure fields only.
  - Failure reasons expose bounded hashes, sequence numbers, and field names.
  - Sensitive audit payload values do not leak through verifier errors.
"""

from __future__ import annotations

from dataclasses import asdict

from mcoi_runtime.governance.audit.trail import (
    AuditTrail,
    ExternalVerifyResult,
    verify_chain_from_entries,
)


SENSITIVE_DETAIL = "customer-secret-token-123"
SENSITIVE_TARGET = "private-ledger-account-789"
DOCUMENTED_FAILURE_FIELDS = {"", "schema", "sequence", "previous_hash", "entry_hash"}


def fixed_clock() -> str:
    return "2026-03-26T12:00:00Z"


def _entries_with_sensitive_detail() -> list[dict]:
    trail = AuditTrail(clock=fixed_clock)
    trail.record(
        action="payment.review",
        actor_id="operator-1",
        tenant_id="tenant-1",
        target=SENSITIVE_TARGET,
        outcome="success",
        detail={"secret": SENSITIVE_DETAIL},
    )
    trail.record(
        action="payment.close",
        actor_id="operator-1",
        tenant_id="tenant-1",
        target=SENSITIVE_TARGET,
        outcome="success",
        detail={"closed": True},
    )
    return [asdict(entry) for entry in trail.query(limit=100)]


def _assert_bounded_failure(result: ExternalVerifyResult) -> None:
    assert result.valid is False
    assert result.failure_field in DOCUMENTED_FAILURE_FIELDS
    assert SENSITIVE_DETAIL not in result.failure_reason
    assert SENSITIVE_TARGET not in result.failure_reason
    assert "customer-secret" not in result.failure_reason
    assert "private-ledger" not in result.failure_reason


def test_entry_hash_failure_reason_does_not_leak_detail_payload() -> None:
    entries = _entries_with_sensitive_detail()
    entries[0]["detail"] = {"secret": SENSITIVE_DETAIL, "tampered": True}

    result = verify_chain_from_entries(entries)

    _assert_bounded_failure(result)
    assert result.failure_field == "entry_hash"
    assert result.failure_sequence == 1
    assert "recomputed" in result.failure_reason
    assert "stored" in result.failure_reason


def test_previous_hash_failure_reason_does_not_leak_target_or_detail() -> None:
    entries = _entries_with_sensitive_detail()
    entries[1]["previous_hash"] = "0" * 64

    result = verify_chain_from_entries(entries)

    _assert_bounded_failure(result)
    assert result.failure_field == "previous_hash"
    assert result.failure_sequence == 2
    assert "expected" in result.failure_reason
    assert "got" in result.failure_reason


def test_schema_failure_reason_is_limited_to_field_names() -> None:
    entries = _entries_with_sensitive_detail()
    del entries[0]["detail"]

    result = verify_chain_from_entries(entries)

    _assert_bounded_failure(result)
    assert result.failure_field == "schema"
    assert result.failure_sequence == 1
    assert "detail" in result.failure_reason
    assert "secret" not in result.failure_reason


def test_sequence_failure_reason_is_limited_to_index_and_sequence() -> None:
    entries = _entries_with_sensitive_detail()
    entries[1]["sequence"] = 4
    entries[1]["entry_hash"] = entries[0]["entry_hash"]

    result = verify_chain_from_entries(entries)

    _assert_bounded_failure(result)
    assert result.failure_field == "sequence"
    assert result.failure_sequence == 4
    assert "expected 2" in result.failure_reason
    assert "got 4" in result.failure_reason


def test_success_and_failure_fields_remain_documented() -> None:
    success = verify_chain_from_entries([])
    entries = _entries_with_sensitive_detail()
    entries[0]["detail"] = {"secret": SENSITIVE_DETAIL, "tampered": True}
    failure = verify_chain_from_entries(entries)

    assert success.valid is True
    assert success.failure_field == ""
    assert failure.failure_field == "entry_hash"
    assert {success.failure_field, failure.failure_field} <= DOCUMENTED_FAILURE_FIELDS
