"""Tests for personal-assistant memory observation contracts.

Purpose: prove memory observations are evidence-backed records rather than raw
conversation storage.
Governance scope: memory source, confidence, scope, mutability, receipt
reference, evidence reference, retention policy, and Nested Mind staging.
Dependencies: schemas/personal_assistant_memory_observation.schema.json.
Invariants:
  - Memory observations require source, confidence, scope, mutability, and
    receipt reference.
  - Live Nested Mind activation is not represented as complete.
  - Secret storage can only be represented as forbidden.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.validate_personal_assistant_memory_observation import validate_personal_assistant_memory_observation
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parent.parent
MEMORY_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_memory_observation.schema.json"
MEMORY_READ_MODEL_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_memory_read_model.schema.json"
MEMORY_READ_MODEL_EXAMPLE_PATH = ROOT / "examples" / "personal_assistant_memory_read_model.json"


def test_personal_assistant_memory_observation_accepts_evidence_backed_claim() -> None:
    schema = _load_schema(MEMORY_SCHEMA_PATH)
    observation = _memory_observation()

    errors = _validate_schema_instance(schema, observation)

    assert errors == []
    assert observation["source"]["source_type"] == "user_confirmation"
    assert observation["confidence"] == "high"
    assert observation["scope"] == "assistant_workflow"
    assert observation["mutable"] is True
    assert observation["receipt_id"] == "pa_receipt_email_draft_001"
    assert observation["nested_mind_status"] == "staging_only"


def test_personal_assistant_memory_observation_requires_governed_fields() -> None:
    schema = _load_schema(MEMORY_SCHEMA_PATH)
    missing_source = deepcopy(_memory_observation())
    missing_confidence = deepcopy(_memory_observation())
    missing_scope = deepcopy(_memory_observation())
    missing_mutability = deepcopy(_memory_observation())
    missing_receipt = deepcopy(_memory_observation())

    del missing_source["source"]
    del missing_confidence["confidence"]
    del missing_scope["scope"]
    del missing_mutability["mutable"]
    del missing_receipt["receipt_id"]

    source_errors = _validate_schema_instance(schema, missing_source)
    confidence_errors = _validate_schema_instance(schema, missing_confidence)
    scope_errors = _validate_schema_instance(schema, missing_scope)
    mutability_errors = _validate_schema_instance(schema, missing_mutability)
    receipt_errors = _validate_schema_instance(schema, missing_receipt)

    assert any("source" in error for error in source_errors)
    assert any("confidence" in error for error in confidence_errors)
    assert any("scope" in error for error in scope_errors)
    assert any("mutable" in error for error in mutability_errors)
    assert any("receipt_id" in error for error in receipt_errors)


def test_personal_assistant_memory_observation_rejects_live_activation_overclaim() -> None:
    schema = _load_schema(MEMORY_SCHEMA_PATH)
    observation = _memory_observation()
    observation["nested_mind_status"] = "activated"

    errors = _validate_schema_instance(schema, observation)

    assert errors
    assert any("nested_mind_status" in error for error in errors)
    assert observation["sensitivity"] == "internal"


def test_personal_assistant_memory_read_model_validator_accepts_example() -> None:
    schema = _load_schema(MEMORY_READ_MODEL_SCHEMA_PATH)
    payload = json.loads(MEMORY_READ_MODEL_EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_personal_assistant_memory_observation()

    assert _validate_schema_instance(schema, payload) == []
    assert result.valid is True
    assert result.candidate_count == 1
    assert result.receipt_count == 1
    assert result.errors == ()
    assert result.read_model_path == "examples/personal_assistant_memory_read_model.json"


def test_personal_assistant_memory_read_model_validator_rejects_live_write_claim(tmp_path: Path) -> None:
    payload = json.loads(MEMORY_READ_MODEL_EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload["live_memory_write_allowed"] = True
    payload["metadata"]["live_memory_write_allowed"] = True
    rejected_path = tmp_path / "personal_assistant_memory_read_model_rejected.json"
    rejected_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_memory_observation(read_model_path=rejected_path)

    assert result.valid is False
    assert result.candidate_count == 1
    assert result.receipt_count == 1
    assert any("live_memory_write_allowed" in error for error in result.errors)
    assert any("metadata.live_memory_write_allowed" in error for error in result.errors)


def _memory_observation() -> dict:
    return {
        "memory_observation_id": "pa_memory_preference_001",
        "memory_type": "preference",
        "claim": "User prefers one-at-a-time repository closures.",
        "source": {
            "source_type": "user_confirmation",
            "source_ref": "conversation:personal-assistant-foundation",
            "observed_at": "2026-06-14T00:00:00+00:00"
        },
        "confidence": "high",
        "scope": "assistant_workflow",
        "mutable": True,
        "receipt_id": "pa_receipt_email_draft_001",
        "evidence_refs": ["proof://personal-assistant/memory/preference-001"],
        "sensitivity": "internal",
        "retention_policy": "operator_review",
        "nested_mind_status": "staging_only",
        "metadata": {
            "fixture": "personal_assistant_memory_observation"
        }
    }
