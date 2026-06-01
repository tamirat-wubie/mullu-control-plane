"""Purpose: define the read-only agentic-control governor chain workflow.
Governance scope: policy, decision, design, coding, quality, release, and
runtime governor cohesion.
Dependencies: skill descriptors, workflow contracts, and default skill catalog.
Invariants:
  - The chain composes existing governor skills; it registers no new skill.
  - Every stage is read-only and grants no capability authority.
  - Data handoff is explicit through workflow bindings.
  - Validation fails closed on missing, blocked, writable, or reordered stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from mcoi_runtime.contracts.skill import (
    EffectClass,
    SkillDescriptor,
    SkillLifecycle,
    VerificationStrength,
)
from mcoi_runtime.contracts.workflow import (
    StageType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowStage,
)
from mcoi_runtime.core.default_skill_catalog import default_skill_descriptors


GOVERNOR_CHAIN_WORKFLOW_ID = "agentic_control.governor_chain.cohesion.v1"
GOVERNOR_CHAIN_CREATED_AT = "2026-06-01T00:00:00+00:00"
GOVERNOR_CHAIN_OUTPUT_KEY = "governance_packet_ref"
GOVERNOR_CHAIN_INPUT_KEY = "upstream_governance_packet_ref"
GOVERNOR_STAGE_TIMEOUT_SECONDS = 900


@dataclass(frozen=True, slots=True)
class GovernorChainStage:
    """Canonical stage binding for one existing read-only governor skill."""

    order: int
    stage_id: str
    skill_id: str
    responsibility: str
    verification_evidence: str


CANONICAL_GOVERNOR_CHAIN: tuple[GovernorChainStage, ...] = (
    GovernorChainStage(
        1,
        "policy_governor",
        "agentic_control.policy_governor.v1",
        "establish authority, policy, approval, and hard-stop boundaries",
        "policy_verification_plan_ref",
    ),
    GovernorChainStage(
        2,
        "decision_governor",
        "agentic_control.decision_governor.v1",
        "rank options and preserve selected and rejected decision proof",
        "decision_verification_plan_ref",
    ),
    GovernorChainStage(
        3,
        "design_governor",
        "agentic_control.design_governor.v1",
        "bound research, interaction risk, and design validation evidence",
        "design_verification_plan_ref",
    ),
    GovernorChainStage(
        4,
        "coding_governor",
        "agentic_control.coding_governor.v1",
        "bound repository change, test contract, threat model, and rollback plan",
        "code_verification_plan_ref",
    ),
    GovernorChainStage(
        5,
        "quality_governor",
        "agentic_control.quality_governor.v1",
        "verify acceptance, quality gates, residual gaps, and closure rule",
        "quality_verification_plan_ref",
    ),
    GovernorChainStage(
        6,
        "release_governor",
        "agentic_control.release_governor.v1",
        "prepare release evidence, handoff boundaries, and rollback readiness",
        "release_verification_plan_ref",
    ),
    GovernorChainStage(
        7,
        "runtime_governor",
        "agentic_control.runtime_governor.v1",
        "bind observability, recovery, telemetry, and runtime closure evidence",
        "runtime_verification_plan_ref",
    ),
)


def canonical_governor_chain_skill_ids() -> tuple[str, ...]:
    """Return the canonical ordered governor skill identifiers."""

    return tuple(stage.skill_id for stage in CANONICAL_GOVERNOR_CHAIN)


def build_governor_chain_descriptor(
    *,
    created_at: str = GOVERNOR_CHAIN_CREATED_AT,
) -> WorkflowDescriptor:
    """Build the read-only workflow descriptor for governor-chain cohesion."""

    stages: list[WorkflowStage] = []
    bindings: list[WorkflowBinding] = []
    previous_stage: GovernorChainStage | None = None
    for chain_stage in CANONICAL_GOVERNOR_CHAIN:
        predecessors = (previous_stage.stage_id,) if previous_stage is not None else ()
        stages.append(
            WorkflowStage(
                stage_id=chain_stage.stage_id,
                stage_type=StageType.SKILL_EXECUTION,
                skill_id=chain_stage.skill_id,
                description=chain_stage.responsibility,
                predecessors=predecessors,
                timeout_seconds=GOVERNOR_STAGE_TIMEOUT_SECONDS,
            )
        )
        if previous_stage is not None:
            bindings.append(
                WorkflowBinding(
                    binding_id=f"{previous_stage.stage_id}_to_{chain_stage.stage_id}",
                    source_stage_id=previous_stage.stage_id,
                    source_output_key=GOVERNOR_CHAIN_OUTPUT_KEY,
                    target_stage_id=chain_stage.stage_id,
                    target_input_key=GOVERNOR_CHAIN_INPUT_KEY,
                )
            )
        previous_stage = chain_stage

    return WorkflowDescriptor(
        workflow_id=GOVERNOR_CHAIN_WORKFLOW_ID,
        name="Agentic-control governor chain cohesion",
        description=(
            "Read-only workflow descriptor that composes existing policy, "
            "decision, design, coding, quality, release, and runtime governors "
            "into one explicit governed planning chain."
        ),
        stages=tuple(stages),
        bindings=tuple(bindings),
        created_at=created_at,
    )


def validate_governor_chain_descriptor(
    descriptor: WorkflowDescriptor | None = None,
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None = None,
) -> tuple[str, ...]:
    """Return validation violations for the governor chain; empty means valid."""

    workflow = descriptor or build_governor_chain_descriptor()
    skill_map = _skill_map(skill_descriptors)
    violations: list[str] = []

    if workflow.workflow_id != GOVERNOR_CHAIN_WORKFLOW_ID:
        violations.append("governor chain workflow identifier changed")
    if len(workflow.stages) != len(CANONICAL_GOVERNOR_CHAIN):
        violations.append("governor chain stage count changed")

    expected_stage_ids = tuple(stage.stage_id for stage in CANONICAL_GOVERNOR_CHAIN)
    actual_stage_ids = tuple(stage.stage_id for stage in workflow.stages)
    if actual_stage_ids != expected_stage_ids:
        violations.append("governor chain stage order changed")

    for index, expected in enumerate(CANONICAL_GOVERNOR_CHAIN):
        if index >= len(workflow.stages):
            continue
        actual = workflow.stages[index]
        expected_predecessors = () if index == 0 else (CANONICAL_GOVERNOR_CHAIN[index - 1].stage_id,)
        if actual.stage_id != expected.stage_id:
            violations.append(f"{expected.stage_id} stage identifier changed")
        if actual.stage_type is not StageType.SKILL_EXECUTION:
            violations.append(f"{expected.stage_id} must be a skill_execution stage")
        if actual.skill_id != expected.skill_id:
            violations.append(f"{expected.stage_id} skill binding changed")
        if actual.predecessors != expected_predecessors:
            violations.append(f"{expected.stage_id} predecessor binding changed")
        if actual.timeout_seconds != GOVERNOR_STAGE_TIMEOUT_SECONDS:
            violations.append(f"{expected.stage_id} timeout boundary changed")
        violations.extend(_validate_governor_skill(expected, skill_map))

    expected_bindings = _expected_bindings()
    actual_bindings = tuple(
        (
            binding.binding_id,
            binding.source_stage_id,
            binding.source_output_key,
            binding.target_stage_id,
            binding.target_input_key,
        )
        for binding in workflow.bindings
    )
    if actual_bindings != expected_bindings:
        violations.append("governor chain handoff bindings changed")

    return tuple(violations)


def build_governor_chain_read_model(
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None = None,
    *,
    created_at: str = GOVERNOR_CHAIN_CREATED_AT,
) -> dict[str, object]:
    """Project governor-chain cohesion into a deterministic read model."""

    workflow = build_governor_chain_descriptor(created_at=created_at)
    skill_map = _skill_map(skill_descriptors)
    violations = validate_governor_chain_descriptor(workflow, skill_map)
    stage_rows = []
    for chain_stage in CANONICAL_GOVERNOR_CHAIN:
        skill = skill_map.get(chain_stage.skill_id)
        stage_rows.append(
            {
                "order": chain_stage.order,
                "stage_id": chain_stage.stage_id,
                "skill_id": chain_stage.skill_id,
                "skill_name": skill.name if skill is not None else "",
                "effect_class": skill.effect_class.value if skill is not None else "",
                "lifecycle": skill.lifecycle.value if skill is not None else "",
                "verification_strength": skill.verification_strength.value if skill is not None else "",
                "responsibility": chain_stage.responsibility,
                "verification_evidence": chain_stage.verification_evidence,
                "input_key": "" if chain_stage.order == 1 else GOVERNOR_CHAIN_INPUT_KEY,
                "output_key": GOVERNOR_CHAIN_OUTPUT_KEY,
                "grants_new_capability_authority": (
                    skill.metadata.get("grants_new_capability_authority") if skill is not None else None
                ),
            }
        )
    return {
        "read_model_id": GOVERNOR_CHAIN_WORKFLOW_ID,
        "read_only": True,
        "governed": True,
        "valid": not violations,
        "violations": violations,
        "stage_count": len(stage_rows),
        "binding_count": len(workflow.bindings),
        "handoff": f"{GOVERNOR_CHAIN_OUTPUT_KEY} -> {GOVERNOR_CHAIN_INPUT_KEY}",
        "chain": canonical_governor_chain_skill_ids(),
        "stages": stage_rows,
        "workflow": workflow.to_json_dict(),
    }


def _skill_map(
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None,
) -> dict[str, SkillDescriptor]:
    if skill_descriptors is None:
        descriptors = default_skill_descriptors()
        return {descriptor.skill_id: descriptor for descriptor in descriptors}
    if isinstance(skill_descriptors, Mapping):
        return dict(skill_descriptors)
    return {descriptor.skill_id: descriptor for descriptor in skill_descriptors}


def _validate_governor_skill(
    chain_stage: GovernorChainStage,
    skill_map: Mapping[str, SkillDescriptor],
) -> tuple[str, ...]:
    skill = skill_map.get(chain_stage.skill_id)
    if skill is None:
        return (f"{chain_stage.skill_id} missing from skill catalog",)
    violations: list[str] = []
    if skill.effect_class is not EffectClass.EXTERNAL_READ:
        violations.append(f"{chain_stage.skill_id} must remain read-only")
    if skill.lifecycle is SkillLifecycle.BLOCKED:
        violations.append(f"{chain_stage.skill_id} must not be blocked")
    if skill.verification_strength is not VerificationStrength.MANDATORY:
        violations.append(f"{chain_stage.skill_id} must keep mandatory verification")
    if skill.metadata.get("grants_new_capability_authority") is not False:
        violations.append(f"{chain_stage.skill_id} must not grant capability authority")
    return tuple(violations)


def _expected_bindings() -> tuple[tuple[str, str, str, str, str], ...]:
    expected: list[tuple[str, str, str, str, str]] = []
    for previous_stage, next_stage in zip(CANONICAL_GOVERNOR_CHAIN, CANONICAL_GOVERNOR_CHAIN[1:]):
        expected.append(
            (
                f"{previous_stage.stage_id}_to_{next_stage.stage_id}",
                previous_stage.stage_id,
                GOVERNOR_CHAIN_OUTPUT_KEY,
                next_stage.stage_id,
                GOVERNOR_CHAIN_INPUT_KEY,
            )
        )
    return tuple(expected)
