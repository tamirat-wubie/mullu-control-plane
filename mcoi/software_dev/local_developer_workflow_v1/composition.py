"""Local Developer Workflow v1 governed composition.

Purpose: compose closure planning, patch proposal, local workflow preview,
safe-action rehearsal, operator dashboard projection, causal repair, and PR
command preview halt into one governed workflow descriptor.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi_runtime workflow contracts and local workflow preview
artifact runner.
Invariants:
  - The composition coordinates existing capabilities and grants no new authority.
  - The terminal stage is a wait boundary before external PR execution.
  - File writes, branch pushes, PR creation, merge, deployment, connector calls,
    email sends, money movement, and production writes remain blocked.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from mcoi_runtime.contracts.workflow import (
    StageType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowStage,
)
from mcoi_runtime.core.workflow import WorkflowValidator

from .runner import FORBIDDEN_EFFECTS, VALIDATOR_COMMANDS, WORKFLOW_ID


COMPOSITION_WORKFLOW_ID = "mullu.local_developer_workflow.foundation_composition.v1"
COMPOSITION_CREATED_AT = "2026-07-02T00:00:00+00:00"
COMPOSITION_MODE = "foundation"
TERMINAL_WAIT_STAGE_ID = "await_external_execution_approval"
BLOCKED_EXTERNAL_EFFECTS = (
    "file_write",
    "branch_push",
    "pull_request_create",
    "merge",
    "deploy",
    "connector_call",
    "send_email",
    "move_money",
    "write_production_data",
)
_EXPECTED_STAGE_IDS = (
    "select_capability_closure_lane",
    "draft_patch_proposal",
    "assemble_local_workflow_preview",
    "rehearse_safe_local_action",
    "project_operator_dashboard",
    "classify_causal_repair",
    "operator_review_gate",
    TERMINAL_WAIT_STAGE_ID,
)


@dataclass(frozen=True, slots=True)
class WorkflowCompositionValidation:
    """Validation report for the governed local workflow composition."""

    ok: bool
    errors: tuple[str, ...]
    workflow_id: str
    stage_count: int
    binding_count: int
    terminal_stage_id: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_foundation_workflow_composition_descriptor() -> WorkflowDescriptor:
    """Return the canonical governed composition descriptor."""

    return WorkflowDescriptor(
        workflow_id=COMPOSITION_WORKFLOW_ID,
        name="Mullu Local Developer Workflow v1 Foundation Composition",
        description=(
            "Projection-only governed workflow that closes one capability-debt "
            "lane, drafts a patch proposal, builds local workflow preview "
            "artifacts, rehearses safe local action, projects the operator "
            "dashboard, classifies repair needs, and halts before external PR "
            "execution."
        ),
        stages=(
            WorkflowStage(
                stage_id="select_capability_closure_lane",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="mcoi.capability_closure.runner.v1",
                description="Choose one ranked capability-debt closure lane and emit missing evidence refs.",
                timeout_seconds=120,
            ),
            WorkflowStage(
                stage_id="draft_patch_proposal",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="software_dev.github_patch_proposal.draft",
                description="Draft patch proposal, likely files, safe diff preview, test plan, rollback plan, and risk.",
                predecessors=("select_capability_closure_lane",),
                timeout_seconds=120,
            ),
            WorkflowStage(
                stage_id="assemble_local_workflow_preview",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="software_dev.local_developer_workflow_v1.preview",
                description="Build repo status, patch-plan draft, diff proposal, test plan, receipt, approval request, and PR command preview artifacts.",
                predecessors=("draft_patch_proposal",),
                timeout_seconds=180,
            ),
            WorkflowStage(
                stage_id="rehearse_safe_local_action",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="govern.safe_local_action.rehearsal",
                description="Simulate local file, PR, merge, rollback, and connector actions without mutation.",
                predecessors=("assemble_local_workflow_preview",),
                timeout_seconds=120,
            ),
            WorkflowStage(
                stage_id="project_operator_dashboard",
                stage_type=StageType.OBSERVATION,
                description="Project task, gate, missing evidence, receipts, rollback, approval, and promotion filters.",
                predecessors=("rehearse_safe_local_action",),
                timeout_seconds=60,
            ),
            WorkflowStage(
                stage_id="classify_causal_repair",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="mcoi.causal_repair.service.v1",
                description="Classify missing evidence, failed tests, stale evidence, impossible rollback, CI failure, or unsafe browser evidence.",
                predecessors=("project_operator_dashboard",),
                timeout_seconds=120,
            ),
            WorkflowStage(
                stage_id="operator_review_gate",
                stage_type=StageType.APPROVAL_GATE,
                description="Operator reviews evidence bundle; approval is review-only and does not authorize external mutation.",
                predecessors=("classify_causal_repair",),
                timeout_seconds=86400,
            ),
            WorkflowStage(
                stage_id=TERMINAL_WAIT_STAGE_ID,
                stage_type=StageType.WAIT_FOR_EVENT,
                description="Wait for separate external execution approval before any branch push or PR creation.",
                predecessors=("operator_review_gate",),
                timeout_seconds=86400,
            ),
        ),
        bindings=(
            _binding("closure_to_patch", "select_capability_closure_lane", "closure_plan_ref", "draft_patch_proposal", "closure_plan_ref"),
            _binding("patch_to_preview", "draft_patch_proposal", "patch_proposal_ref", "assemble_local_workflow_preview", "patch_proposal_ref"),
            _binding("preview_to_rehearsal", "assemble_local_workflow_preview", "workflow_receipt_ref", "rehearse_safe_local_action", "workflow_receipt_ref"),
            _binding("rehearsal_to_dashboard", "rehearse_safe_local_action", "rehearsal_receipt_ref", "project_operator_dashboard", "safe_action_receipt_ref"),
            _binding("dashboard_to_repair", "project_operator_dashboard", "dashboard_ref", "classify_causal_repair", "dashboard_ref"),
            _binding("repair_to_review", "classify_causal_repair", "repair_receipt_ref", "operator_review_gate", "repair_receipt_ref"),
            _binding("review_to_wait", "operator_review_gate", "approval_decision_ref", TERMINAL_WAIT_STAGE_ID, "external_execution_approval_ref"),
        ),
        created_at=COMPOSITION_CREATED_AT,
    )


def build_foundation_workflow_composition_read_model(
    descriptor: WorkflowDescriptor | None = None,
) -> dict[str, Any]:
    """Return an operator-facing read model for the governed composition."""

    effective_descriptor = descriptor or build_foundation_workflow_composition_descriptor()
    validation = validate_foundation_workflow_composition(effective_descriptor)
    return {
        "read_model_id": "local_developer_workflow_v1.foundation_composition",
        "workflow_id": effective_descriptor.workflow_id,
        "base_workflow_id": WORKFLOW_ID,
        "mode": COMPOSITION_MODE,
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "grants_new_capability_authority": False,
        "terminal_closure_condition": "review_complete_then_wait_for_separate_external_execution_approval",
        "terminal_stage_id": TERMINAL_WAIT_STAGE_ID,
        "stage_count": len(effective_descriptor.stages),
        "binding_count": len(effective_descriptor.bindings),
        "blocked_external_effects": list(BLOCKED_EXTERNAL_EFFECTS),
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
        "stages": [_stage_read_model(stage) for stage in effective_descriptor.stages],
        "bindings": [_binding_read_model(binding) for binding in effective_descriptor.bindings],
        "verification": {
            "valid": validation.ok,
            "violations": list(validation.errors),
            "descriptor_validator": "mcoi_runtime.core.workflow.WorkflowValidator",
            "artifact_validators": list(VALIDATOR_COMMANDS),
        },
        "rollback": {
            "required_before_live_execution": True,
            "rollback_execution_performed": False,
            "compensation_path": "discard preview artifacts and generated receipts; no external state has changed",
        },
        "replay": {
            "deterministic_descriptor": True,
            "replay_inputs": [
                "capability_closure_plan_ref",
                "patch_proposal_ref",
                "local_workflow_receipt_ref",
                "safe_local_action_rehearsal_ref",
                "operator_dashboard_ref",
                "causal_repair_receipt_ref",
            ],
        },
    }


def validate_foundation_workflow_composition(
    descriptor: WorkflowDescriptor | None = None,
) -> WorkflowCompositionValidation:
    """Validate topology, terminal halt, and no-authority semantics."""

    effective_descriptor = descriptor or build_foundation_workflow_composition_descriptor()
    errors = list(WorkflowValidator().validate(effective_descriptor))
    stage_ids = tuple(stage.stage_id for stage in effective_descriptor.stages)
    stages_by_id = {stage.stage_id: stage for stage in effective_descriptor.stages}
    if effective_descriptor.workflow_id != COMPOSITION_WORKFLOW_ID:
        errors.append("workflow_id_mismatch")
    if stage_ids != _EXPECTED_STAGE_IDS:
        errors.append("stage_order_mismatch")
    terminal_stage = stages_by_id.get(TERMINAL_WAIT_STAGE_ID)
    if terminal_stage is None:
        errors.append("terminal_wait_stage_missing")
    elif terminal_stage.stage_type is not StageType.WAIT_FOR_EVENT:
        errors.append("terminal_stage_must_wait_for_event")
    approval_stage = stages_by_id.get("operator_review_gate")
    if approval_stage is None or approval_stage.stage_type is not StageType.APPROVAL_GATE:
        errors.append("operator_review_gate_missing")
    elif terminal_stage is not None and "operator_review_gate" not in terminal_stage.predecessors:
        errors.append("terminal_wait_must_depend_on_operator_review_gate")
    writable_stage_ids = {
        stage.stage_id
        for stage in effective_descriptor.stages
        if stage.skill_id in {"software_dev.local_developer_workflow_v1.preview", "software_dev.github_patch_proposal.draft"}
    }
    if writable_stage_ids != {"draft_patch_proposal", "assemble_local_workflow_preview"}:
        errors.append("preview_stage_skill_binding_mismatch")
    if len(effective_descriptor.bindings) != len(_EXPECTED_STAGE_IDS) - 1:
        errors.append("binding_count_mismatch")
    return WorkflowCompositionValidation(
        ok=not errors,
        errors=tuple(errors),
        workflow_id=effective_descriptor.workflow_id,
        stage_count=len(effective_descriptor.stages),
        binding_count=len(effective_descriptor.bindings),
        terminal_stage_id=TERMINAL_WAIT_STAGE_ID,
    )


def _binding(
    binding_id: str,
    source_stage_id: str,
    source_output_key: str,
    target_stage_id: str,
    target_input_key: str,
) -> WorkflowBinding:
    return WorkflowBinding(
        binding_id=binding_id,
        source_stage_id=source_stage_id,
        source_output_key=source_output_key,
        target_stage_id=target_stage_id,
        target_input_key=target_input_key,
    )


def _stage_read_model(stage: WorkflowStage) -> dict[str, Any]:
    return {
        "stage_id": stage.stage_id,
        "stage_type": stage.stage_type.value,
        "skill_id": stage.skill_id or "",
        "description": stage.description,
        "predecessors": list(stage.predecessors),
        "timeout_seconds": stage.timeout_seconds,
        "execution_performed": False,
        "external_effects_allowed": False,
        "grants_new_capability_authority": False,
    }


def _binding_read_model(binding: WorkflowBinding) -> dict[str, str]:
    return {
        "binding_id": binding.binding_id,
        "source_stage_id": binding.source_stage_id,
        "source_output_key": binding.source_output_key,
        "target_stage_id": binding.target_stage_id,
        "target_input_key": binding.target_input_key,
    }
