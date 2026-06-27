"""Purpose: reusable capability unlock ladder and local developer workflow.
Governance scope: capability maturity interpretation, reusable gate templates,
local software-development workflow composition, approval boundary placement,
and receipt obligations.
Dependencies: dataclasses and workflow runtime contracts.
Invariants:
  - Unlock levels describe admission expectations; they do not promote authority.
  - Effect-bearing levels require explicit receipt evidence.
  - External or durable mutation levels require approval and rollback evidence.
  - Local developer workflow stages are acyclic and bind through declared keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry
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


GATE_EVIDENCE_INTAKE = "evidence_intake_gate"
GATE_APPROVAL = "approval_gate"
GATE_VERIFIER = "verifier_gate"
GATE_WORKSPACE_WRITE = "workspace_write_gate"
GATE_CONNECTOR_LEASE = "connector_lease_gate"
GATE_EXECUTION_RECEIPT = "execution_receipt_gate"
GATE_ROLLBACK = "rollback_gate"
GATE_OPERATOR_REVIEW = "operator_review_gate"

UNLOCK_LADDER_ID = "mullu.capability_unlock_ladder.v1"
LOCAL_DEVELOPER_WORKFLOW_ID = "mullu.local_developer_workflow.v1"
FIXED_DESCRIPTOR_CREATED_AT = "2026-06-26T00:00:00+00:00"
LOCAL_DEVELOPER_STAGE_TIMEOUT_SECONDS = {
    "plan_local_change": 300,
    "run_local_change_chain": 1200,
    "verify_local_receipt": 300,
    "operator_review_gate": 86400,
    "prepare_pr_evidence": 300,
}


@dataclass(frozen=True, slots=True)
class CapabilityUnlockLevel:
    """One non-authoritative capability unlock level."""

    level: int
    name: str
    summary: str
    maturity_floor: str
    required_gate_ids: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    requires_operator_approval: bool
    requires_receipt: bool
    requires_rollback: bool
    requires_live_witness: bool

    @property
    def level_id(self) -> str:
        """Return the stable ladder level identifier."""
        return f"L{self.level}"


@dataclass(frozen=True, slots=True)
class CapabilityUnlockAdmissionProfile:
    """Resolved ladder obligations for one governed capability."""

    capability_id: str
    ladder_id: str
    level: int
    level_id: str
    gate_template_ids: tuple[str, ...]
    requires_operator_approval: bool
    requires_receipt: bool
    requires_rollback: bool
    requires_live_witness: bool
    allowed_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowStage:
    """Canonical stage contract for the local developer workflow."""

    order: int
    stage_id: str
    stage_type: StageType
    skill_id: str
    predecessor_id: str
    closure_evidence_key: str
    responsibility: str


CANONICAL_LOCAL_DEVELOPER_WORKFLOW: tuple[LocalDeveloperWorkflowStage, ...] = (
    LocalDeveloperWorkflowStage(
        order=1,
        stage_id="plan_local_change",
        stage_type=StageType.SKILL_EXECUTION,
        skill_id="agentic_control.coding_governor.v1",
        predecessor_id="",
        closure_evidence_key="code_change_plan_ref",
        responsibility="create the local plan, change boundary, test contract, and rollback plan",
    ),
    LocalDeveloperWorkflowStage(
        order=2,
        stage_id="run_local_change_chain",
        stage_type=StageType.SKILL_EXECUTION,
        skill_id="software_dev.change_closure.v1",
        predecessor_id="plan_local_change",
        closure_evidence_key="change_receipt_id",
        responsibility="generate context, run the bounded local change path, and emit receipt evidence",
    ),
    LocalDeveloperWorkflowStage(
        order=3,
        stage_id="verify_local_receipt",
        stage_type=StageType.SKILL_EXECUTION,
        skill_id="agentic_control.quality_governor.v1",
        predecessor_id="run_local_change_chain",
        closure_evidence_key="quality_verification_plan_ref",
        responsibility="verify receipt, gates, rollback evidence, and residual risk before review",
    ),
    LocalDeveloperWorkflowStage(
        order=4,
        stage_id="operator_review_gate",
        stage_type=StageType.APPROVAL_GATE,
        skill_id="",
        predecessor_id="verify_local_receipt",
        closure_evidence_key="approval_decision_ref",
        responsibility="suspend for operator approval before PR-opening or external mutation intent",
    ),
    LocalDeveloperWorkflowStage(
        order=5,
        stage_id="prepare_pr_evidence",
        stage_type=StageType.SKILL_EXECUTION,
        skill_id="agentic_control.release_governor.v1",
        predecessor_id="operator_review_gate",
        closure_evidence_key="release_handoff_plan_ref",
        responsibility="prepare PR evidence and release handoff packet without pushing or opening PR",
    ),
)


def default_gate_template_ids() -> tuple[str, ...]:
    """Return reusable gate template ids available to capability profiles."""
    return (
        GATE_EVIDENCE_INTAKE,
        GATE_APPROVAL,
        GATE_VERIFIER,
        GATE_WORKSPACE_WRITE,
        GATE_CONNECTOR_LEASE,
        GATE_EXECUTION_RECEIPT,
        GATE_ROLLBACK,
        GATE_OPERATOR_REVIEW,
    )


def default_capability_unlock_ladder() -> tuple[CapabilityUnlockLevel, ...]:
    """Return the canonical local-first Level 0-9 unlock ladder."""
    return (
        CapabilityUnlockLevel(
            level=0,
            name="Read-only",
            summary="Inspect, explain, and summarize without durable or external effects.",
            maturity_floor="C0",
            required_gate_ids=(GATE_EVIDENCE_INTAKE,),
            allowed_effects=("inspect", "explain", "summarize"),
            forbidden_effects=("workspace_file_written", "external_write", "credentialed_mutation"),
            requires_operator_approval=False,
            requires_receipt=False,
            requires_rollback=False,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=1,
            name="Local demo",
            summary="Run safe local workflows without external effects.",
            maturity_floor="C1",
            required_gate_ids=(GATE_EVIDENCE_INTAKE, GATE_VERIFIER),
            allowed_effects=("local_execution", "dry_run"),
            forbidden_effects=("external_write", "credentialed_mutation", "production_deployment"),
            requires_operator_approval=False,
            requires_receipt=True,
            requires_rollback=False,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=2,
            name="File preparation",
            summary="Generate diffs, documents, schemas, tests, and review packets.",
            maturity_floor="C2",
            required_gate_ids=(GATE_EVIDENCE_INTAKE, GATE_VERIFIER, GATE_EXECUTION_RECEIPT),
            allowed_effects=("diff_generated", "artifact_prepared", "receipt_emitted"),
            forbidden_effects=("workspace_file_written", "external_write", "production_deployment"),
            requires_operator_approval=False,
            requires_receipt=True,
            requires_rollback=False,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=3,
            name="File writing",
            summary="Write inside a controlled workspace or branch only.",
            maturity_floor="C3",
            required_gate_ids=(
                GATE_EVIDENCE_INTAKE,
                GATE_WORKSPACE_WRITE,
                GATE_EXECUTION_RECEIPT,
                GATE_ROLLBACK,
                GATE_OPERATOR_REVIEW,
            ),
            allowed_effects=("workspace_file_written", "local_branch_changed"),
            forbidden_effects=("path_outside_workspace_written", "external_write", "production_deployment"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=True,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=4,
            name="Test execution",
            summary="Run bounded tests and capture receipts.",
            maturity_floor="C3",
            required_gate_ids=(GATE_EVIDENCE_INTAKE, GATE_VERIFIER, GATE_EXECUTION_RECEIPT, GATE_ROLLBACK),
            allowed_effects=("test_process_started", "test_receipt_emitted"),
            forbidden_effects=("network_enabled_by_default", "external_write", "production_deployment"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=True,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=5,
            name="PR creation",
            summary="Prepare pull request evidence; opening requires explicit approval.",
            maturity_floor="C4",
            required_gate_ids=(
                GATE_EVIDENCE_INTAKE,
                GATE_APPROVAL,
                GATE_VERIFIER,
                GATE_EXECUTION_RECEIPT,
                GATE_OPERATOR_REVIEW,
            ),
            allowed_effects=("review_packet_emitted", "pr_intent_prepared"),
            forbidden_effects=("git_push_without_approval", "pull_request_opened_without_approval"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=True,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=6,
            name="Human approval",
            summary="Operator approves or rejects the next effect boundary.",
            maturity_floor="C4",
            required_gate_ids=(GATE_APPROVAL, GATE_OPERATOR_REVIEW, GATE_EXECUTION_RECEIPT),
            allowed_effects=("approval_decision_recorded", "rejection_recorded"),
            forbidden_effects=("implicit_approval", "approval_timeout_continues"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=False,
            requires_live_witness=False,
        ),
        CapabilityUnlockLevel(
            level=7,
            name="Live connector probe",
            summary="Run limited read-only credentialed connector probes.",
            maturity_floor="C5",
            required_gate_ids=(GATE_CONNECTOR_LEASE, GATE_VERIFIER, GATE_EXECUTION_RECEIPT),
            allowed_effects=("credentialed_read", "live_read_receipt_emitted"),
            forbidden_effects=("credentialed_write", "external_message_send", "payment_started"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=False,
            requires_live_witness=True,
        ),
        CapabilityUnlockLevel(
            level=8,
            name="Approved live action",
            summary="Execute approved live writes only with receipts and recovery.",
            maturity_floor="C6",
            required_gate_ids=(
                GATE_CONNECTOR_LEASE,
                GATE_APPROVAL,
                GATE_VERIFIER,
                GATE_EXECUTION_RECEIPT,
                GATE_ROLLBACK,
            ),
            allowed_effects=("credentialed_write", "approved_external_mutation"),
            forbidden_effects=("unapproved_external_write", "receiptless_mutation"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=True,
            requires_live_witness=True,
        ),
        CapabilityUnlockLevel(
            level=9,
            name="Customer-ready product",
            summary="Operate with onboarding, support, billing, monitoring, and production witnesses.",
            maturity_floor="C7",
            required_gate_ids=(
                GATE_APPROVAL,
                GATE_VERIFIER,
                GATE_EXECUTION_RECEIPT,
                GATE_ROLLBACK,
                GATE_OPERATOR_REVIEW,
            ),
            allowed_effects=("customer_workflow", "production_operation"),
            forbidden_effects=("unmonitored_runtime", "unsupported_customer_exposure"),
            requires_operator_approval=True,
            requires_receipt=True,
            requires_rollback=True,
            requires_live_witness=True,
        ),
    )


def validate_capability_unlock_ladder(
    levels: tuple[CapabilityUnlockLevel, ...],
) -> tuple[str, ...]:
    """Return structural validation errors for an unlock ladder."""
    errors: list[str] = []
    expected_levels = tuple(range(10))
    observed_levels = tuple(level.level for level in levels)
    known_gates = set(default_gate_template_ids())

    if observed_levels != expected_levels:
        errors.append("unlock_levels_must_be_consecutive_L0_through_L9")

    for level in levels:
        if not level.required_gate_ids:
            errors.append(f"{level.level_id}:required_gates_missing")
        unknown_gates = tuple(gate_id for gate_id in level.required_gate_ids if gate_id not in known_gates)
        if unknown_gates:
            errors.append(f"{level.level_id}:unknown_gate_template")
        if level.level >= 1 and not level.requires_receipt:
            errors.append(f"{level.level_id}:receipt_required_after_read_only")
        if level.level in {3, 4, 5, 8, 9} and not level.requires_rollback:
            errors.append(f"{level.level_id}:rollback_required_for_mutation_boundary")
        if level.level >= 3 and not level.requires_operator_approval:
            errors.append(f"{level.level_id}:operator_approval_required_for_effect_boundary")
        if level.level >= 7 and not level.requires_live_witness:
            errors.append(f"{level.level_id}:live_witness_required_for_live_boundary")

    return tuple(errors)


def capability_unlock_profile_errors(entry: CapabilityRegistryEntry) -> tuple[str, ...]:
    """Return explicit errors for an entry's reusable unlock ladder profile."""
    if not isinstance(entry, CapabilityRegistryEntry):
        return ("entry_must_be_capability_registry_entry",)
    raw_profile = entry.metadata.get("unlock_ladder")
    if raw_profile is None:
        return ()
    if not isinstance(raw_profile, Mapping):
        return ("unlock_ladder_profile_must_be_object",)

    errors: list[str] = []
    levels_by_number = {level.level: level for level in default_capability_unlock_ladder()}
    levels_by_id = {level.level_id: level for level in levels_by_number.values()}

    ladder_id = raw_profile.get("ladder_id")
    level = raw_profile.get("level")
    level_id = raw_profile.get("level_id")
    gate_template_ids = raw_profile.get("gate_template_ids")

    if ladder_id != UNLOCK_LADDER_ID:
        errors.append("unlock_ladder_id_mismatch")
    if not isinstance(level, int) or isinstance(level, bool):
        errors.append("unlock_ladder_level_must_be_integer")
        ladder_level = None
    else:
        ladder_level = levels_by_number.get(level)
        if ladder_level is None:
            errors.append("unlock_ladder_level_unknown")

    if not isinstance(level_id, str) or not level_id:
        errors.append("unlock_ladder_level_id_missing")
    elif level_id not in levels_by_id:
        errors.append("unlock_ladder_level_id_unknown")
    elif ladder_level is not None and level_id != ladder_level.level_id:
        errors.append("unlock_ladder_level_id_mismatch")

    if not isinstance(gate_template_ids, (tuple, list)) or not gate_template_ids:
        errors.append("unlock_ladder_gate_template_ids_missing")
    elif ladder_level is not None:
        observed_gate_ids = tuple(str(gate_id) for gate_id in gate_template_ids)
        if observed_gate_ids != ladder_level.required_gate_ids:
            errors.append("unlock_ladder_gate_template_ids_mismatch")
        unknown_gate_ids = tuple(gate_id for gate_id in observed_gate_ids if gate_id not in default_gate_template_ids())
        if unknown_gate_ids:
            errors.append("unlock_ladder_gate_template_ids_unknown")

    return tuple(errors)


def capability_unlock_admission_profile(
    entry: CapabilityRegistryEntry,
) -> CapabilityUnlockAdmissionProfile | None:
    """Resolve a valid unlock profile into runtime admission obligations."""
    errors = capability_unlock_profile_errors(entry)
    if errors:
        raise ValueError(";".join(errors))
    raw_profile = entry.metadata.get("unlock_ladder")
    if raw_profile is None:
        return None
    profile = _as_mapping(raw_profile)
    level_number = int(profile["level"])
    ladder_level = {level.level: level for level in default_capability_unlock_ladder()}[level_number]
    return CapabilityUnlockAdmissionProfile(
        capability_id=entry.capability_id,
        ladder_id=UNLOCK_LADDER_ID,
        level=ladder_level.level,
        level_id=ladder_level.level_id,
        gate_template_ids=ladder_level.required_gate_ids,
        requires_operator_approval=ladder_level.requires_operator_approval,
        requires_receipt=ladder_level.requires_receipt,
        requires_rollback=ladder_level.requires_rollback,
        requires_live_witness=ladder_level.requires_live_witness,
        allowed_effects=ladder_level.allowed_effects,
        forbidden_effects=ladder_level.forbidden_effects,
    )


def mullu_local_developer_workflow_v1_descriptor() -> WorkflowDescriptor:
    """Return the reusable local developer workflow descriptor."""
    return WorkflowDescriptor(
        workflow_id=LOCAL_DEVELOPER_WORKFLOW_ID,
        name="Mullu Local Developer Workflow v1",
        description=(
            "Composes reusable gates for local plan, bounded code change, dry-run "
            "verification, operator approval, and PR evidence preparation."
        ),
        stages=(
            WorkflowStage(
                stage_id="plan_local_change",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="agentic_control.coding_governor.v1",
                description="Create the local plan, change boundary, test contract, and rollback plan.",
                timeout_seconds=300,
            ),
            WorkflowStage(
                stage_id="run_local_change_chain",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="software_dev.change_closure.v1",
                description="Generate context, select gates, run bounded local change, and emit receipt.",
                predecessors=("plan_local_change",),
                timeout_seconds=1200,
            ),
            WorkflowStage(
                stage_id="verify_local_receipt",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="agentic_control.quality_governor.v1",
                description="Verify receipt, gates, rollback evidence, and residual risk before review.",
                predecessors=("run_local_change_chain",),
                timeout_seconds=300,
            ),
            WorkflowStage(
                stage_id="operator_review_gate",
                stage_type=StageType.APPROVAL_GATE,
                description="Suspend for operator approval before PR-opening or external mutation intent.",
                predecessors=("verify_local_receipt",),
                timeout_seconds=86400,
            ),
            WorkflowStage(
                stage_id="prepare_pr_evidence",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="agentic_control.release_governor.v1",
                description="Prepare PR evidence and release handoff packet without pushing or opening PR.",
                predecessors=("operator_review_gate",),
                timeout_seconds=300,
            ),
        ),
        bindings=(
            WorkflowBinding(
                binding_id="local_plan_to_change_chain",
                source_stage_id="plan_local_change",
                source_output_key="code_change_plan_ref",
                target_stage_id="run_local_change_chain",
                target_input_key="code_change_plan_ref",
            ),
            WorkflowBinding(
                binding_id="change_receipt_to_verifier",
                source_stage_id="run_local_change_chain",
                source_output_key="change_receipt_id",
                target_stage_id="verify_local_receipt",
                target_input_key="change_receipt_id",
            ),
            WorkflowBinding(
                binding_id="verification_to_operator_review",
                source_stage_id="verify_local_receipt",
                source_output_key="quality_verification_plan_ref",
                target_stage_id="operator_review_gate",
                target_input_key="verification_plan_ref",
            ),
            WorkflowBinding(
                binding_id="approval_to_pr_evidence",
                source_stage_id="operator_review_gate",
                source_output_key="approval_decision_ref",
                target_stage_id="prepare_pr_evidence",
                target_input_key="approval_decision_ref",
            ),
        ),
        created_at=FIXED_DESCRIPTOR_CREATED_AT,
    )


def validate_local_developer_workflow_descriptor(
    descriptor: WorkflowDescriptor | None = None,
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None = None,
) -> tuple[str, ...]:
    """Return validation violations for Local Developer Workflow v1."""
    workflow = descriptor or mullu_local_developer_workflow_v1_descriptor()
    skill_map = _skill_map(skill_descriptors)
    violations: list[str] = []

    if workflow.workflow_id != LOCAL_DEVELOPER_WORKFLOW_ID:
        violations.append("local developer workflow identifier changed")
    if len(workflow.stages) != len(CANONICAL_LOCAL_DEVELOPER_WORKFLOW):
        violations.append("local developer workflow stage count changed")

    expected_stage_ids = tuple(stage.stage_id for stage in CANONICAL_LOCAL_DEVELOPER_WORKFLOW)
    actual_stage_ids = tuple(stage.stage_id for stage in workflow.stages)
    if actual_stage_ids != expected_stage_ids:
        violations.append("local developer workflow stage order changed")

    for index, expected in enumerate(CANONICAL_LOCAL_DEVELOPER_WORKFLOW):
        if index >= len(workflow.stages):
            continue
        actual = workflow.stages[index]
        expected_predecessors = () if not expected.predecessor_id else (expected.predecessor_id,)
        expected_skill_id = expected.skill_id or None
        if actual.stage_id != expected.stage_id:
            violations.append(f"{expected.stage_id} stage identifier changed")
        if actual.stage_type is not expected.stage_type:
            violations.append(f"{expected.stage_id} stage type changed")
        if actual.skill_id != expected_skill_id:
            violations.append(f"{expected.stage_id} skill binding changed")
        if actual.predecessors != expected_predecessors:
            violations.append(f"{expected.stage_id} predecessor binding changed")
        if actual.timeout_seconds != LOCAL_DEVELOPER_STAGE_TIMEOUT_SECONDS[expected.stage_id]:
            violations.append(f"{expected.stage_id} timeout boundary changed")
        if expected.skill_id:
            violations.extend(_validate_local_developer_skill(expected, skill_map))

    expected_bindings = _expected_local_developer_bindings()
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
        violations.append("local developer workflow handoff bindings changed")

    return tuple(violations)


def build_local_developer_workflow_read_model(
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None = None,
    *,
    created_at: str = FIXED_DESCRIPTOR_CREATED_AT,
) -> dict[str, object]:
    """Project Local Developer Workflow v1 into a deterministic operator read model."""
    workflow = mullu_local_developer_workflow_v1_descriptor()
    if created_at != FIXED_DESCRIPTOR_CREATED_AT:
        workflow = WorkflowDescriptor(
            workflow_id=workflow.workflow_id,
            name=workflow.name,
            description=workflow.description,
            stages=workflow.stages,
            bindings=workflow.bindings,
            created_at=created_at,
        )
    skill_map = _skill_map(skill_descriptors)
    violations = validate_local_developer_workflow_descriptor(workflow, skill_map)
    stage_rows = []
    for stage in CANONICAL_LOCAL_DEVELOPER_WORKFLOW:
        skill = skill_map.get(stage.skill_id) if stage.skill_id else None
        stage_rows.append(
            {
                "order": stage.order,
                "stage_id": stage.stage_id,
                "stage_type": stage.stage_type.value,
                "skill_id": stage.skill_id,
                "skill_name": skill.name if skill is not None else "",
                "effect_class": skill.effect_class.value if skill is not None else "",
                "lifecycle": skill.lifecycle.value if skill is not None else "",
                "verification_strength": skill.verification_strength.value if skill is not None else "",
                "responsibility": stage.responsibility,
                "closure_evidence_key": stage.closure_evidence_key,
                "predecessor_id": stage.predecessor_id,
                "timeout_seconds": LOCAL_DEVELOPER_STAGE_TIMEOUT_SECONDS[stage.stage_id],
                "grants_new_capability_authority": (
                    skill.metadata.get("grants_new_capability_authority") if skill is not None else False
                ),
            }
        )
    return {
        "read_model_id": LOCAL_DEVELOPER_WORKFLOW_ID,
        "foundation_mode": True,
        "governed": True,
        "valid": not violations,
        "violations": violations,
        "stage_count": len(stage_rows),
        "binding_count": len(workflow.bindings),
        "approval_stage_id": "operator_review_gate",
        "external_mutation_allowed": False,
        "workflow": workflow.to_json_dict(),
        "stages": stage_rows,
    }


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("value_must_be_mapping")
    return value


def _skill_map(
    skill_descriptors: Iterable[SkillDescriptor] | Mapping[str, SkillDescriptor] | None,
) -> dict[str, SkillDescriptor]:
    if skill_descriptors is None:
        descriptors = default_skill_descriptors()
    elif isinstance(skill_descriptors, Mapping):
        return dict(skill_descriptors)
    else:
        descriptors = tuple(skill_descriptors)
    return {descriptor.skill_id: descriptor for descriptor in descriptors}


def _validate_local_developer_skill(
    expected: LocalDeveloperWorkflowStage,
    skill_map: Mapping[str, SkillDescriptor],
) -> tuple[str, ...]:
    violations: list[str] = []
    skill = skill_map.get(expected.skill_id)
    if skill is None:
        return (f"{expected.stage_id} skill descriptor missing",)
    if skill.lifecycle is SkillLifecycle.BLOCKED:
        violations.append(f"{expected.stage_id} skill is blocked")
    if skill.verification_strength is not VerificationStrength.MANDATORY:
        violations.append(f"{expected.stage_id} skill must require mandatory verification")
    if skill.metadata.get("grants_new_capability_authority") is not False:
        violations.append(f"{expected.stage_id} skill must not grant capability authority")
    if expected.stage_id == "run_local_change_chain":
        if skill.effect_class is not EffectClass.EXTERNAL_WRITE:
            violations.append("run_local_change_chain must remain the only write-bearing skill stage")
        if skill.metadata.get("approval_expected") is not True:
            violations.append("run_local_change_chain approval expectation missing")
    elif skill.effect_class is not EffectClass.EXTERNAL_READ:
        violations.append(f"{expected.stage_id} skill must remain read-only")
    if not _skill_outputs_key(skill, expected.closure_evidence_key):
        violations.append(f"{expected.stage_id} closure evidence key missing")
    return tuple(violations)


def _skill_outputs_key(skill: SkillDescriptor, output_key: str) -> bool:
    return any(output_key in step.output_keys for step in skill.steps)


def _expected_local_developer_bindings() -> tuple[tuple[str, str, str, str, str], ...]:
    return (
        (
            "local_plan_to_change_chain",
            "plan_local_change",
            "code_change_plan_ref",
            "run_local_change_chain",
            "code_change_plan_ref",
        ),
        (
            "change_receipt_to_verifier",
            "run_local_change_chain",
            "change_receipt_id",
            "verify_local_receipt",
            "change_receipt_id",
        ),
        (
            "verification_to_operator_review",
            "verify_local_receipt",
            "quality_verification_plan_ref",
            "operator_review_gate",
            "verification_plan_ref",
        ),
        (
            "approval_to_pr_evidence",
            "operator_review_gate",
            "approval_decision_ref",
            "prepare_pr_evidence",
            "approval_decision_ref",
        ),
    )
