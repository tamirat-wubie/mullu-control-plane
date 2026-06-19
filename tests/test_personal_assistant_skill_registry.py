"""Tests for the personal-assistant skill registry and capability pack.

Purpose: prove the foundation personal-assistant skill registry preserves
read-only, draft-only, approval, capability-pack, and capsule boundaries.
Governance scope: skill schema conformance, mutation denial, draft send
denial, approval-required risk tiers, capability registry conformance, and
production-readiness overclaim blocking.
Dependencies: scripts.validate_personal_assistant_skill_registry and personal
assistant capability artifacts.
Invariants:
  - Read-only skills cannot declare mutation authority.
  - Draft-only skills cannot send externally.
  - Math skills stay connector-free, planning/read-only, and non-mutating.
  - P3/P4/P5 skills require explicit approval.
  - Capability pack entries remain candidate-only and non-production.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_personal_assistant_skill_registry import (
    validate_personal_assistant_skill_registry,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "examples" / "personal_assistant_skill_registry.json"
CAPABILITY_PACK_PATH = ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
CAPSULE_PATH = ROOT / "capsules" / "personal_assistant.json"
CAPABILITY_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "capability_registry_entry.schema.json"
DOMAIN_CAPSULE_SCHEMA_PATH = ROOT / "schemas" / "domain_capsule.schema.json"


def test_personal_assistant_skill_registry_accepts_foundation_fixture() -> None:
    result = validate_personal_assistant_skill_registry()

    assert result.valid is True
    assert result.skill_count == 17
    assert "email.inbox.summarize" in result.skill_ids
    assert "math.reasoning.plan" in result.skill_ids
    assert "planning.optimize_schedule" in result.skill_ids
    assert "task.create_draft" in result.skill_ids
    assert "email.send.with_approval" in result.skill_ids
    assert "calendar.event.create.with_approval" in result.skill_ids
    assert "task.create.with_approval" in result.skill_ids
    assert "deployment.publish.review" in result.skill_ids
    assert result.errors == ()


def test_read_only_skills_cannot_declare_mutation_authority(tmp_path: Path) -> None:
    registry = _load_json(REGISTRY_PATH)
    inbox_skill = _skill_by_id(registry, "email.inbox.summarize")
    inbox_skill["allowed_actions"].append("send")
    inbox_skill["effect_boundary"]["external_write_allowed"] = True
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = validate_personal_assistant_skill_registry(registry_path=registry_path)

    assert result.valid is False
    assert result.skill_count == 17
    assert any("read-only skill allows mutating actions" in error for error in result.errors)
    assert any("external_write_allowed=true" in error for error in result.errors)


def test_draft_only_skills_cannot_send_externally(tmp_path: Path) -> None:
    registry = _load_json(REGISTRY_PATH)
    draft_skill = _skill_by_id(registry, "email.response.draft")
    draft_skill["allowed_actions"].append("send")
    draft_skill["effect_boundary"]["connector_mutation_allowed"] = True
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = validate_personal_assistant_skill_registry(registry_path=registry_path)

    assert result.valid is False
    assert any("draft-only skill allows forbidden actions" in error for error in result.errors)
    assert any("connector_mutation_allowed=true" in error for error in result.errors)
    assert not any("secret-like value" in error for error in result.errors)


def test_math_skills_remain_planning_only_and_non_mutating(tmp_path: Path) -> None:
    registry = _load_json(REGISTRY_PATH)
    math_skill = _skill_by_id(registry, "math.reasoning.plan")
    math_skill["mode"] = "approval_required"
    math_skill["connectors"] = ["stripe"]
    math_skill["private_connector_required"] = True
    math_skill["allowed_actions"].append("pay_invoice")
    math_skill["effect_boundary"]["money_legal_public_allowed"] = True
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = validate_personal_assistant_skill_registry(registry_path=registry_path)

    assert result.valid is False
    assert any("math skill cannot require connectors" in error for error in result.errors)
    assert any("math skill cannot require private connectors" in error for error in result.errors)
    assert any("math skill allows unsafe actions" in error for error in result.errors)
    assert any("math skill sets money_legal_public_allowed=true" in error for error in result.errors)
    assert any("math skill must be planning_only or read_only" in error for error in result.errors)


def test_planning_skills_remain_preview_only_and_non_mutating(tmp_path: Path) -> None:
    registry = _load_json(REGISTRY_PATH)
    planning_skill = _skill_by_id(registry, "planning.optimize_schedule")
    planning_skill["mode"] = "approval_required"
    planning_skill["connectors"] = ["google_calendar"]
    planning_skill["private_connector_required"] = True
    planning_skill["allowed_actions"].append("create_event")
    planning_skill["effect_boundary"]["system_of_record_write_allowed"] = True
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = validate_personal_assistant_skill_registry(registry_path=registry_path)

    assert result.valid is False
    assert any("planning skill cannot require connectors" in error for error in result.errors)
    assert any("planning skill cannot require private connectors" in error for error in result.errors)
    assert any("planning skill allows unsafe actions" in error for error in result.errors)
    assert any("planning skill sets system_of_record_write_allowed=true" in error for error in result.errors)
    assert any("planning skill must be planning_only or read_only" in error for error in result.errors)


def test_p3_p4_p5_skills_require_explicit_approval(tmp_path: Path) -> None:
    registry = _load_json(REGISTRY_PATH)
    _skill_by_id(registry, "calendar.event.create.with_approval")["requires_approval"] = False
    _skill_by_id(registry, "task.create.with_approval")["requires_approval"] = False
    _skill_by_id(registry, "email.send.with_approval")["requires_approval"] = False
    _skill_by_id(registry, "deployment.publish.review")["requires_approval"] = False
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = validate_personal_assistant_skill_registry(registry_path=registry_path)

    assert result.valid is False
    assert any(
        "calendar.event.create.with_approval" in error and "requires explicit approval" in error
        for error in result.errors
    )
    assert any("task.create.with_approval" in error and "requires explicit approval" in error for error in result.errors)
    assert any("email.send.with_approval" in error and "requires explicit approval" in error for error in result.errors)
    assert any("deployment.publish.review" in error and "requires explicit approval" in error for error in result.errors)
    assert sum("requires explicit approval" in error for error in result.errors) >= 4


def test_personal_assistant_capability_pack_and_capsule_are_schema_valid() -> None:
    registry_schema = _load_schema(CAPABILITY_REGISTRY_SCHEMA_PATH)
    capsule_schema = _load_schema(DOMAIN_CAPSULE_SCHEMA_PATH)
    pack = _load_json(CAPABILITY_PACK_PATH)
    capsule = _load_json(CAPSULE_PATH)
    capability_ids = tuple(entry["capability_id"] for entry in pack["capabilities"])

    assert len(capability_ids) == 12
    assert all(_validate_schema_instance(registry_schema, entry) == [] for entry in pack["capabilities"])
    assert _validate_schema_instance(capsule_schema, capsule) == []
    assert tuple(capsule["capability_refs"]) == capability_ids
    assert all(entry["certification_status"] == "candidate" for entry in pack["capabilities"])
    assert all(entry["metadata"]["production_ready"] is False for entry in pack["capabilities"])
    assert capsule["extensions"]["live_connector_execution_allowed"] is False
    assert capsule["extensions"]["live_nested_mind_activation_allowed"] is False


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_by_id(registry: dict, skill_id: str) -> dict:
    for skill in registry["skills"]:
        if skill["skill_id"] == skill_id:
            return skill
    raise AssertionError(f"missing skill {skill_id}")
