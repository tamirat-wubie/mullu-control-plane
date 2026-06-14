"""Purpose: deterministic personal-assistant skill registry loading and query.
Governance scope: registry admission, duplicate prevention, risk filtering,
connector filtering, and capability selection without execution authority.
Dependencies: JSON registry fixtures and personal-assistant skill contracts.
Invariants:
  - Invalid or duplicate skills fail closed before admission.
  - Registry queries return immutable tuples or skill contract objects.
  - Loading a registry never executes connector, mailbox, calendar, memory, or
    deployment actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    PersonalAssistantInvariantError,
    PersonalAssistantSkill,
    SkillMode,
    SkillRiskLevel,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILL_REGISTRY_PATH = REPO_ROOT / "examples" / "personal_assistant_skill_registry.json"


@dataclass(slots=True)
class PersonalAssistantSkillRegistry:
    """In-memory governed registry for personal-assistant skill definitions."""

    _skills: dict[str, PersonalAssistantSkill] = field(default_factory=dict)

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "PersonalAssistantSkillRegistry":
        """Build a registry from a parsed registry fixture."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("skill registry root must be an object")
        skills_payload = payload.get("skills")
        if not isinstance(skills_payload, list):
            raise PersonalAssistantInvariantError("skill registry skills must be a list")
        registry = PersonalAssistantSkillRegistry()
        for index, item in enumerate(skills_payload):
            try:
                skill = PersonalAssistantSkill.from_mapping(item)
            except PersonalAssistantInvariantError as exc:
                raise PersonalAssistantInvariantError(f"skills[{index}]: {exc}") from exc
            registry.register(skill)
        return registry

    def register(self, skill: PersonalAssistantSkill) -> None:
        """Register one governed skill definition."""
        if not isinstance(skill, PersonalAssistantSkill):
            raise PersonalAssistantInvariantError("skill must be a PersonalAssistantSkill")
        if skill.skill_id in self._skills:
            raise PersonalAssistantInvariantError(f"duplicate skill_id: {skill.skill_id}")
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> PersonalAssistantSkill:
        """Return one skill by id or raise an explicit invariant error."""
        _require_query_text(skill_id, "skill_id")
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"unknown skill_id: {skill_id}") from exc

    def all_skills(self) -> tuple[PersonalAssistantSkill, ...]:
        """Return all admitted skills sorted by skill id."""
        return tuple(self._skills[skill_id] for skill_id in sorted(self._skills))

    def skill_ids(self) -> tuple[str, ...]:
        """Return all admitted skill ids sorted lexicographically."""
        return tuple(sorted(self._skills))

    def skills_for_group(self, group: str) -> tuple[PersonalAssistantSkill, ...]:
        """Return skills matching one group."""
        group = _require_query_text(group, "group")
        return tuple(skill for skill in self.all_skills() if skill.group == group)

    def skills_for_connector(self, connector: str) -> tuple[PersonalAssistantSkill, ...]:
        """Return skills that declare one connector requirement."""
        connector = _require_query_text(connector, "connector")
        return tuple(skill for skill in self.all_skills() if connector in skill.connectors)

    def skills_for_capabilities(
        self,
        capability_refs: tuple[str, ...],
        *,
        max_risk_level: SkillRiskLevel | str | None = None,
        include_blocked: bool = False,
    ) -> tuple[PersonalAssistantSkill, ...]:
        """Return admitted skills that cover every requested capability ref."""
        requested = _normalize_query_tuple(capability_refs, "capability_refs")
        risk_ceiling = _coerce_optional_risk(max_risk_level)
        matches: list[PersonalAssistantSkill] = []
        for skill in self.all_skills():
            if not include_blocked and skill.mode is SkillMode.BLOCKED:
                continue
            if risk_ceiling is not None and skill.risk_level.order > risk_ceiling.order:
                continue
            if skill.supports_capabilities(requested):
                matches.append(skill)
        return tuple(matches)

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator-facing registry read model."""
        skills = self.all_skills()
        return {
            "skill_count": len(skills),
            "skill_ids": [skill.skill_id for skill in skills],
            "groups": sorted({skill.group for skill in skills}),
            "risk_levels": {
                risk_level.value: sum(1 for skill in skills if skill.risk_level is risk_level)
                for risk_level in SkillRiskLevel
            },
            "skills": [skill.as_dict() for skill in skills],
        }

    @property
    def count(self) -> int:
        """Return admitted skill count."""
        return len(self._skills)


def load_default_skill_registry() -> PersonalAssistantSkillRegistry:
    """Load the foundation personal-assistant skill registry fixture."""
    return load_skill_registry(DEFAULT_SKILL_REGISTRY_PATH)


def load_skill_registry(path: Path) -> PersonalAssistantSkillRegistry:
    """Load and admit a personal-assistant skill registry from JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PersonalAssistantInvariantError(f"skill registry could not be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PersonalAssistantInvariantError(f"skill registry must be JSON: {path}") from exc
    return PersonalAssistantSkillRegistry.from_mapping(payload)


def _coerce_optional_risk(value: SkillRiskLevel | str | None) -> SkillRiskLevel | None:
    if value is None:
        return None
    if isinstance(value, SkillRiskLevel):
        return value
    if isinstance(value, str):
        return SkillRiskLevel.coerce(value)
    raise PersonalAssistantInvariantError("max_risk_level must be a SkillRiskLevel or string")


def _normalize_query_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise PersonalAssistantInvariantError(f"{field_name} must be a tuple")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a non-empty string")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _require_query_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value
