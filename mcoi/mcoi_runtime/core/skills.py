"""Purpose: skill system core — registration, selection, execution orchestration.
Governance scope: skill lifecycle management, selection, and execution orchestration only.
Dependencies: skill contracts, meta-reasoning engine, provider registry, invariant helpers.
Invariants:
  - Blocked skills MUST NOT be selected under any circumstances.
  - Skill execution MUST produce a typed outcome.
  - Composite skill execution stops on first step failure.
  - Selection is deterministic for identical inputs.
  - Confidence is updated from skill outcomes.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol

from mcoi_runtime.contracts.skill import (
    SkillClass,
    SkillDescriptor,
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcome,
    SkillOutcomeStatus,
    SkillSelectionDecision,
    SkillStepOutcome,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


# --- Lifecycle transition rules ---

_VALID_TRANSITIONS: dict[SkillLifecycle, frozenset[SkillLifecycle]] = {
    SkillLifecycle.CANDIDATE: frozenset({SkillLifecycle.PROVISIONAL, SkillLifecycle.DEPRECATED, SkillLifecycle.BLOCKED}),
    SkillLifecycle.PROVISIONAL: frozenset({SkillLifecycle.VERIFIED, SkillLifecycle.DEPRECATED, SkillLifecycle.BLOCKED}),
    SkillLifecycle.VERIFIED: frozenset({SkillLifecycle.TRUSTED, SkillLifecycle.DEPRECATED, SkillLifecycle.BLOCKED}),
    SkillLifecycle.TRUSTED: frozenset({SkillLifecycle.DEPRECATED, SkillLifecycle.BLOCKED}),
    SkillLifecycle.DEPRECATED: frozenset({SkillLifecycle.BLOCKED}),
    SkillLifecycle.BLOCKED: frozenset(),
}

# Selection ranking: higher is preferred
_LIFECYCLE_RANK: dict[SkillLifecycle, int] = {
    SkillLifecycle.TRUSTED: 4,
    SkillLifecycle.VERIFIED: 3,
    SkillLifecycle.PROVISIONAL: 2,
    SkillLifecycle.CANDIDATE: 1,
    SkillLifecycle.DEPRECATED: 0,
    SkillLifecycle.BLOCKED: -1,
}

# Effect class preference: lower number = less privileged = preferred
_EFFECT_RANK: dict[str, int] = {
    "internal_pure": 0,
    "external_read": 1,
    "external_write": 2,
    "human_mediated": 3,
    "privileged": 4,
}


class StepExecutor(Protocol):
    """Protocol for executing a single skill step.

    Implementations provide the actual execution logic for different action types.
    """

    def execute_step(
        self,
        step_id: str,
        action_type: str,
        input_bindings: Mapping[str, Any],
    ) -> SkillStepOutcome: ...


class PreconditionChecker(Protocol):
    """Protocol for checking skill preconditions against current state."""

    def check(self, condition_id: str, condition_type: str, parameters: Mapping[str, Any]) -> bool: ...


class PostconditionChecker(Protocol):
    """Protocol for checking skill postconditions after execution."""

    def check(self, condition_id: str, condition_type: str, parameters: Mapping[str, Any]) -> bool: ...


class SkillRegistry:
    """Central registry for skill descriptors with lifecycle management.

    Registration, lookup, lifecycle transitions, and querying.
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}

    def register(self, descriptor: SkillDescriptor) -> SkillDescriptor:
        if descriptor.skill_id in self._skills:
            raise RuntimeCoreInvariantError("skill already registered")
        self._skills[descriptor.skill_id] = descriptor
        return descriptor

    def get(self, skill_id: str) -> SkillDescriptor | None:
        ensure_non_empty_text("skill_id", skill_id)
        return self._skills.get(skill_id)

    def list_skills(
        self,
        *,
        skill_class: SkillClass | None = None,
        lifecycle: SkillLifecycle | None = None,
        exclude_blocked: bool = True,
    ) -> tuple[SkillDescriptor, ...]:
        result = sorted(self._skills.values(), key=lambda s: s.skill_id)
        if skill_class is not None:
            result = [s for s in result if s.skill_class == skill_class]
        if lifecycle is not None:
            result = [s for s in result if s.lifecycle == lifecycle]
        if exclude_blocked:
            result = [s for s in result if s.lifecycle is not SkillLifecycle.BLOCKED]
        return tuple(result)

    def transition(self, skill_id: str, new_lifecycle: SkillLifecycle) -> SkillDescriptor:
        """Transition a skill's lifecycle state. Returns the updated descriptor."""
        ensure_non_empty_text("skill_id", skill_id)
        current = self._skills.get(skill_id)
        if current is None:
            raise RuntimeCoreInvariantError("skill not found")
        allowed = _VALID_TRANSITIONS.get(current.lifecycle, frozenset())
        if new_lifecycle not in allowed:
            raise RuntimeCoreInvariantError("invalid lifecycle transition")
        # Rebuild descriptor with new lifecycle (frozen dataclass)
        updated = SkillDescriptor(
            skill_id=current.skill_id,
            name=current.name,
            skill_class=current.skill_class,
            effect_class=current.effect_class,
            determinism_class=current.determinism_class,
            trust_class=current.trust_class,
            verification_strength=current.verification_strength,
            lifecycle=new_lifecycle,
            preconditions=current.preconditions,
            postconditions=current.postconditions,
            steps=current.steps,
            provider_requirements=current.provider_requirements,
            description=current.description,
            runbook_id=current.runbook_id,
            confidence=current.confidence,
            metadata=current.metadata,
        )
        self._skills[skill_id] = updated
        return updated

    def update_confidence(self, skill_id: str, confidence: float) -> SkillDescriptor:
        """Update a skill's confidence score. Returns the updated descriptor."""
        ensure_non_empty_text("skill_id", skill_id)
        if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            raise RuntimeCoreInvariantError("confidence must be in [0.0, 1.0]")
        current = self._skills.get(skill_id)
        if current is None:
            raise RuntimeCoreInvariantError("skill not found")
        updated = SkillDescriptor(
            skill_id=current.skill_id,
            name=current.name,
            skill_class=current.skill_class,
            effect_class=current.effect_class,
            determinism_class=current.determinism_class,
            trust_class=current.trust_class,
            verification_strength=current.verification_strength,
            lifecycle=current.lifecycle,
            preconditions=current.preconditions,
            postconditions=current.postconditions,
            steps=current.steps,
            provider_requirements=current.provider_requirements,
            description=current.description,
            runbook_id=current.runbook_id,
            confidence=confidence,
            metadata=current.metadata,
        )
        self._skills[skill_id] = updated
        return updated

    @property
    def size(self) -> int:
        return len(self._skills)


class SkillSelector:
    """Deterministic skill selection based on lifecycle, confidence, and effect class.

    Selection rules (docs/19_skill_system.md section 8):
    1. Filter by precondition satisfaction
    2. Filter by policy allowance (via callable)
    3. Filter by provider availability (via callable)
    4. Rank by lifecycle state (trusted > verified > provisional > candidate)
    5. Rank by confidence score
    6. Rank by effect class (prefer least-privileged)
    7. Stable sort by skill_id on ties
    """

    def select(
        self,
        candidates: tuple[SkillDescriptor, ...],
        *,
        precondition_checker: PreconditionChecker | None = None,
        policy_checker: Callable[[str], bool] | None = None,
        provider_checker: Callable[[tuple[str, ...]], bool] | None = None,
    ) -> SkillSelectionDecision | None:
        """Select the best skill from candidates. Returns None if no candidates survive filtering."""
        if not candidates:
            return None

        all_ids = tuple(s.skill_id for s in candidates)
        rejected: dict[str, str] = {}
        surviving: list[SkillDescriptor] = []

        for skill in candidates:
            # Never select blocked
            if skill.lifecycle is SkillLifecycle.BLOCKED:
                rejected[skill.skill_id] = "blocked"
                continue

            # Precondition check
            if precondition_checker is not None and skill.preconditions:
                precond_ok = all(
                    precondition_checker.check(
                        pc.condition_id, pc.condition_type.value, dict(pc.parameters)
                    )
                    for pc in skill.preconditions
                )
                if not precond_ok:
                    rejected[skill.skill_id] = "precondition_not_met"
                    continue

            # Policy check
            if policy_checker is not None and not policy_checker(skill.skill_id):
                rejected[skill.skill_id] = "policy_denied"
                continue

            # Provider check
            if provider_checker is not None and skill.provider_requirements:
                if not provider_checker(skill.provider_requirements):
                    rejected[skill.skill_id] = "provider_unavailable"
                    continue

            surviving.append(skill)

        if not surviving:
            return None

        # Deterministic multi-key sort: lifecycle desc, confidence desc, effect asc, skill_id asc
        surviving.sort(key=lambda s: (
            -_LIFECYCLE_RANK.get(s.lifecycle, -1),
            -s.confidence,
            _EFFECT_RANK.get(s.effect_class.value, 99),
            s.skill_id,
        ))

        selected = surviving[0]
        reasons: list[str] = []
        reasons.append(f"lifecycle:{selected.lifecycle.value}")
        reasons.append(f"confidence:{selected.confidence:.4f}")
        reasons.append(f"effect_class:{selected.effect_class.value}")
        if len(surviving) > 1:
            reasons.append(f"preferred_over:{surviving[1].skill_id}")

        return SkillSelectionDecision(
            selected_skill_id=selected.skill_id,
            candidates_considered=all_ids,
            selection_reasons=tuple(reasons),
            rejected_reasons=rejected,
        )


class SkillExecutor:
    """Orchestrates skill execution: preconditions -> steps -> postconditions -> outcome.

    For primitive skills: executes the single action.
    For composite skills: executes steps in dependency order, stopping on first failure.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    def execute(
        self,
        skill: SkillDescriptor,
        *,
        step_executor: StepExecutor,
        precondition_checker: PreconditionChecker | None = None,
        postcondition_checker: PostconditionChecker | None = None,
        input_context: Mapping[str, Any] | None = None,
    ) -> SkillExecutionRecord:
        """Execute a skill and produce a full execution record."""
        started_at = self._clock()
        context = dict(input_context) if input_context else {}

        # Check preconditions
        if precondition_checker is not None:
            for pc in skill.preconditions:
                if not precondition_checker.check(pc.condition_id, pc.condition_type.value, dict(pc.parameters)):
                    outcome = SkillOutcome(
                        skill_id=skill.skill_id,
                        status=SkillOutcomeStatus.PRECONDITION_NOT_MET,
                        preconditions_met=False,
                        error_message=f"precondition failed: {pc.condition_id}",
                    )
                    return self._make_record(skill, outcome, started_at)

        # Execute steps
        if skill.skill_class is SkillClass.PRIMITIVE:
            step_outcomes = self._execute_primitive(skill, step_executor, context)
        else:
            step_outcomes = self._execute_composite(skill, step_executor, context)

        # Check for step failures
        failed_steps = [so for so in step_outcomes if so.status is not SkillOutcomeStatus.SUCCEEDED]
        if failed_steps:
            status = SkillOutcomeStatus.STEP_FAILED
            outcome = SkillOutcome(
                skill_id=skill.skill_id,
                status=status,
                step_outcomes=tuple(step_outcomes),
                error_message=f"step failed: {failed_steps[0].step_id}",
            )
            return self._make_record(skill, outcome, started_at)

        # Check postconditions
        postconditions_met = True
        if postcondition_checker is not None:
            for pc in skill.postconditions:
                if not postcondition_checker.check(pc.condition_id, pc.condition_type.value, dict(pc.parameters)):
                    postconditions_met = False
                    break

        if not postconditions_met:
            outcome = SkillOutcome(
                skill_id=skill.skill_id,
                status=SkillOutcomeStatus.POSTCONDITION_NOT_SATISFIED,
                step_outcomes=tuple(step_outcomes),
                postconditions_met=False,
                error_message="postcondition not satisfied",
            )
            return self._make_record(skill, outcome, started_at)

        # Success
        outcome = SkillOutcome(
            skill_id=skill.skill_id,
            status=SkillOutcomeStatus.SUCCEEDED,
            step_outcomes=tuple(step_outcomes),
        )
        return self._make_record(skill, outcome, started_at)

    def _execute_primitive(
        self,
        skill: SkillDescriptor,
        step_executor: StepExecutor,
        context: dict[str, Any],
    ) -> list[SkillStepOutcome]:
        """Execute a primitive skill as a single step."""
        result = step_executor.execute_step(
            step_id=f"{skill.skill_id}_primitive",
            action_type=skill.name,
            input_bindings=context,
        )
        return [result]

    def _execute_composite(
        self,
        skill: SkillDescriptor,
        step_executor: StepExecutor,
        context: dict[str, Any],
    ) -> list[SkillStepOutcome]:
        """Execute composite skill steps in topological order, stopping on first failure."""
        execution_order = self._topological_sort(skill.steps)
        step_outputs: dict[str, Mapping[str, Any]] = {}
        outcomes: list[SkillStepOutcome] = []

        for step in execution_order:
            # Build input bindings from context and prior step outputs
            bindings: dict[str, Any] = dict(context)
            for binding_key, source_ref in step.input_bindings.items():
                # source_ref format: "step_id.output_key" or "context.key"
                parts = source_ref.split(".", 1)
                if len(parts) == 2 and parts[0] in step_outputs:
                    bindings[binding_key] = step_outputs[parts[0]].get(parts[1])
                elif len(parts) == 2 and parts[0] == "context":
                    bindings[binding_key] = context.get(parts[1])

            result = step_executor.execute_step(
                step_id=step.step_id,
                action_type=step.action_type,
                input_bindings=bindings,
            )
            outcomes.append(result)

            if result.status is not SkillOutcomeStatus.SUCCEEDED:
                break  # Stop on first failure

            step_outputs[step.step_id] = dict(result.outputs)

        return outcomes

    def _topological_sort(self, steps: tuple) -> list:
        """Sort steps by dependency order (Kahn's algorithm)."""
        step_map = {s.step_id: s for s in steps}
        in_degree: dict[str, int] = {s.step_id: 0 for s in steps}
        dependents: dict[str, list[str]] = {s.step_id: [] for s in steps}

        for step in steps:
            for dep in step.depends_on:
                in_degree[step.step_id] += 1
                dependents[dep].append(step.step_id)

        # Start with steps that have no dependencies, sorted by ID for determinism
        queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])
        result: list = []

        while queue:
            current = queue.pop(0)
            result.append(step_map[current])
            for dependent in sorted(dependents[current]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
                    queue.sort()

        return result

    def _make_record(
        self,
        skill: SkillDescriptor,
        outcome: SkillOutcome,
        started_at: str,
    ) -> SkillExecutionRecord:
        record_id = stable_identifier("skill-exec", {
            "skill_id": skill.skill_id,
            "started_at": started_at,
        })
        return SkillExecutionRecord(
            record_id=record_id,
            skill_id=skill.skill_id,
            outcome=outcome,
            started_at=started_at,
            finished_at=self._clock(),
        )
