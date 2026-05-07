"""Tests for the public effect assurance schema.

Purpose: prove planned, observed, and reconciled effect records are enforced
as a public protocol contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/effect_assurance.schema.json and scripts.validate_schemas.
Invariants:
  - Local $ref entries resolve into nested schema validation.
  - Nullable string fields allow null but reject malformed strings.
  - Unexpected nested fields fail closed.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "effect_assurance.schema.json"


def test_effect_assurance_schema_accepts_canonical_record() -> None:
    schema = _load_schema(SCHEMA_PATH)
    record = _effect_assurance_record()

    errors = _validate_schema_instance(schema, record)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:effect-assurance:1"
    assert schema["title"] == "Effect Assurance Record"


def test_effect_assurance_schema_rejects_missing_nested_required_field() -> None:
    schema = _load_schema(SCHEMA_PATH)
    record = _effect_assurance_record()
    del record["effect_plan"]["expected_effects"][0]["verification_method"]

    errors = _validate_schema_instance(schema, record)

    assert len(errors) == 1
    assert "$.effect_plan.expected_effects[0]" in errors[0]
    assert "verification_method" in errors[0]


def test_effect_assurance_schema_rejects_unexpected_nested_field() -> None:
    schema = _load_schema(SCHEMA_PATH)
    record = _effect_assurance_record()
    record["reconciliation"]["silent_override"] = True

    errors = _validate_schema_instance(schema, record)

    assert len(errors) == 1
    assert "$.reconciliation" in errors[0]
    assert "unexpected property 'silent_override'" in errors[0]


def test_effect_assurance_schema_rejects_empty_nullable_string_branch() -> None:
    schema = _load_schema(SCHEMA_PATH)
    record = _effect_assurance_record()
    record["effect_plan"]["rollback_plan_id"] = ""

    errors = _validate_schema_instance(schema, record)

    assert len(errors) == 3
    assert all("$.effect_plan.rollback_plan_id" in error for error in errors)
    assert any("no type branch matched" in error for error in errors)
    assert any("minimum length" in error for error in errors)
    assert any("expected null" in error for error in errors)


def test_effect_assurance_schema_rejects_invalid_datetime() -> None:
    schema = _load_schema(SCHEMA_PATH)
    record = _effect_assurance_record()
    record["observed_effects"][0]["observed_at"] = "not-a-time"

    errors = _validate_schema_instance(schema, record)

    assert len(errors) == 1
    assert "$.observed_effects[0].observed_at" in errors[0]
    assert "invalid ISO 8601 date-time" in errors[0]


def _effect_assurance_record() -> dict[str, Any]:
    return deepcopy(
        {
            "effect_plan": {
                "effect_plan_id": "effect-plan-001",
                "command_id": "command-001",
                "tenant_id": "tenant-001",
                "capability_id": "communication.notification_send",
                "expected_effects": [
                    {
                        "effect_id": "effect-001",
                        "name": "notification_sent",
                        "target_ref": "channel:ops",
                        "required": True,
                        "verification_method": "delivery_receipt",
                        "expected_value": {"status": "delivered"},
                    }
                ],
                "forbidden_effects": ["payment_created"],
                "rollback_plan_id": None,
                "compensation_plan_id": "compensation-001",
                "graph_node_refs": ["node:command-001", "node:effect-001"],
                "graph_edge_refs": ["edge:command-001->effect-001"],
                "created_at": "2026-05-01T12:00:00Z",
            },
            "observed_effects": [
                {
                    "effect_id": "effect-001",
                    "name": "notification_sent",
                    "source": "receipt:notification-001",
                    "observed_value": {"status": "delivered"},
                    "evidence_ref": "evidence:notification-001",
                    "observed_at": "2026-05-01T12:00:05Z",
                }
            ],
            "reconciliation": {
                "reconciliation_id": "reconciliation-001",
                "command_id": "command-001",
                "effect_plan_id": "effect-plan-001",
                "status": "match",
                "matched_effects": ["effect-001"],
                "missing_effects": [],
                "unexpected_effects": [],
                "verification_result_id": "verification-001",
                "case_id": None,
                "decided_at": "2026-05-01T12:00:06Z",
            },
            "metadata": {"owner": "protocol-tests"},
            "extensions": {},
        }
    )
