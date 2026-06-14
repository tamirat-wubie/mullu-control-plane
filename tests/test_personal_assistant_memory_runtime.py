"""Tests for governed personal-assistant memory observation runtime.

Purpose: prove PR7 memory observation candidates are evidence-backed and do not
write live memory or activate Nested Mind.
Governance scope: memory observation schema, receipt schema, local candidate
ledger, source evidence, sensitivity, retention, and secret/raw-payload denial.
Dependencies: mcoi_runtime.personal_assistant memory helpers.
Invariants:
  - Memory observations are candidate records for operator review.
  - Live memory writes and Nested Mind activation remain blocked.
  - Raw chat logs, raw connector payloads, and secret-like values are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    MemoryConfidence,
    MemoryObservationSource,
    MemoryObservationType,
    MemoryRetentionPolicy,
    MemoryScope,
    MemorySensitivity,
    NestedMindStatus,
    PersonalAssistantInvariantError,
    PersonalAssistantMemoryObservationLedger,
    prepare_memory_observation,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
MEMORY_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_memory_observation.schema.json"
MEMORY_READ_MODEL_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_memory_read_model.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
OBSERVED_AT = "2026-06-14T00:00:00+00:00"


def test_prepare_memory_observation_emits_schema_ready_candidate_and_receipt() -> None:
    candidate = _preference_candidate()
    observation = dict(candidate.observation)
    receipt = dict(candidate.receipt)
    serialized = json.dumps(candidate.as_dict(), sort_keys=True)

    assert _validate_schema_instance(_load_schema(MEMORY_SCHEMA_PATH), observation) == []
    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert observation["memory_type"] == "preference"
    assert observation["source"]["source_type"] == "user_confirmation"
    assert observation["receipt_id"] == "pa_receipt_operator_preference_source_001"
    assert observation["nested_mind_status"] == "staging_only"
    assert receipt["skill_id"] == "memory.observe"
    assert receipt["memory_observation_refs"] == ["pa_memory_preference_runtime_001"]
    assert "live_memory_not_written" in receipt["actions_not_taken"]
    assert "private transcript" not in serialized


def test_memory_observation_ledger_indexes_candidates_without_live_memory_write() -> None:
    ledger = PersonalAssistantMemoryObservationLedger()
    preference = _preference_candidate()
    project_state = prepare_memory_observation(
        request_id="pa_request_memory_project_001",
        memory_observation_id="pa_memory_project_state_001",
        memory_type=MemoryObservationType.PROJECT_STATE,
        claim="Personal-assistant PR7 is limited to candidate observations.",
        source=MemoryObservationSource(
            source_type="project_artifact",
            source_ref="repo:personal-assistant-memory-runtime",
            observed_at=OBSERVED_AT,
        ),
        confidence=MemoryConfidence.VERIFIED,
        scope=MemoryScope.PROJECT,
        mutable=True,
        receipt_id="pa_receipt_project_state_source_001",
        evidence_refs=("proof://personal-assistant/memory/project-state-001",),
        observed_at=OBSERVED_AT,
        sensitivity=MemorySensitivity.INTERNAL,
        retention_policy=MemoryRetentionPolicy.OPERATOR_REVIEW,
    )

    ledger.append(preference)
    ledger.append(project_state)
    read_model = ledger.read_model()

    assert _validate_schema_instance(_load_schema(MEMORY_READ_MODEL_SCHEMA_PATH), read_model) == []
    assert read_model["candidate_count"] == 2
    assert read_model["live_memory_write_allowed"] is False
    assert read_model["nested_mind_live_activation_allowed"] is False
    assert read_model["raw_private_payload_storage_allowed"] is False
    assert read_model["secret_value_storage_allowed"] is False
    assert read_model["candidate_only"] is True
    assert read_model["memory_types"] == ["preference", "project_state"]
    assert ledger.get("pa_memory_preference_runtime_001").observation["mutable"] is True
    assert "pa_memory_project_state_001" in read_model["memory_observation_ids"]


def test_memory_observation_records_approval_rule_without_granting_authority() -> None:
    candidate = prepare_memory_observation(
        request_id="pa_request_memory_approval_rule_001",
        memory_observation_id="pa_memory_approval_rule_001",
        memory_type="approval_rule",
        claim="External communication requires explicit operator approval.",
        source={
            "source_type": "system_receipt",
            "source_ref": "governance/personal_assistant_approval_matrix.yaml#P4",
            "observed_at": OBSERVED_AT,
        },
        confidence="verified",
        scope="security",
        mutable=False,
        receipt_id="pa_receipt_approval_rule_source_001",
        evidence_refs=("proof://personal-assistant/memory/approval-rule-001",),
        observed_at=OBSERVED_AT,
    )
    observation = dict(candidate.observation)
    receipt = dict(candidate.receipt)

    assert observation["memory_type"] == "approval_rule"
    assert observation["mutable"] is False
    assert observation["scope"] == "security"
    assert receipt["metadata"]["candidate_only"] is True
    assert receipt["metadata"]["live_memory_write_allowed"] is False
    assert "nested_mind_not_activated" in receipt["actions_not_taken"]


def test_memory_observation_blocks_nested_mind_activation_and_do_not_store() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as nested_exc:
        _preference_candidate(nested_mind_status=NestedMindStatus.AWAITING_EVIDENCE)

    with pytest.raises(PersonalAssistantInvariantError) as retention_exc:
        _preference_candidate(retention_policy=MemoryRetentionPolicy.DO_NOT_STORE)

    with pytest.raises(PersonalAssistantInvariantError) as sensitivity_exc:
        _preference_candidate(sensitivity=MemorySensitivity.SECRET_FORBIDDEN)

    assert "staging_only" in str(nested_exc.value)
    assert "do_not_store" in str(retention_exc.value)
    assert "secret_forbidden" in str(sensitivity_exc.value)


def test_memory_observation_rejects_raw_payload_fields_and_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        prepare_memory_observation(
            request_id="pa_request_memory_raw_001",
            memory_observation_id="pa_memory_raw_001",
            memory_type="preference",
            claim="User prefers governed closure.",
            source={
                "source_type": "conversation",
                "source_ref": "conversation:raw",
                "observed_at": OBSERVED_AT,
                "raw_chat_log": "private transcript",
            },
            confidence="high",
            scope="assistant_workflow",
            mutable=True,
            receipt_id="pa_receipt_raw_source_001",
            evidence_refs=("proof://personal-assistant/memory/raw-001",),
            observed_at=OBSERVED_AT,
        )

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        _preference_candidate(claim="Remember secret-token-value for later.")

    assert "raw_chat_log" in str(raw_exc.value)
    assert "private transcript" not in str(raw_exc.value)
    assert "secret-like values" in str(secret_exc.value)


def test_memory_ledger_rejects_duplicate_candidate_ids() -> None:
    ledger = PersonalAssistantMemoryObservationLedger()
    candidate = _preference_candidate()
    ledger.append(candidate)

    with pytest.raises(PersonalAssistantInvariantError) as duplicate_exc:
        ledger.append(candidate)

    assert "duplicate memory_observation_id" in str(duplicate_exc.value)
    assert ledger.read_model()["candidate_count"] == 1
    assert ledger.get("pa_memory_preference_runtime_001").receipt["outcome"] == "SolvedVerified"


def _preference_candidate(
    *,
    claim: str = "User prefers one-at-a-time repository closures.",
    sensitivity: MemorySensitivity | str = MemorySensitivity.INTERNAL,
    retention_policy: MemoryRetentionPolicy | str = MemoryRetentionPolicy.OPERATOR_REVIEW,
    nested_mind_status: NestedMindStatus | str = NestedMindStatus.STAGING_ONLY,
):
    return prepare_memory_observation(
        request_id="pa_request_memory_preference_001",
        memory_observation_id="pa_memory_preference_runtime_001",
        memory_type=MemoryObservationType.PREFERENCE,
        claim=claim,
        source=MemoryObservationSource(
            source_type="user_confirmation",
            source_ref="conversation:personal-assistant-foundation",
            observed_at=OBSERVED_AT,
        ),
        confidence=MemoryConfidence.HIGH,
        scope=MemoryScope.ASSISTANT_WORKFLOW,
        mutable=True,
        receipt_id="pa_receipt_operator_preference_source_001",
        evidence_refs=("proof://personal-assistant/memory/preference-runtime-001",),
        observed_at=OBSERVED_AT,
        sensitivity=sensitivity,
        retention_policy=retention_policy,
        nested_mind_status=nested_mind_status,
        metadata={"fixture": "personal_assistant_memory_runtime"},
    )
