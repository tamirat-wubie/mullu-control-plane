"""Tests for the personal-assistant approval matrix.

Purpose: prove effect-bearing personal-assistant actions remain approval-gated.
Governance scope: P0-P5 approval classification, P4/P5 explicit approval,
blocked-without-approval coverage, and approval packet schema conformance.
Dependencies: scripts.validate_personal_assistant_approval_matrix.
Invariants:
  - P4/P5 actions require explicit approval.
  - P5 actions bind named evidence requirements.
  - Overclaim flags remain false.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_personal_assistant_approval_matrix import (
    validate_personal_assistant_approval_matrix,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance
from mcoi_runtime.personal_assistant import SkillMode, load_default_skill_registry

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
APPROVAL_PATH = ROOT / "examples" / "personal_assistant_approval_packet.json"
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_request.schema.json"
PLAN_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_plan.schema.json"
REQUEST_EXAMPLES = (
    ROOT / "examples" / "personal_assistant_request_inbox_summary.json",
    ROOT / "examples" / "personal_assistant_request_calendar_brief.json",
    ROOT / "examples" / "personal_assistant_request_math_reasoning.json",
)
MATH_PLAN_PATH = ROOT / "examples" / "personal_assistant_plan_math_reasoning.json"


def test_personal_assistant_approval_matrix_accepts_foundation_fixture() -> None:
    result = validate_personal_assistant_approval_matrix()

    assert result.valid is True
    assert result.risk_levels == ("P0", "P1", "P2", "P3", "P4", "P5")
    assert result.errors == ()


def test_p4_p5_matrix_entries_require_explicit_approval(tmp_path: Path) -> None:
    matrix = _load_json(MATRIX_PATH)
    for entry in matrix["risk_levels"]:
        if entry["level"] in {"P4", "P5"}:
            entry["explicit_approval_required"] = False
    matrix_path = tmp_path / "matrix.yaml"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    result = validate_personal_assistant_approval_matrix(matrix_path=matrix_path)

    assert result.valid is False
    assert any("P4: explicit_approval_required must be true" in error for error in result.errors)
    assert any("P5: explicit_approval_required must be true" in error for error in result.errors)
    assert result.risk_levels == ("P0", "P1", "P2", "P3", "P4", "P5")


def test_approval_packet_cannot_mark_p4_action_not_required(tmp_path: Path) -> None:
    approval = _load_json(APPROVAL_PATH)
    approval["approval_state"] = "not_required"
    approval["explicit_approval_required"] = False
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    result = validate_personal_assistant_approval_matrix(approval_path=approval_path)

    assert result.valid is False
    assert any("explicit_approval_required must be true" in error for error in result.errors)
    assert any("approval_state cannot be not_required" in error for error in result.errors)
    assert not any(str(tmp_path) in error for error in result.errors)


def test_request_examples_validate_against_intake_schema() -> None:
    schema = _load_schema(REQUEST_SCHEMA_PATH)
    inbox_request = _load_json(REQUEST_EXAMPLES[0])
    calendar_request = _load_json(REQUEST_EXAMPLES[1])
    math_request = _load_json(REQUEST_EXAMPLES[2])

    assert _validate_schema_instance(schema, inbox_request) == []
    assert _validate_schema_instance(schema, calendar_request) == []
    assert _validate_schema_instance(schema, math_request) == []
    assert inbox_request["blocked_actions"] == ["send", "archive", "delete", "forward", "label_batch"]
    assert calendar_request["blocked_actions"] == ["create_event", "move_event", "cancel_event", "invite_people"]
    assert math_request["connector_refs"] == []


def test_math_request_and_plan_preserve_planning_only_boundary() -> None:
    request_schema = _load_schema(REQUEST_SCHEMA_PATH)
    plan_schema = _load_schema(PLAN_SCHEMA_PATH)
    math_request = _load_json(REQUEST_EXAMPLES[2])
    math_plan = _load_json(MATH_PLAN_PATH)
    math_skill = load_default_skill_registry().get("math.reasoning.plan")

    assert _validate_schema_instance(request_schema, math_request) == []
    assert _validate_schema_instance(plan_schema, math_plan) == []
    assert math_request["requested_skill_ids"] == ["math.reasoning.plan"]
    assert math_plan["steps"][0]["skill_id"] == "math.reasoning.plan"
    assert math_plan["execution_allowed"] is False
    assert "pay_invoice" in math_plan["actions_not_authorized"]
    assert math_skill.mode is SkillMode.PLANNING_ONLY
    assert math_skill.connectors == ()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
