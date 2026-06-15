"""Tests for personal-assistant memory review evidence validation.

Purpose: prove memory observation review evidence is schema-backed,
receipt-anchored, and unable to write live memory.
Governance scope: PR7 memory review evidence, candidate review separation,
receipt conformance, private payload redaction, and Foundation Mode boundaries.
Dependencies: scripts.validate_personal_assistant_memory_review.
Invariants:
  - Fixture and runtime envelopes validate.
  - Memory review decisions do not write memory, mutate connectors, or activate Nested Mind.
  - Rejected and expired reviews block memory admission.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    MemoryConfidence,
    MemoryObservationSource,
    MemoryObservationType,
    MemoryRetentionPolicy,
    MemoryReviewDecision,
    MemoryScope,
    MemorySensitivity,
    NestedMindStatus,
    PersonalAssistantInvariantError,
    prepare_memory_observation,
    review_memory_observation_candidate,
)
from scripts.validate_personal_assistant_memory_review import (
    DEFAULT_REVIEW,
    build_runtime_memory_review_evidence,
    validate_personal_assistant_memory_review,
)


def test_personal_assistant_memory_review_fixture_validates() -> None:
    result = validate_personal_assistant_memory_review()

    assert result.valid is True
    assert result.review_path == "examples/personal_assistant_memory_review_evidence.json"
    assert result.runtime_validated is True
    assert result.review_count == 5
    assert result.receipt_count == 5
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_runtime_memory_review_blocks_effect_boundaries() -> None:
    envelope = build_runtime_memory_review_evidence()
    effect_boundary = envelope["effect_boundary"]
    reviews = {item["decision"]: item for item in envelope["reviews"]}

    assert envelope["governed"] is True
    assert envelope["source_projection"] == "operator_supplied_memory_review_evidence"
    assert effect_boundary["memory_review_records_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["live_memory_write_allowed"] is False
    assert effect_boundary["memory_admission_allowed"] is False
    assert effect_boundary["nested_mind_live_activation_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert reviews["kept_for_operator_review"]["receipt"]["decision"] == "deferred"
    assert reviews["revision_requested"]["receipt"]["decision"] == "deferred"
    assert reviews["deferred"]["receipt"]["decision"] == "deferred"
    assert reviews["rejected"]["receipt"]["decision"] == "blocked"
    assert reviews["expired"]["receipt"]["decision"] == "blocked"


def test_memory_review_runtime_requires_decision_specific_bindings() -> None:
    candidate = _memory_candidate()

    with pytest.raises(PersonalAssistantInvariantError) as revision_exc:
        review_memory_observation_candidate(
            candidate=candidate,
            review_id="pa_memory_review_missing_revision_001",
            decision=MemoryReviewDecision.REVISION_REQUESTED,
            reviewer_ref="operator:tamirat",
            reason_codes=("missing_revision_request",),
            reviewed_at="2026-06-15T00:04:00+00:00",
        )
    with pytest.raises(PersonalAssistantInvariantError) as deferred_exc:
        review_memory_observation_candidate(
            candidate=candidate,
            review_id="pa_memory_review_missing_deferred_001",
            decision="deferred",
            reviewer_ref="operator:tamirat",
            reason_codes=("missing_deferred_until",),
            reviewed_at="2026-06-15T00:04:00+00:00",
        )
    with pytest.raises(PersonalAssistantInvariantError) as expired_exc:
        review_memory_observation_candidate(
            candidate=candidate,
            review_id="pa_memory_review_missing_expiry_001",
            decision="expired",
            reviewer_ref="operator:tamirat",
            reason_codes=("missing_expires_at",),
            reviewed_at="2026-06-15T00:04:00+00:00",
        )

    assert "revision_request" in str(revision_exc.value)
    assert "deferred_until" in str(deferred_exc.value)
    assert "expires_at" in str(expired_exc.value)


def test_memory_review_validator_rejects_memory_write_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["live_memory_write_allowed"] = True
    payload["effect_boundary"]["memory_admission_allowed"] = True
    payload["metadata"]["system_of_record_write_allowed"] = True
    candidate = tmp_path / "unsafe_memory_review.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_memory_review(review_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "effect_boundary.live_memory_write_allowed must be false" in result.errors
    assert "effect_boundary.memory_admission_allowed must be false" in result.errors
    assert any("metadata.system_of_record_write_allowed" in error for error in result.errors)
    assert result.runtime_validated is False


def test_memory_review_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["reviews"][0]["receipt"]["decision"] = "allowed"
    payload["reviews"][1]["receipt"]["decision"] = "deferred"
    payload["reviews"][2]["receipt"]["metadata"]["live_memory_write_allowed"] = True
    candidate = tmp_path / "receipt_drift_memory_review.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_memory_review(review_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "reviews[0].receipt.decision must be deferred for kept_for_operator_review" in result.errors
    assert "reviews[1].receipt.decision must be blocked for rejected" in result.errors
    assert "reviews[2].receipt.metadata.live_memory_write_allowed must be false" in result.errors
    assert result.receipt_count == 5


def test_memory_review_validator_rejects_missing_decision_state(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["reviews"] = [item for item in payload["reviews"] if item["decision"] != "expired"]
    payload["review_ids"] = [item["review_id"] for item in payload["reviews"]]
    payload["memory_observation_ids"] = [item["memory_observation_id"] for item in payload["reviews"]]
    payload["receipt_ids"] = [item["receipt"]["receipt_id"] for item in payload["reviews"]]
    payload["review_count"] = len(payload["reviews"])
    candidate = tmp_path / "missing_expired_memory_review.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_memory_review(review_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "reviews must include expired" in result.errors
    assert result.review_count == 4


def test_memory_review_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["reviews"][0]["candidate"]["raw_chat_log"] = "private transcript"
    payload["reviews"][1]["review"]["reason_codes"] = ["rotate Bearer secret-worker-token"]
    candidate = tmp_path / "raw_payload_memory_review.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_memory_review(review_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "$.reviews[0].candidate.raw_chat_log: raw private or secret field is forbidden" in result.errors
    assert "$.reviews[1].review.reason_codes[0]: secret-like value must not be serialized" in result.errors
    assert result.runtime_validated is False


def _memory_candidate():
    return prepare_memory_observation(
        request_id="pa_request_memory_review_test_001",
        memory_observation_id="pa_memory_review_test_001",
        memory_type=MemoryObservationType.PREFERENCE,
        claim="User prefers one-at-a-time repository closures.",
        source=MemoryObservationSource(
            source_type="user_confirmation",
            source_ref="conversation:memory-review-test",
            observed_at="2026-06-15T00:00:00+00:00",
        ),
        confidence=MemoryConfidence.HIGH,
        scope=MemoryScope.ASSISTANT_WORKFLOW,
        mutable=True,
        receipt_id="pa_receipt_memory_review_test_001",
        evidence_refs=("proof://personal-assistant/memory/review-test-001",),
        observed_at="2026-06-15T00:00:00+00:00",
        sensitivity=MemorySensitivity.INTERNAL,
        retention_policy=MemoryRetentionPolicy.OPERATOR_REVIEW,
        nested_mind_status=NestedMindStatus.STAGING_ONLY,
    )


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_REVIEW.read_text(encoding="utf-8")))
