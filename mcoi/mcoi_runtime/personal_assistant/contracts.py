"""Purpose: typed contracts for governed personal-assistant skills.
Governance scope: P0-P5 risk levels, skill execution modes, effect boundary
projection, connector requirements, and admission invariants.
Dependencies: Python dataclasses, enums, and runtime invariant helpers.
Invariants:
  - Registered skills are immutable after admission.
  - Risk, approval, connector, UAO, receipt, and effect boundaries are explicit.
  - Foundation contracts do not authorize live connector execution.
  - Math skills remain connector-free, planning/read-only, and non-mutating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


class PersonalAssistantInvariantError(RuntimeCoreInvariantError):
    """Raised when a personal-assistant registry invariant is violated."""


class SkillRiskLevel(StrEnum):
    """Governed personal-assistant risk classes."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"

    @property
    def order(self) -> int:
        """Return the monotonic approval-risk order."""
        return _RISK_ORDER[self]

    @property
    def requires_explicit_approval(self) -> bool:
        """Return whether this risk level requires explicit approval."""
        return self in {SkillRiskLevel.P3, SkillRiskLevel.P4, SkillRiskLevel.P5}

    @staticmethod
    def coerce(value: str) -> "SkillRiskLevel":
        """Coerce a string into a typed risk level."""
        try:
            return SkillRiskLevel(value)
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown risk level: {value}") from exc


class SkillMode(StrEnum):
    """Allowed foundation execution modes for registered skills."""

    READ_ONLY = "read_only"
    DRAFT_ONLY = "draft_only"
    PLANNING_ONLY = "planning_only"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"

    @staticmethod
    def coerce(value: str) -> "SkillMode":
        """Coerce a string into a typed skill mode."""
        try:
            return SkillMode(value)
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown skill mode: {value}") from exc


_RISK_ORDER = {
    SkillRiskLevel.P0: 0,
    SkillRiskLevel.P1: 1,
    SkillRiskLevel.P2: 2,
    SkillRiskLevel.P3: 3,
    SkillRiskLevel.P4: 4,
    SkillRiskLevel.P5: 5,
}

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

WRITE_BOUNDARY_FIELDS = (
    "internal_write_allowed",
    "external_write_allowed",
    "system_of_record_write_allowed",
    "connector_mutation_allowed",
    "money_legal_public_allowed",
)


@dataclass(frozen=True, slots=True)
class EffectBoundary:
    """Effect authority projection for one personal-assistant skill."""

    read_only: bool
    draft_only: bool
    internal_write_allowed: bool
    external_write_allowed: bool
    system_of_record_write_allowed: bool
    connector_mutation_allowed: bool
    money_legal_public_allowed: bool

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "EffectBoundary":
        """Build a typed effect boundary from a registry mapping."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("effect_boundary must be an object")
        return EffectBoundary(
            read_only=_require_bool(payload, "read_only"),
            draft_only=_require_bool(payload, "draft_only"),
            internal_write_allowed=_require_bool(payload, "internal_write_allowed"),
            external_write_allowed=_require_bool(payload, "external_write_allowed"),
            system_of_record_write_allowed=_require_bool(payload, "system_of_record_write_allowed"),
            connector_mutation_allowed=_require_bool(payload, "connector_mutation_allowed"),
            money_legal_public_allowed=_require_bool(payload, "money_legal_public_allowed"),
        )

    @property
    def writes_allowed(self) -> bool:
        """Return whether this boundary admits any write authority."""
        return any(getattr(self, field_name) for field_name in WRITE_BOUNDARY_FIELDS)

    def as_dict(self) -> dict[str, bool]:
        """Return a deterministic JSON-ready effect boundary."""
        return {
            "read_only": self.read_only,
            "draft_only": self.draft_only,
            "internal_write_allowed": self.internal_write_allowed,
            "external_write_allowed": self.external_write_allowed,
            "system_of_record_write_allowed": self.system_of_record_write_allowed,
            "connector_mutation_allowed": self.connector_mutation_allowed,
            "money_legal_public_allowed": self.money_legal_public_allowed,
        }


@dataclass(frozen=True, slots=True)
class PersonalAssistantSkill:
    """Governed registry entry for one personal-assistant skill."""

    skill_id: str
    name: str
    description: str
    group: str
    mode: SkillMode
    risk_level: SkillRiskLevel
    requires_approval: bool
    connectors: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    receipt_required: bool
    memory_write_allowed: bool
    private_connector_required: bool
    approval_policy_ref: str
    capability_refs: tuple[str, ...]
    uao_required: bool
    effect_boundary: EffectBoundary
    nested_mind_live_activation_allowed: bool
    public_readiness_claim_allowed: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "PersonalAssistantSkill":
        """Build and validate a skill from a registry mapping."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("skill must be an object")
        skill = PersonalAssistantSkill(
            skill_id=_require_text(payload, "skill_id"),
            name=_require_text(payload, "name"),
            description=_require_text(payload, "description"),
            group=_require_text(payload, "group"),
            mode=SkillMode.coerce(_require_text(payload, "mode")),
            risk_level=SkillRiskLevel.coerce(_require_text(payload, "risk_level")),
            requires_approval=_require_bool(payload, "requires_approval"),
            connectors=_text_tuple(payload, "connectors", allow_empty=True),
            inputs=_text_tuple(payload, "inputs"),
            outputs=_text_tuple(payload, "outputs"),
            allowed_actions=_text_tuple(payload, "allowed_actions"),
            blocked_actions=_text_tuple(payload, "blocked_actions"),
            receipt_required=_require_bool(payload, "receipt_required"),
            memory_write_allowed=_require_bool(payload, "memory_write_allowed"),
            private_connector_required=_require_bool(payload, "private_connector_required"),
            approval_policy_ref=_require_text(payload, "approval_policy_ref"),
            capability_refs=_text_tuple(payload, "capability_refs"),
            uao_required=_require_bool(payload, "uao_required"),
            effect_boundary=EffectBoundary.from_mapping(payload.get("effect_boundary")),
            nested_mind_live_activation_allowed=_require_bool(
                payload,
                "nested_mind_live_activation_allowed",
            ),
            public_readiness_claim_allowed=_require_bool(payload, "public_readiness_claim_allowed"),
            metadata=_frozen_metadata(payload.get("metadata", {})),
        )
        skill.assert_governed()
        return skill

    def assert_governed(self) -> None:
        """Validate skill-level policy invariants."""
        _require_no_duplicates(self.connectors, f"{self.skill_id}.connectors")
        _require_no_duplicates(self.inputs, f"{self.skill_id}.inputs")
        _require_no_duplicates(self.outputs, f"{self.skill_id}.outputs")
        _require_no_duplicates(self.allowed_actions, f"{self.skill_id}.allowed_actions")
        _require_no_duplicates(self.blocked_actions, f"{self.skill_id}.blocked_actions")
        _require_no_duplicates(self.capability_refs, f"{self.skill_id}.capability_refs")

        overlap = set(self.allowed_actions).intersection(self.blocked_actions)
        if overlap:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: allowed_actions overlap blocked_actions {sorted(overlap)}"
            )
        if self.receipt_required is not True:
            raise PersonalAssistantInvariantError(f"{self.skill_id}: receipt_required must be true")
        if self.uao_required is not True:
            raise PersonalAssistantInvariantError(f"{self.skill_id}: uao_required must be true")
        if self.memory_write_allowed:
            raise PersonalAssistantInvariantError(f"{self.skill_id}: foundation skills cannot write memory")
        if self.nested_mind_live_activation_allowed:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: live Nested Mind activation must be false"
            )
        if self.public_readiness_claim_allowed:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: public readiness claims must be false"
            )
        if self.private_connector_required and not self.connectors:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: private connector requirement needs connector refs"
            )
        if self.private_connector_required and self.risk_level is SkillRiskLevel.P0:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: P0 skills cannot require private connectors"
            )
        if not self.approval_policy_ref.endswith(f"#{self.risk_level.value}"):
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: approval policy ref must bind {self.risk_level.value}"
            )

        self._assert_mode_boundaries()
        self._assert_math_boundaries()
        if self.risk_level.requires_explicit_approval or self.effect_boundary.writes_allowed:
            if not self.requires_approval:
                raise PersonalAssistantInvariantError(
                    f"{self.skill_id}: {self.risk_level.value} or write-capable skill requires approval"
                )
        if self.risk_level in {SkillRiskLevel.P4, SkillRiskLevel.P5} and self.mode not in {
            SkillMode.APPROVAL_REQUIRED,
            SkillMode.BLOCKED,
        }:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: {self.risk_level.value} skill must be approval_required or blocked"
            )

    def _assert_mode_boundaries(self) -> None:
        allowed = set(self.allowed_actions)
        if self.mode is SkillMode.READ_ONLY or self.effect_boundary.read_only:
            mutations = sorted(allowed.intersection(MUTATING_ACTIONS))
            if mutations:
                raise PersonalAssistantInvariantError(
                    f"{self.skill_id}: read-only skill allows mutating actions {mutations}"
                )
            for field_name in WRITE_BOUNDARY_FIELDS:
                if getattr(self.effect_boundary, field_name):
                    raise PersonalAssistantInvariantError(
                        f"{self.skill_id}: read-only skill sets {field_name}=true"
                    )

        if self.mode is SkillMode.DRAFT_ONLY or self.effect_boundary.draft_only:
            forbidden = sorted(allowed.intersection(DRAFT_FORBIDDEN_ACTIONS))
            if forbidden:
                raise PersonalAssistantInvariantError(
                    f"{self.skill_id}: draft-only skill allows forbidden actions {forbidden}"
                )
            for field_name in (
                "external_write_allowed",
                "system_of_record_write_allowed",
                "connector_mutation_allowed",
                "money_legal_public_allowed",
            ):
                if getattr(self.effect_boundary, field_name):
                    raise PersonalAssistantInvariantError(
                        f"{self.skill_id}: draft-only skill sets {field_name}=true"
                    )

    def _assert_math_boundaries(self) -> None:
        if self.group != "math" and not self.skill_id.startswith("math."):
            return
        if self.connectors:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: math skill cannot require connectors {list(self.connectors)}"
            )
        if self.private_connector_required:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: math skill cannot require private connectors"
            )
        unsafe_actions = sorted(set(self.allowed_actions).difference(MATH_SAFE_ACTIONS))
        if unsafe_actions:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: math skill allows unsafe actions {unsafe_actions}"
            )
        for field_name in WRITE_BOUNDARY_FIELDS:
            if getattr(self.effect_boundary, field_name):
                raise PersonalAssistantInvariantError(
                    f"{self.skill_id}: math skill sets {field_name}=true"
                )
        if self.mode not in {SkillMode.PLANNING_ONLY, SkillMode.READ_ONLY}:
            raise PersonalAssistantInvariantError(
                f"{self.skill_id}: math skill must be planning_only or read_only"
            )

    def supports_capabilities(self, capability_refs: tuple[str, ...]) -> bool:
        """Return whether every requested capability is registered on this skill."""
        requested = set(_normalize_text_tuple(capability_refs, "capability_refs"))
        return requested.issubset(set(self.capability_refs))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready skill projection."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "group": self.group,
            "mode": self.mode.value,
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "connectors": list(self.connectors),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "allowed_actions": list(self.allowed_actions),
            "blocked_actions": list(self.blocked_actions),
            "receipt_required": self.receipt_required,
            "memory_write_allowed": self.memory_write_allowed,
            "private_connector_required": self.private_connector_required,
            "approval_policy_ref": self.approval_policy_ref,
            "capability_refs": list(self.capability_refs),
            "uao_required": self.uao_required,
            "effect_boundary": self.effect_boundary.as_dict(),
            "nested_mind_live_activation_allowed": self.nested_mind_live_activation_allowed,
            "public_readiness_claim_allowed": self.public_readiness_claim_allowed,
            "metadata": dict(self.metadata),
        }


def _require_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _require_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be a boolean")
    return value


def _text_tuple(payload: Mapping[str, Any], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = payload.get(field_name)
    if not isinstance(values, list):
        raise PersonalAssistantInvariantError(f"{field_name} must be a list")
    normalized = _normalize_text_tuple(tuple(values), field_name, allow_empty=allow_empty)
    return normalized


def _normalize_text_tuple(
    values: tuple[Any, ...],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a non-empty string")
        normalized.append(value)
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _require_no_duplicates(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise PersonalAssistantInvariantError(f"{field_name} contains duplicate entries")


def _frozen_metadata(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError("metadata must be an object")
    return MappingProxyType(dict(value))
