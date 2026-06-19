"""Tests for the personal-assistant runtime skill registry.

Purpose: prove PR 2 registry loading, admission, querying, and read-model
projection remain deterministic and non-executing.
Governance scope: P0-P5 risk ordering, connector requirements, blocked action
boundaries, UAO and receipt preservation, and approval enforcement.
Dependencies: mcoi_runtime.personal_assistant and the foundation registry
fixture.
Invariants:
  - Loading the registry never executes connectors.
  - Duplicate or policy-invalid skill definitions fail closed.
  - Math and planning skills remain connector-free, planning/read-only, and
    non-mutating.
  - Queries return deterministic skill selections.
  - Read models do not expose live execution authority.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    PersonalAssistantSkillRegistry,
    SkillMode,
    SkillRiskLevel,
    load_default_skill_registry,
)


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "examples" / "personal_assistant_skill_registry.json"


def test_default_registry_loads_foundation_skills() -> None:
    registry = load_default_skill_registry()
    skill_ids = registry.skill_ids()
    inbox_summary = registry.get("email.inbox.summarize")

    assert registry.count == 17
    assert skill_ids == tuple(sorted(skill_ids))
    assert "email.inbox.summarize" in skill_ids
    assert "math.reasoning.plan" in skill_ids
    assert "planning.optimize_schedule" in skill_ids
    assert "task.create_draft" in skill_ids
    assert "calendar.event.create.with_approval" in skill_ids
    assert "task.create.with_approval" in skill_ids
    assert inbox_summary.mode is SkillMode.READ_ONLY
    assert inbox_summary.risk_level is SkillRiskLevel.P1
    assert inbox_summary.receipt_required is True
    assert inbox_summary.uao_required is True


def test_registry_queries_by_connector_and_capability_are_deterministic() -> None:
    registry = load_default_skill_registry()
    gmail_skill_ids = tuple(skill.skill_id for skill in registry.skills_for_connector("gmail"))
    draft_matches = registry.skills_for_capabilities(("email.reply_suggest",), max_risk_level="P2")
    send_below_risk = registry.skills_for_capabilities(("email.send.with_approval",), max_risk_level="P3")
    send_with_risk = registry.skills_for_capabilities(("email.send.with_approval",), max_risk_level=SkillRiskLevel.P4)
    calendar_create = registry.skills_for_capabilities(
        ("calendar.event.create.with_approval",),
        max_risk_level=SkillRiskLevel.P3,
    )
    task_create = registry.skills_for_capabilities(("task.create.with_approval",), max_risk_level=SkillRiskLevel.P3)
    math_matches = registry.skills_for_capabilities(("personal_assistant.skill_plan.build",), max_risk_level="P2")

    assert gmail_skill_ids == (
        "email.inbox.summarize",
        "email.response.draft",
        "email.send.with_approval",
        "teamops.shared_inbox.plan",
    )
    assert tuple(skill.skill_id for skill in draft_matches) == ("email.response.draft",)
    assert send_below_risk == ()
    assert tuple(skill.skill_id for skill in send_with_risk) == ("email.send.with_approval",)
    assert tuple(skill.skill_id for skill in calendar_create) == ("calendar.event.create.with_approval",)
    assert tuple(skill.skill_id for skill in task_create) == ("task.create.with_approval",)
    assert "math.reasoning.plan" in tuple(skill.skill_id for skill in math_matches)
    assert all(skill.risk_level.order <= SkillRiskLevel.P2.order for skill in math_matches)


def test_blocked_skills_are_excluded_unless_requested() -> None:
    registry = load_default_skill_registry()
    default_matches = registry.skills_for_capabilities(("personal_assistant.approval.classify",), max_risk_level="P5")
    blocked_matches = registry.skills_for_capabilities(
        ("personal_assistant.approval.classify",),
        max_risk_level="P5",
        include_blocked=True,
    )

    assert default_matches == ()
    assert tuple(skill.skill_id for skill in blocked_matches) == ("deployment.publish.review",)
    assert blocked_matches[0].mode is SkillMode.BLOCKED
    assert blocked_matches[0].requires_approval is True


def test_duplicate_skill_id_is_rejected() -> None:
    registry_payload = _load_registry_payload()
    registry_payload["skills"].append(deepcopy(registry_payload["skills"][0]))

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantSkillRegistry.from_mapping(registry_payload)

    assert "duplicate skill_id" in str(exc_info.value)
    assert "email.inbox.summarize" in str(exc_info.value)
    assert len(registry_payload["skills"]) == 18


def test_read_only_mutation_is_rejected_by_runtime_contract() -> None:
    registry_payload = _load_registry_payload()
    skill = _skill_by_id(registry_payload, "email.inbox.summarize")
    skill["allowed_actions"].append("create_event")
    skill["effect_boundary"]["external_write_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantSkillRegistry.from_mapping(registry_payload)

    assert "email.inbox.summarize" in str(exc_info.value)
    assert "read-only skill allows mutating actions" in str(exc_info.value)
    assert "create_event" in str(exc_info.value)


def test_draft_only_external_send_is_rejected_by_runtime_contract() -> None:
    registry_payload = _load_registry_payload()
    skill = _skill_by_id(registry_payload, "email.response.draft")
    skill["allowed_actions"].append("public_post")
    skill["effect_boundary"]["connector_mutation_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantSkillRegistry.from_mapping(registry_payload)

    assert "email.response.draft" in str(exc_info.value)
    assert "draft-only skill allows forbidden actions" in str(exc_info.value)
    assert "public_post" in str(exc_info.value)


def test_math_skill_mutation_is_rejected_by_runtime_contract() -> None:
    connector_payload = _load_registry_payload()
    _skill_by_id(connector_payload, "math.reasoning.plan")["connectors"] = ["stripe"]

    with pytest.raises(PersonalAssistantInvariantError) as connector_exc:
        PersonalAssistantSkillRegistry.from_mapping(connector_payload)

    unsafe_action_payload = _load_registry_payload()
    _skill_by_id(unsafe_action_payload, "math.reasoning.plan")["allowed_actions"].append("read")

    with pytest.raises(PersonalAssistantInvariantError) as action_exc:
        PersonalAssistantSkillRegistry.from_mapping(unsafe_action_payload)

    write_payload = _load_registry_payload()
    _skill_by_id(write_payload, "math.reasoning.plan")["effect_boundary"]["money_legal_public_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as write_exc:
        PersonalAssistantSkillRegistry.from_mapping(write_payload)

    mode_payload = _load_registry_payload()
    _skill_by_id(mode_payload, "math.reasoning.plan")["mode"] = "approval_required"

    with pytest.raises(PersonalAssistantInvariantError) as mode_exc:
        PersonalAssistantSkillRegistry.from_mapping(mode_payload)

    assert "math.reasoning.plan" in str(connector_exc.value)
    assert "math skill cannot require connectors" in str(connector_exc.value)
    assert "math skill allows unsafe actions" in str(action_exc.value)
    assert "math skill sets money_legal_public_allowed=true" in str(write_exc.value)
    assert "math skill must be planning_only or read_only" in str(mode_exc.value)


def test_planning_skill_mutation_is_rejected_by_runtime_contract() -> None:
    connector_payload = _load_registry_payload()
    _skill_by_id(connector_payload, "planning.optimize_schedule")["connectors"] = ["google_calendar"]

    with pytest.raises(PersonalAssistantInvariantError) as connector_exc:
        PersonalAssistantSkillRegistry.from_mapping(connector_payload)

    unsafe_action_payload = _load_registry_payload()
    _skill_by_id(unsafe_action_payload, "planning.optimize_schedule")["allowed_actions"].append("read")

    with pytest.raises(PersonalAssistantInvariantError) as action_exc:
        PersonalAssistantSkillRegistry.from_mapping(unsafe_action_payload)

    write_payload = _load_registry_payload()
    _skill_by_id(write_payload, "planning.optimize_schedule")["effect_boundary"]["system_of_record_write_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as write_exc:
        PersonalAssistantSkillRegistry.from_mapping(write_payload)

    mode_payload = _load_registry_payload()
    _skill_by_id(mode_payload, "planning.optimize_schedule")["mode"] = "approval_required"

    with pytest.raises(PersonalAssistantInvariantError) as mode_exc:
        PersonalAssistantSkillRegistry.from_mapping(mode_payload)

    assert "planning.optimize_schedule" in str(connector_exc.value)
    assert "planning skill cannot require connectors" in str(connector_exc.value)
    assert "planning skill allows unsafe actions" in str(action_exc.value)
    assert "planning skill sets system_of_record_write_allowed=true" in str(write_exc.value)
    assert "planning skill must be planning_only or read_only" in str(mode_exc.value)


def test_high_risk_or_write_capable_skill_requires_approval() -> None:
    email_payload = _load_registry_payload()
    _skill_by_id(email_payload, "email.send.with_approval")["requires_approval"] = False

    with pytest.raises(PersonalAssistantInvariantError) as email_exc:
        PersonalAssistantSkillRegistry.from_mapping(email_payload)

    calendar_payload = _load_registry_payload()
    _skill_by_id(calendar_payload, "calendar.event.create.with_approval")["requires_approval"] = False

    with pytest.raises(PersonalAssistantInvariantError) as calendar_exc:
        PersonalAssistantSkillRegistry.from_mapping(calendar_payload)

    assert "email.send.with_approval" in str(email_exc.value)
    assert "P4" in str(email_exc.value)
    assert "requires approval" in str(email_exc.value)
    assert "calendar.event.create.with_approval" in str(calendar_exc.value)
    assert "P3" in str(calendar_exc.value)
    assert "requires approval" in str(calendar_exc.value)


def test_read_model_preserves_non_execution_boundary() -> None:
    registry = load_default_skill_registry()
    read_model = registry.read_model()
    skills_by_id = {skill["skill_id"]: skill for skill in read_model["skills"]}
    send_skill = skills_by_id["email.send.with_approval"]
    calendar_skill = skills_by_id["calendar.event.create.with_approval"]
    task_skill = skills_by_id["task.create.with_approval"]
    memory_skill = skills_by_id["memory.observe"]

    assert read_model["skill_count"] == 17
    assert read_model["risk_levels"]["P3"] == 2
    assert read_model["risk_levels"]["P4"] == 1
    assert read_model["risk_levels"]["P5"] == 1
    assert send_skill["metadata"]["execution_enabled"] is False
    assert calendar_skill["metadata"]["execution_enabled"] is False
    assert task_skill["metadata"]["execution_enabled"] is False
    assert memory_skill["metadata"]["nested_mind_status"] == "staging_only"
    assert all(skill["receipt_required"] is True for skill in read_model["skills"])
    assert all(skill["uao_required"] is True for skill in read_model["skills"])


def _load_registry_payload() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _skill_by_id(registry_payload: dict, skill_id: str) -> dict:
    for skill in registry_payload["skills"]:
        if skill["skill_id"] == skill_id:
            return skill
    raise AssertionError(f"missing skill {skill_id}")
