"""Purpose: canonical skill system contract mapping.
Governance scope: skill descriptor, step, precondition, postcondition, outcome, and selection typing.
Dependencies: docs/19_skill_system.md, shared contract base helpers.
Invariants:
  - Every skill carries explicit identity, classification, effect/trust/determinism class.
  - Preconditions are checked before execution; postconditions after.
  - Composite skills MUST NOT have circular step dependencies.
  - Blocked skills MUST NOT be selected under any circumstances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


# --- Classification enums ---


class SkillClass(StrEnum):
    PRIMITIVE = "primitive"
    COMPOSITE = "composite"
    LEARNED = "learned"


class EffectClass(StrEnum):
    INTERNAL_PURE = "internal_pure"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    HUMAN_MEDIATED = "human_mediated"
    PRIVILEGED = "privileged"


class DeterminismClass(StrEnum):
    DETERMINISTIC = "deterministic"
    INPUT_BOUNDED = "input_bounded"
    RECORDED_NONDETERMINISTIC = "recorded_nondeterministic"


class TrustClass(StrEnum):
    TRUSTED_INTERNAL = "trusted_internal"
    BOUNDED_EXTERNAL = "bounded_external"
    UNTRUSTED_EXTERNAL = "untrusted_external"


class VerificationStrength(StrEnum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    MANDATORY = "mandatory"


class SkillLifecycle(StrEnum):
    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class PreconditionType(StrEnum):
    STATE_CHECK = "state_check"
    CAPABILITY_AVAILABLE = "capability_available"
    PROVIDER_HEALTHY = "provider_healthy"
    POLICY_ALLOWS = "policy_allows"


class PostconditionType(StrEnum):
    STATE_CHANGED = "state_changed"
    FILE_EXISTS = "file_exists"
    PROCESS_STATE = "process_state"
    VERIFICATION_PASSED = "verification_passed"


class SkillOutcomeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PRECONDITION_NOT_MET = "precondition_not_met"
    POLICY_DENIED = "policy_denied"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    STEP_FAILED = "step_failed"
    POSTCONDITION_NOT_SATISFIED = "postcondition_not_satisfied"
    VERIFICATION_FAILED = "verification_failed"
    TIMEOUT = "timeout"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class SkillPrecondition(ContractRecord):
    """A typed condition that MUST hold before skill execution may begin."""

    condition_id: str
    condition_type: PreconditionType
    description: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition_id", require_non_empty_text(self.condition_id, "condition_id"))
        if not isinstance(self.condition_type, PreconditionType):
            raise ValueError("condition_type must be a PreconditionType value")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "parameters", freeze_value(self.parameters))


@dataclass(frozen=True, slots=True)
class SkillPostcondition(ContractRecord):
    """A typed condition that MUST hold after execution for the skill to be considered successful."""

    condition_id: str
    condition_type: PostconditionType
    description: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition_id", require_non_empty_text(self.condition_id, "condition_id"))
        if not isinstance(self.condition_type, PostconditionType):
            raise ValueError("condition_type must be a PostconditionType value")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "parameters", freeze_value(self.parameters))


@dataclass(frozen=True, slots=True)
class SkillStep(ContractRecord):
    """One unit of work within a skill, with typed inputs/outputs and dependencies."""

    step_id: str
    name: str
    action_type: str
    depends_on: tuple[str, ...] = ()
    input_bindings: Mapping[str, str] = field(default_factory=dict)
    output_keys: tuple[str, ...] = ()
    provider_class_required: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "action_type", require_non_empty_text(self.action_type, "action_type"))
        object.__setattr__(self, "depends_on", freeze_value(list(self.depends_on)))
        for idx, dep in enumerate(self.depends_on):
            require_non_empty_text(dep, f"depends_on[{idx}]")
        object.__setattr__(self, "input_bindings", freeze_value(self.input_bindings))
        object.__setattr__(self, "output_keys", freeze_value(list(self.output_keys)))
        if self.provider_class_required is not None:
            object.__setattr__(
                self, "provider_class_required",
                require_non_empty_text(self.provider_class_required, "provider_class_required"),
            )


@dataclass(frozen=True, slots=True)
class SkillDescriptor(ContractRecord):
    """Full identity and classification of a registered skill."""

    skill_id: str
    name: str
    skill_class: SkillClass
    effect_class: EffectClass
    determinism_class: DeterminismClass
    trust_class: TrustClass
    verification_strength: VerificationStrength
    lifecycle: SkillLifecycle = SkillLifecycle.CANDIDATE
    preconditions: tuple[SkillPrecondition, ...] = ()
    postconditions: tuple[SkillPostcondition, ...] = ()
    steps: tuple[SkillStep, ...] = ()
    provider_requirements: tuple[str, ...] = ()
    description: str | None = None
    runbook_id: str | None = None
    confidence: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        for attr, enum_type in (
            ("skill_class", SkillClass),
            ("effect_class", EffectClass),
            ("determinism_class", DeterminismClass),
            ("trust_class", TrustClass),
            ("verification_strength", VerificationStrength),
            ("lifecycle", SkillLifecycle),
        ):
            if not isinstance(getattr(self, attr), enum_type):
                raise ValueError(f"{attr} must be a {enum_type.__name__} value")
        object.__setattr__(self, "preconditions", freeze_value(list(self.preconditions)))
        object.__setattr__(self, "postconditions", freeze_value(list(self.postconditions)))
        object.__setattr__(self, "steps", freeze_value(list(self.steps)))
        object.__setattr__(self, "provider_requirements", freeze_value(list(self.provider_requirements)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        # Composite skills must have steps
        if self.skill_class is SkillClass.COMPOSITE and not self.steps:
            raise ValueError("composite skills must have at least one step")
        # Learned skills must reference a runbook
        if self.skill_class is SkillClass.LEARNED and not self.runbook_id:
            raise ValueError("learned skills must reference a runbook_id")
        # Validate no circular step dependencies
        if self.steps:
            self._check_no_circular_deps()

    def _check_no_circular_deps(self) -> None:
        step_ids = {s.step_id for s in self.steps}
        # Validate all dependencies reference existing steps
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"step {step.step_id} depends on unknown step {dep}")
        # Topological check via DFS
        visited: set[str] = set()
        in_stack: set[str] = set()
        deps_map = {s.step_id: s.depends_on for s in self.steps}

        def visit(sid: str) -> None:
            if sid in in_stack:
                raise ValueError(f"circular dependency detected involving step {sid}")
            if sid in visited:
                return
            in_stack.add(sid)
            for dep in deps_map.get(sid, ()):
                visit(dep)
            in_stack.discard(sid)
            visited.add(sid)

        for step in self.steps:
            visit(step.step_id)


@dataclass(frozen=True, slots=True)
class SkillStepOutcome(ContractRecord):
    """Result of executing one step within a skill."""

    step_id: str
    status: SkillOutcomeStatus
    execution_id: str | None = None
    verification_id: str | None = None
    error_message: str | None = None
    outputs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        if not isinstance(self.status, SkillOutcomeStatus):
            raise ValueError("status must be a SkillOutcomeStatus value")
        object.__setattr__(self, "outputs", freeze_value(self.outputs))


@dataclass(frozen=True, slots=True)
class SkillOutcome(ContractRecord):
    """Terminal result of a full skill execution."""

    skill_id: str
    status: SkillOutcomeStatus
    step_outcomes: tuple[SkillStepOutcome, ...] = ()
    preconditions_met: bool = True
    postconditions_met: bool = True
    execution_id: str | None = None
    verification_id: str | None = None
    error_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        if not isinstance(self.status, SkillOutcomeStatus):
            raise ValueError("status must be a SkillOutcomeStatus value")
        object.__setattr__(self, "step_outcomes", freeze_value(list(self.step_outcomes)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SkillSelectionDecision(ContractRecord):
    """Why a particular skill was chosen over alternatives."""

    selected_skill_id: str
    candidates_considered: tuple[str, ...]
    selection_reasons: tuple[str, ...]
    rejected_reasons: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "selected_skill_id",
            require_non_empty_text(self.selected_skill_id, "selected_skill_id"),
        )
        object.__setattr__(self, "candidates_considered", freeze_value(list(self.candidates_considered)))
        object.__setattr__(self, "selection_reasons", freeze_value(list(self.selection_reasons)))
        object.__setattr__(self, "rejected_reasons", freeze_value(self.rejected_reasons))


@dataclass(frozen=True, slots=True)
class SkillExecutionRecord(ContractRecord):
    """Full trace of a skill run including all step records and selection decision."""

    record_id: str
    skill_id: str
    outcome: SkillOutcome
    selection: SkillSelectionDecision | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        if not isinstance(self.outcome, SkillOutcome):
            raise ValueError("outcome must be a SkillOutcome instance")
