"""Purpose: verify ClarificationRequest contract validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_clarification_request and SDLC validator.
Invariants:
  - Clarification requests ask one focused question only.
  - Missing action slots block execution with safe default no_execution.
  - Raw user text and secrets remain absent.
  - SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_clarification_request as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_clarification_request_passes() -> None:
    errors = validator.validate_request()
    request = validator.load_json_object(validator.DEFAULT_REQUEST_PATH, "ClarificationRequest")

    assert errors == []
    assert request["max_questions"] == validator.EXPECTED_MAX_QUESTIONS
    assert request["safe_default"] == validator.EXPECTED_SAFE_DEFAULT
    assert request["reason"] == validator.EXPECTED_REASON
    assert request["question"].count("?") == 1
    assert validator.validate_request_record(request) == []


def test_schema_requires_one_question_profile() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    max_questions_schema = schema["properties"]["max_questions"]

    assert validator.validate_schema_artifact(schema) == []
    assert max_questions_schema["const"] == 1
    assert "maximum" not in max_questions_schema
    assert schema["properties"]["raw_message_hash"]["pattern"] == "^hash://.+$"
    assert schema["additionalProperties"] is False


def test_request_rejects_multiple_questions_and_execution_default() -> None:
    mutated = validator.build_mutated_request(
        max_questions=2,
        safe_default="execute_after_reply",
        question="Which target should I use? Should I change it?",
    )

    errors = validator.validate_request_record(mutated)

    assert any("max_questions" in error for error in errors)
    assert any("safe_default" in error for error in errors)
    assert any("exactly one question mark" in error for error in errors)
    assert mutated["missing_fields"] == ["target", "allowed_action"]
    assert mutated["reason"] == validator.EXPECTED_REASON


def test_request_rejects_missing_action_slots_and_bad_prefixes() -> None:
    mutated = validator.build_mutated_request(
        clarification_id="clarification-a1b2c3d4e5f60718",
        request_id="request-0f1e2d3c4b5a6978",
        raw_message_hash="abc123",
        missing_fields=["intent"],
    )

    errors = validator.validate_request_record(mutated)

    assert any("clarification_id" in error for error in errors)
    assert any("request_id" in error for error in errors)
    assert any("raw_message_hash" in error for error in errors)
    assert any("missing_fields must include target" in error for error in errors)
    assert any("missing_fields must include allowed_action" in error for error in errors)


def test_request_rejects_raw_or_authority_payload() -> None:
    mutated = validator.build_mutated_request(
        raw_message="fix my site secret-token-123",
        execution_allowed=True,
        approval_granted=True,
    )

    errors = validator.validate_request_record(mutated)

    assert any("forbidden payload key present: raw_message" in error for error in errors)
    assert any("forbidden payload key present: execution_allowed" in error for error in errors)
    assert any("forbidden payload key present: approval_granted" in error for error in errors)
    assert any("secret-token" in error for error in errors)
    assert mutated["safe_default"] == "no_execution"


def test_saved_request_file_validation(tmp_path: Path) -> None:
    request_path = tmp_path / "clarification_request.json"
    request = validator.load_json_object(validator.DEFAULT_REQUEST_PATH, "ClarificationRequest")
    request_path.write_text(json.dumps(request), encoding="utf-8")

    loaded = validator.load_json_object(request_path, "saved ClarificationRequest")
    errors = validator.validate_request_record(loaded)

    assert errors == []
    assert loaded["clarification_id"].startswith("clarification-request-")
    assert loaded["request_id"].startswith("interpreted-request-")
    assert loaded["raw_message_hash"].startswith("hash://")
    assert loaded["max_questions"] == 1


def test_malformed_request_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_request_record(None, schema)
    list_errors = validator.validate_request_record([], schema)

    assert any("clarification request must be a JSON object" in error for error in none_errors)
    assert any("clarification request must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_clarification_request() -> None:
    requirement_path = Path("examples/sdlc/requirement_clarification_request_contract_20260614.json")
    design_path = Path("examples/sdlc/design_clarification_request_contract_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "ClarificationRequest requirement")
    design = sdlc_validator.load_json_object(design_path, "ClarificationRequest design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/clarification_request.schema.json" in design["schema_changes"]
    assert "scripts/validate_clarification_request.py" in design["validator_changes"]
    assert "no execution authority" in requirement["non_goals"]
    assert "max_questions is fixed to one focused question" in requirement["success_criteria"]
    assert design["security_model"]["tenant_scope_reviewed"] is True
    assert any("validate_clarification_request.py" in command for command in design["test_plan"])
