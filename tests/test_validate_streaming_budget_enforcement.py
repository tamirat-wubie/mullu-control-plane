"""Tests for streaming budget enforcement event validation.

Purpose: prove predictive debit events enforce arithmetic and cutoff semantics.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_streaming_budget_enforcement and the public schema.
Invariants:
  - Reservation arithmetic is deterministic.
  - Emitted output never exceeds reservation.
  - Cutoff retry eligibility is semantically explicit.
  - Settlement token deltas are reproducible.
"""

from __future__ import annotations

from scripts.validate_streaming_budget_enforcement import validate_streaming_budget_event


def _base_event(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "event_type": "reservation_created",
        "reservation_id": "reservation-1",
        "request_id": "request-1",
        "tenant_id": "tenant-1",
        "budget_id": "budget-1",
        "policy_version": "policy-v1",
        "proof_id": "proof-1",
        "timestamp": "2026-05-04T00:00:00Z",
        "estimated_input_tokens": 12,
        "reserved_output_tokens": 8,
        "reserved_total_tokens": 20,
        "reserved_cost": 0.002,
    }
    payload.update(overrides)
    return payload


def test_reservation_event_accepts_valid_predictive_debit() -> None:
    validation = validate_streaming_budget_event(_base_event())

    assert validation.valid is True
    assert validation.errors == ()
    assert len(validation.errors) == 0


def test_reservation_event_rejects_total_token_drift() -> None:
    validation = validate_streaming_budget_event(_base_event(reserved_total_tokens=19))

    assert validation.valid is False
    assert len(validation.errors) == 1
    assert "reserved_total_tokens must equal" in validation.errors[0]


def test_chunk_debit_rejects_over_reservation_emission() -> None:
    validation = validate_streaming_budget_event(
        _base_event(
            event_type="chunk_debited",
            emitted_output_tokens=9,
        )
    )

    assert validation.valid is False
    assert len(validation.errors) == 1
    assert validation.errors[0] == "emitted_output_tokens must not exceed reserved_output_tokens"


def test_cutoff_requires_retry_flag_to_match_semantic() -> None:
    validation = validate_streaming_budget_event(
        _base_event(
            event_type="cutoff_emitted",
            emitted_output_tokens=8,
            cutoff_semantic="retry_eligible",
            retry_eligible=False,
        )
    )

    assert validation.valid is False
    assert len(validation.errors) == 1
    assert validation.errors[0] == "retry_eligible cutoff_semantic requires retry_eligible true"


def test_cutoff_requires_exhausted_output_reservation() -> None:
    validation = validate_streaming_budget_event(
        _base_event(
            event_type="cutoff_emitted",
            emitted_output_tokens=7,
            cutoff_semantic="graceful",
            retry_eligible=False,
        )
    )

    assert validation.valid is False
    assert len(validation.errors) == 1
    assert validation.errors[0] == "cutoff_emitted requires emitted_output_tokens to equal reserved_output_tokens"


def test_settlement_requires_reproducible_delta_tokens() -> None:
    validation = validate_streaming_budget_event(
        _base_event(
            event_type="settled",
            actual_input_tokens=13,
            actual_output_tokens=6,
            actual_cost=0.0019,
            delta_tokens=0,
            delta_cost=-0.0001,
        )
    )

    assert validation.valid is False
    assert len(validation.errors) == 1
    assert validation.errors[0] == "delta_tokens must equal actual total tokens minus reserved_total_tokens"


def test_schema_errors_are_bounded() -> None:
    payload = _base_event(tenant_id="")
    payload["secret_detail"] = "secret-streaming-budget-token"

    validation = validate_streaming_budget_event(payload)

    assert validation.valid is False
    assert len(validation.errors) == 2
    assert "secret-streaming-budget-token" not in repr(validation.errors)
