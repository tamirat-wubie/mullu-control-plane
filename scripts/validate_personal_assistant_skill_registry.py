#!/usr/bin/env python3
"""Validate the personal-assistant skill registry fixture.

Purpose: keep personal-assistant skills bounded to governed planning,
read-only, draft-only, approval-gated, or blocked behavior.
Governance scope: P0-P5 risk classification, read-only mutation denial,
draft-only send denial, explicit approval for effect-bearing skills, UAO
binding, receipt requirements, no secret serialization, no public-readiness
overclaim, and no live Nested Mind activation.
Dependencies: examples/personal_assistant_skill_registry.json,
schemas/personal_assistant_skill.schema.json, and
governance/personal_assistant_skill_policy.yaml.
Invariants:
  - Read-only skills cannot declare mutation authority.
  - Draft-only skills cannot send externally.
  - Math skills stay connector-free, planning/read-only, and non-mutating.
  - P3, P4, and P5 skills require explicit approval.
  - Receipts and UAO boundaries are required for every registered skill.
  - Raw secret-like values are never admitted in the registry.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_REGISTRY = REPO_ROOT / "examples" / "personal_assistant_skill_registry.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_skill.schema.json"
DEFAULT_POLICY = REPO_ROOT / "governance" / "personal_assistant_skill_policy.yaml"

MUTATING_ACTIONS = frozenset(
    {
        "send",
        "delete",
        "archive",
        "forward",
        "label_batch",
        "create_event",
        "move_event",
        "cancel_event",
        "invite_people",
        "message_person",
        "store_contact",
        "export_contacts",
        "external_submission",
        "public_post",
        "paid_subscription_action",
        "open_pull_request",
        "merge_pull_request",
        "push_branch",
        "deploy_service",
        "pay_invoice",
        "publish",
        "connector_mutation",
        "system_of_record_write",
    }
)

DRAFT_FORBIDDEN_ACTIONS = frozenset(
    {
        "send",
        "forward",
        "invite_people",
        "message_person",
        "external_submission",
        "public_post",
        "paid_subscription_action",
        "open_pull_request",
        "merge_pull_request",
        "push_branch",
        "deploy_service",
        "pay_invoice",
        "publish",
        "connector_mutation",
        "system_of_record_write",
    }
)

MATH_SAFE_ACTIONS = frozenset(
    {
        "plan",
        "compare",
        "optimize",
        "ask_clarification",
        "produce_receipt",
        "classify",
        "detect",
    }
)

APPROVAL_REQUIRED_LEVELS = frozenset({"P3", "P4", "P5"})

WRITE_BOUNDARY_FIELDS = (
    "internal_write_allowed",
    "external_write_allowed",
    "system_of_record_write_allowed",
    "connector_mutation_allowed",
    "money_legal_public_allowed",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantSkillRegistryValidation:
    """Validation result for the personal-assistant skill registry."""

    valid: bool
    registry_path: str
    skill_count: int
    skill_ids: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["skill_ids"] = list(self.skill_ids)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_skill_registry(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    schema_path: Path = DEFAULT_SCHEMA,
    policy_path: Path = DEFAULT_POLICY,
) -> PersonalAssistantSkillRegistryValidation:
    """Validate one personal-assistant skill registry fixture."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "personal-assistant skill schema", errors)
    policy = _load_json_object(policy_path, "personal-assistant skill policy", errors)
    registry = _load_json_object(registry_path, "personal-assistant skill registry", errors)
    if not schema or not registry:
        return _result(registry_path=registry_path, registry=registry, errors=errors)

    skills = registry.get("skills")
    if not isinstance(skills, list):
        errors.append("skill registry skills must be a list")
        return _result(registry_path=registry_path, registry=registry, errors=errors)

    expected_levels = tuple(policy.get("risk_levels", ())) if isinstance(policy, dict) else ()
    if expected_levels and expected_levels != ("P0", "P1", "P2", "P3", "P4", "P5"):
        errors.append("skill policy risk_levels must be exactly P0 through P5")

    seen_skill_ids: set[str] = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"skills[{index}] must be an object")
            continue
        skill_id = str(skill.get("skill_id", f"skills[{index}]"))
        if skill_id in seen_skill_ids:
            errors.append(f"{skill_id}: duplicate skill_id")
        seen_skill_ids.add(skill_id)
        errors.extend(f"{skill_id}: {message}" for message in _validate_schema_instance(schema, skill))
        _validate_skill_semantics(skill, errors)

    _scan_secret_like_values(registry, errors, path="$")
    return _result(registry_path=registry_path, registry=registry, errors=errors)


def _validate_skill_semantics(skill: dict[str, Any], errors: list[str]) -> None:
    skill_id = str(skill.get("skill_id", "<unknown-skill>"))
    group = str(skill.get("group", ""))
    mode = str(skill.get("mode", ""))
    risk_level = str(skill.get("risk_level", ""))
    allowed_actions = set(_string_list(skill, "allowed_actions"))
    effect_boundary = skill.get("effect_boundary", {})
    if not isinstance(effect_boundary, dict):
        effect_boundary = {}

    if skill.get("receipt_required") is not True:
        errors.append(f"{skill_id}: receipt_required must be true")
    if skill.get("uao_required") is not True:
        errors.append(f"{skill_id}: uao_required must be true")
    if skill.get("nested_mind_live_activation_allowed") is not False:
        errors.append(f"{skill_id}: live Nested Mind activation must be false")
    if skill.get("public_readiness_claim_allowed") is not False:
        errors.append(f"{skill_id}: public readiness claims must be false")
    if skill.get("private_connector_required") is True and risk_level == "P0":
        errors.append(f"{skill_id}: P0 skills cannot require a private connector")
    if skill.get("memory_write_allowed") is True:
        errors.append(f"{skill_id}: foundation skills cannot write memory")

    writes_allowed = any(effect_boundary.get(field_name) is True for field_name in WRITE_BOUNDARY_FIELDS)
    if mode == "read_only" or effect_boundary.get("read_only") is True:
        mutating_actions = sorted(allowed_actions.intersection(MUTATING_ACTIONS))
        if mutating_actions:
            errors.append(f"{skill_id}: read-only skill allows mutating actions {mutating_actions}")
        for field_name in WRITE_BOUNDARY_FIELDS:
            if effect_boundary.get(field_name) is True:
                errors.append(f"{skill_id}: read-only skill sets {field_name}=true")

    if mode == "draft_only" or effect_boundary.get("draft_only") is True:
        draft_violations = sorted(allowed_actions.intersection(DRAFT_FORBIDDEN_ACTIONS))
        if draft_violations:
            errors.append(f"{skill_id}: draft-only skill allows forbidden actions {draft_violations}")
        for field_name in ("external_write_allowed", "system_of_record_write_allowed", "connector_mutation_allowed", "money_legal_public_allowed"):
            if effect_boundary.get(field_name) is True:
                errors.append(f"{skill_id}: draft-only skill sets {field_name}=true")

    if group == "math" or skill_id.startswith("math."):
        _validate_math_skill_contract(
            skill=skill,
            skill_id=skill_id,
            mode=mode,
            allowed_actions=allowed_actions,
            effect_boundary=effect_boundary,
            errors=errors,
        )

    if risk_level in APPROVAL_REQUIRED_LEVELS or writes_allowed:
        if skill.get("requires_approval") is not True:
            errors.append(f"{skill_id}: {risk_level} or write-capable skill requires explicit approval")

    if risk_level in {"P4", "P5"} and mode not in {"approval_required", "blocked"}:
        errors.append(f"{skill_id}: {risk_level} skill must use approval_required or blocked mode")


def _validate_math_skill_contract(
    *,
    skill: dict[str, Any],
    skill_id: str,
    mode: str,
    allowed_actions: set[str],
    effect_boundary: dict[str, Any],
    errors: list[str],
) -> None:
    connectors = sorted(_string_list(skill, "connectors"))
    if connectors:
        errors.append(f"{skill_id}: math skill cannot require connectors {connectors}")
    if skill.get("private_connector_required") is True:
        errors.append(f"{skill_id}: math skill cannot require private connectors")

    unsafe_actions = sorted(allowed_actions.difference(MATH_SAFE_ACTIONS))
    if unsafe_actions:
        errors.append(f"{skill_id}: math skill allows unsafe actions {unsafe_actions}")

    for field_name in WRITE_BOUNDARY_FIELDS:
        if effect_boundary.get(field_name) is True:
            errors.append(f"{skill_id}: math skill sets {field_name}=true")

    if mode not in {"planning_only", "read_only"}:
        errors.append(f"{skill_id}: math skill must be planning_only or read_only")


def _result(
    *,
    registry_path: Path,
    registry: dict[str, Any],
    errors: list[str],
) -> PersonalAssistantSkillRegistryValidation:
    skills = registry.get("skills", []) if isinstance(registry, dict) else []
    skill_ids = tuple(
        str(skill.get("skill_id", ""))
        for skill in skills
        if isinstance(skill, dict) and isinstance(skill.get("skill_id"), str)
    )
    return PersonalAssistantSkillRegistryValidation(
        valid=not errors,
        registry_path=_path_label(registry_path),
        skill_count=len(skills) if isinstance(skills, list) else 0,
        skill_ids=skill_ids,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON-compatible YAML")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _string_list(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
    values = payload.get(field_name, ())
    return tuple(value for value in values if isinstance(value, str)) if isinstance(values, list) else ()


def _scan_secret_like_values(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            _scan_secret_like_values(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_secret_like_values(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant skill-registry validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant skill registry.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant skill-registry validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_skill_registry(
        registry_path=Path(args.registry),
        schema_path=Path(args.schema),
        policy_path=Path(args.policy),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"personal-assistant skill registry ok skills={result.skill_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
