"""Operational dashboard intelligence for note-memory projections.

Purpose: expose project state, ready actions, blocked actions, blockers,
conflicts, repairs, high-intensity concepts, recent deltas, confidence trend,
workflow health, and execution readiness as a read-only dashboard model.
Governance scope: projection-only display, constructive/fracture separation,
readiness gating, repair visibility, and no execution authority.
Dependencies: dataclasses, Concept Boxes, projection, repair queue, compiled
actions, interrogation queue, simple platform checks, simple workflow plans,
simple onboarding guide, SDLC validation receipts, and runtime invariant
helpers.
Invariants: dashboard state is derived from receipts and candidates; it never
promotes truth, executes actions, claims terminal closure, or hides blockers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox
from mcoi_runtime.core.inceptadive_interrogation_queue import InterrogationTask
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_action_compiler import CompiledMemoryAction
from mcoi_runtime.core.memory_repair_queue import MemoryRepairItem
from mcoi_runtime.core.note_memory_projection import CandidateActionStatus, NoteMemoryProjection
from mcoi_runtime.core.simple_platform import (
    SimpleActionCheck,
    SimpleOnboardingGuide,
    SimplePlatform,
    SimpleWorkflowPlan,
)


class WorkflowHealth(StrEnum):
    """Operational workflow health classes."""

    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    REPAIR_REQUIRED = "repair_required"


@dataclass(frozen=True)
class DashboardSimpleActionSummary:
    """Read-only dashboard projection for one simple action check."""

    action_ref: str
    outcome: str
    status_label: str
    message: str
    risk: str
    approval_needed: bool
    evidence_saved: bool
    next_step: str
    choices: tuple[str, ...]
    audit_details_available: bool
    audit_details_visible: bool
    receipts_visible: bool
    proof_details_hidden: bool
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple action cannot allow execution")
        if self.outcome not in {"ready", "needs_review", "blocked"}:
            raise RuntimeCoreInvariantError("dashboard simple action outcome is unsupported")
        if self.status_label not in {"Ready", "Needs approval", "Blocked"}:
            raise RuntimeCoreInvariantError("dashboard simple action status label is unsupported")
        if not self.audit_details_available:
            raise RuntimeCoreInvariantError("dashboard simple action must expose audit availability")
        if self.audit_details_visible or self.receipts_visible or not self.proof_details_hidden:
            raise RuntimeCoreInvariantError("dashboard simple action cannot expose audit details by default")
        _reject_internal_dashboard_ref(self.action_ref, "dashboard simple action action_ref")
        for field_name, field_value in {
            "action_ref": self.action_ref,
            "message": self.message,
            "risk": self.risk,
            "next_step": self.next_step,
        }.items():
            if not field_value.strip():
                raise RuntimeCoreInvariantError(f"dashboard simple action {field_name} is required")
            if field_value.strip() != field_value:
                raise RuntimeCoreInvariantError(f"dashboard simple action {field_name} must be trimmed")
        if not self.choices:
            raise RuntimeCoreInvariantError("dashboard simple action choices are required")
        for choice in self.choices:
            if not choice.strip():
                raise RuntimeCoreInvariantError("dashboard simple action choice is required")
            if choice.strip() != choice:
                raise RuntimeCoreInvariantError("dashboard simple action choices must be trimmed")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple action summary."""

        return {
            "action_ref": self.action_ref,
            "outcome": self.outcome,
            "title": self.status_label,
            "status_label": self.status_label,
            "message": self.message,
            "risk": self.risk,
            "approval_needed": self.approval_needed,
            "evidence_saved": self.evidence_saved,
            "next_step": self.next_step,
            "choices": list(self.choices),
            "audit_details_available": self.audit_details_available,
            "audit_details_visible": self.audit_details_visible,
            "receipts_visible": self.receipts_visible,
            "proof_details_hidden": self.proof_details_hidden,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleWorkflowSummary:
    """Read-only dashboard projection for one simple workflow plan."""

    workflow_ref: str
    workflow: str
    label: str
    outcome: str
    title: str
    message: str
    next_step: str
    ready_count: int
    review_count: int
    blocked_count: int
    action_refs: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple workflow cannot allow execution")
        if min(self.ready_count, self.review_count, self.blocked_count) < 0:
            raise RuntimeCoreInvariantError("dashboard simple workflow counts cannot be negative")
        if self.outcome not in {"ready", "needs_review", "blocked"}:
            raise RuntimeCoreInvariantError("dashboard simple workflow outcome is unsupported")
        if self.ready_count + self.review_count + self.blocked_count != len(self.action_refs):
            raise RuntimeCoreInvariantError("dashboard simple workflow counts must match action refs")
        if self.outcome == "ready" and (self.review_count or self.blocked_count):
            raise RuntimeCoreInvariantError("dashboard simple workflow ready outcome cannot carry review or blocked counts")
        if self.outcome == "needs_review" and (self.review_count < 1 or self.blocked_count):
            raise RuntimeCoreInvariantError("dashboard simple workflow review outcome must carry review counts only")
        if self.outcome == "blocked" and self.blocked_count < 1:
            raise RuntimeCoreInvariantError("dashboard simple workflow blocked outcome must carry blocked counts")
        for action_ref in self.action_refs:
            _reject_internal_dashboard_ref(action_ref, "dashboard simple workflow action_ref")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple workflow summary."""

        return {
            "workflow_ref": self.workflow_ref,
            "workflow": self.workflow,
            "label": self.label,
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "ready_count": self.ready_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "action_refs": list(self.action_refs),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleStartGuideSummary:
    """Read-only dashboard projection for the simple onboarding guide."""

    title: str
    message: str
    recommended_commands: tuple[str, ...]
    outcomes: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple start guide cannot allow execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple start guide summary."""

        return {
            "title": self.title,
            "message": self.message,
            "recommended_commands": list(self.recommended_commands),
            "outcomes": list(self.outcomes),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleHomeAction:
    """One plain action item for the simple dashboard home."""

    action_ref: str
    label: str
    command: str
    reason: str
    outcome: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple home action cannot allow execution")
        if self.outcome not in {"ready", "needs_review", "blocked", "choose"}:
            raise RuntimeCoreInvariantError("dashboard simple home action outcome is unsupported")
        for field_name, field_value in {
            "action_ref": self.action_ref,
            "label": self.label,
            "command": self.command,
            "reason": self.reason,
        }.items():
            if not field_value.strip():
                raise RuntimeCoreInvariantError(f"dashboard simple home action {field_name} is required")
            if field_value.strip() != field_value:
                raise RuntimeCoreInvariantError(f"dashboard simple home action {field_name} must be trimmed")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible home action item."""

        return {
            "action_ref": self.action_ref,
            "label": self.label,
            "command": self.command,
            "reason": self.reason,
            "outcome": self.outcome,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleHomeSummary:
    """Compact dashboard home projection for non-technical users."""

    title: str
    message: str
    primary_command: str
    ready_workflow_count: int
    review_workflow_count: int
    blocked_workflow_count: int
    status_label: str = ""
    count_summary: str = ""
    next_action: str = ""
    action_items: tuple[DashboardSimpleHomeAction, ...] = ()
    command_guidance: tuple[str, ...] = ()
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple home cannot allow execution")
        if min(self.ready_workflow_count, self.review_workflow_count, self.blocked_workflow_count) < 0:
            raise RuntimeCoreInvariantError("dashboard simple home counts cannot be negative")
        if self.status_label and self.status_label not in {"Ready", "Needs approval", "Blocked"}:
            raise RuntimeCoreInvariantError("dashboard simple home status label is unsupported")
        if self.count_summary.strip() != self.count_summary:
            raise RuntimeCoreInvariantError("dashboard simple home count summary must be trimmed")
        if self.next_action.strip() != self.next_action:
            raise RuntimeCoreInvariantError("dashboard simple home next action must be trimmed")
        if len(self.action_items) > 3:
            raise RuntimeCoreInvariantError("dashboard simple home action items must be three or fewer")
        if any(item.execution_allowed for item in self.action_items):
            raise RuntimeCoreInvariantError("dashboard simple home action items cannot allow execution")
        if len(self.command_guidance) > 3:
            raise RuntimeCoreInvariantError("dashboard simple home command guidance must be three or fewer")
        for command in self.command_guidance:
            if not command.strip():
                raise RuntimeCoreInvariantError("dashboard simple home command guidance item is required")
            if command.strip() != command:
                raise RuntimeCoreInvariantError("dashboard simple home command guidance items must be trimmed")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple dashboard home summary."""

        status_label = self.status_label or self.title
        count_summary = self.count_summary or _home_count_summary(
            ready_count=self.ready_workflow_count,
            review_count=self.review_workflow_count,
            blocked_count=self.blocked_workflow_count,
        )
        next_action = self.next_action or _home_next_action(self.title, self.primary_command)
        command_guidance = self.command_guidance or (self.primary_command,)
        action_items = [item.to_dict() for item in self.action_items]
        return {
            "title": self.title,
            "message": self.message,
            "primary_command": self.primary_command,
            "ready_workflow_count": self.ready_workflow_count,
            "review_workflow_count": self.review_workflow_count,
            "blocked_workflow_count": self.blocked_workflow_count,
            "status_label": status_label,
            "count_summary": count_summary,
            "next_action": next_action,
            "action_items": action_items,
            "command_guidance": list(command_guidance),
            "start_here": {
                "title": "Start here",
                "status_label": status_label,
                "message": self.message,
                "count_summary": count_summary,
                "primary_command": self.primary_command,
                "next_action": next_action,
                "command_guidance": list(command_guidance),
                "action_items": action_items,
                "execution_allowed": self.execution_allowed,
            },
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSdlcReceiptSummary:
    """Read-only dashboard projection for one SDLC validation receipt."""

    receipt_ref: str
    receipt_id: str
    status: str
    valid: bool
    check_count: int
    passed_check_names: tuple[str, ...]
    failed_check_names: tuple[str, ...]
    error_count: int
    terminal_closure_required: bool
    receipt_is_not_terminal_closure: bool
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt cannot allow execution")
        if self.status not in {"passed", "failed"}:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt status is unsupported")
        if min(self.check_count, self.error_count) < 0:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt counts cannot be negative")
        if self.check_count != len(self.passed_check_names) + len(self.failed_check_names):
            raise RuntimeCoreInvariantError("dashboard SDLC receipt check count must match check names")
        if self.valid and (self.status != "passed" or self.error_count):
            raise RuntimeCoreInvariantError("dashboard SDLC receipt valid state contradicts errors")
        if self.valid and self.failed_check_names:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt valid state contradicts failed checks")
        if not self.valid and self.status != "failed":
            raise RuntimeCoreInvariantError("dashboard SDLC receipt invalid state contradicts status")
        if self.failed_check_names and self.status != "failed":
            raise RuntimeCoreInvariantError("dashboard SDLC receipt failed checks contradict status")
        if self.status == "failed" and self.valid:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt failed status contradicts valid state")
        if not self.terminal_closure_required:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt must require terminal closure")
        if not self.receipt_is_not_terminal_closure:
            raise RuntimeCoreInvariantError("dashboard SDLC receipt cannot claim terminal closure")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible SDLC receipt summary."""

        return {
            "receipt_ref": self.receipt_ref,
            "receipt_id": self.receipt_id,
            "status": self.status,
            "valid": self.valid,
            "check_count": self.check_count,
            "passed_check_names": list(self.passed_check_names),
            "failed_check_names": list(self.failed_check_names),
            "error_count": self.error_count,
            "terminal_closure_required": self.terminal_closure_required,
            "receipt_is_not_terminal_closure": self.receipt_is_not_terminal_closure,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class OperationalDashboardState:
    """Read-only operational dashboard model."""

    dashboard_id: str
    projection_id: str
    active_project_count: int
    ready_action_ids: tuple[str, ...]
    blocked_action_ids: tuple[str, ...]
    open_blocker_ids: tuple[str, ...]
    open_conflict_ids: tuple[str, ...]
    repair_ids: tuple[str, ...]
    stale_high_impact_claim_ids: tuple[str, ...]
    high_intensity_box_ids: tuple[str, ...]
    constructive_delta_ids: tuple[str, ...]
    fracture_delta_ids: tuple[str, ...]
    memory_confidence_trend: float
    workflow_health: WorkflowHealth
    execution_readiness: str
    interrogation_task_ids: tuple[str, ...]
    simple_action_summaries: tuple[DashboardSimpleActionSummary, ...] = ()
    simple_workflow_summaries: tuple[DashboardSimpleWorkflowSummary, ...] = ()
    simple_start_guide: DashboardSimpleStartGuideSummary | None = None
    simple_home_summary: DashboardSimpleHomeSummary | None = None
    simple_ready_action_refs: tuple[str, ...] = ()
    simple_review_action_refs: tuple[str, ...] = ()
    simple_blocked_action_refs: tuple[str, ...] = ()
    simple_ready_workflow_refs: tuple[str, ...] = ()
    simple_review_workflow_refs: tuple[str, ...] = ()
    simple_blocked_workflow_refs: tuple[str, ...] = ()
    sdlc_receipt_summaries: tuple[DashboardSdlcReceiptSummary, ...] = ()
    sdlc_passed_receipt_refs: tuple[str, ...] = ()
    sdlc_failed_receipt_refs: tuple[str, ...] = ()
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard state cannot allow execution")
        if not 0.0 <= self.memory_confidence_trend <= 1.0:
            raise RuntimeCoreInvariantError("memory_confidence_trend must be in [0,1]")
        if any(summary.execution_allowed for summary in self.sdlc_receipt_summaries):
            raise RuntimeCoreInvariantError("dashboard state cannot expose executable SDLC receipt")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible dashboard state."""

        return {
            "dashboard_id": self.dashboard_id,
            "projection_id": self.projection_id,
            "active_project_count": self.active_project_count,
            "ready_action_ids": list(self.ready_action_ids),
            "blocked_action_ids": list(self.blocked_action_ids),
            "open_blocker_ids": list(self.open_blocker_ids),
            "open_conflict_ids": list(self.open_conflict_ids),
            "repair_ids": list(self.repair_ids),
            "stale_high_impact_claim_ids": list(self.stale_high_impact_claim_ids),
            "high_intensity_box_ids": list(self.high_intensity_box_ids),
            "constructive_delta_ids": list(self.constructive_delta_ids),
            "fracture_delta_ids": list(self.fracture_delta_ids),
            "memory_confidence_trend": self.memory_confidence_trend,
            "workflow_health": self.workflow_health.value,
            "execution_readiness": self.execution_readiness,
            "interrogation_task_ids": list(self.interrogation_task_ids),
            "simple_action_summaries": [summary.to_dict() for summary in self.simple_action_summaries],
            "simple_workflow_summaries": [summary.to_dict() for summary in self.simple_workflow_summaries],
            "simple_start_guide": self.simple_start_guide.to_dict() if self.simple_start_guide else None,
            "simple_home_summary": self.simple_home_summary.to_dict() if self.simple_home_summary else None,
            "simple_ready_action_refs": list(self.simple_ready_action_refs),
            "simple_review_action_refs": list(self.simple_review_action_refs),
            "simple_blocked_action_refs": list(self.simple_blocked_action_refs),
            "simple_ready_workflow_refs": list(self.simple_ready_workflow_refs),
            "simple_review_workflow_refs": list(self.simple_review_workflow_refs),
            "simple_blocked_workflow_refs": list(self.simple_blocked_workflow_refs),
            "sdlc_receipt_summaries": [summary.to_dict() for summary in self.sdlc_receipt_summaries],
            "sdlc_passed_receipt_refs": list(self.sdlc_passed_receipt_refs),
            "sdlc_failed_receipt_refs": list(self.sdlc_failed_receipt_refs),
            "execution_allowed": self.execution_allowed,
        }


def build_operational_dashboard_state(
    *,
    projection: NoteMemoryProjection,
    boxes: Sequence[ConceptBox] = (),
    repair_items: Sequence[MemoryRepairItem] = (),
    compiled_actions: Sequence[CompiledMemoryAction] = (),
    interrogation_tasks: Sequence[InterrogationTask] = (),
    simple_action_checks: Sequence[SimpleActionCheck] = (),
    simple_workflow_plans: Sequence[SimpleWorkflowPlan] = (),
    simple_start_guide: SimpleOnboardingGuide | None = None,
    sdlc_validation_receipts: Sequence[Mapping[str, Any]] = (),
) -> OperationalDashboardState:
    """Build a read-only dashboard state from projection and candidates."""

    ready_action_ids = tuple(
        action.compiled_action_id
        for action in compiled_actions
        if action.status == CandidateActionStatus.READY_FOR_GOVERNANCE
    )
    blocked_action_ids = tuple(
        action.compiled_action_id
        for action in compiled_actions
        if action.status in {CandidateActionStatus.BLOCKED, CandidateActionStatus.REPAIR_REQUIRED}
    )
    high_intensity_box_ids = tuple(box.box_id for box in boxes if box.risk_facets)
    active_project_count = len(
        {
            box.box_id
            for box in boxes
            if box.box_type.value == "project" and any(note_id in _active_note_ids(projection) for note_id in box.source_note_ids)
        }
    )
    confidence_values = tuple(claim.confidence for claim in projection.active_claims)
    confidence_trend = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    simple_action_summaries = tuple(_simple_action_summary(check) for check in simple_action_checks)
    simple_workflow_summaries = tuple(_simple_workflow_summary(plan) for plan in simple_workflow_plans)
    simple_start_guide_summary = _simple_start_guide_summary(simple_start_guide) if simple_start_guide else None
    sdlc_receipt_summaries = tuple(_sdlc_receipt_summary(receipt) for receipt in sdlc_validation_receipts)
    simple_home_summary = _simple_home_summary(
        simple_workflow_summaries=simple_workflow_summaries,
        simple_start_guide=simple_start_guide_summary,
    )
    workflow_health = _workflow_health(projection, repair_items, blocked_action_ids)
    readiness = _execution_readiness(workflow_health, ready_action_ids, blocked_action_ids)
    dashboard_id = stable_identifier(
        "operational-dashboard",
        {
            "projection_id": projection.projection_id,
            "repair_ids": tuple(repair.repair_id for repair in repair_items),
            "compiled_action_ids": tuple(action.compiled_action_id for action in compiled_actions),
            "interrogation_task_ids": tuple(task.task_id for task in interrogation_tasks),
            "simple_action_refs": tuple(summary.action_ref for summary in simple_action_summaries),
            "simple_workflow_refs": tuple(summary.workflow_ref for summary in simple_workflow_summaries),
            "simple_start_guide": simple_start_guide_summary.to_dict() if simple_start_guide_summary else None,
            "simple_home_summary": simple_home_summary.to_dict() if simple_home_summary else None,
            "sdlc_receipt_refs": tuple(summary.receipt_ref for summary in sdlc_receipt_summaries),
        },
    )
    return OperationalDashboardState(
        dashboard_id=dashboard_id,
        projection_id=projection.projection_id,
        active_project_count=active_project_count,
        ready_action_ids=ready_action_ids,
        blocked_action_ids=blocked_action_ids,
        open_blocker_ids=tuple(blocker.blocker_id for blocker in projection.blockers),
        open_conflict_ids=tuple(conflict.conflict_id for conflict in projection.conflict_clusters),
        repair_ids=tuple(repair.repair_id for repair in repair_items),
        stale_high_impact_claim_ids=tuple(
            claim.claim_id
            for claim in projection.inactive_claims
            if any(marker in claim.claim_text.lower() for marker in ("deploy", "security", "risk", "blocked"))
        ),
        high_intensity_box_ids=high_intensity_box_ids,
        constructive_delta_ids=projection.constructive_delta_ids,
        fracture_delta_ids=projection.fracture_delta_ids,
        memory_confidence_trend=confidence_trend,
        workflow_health=workflow_health,
        execution_readiness=readiness,
        interrogation_task_ids=tuple(task.task_id for task in interrogation_tasks),
        simple_action_summaries=simple_action_summaries,
        simple_workflow_summaries=simple_workflow_summaries,
        simple_start_guide=simple_start_guide_summary,
        simple_home_summary=simple_home_summary,
        simple_ready_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "ready"
        ),
        simple_review_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "needs_review"
        ),
        simple_blocked_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "blocked"
        ),
        simple_ready_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "ready"
        ),
        simple_review_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "needs_review"
        ),
        simple_blocked_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "blocked"
        ),
        sdlc_receipt_summaries=sdlc_receipt_summaries,
        sdlc_passed_receipt_refs=tuple(
            summary.receipt_ref for summary in sdlc_receipt_summaries if summary.status == "passed"
        ),
        sdlc_failed_receipt_refs=tuple(
            summary.receipt_ref for summary in sdlc_receipt_summaries if summary.status == "failed"
        ),
    )


def _simple_action_summary(check: SimpleActionCheck) -> DashboardSimpleActionSummary:
    """Project one simple action check into dashboard display state."""

    experience = SimplePlatform.action_experience(check)
    return DashboardSimpleActionSummary(
        action_ref=_dashboard_simple_action_ref(check),
        outcome=experience.outcome,
        status_label=experience.status_label,
        message=experience.message,
        risk=experience.risk,
        approval_needed=experience.approval_needed,
        evidence_saved=experience.evidence_saved,
        next_step=experience.next_step,
        choices=experience.choices,
        audit_details_available=experience.audit_details_available,
        audit_details_visible=experience.audit_details_visible,
        receipts_visible=experience.receipts_visible,
        proof_details_hidden=experience.proof_details_hidden,
    )


def _simple_workflow_summary(plan: SimpleWorkflowPlan) -> DashboardSimpleWorkflowSummary:
    """Project one simple workflow plan into dashboard display state."""

    action_refs = tuple(_dashboard_simple_action_ref(check) for check in plan.checks)
    workflow_ref = stable_identifier(
        "dashboard-simple-workflow",
        {
            "workflow": plan.workflow,
            "action_refs": action_refs,
            "outcome": plan.outcome,
        },
    )
    return DashboardSimpleWorkflowSummary(
        workflow_ref=workflow_ref,
        workflow=plan.workflow,
        label=plan.label,
        outcome=plan.outcome,
        title=plan.title,
        message=plan.message,
        next_step=plan.next_step,
        ready_count=plan.ready_count,
        review_count=plan.review_count,
        blocked_count=plan.blocked_count,
        action_refs=action_refs,
    )


def _dashboard_simple_action_ref(check: SimpleActionCheck) -> str:
    """Return a dashboard-local action ref without exposing governance ids."""

    return stable_identifier(
        "dashboard-simple-action",
        {
            "decision_ref": check.decision_ref,
            "outcome": check.outcome,
        },
    )


def _reject_internal_dashboard_ref(value: str, field_name: str) -> None:
    """Reject proof-bearing refs from normal dashboard projections."""

    if value.startswith(("gate-decision-", "proof-", "witness-")):
        raise RuntimeCoreInvariantError(f"{field_name} cannot expose internal governance refs")


def _simple_start_guide_summary(guide: SimpleOnboardingGuide) -> DashboardSimpleStartGuideSummary:
    """Project the simple onboarding guide into dashboard display state."""

    return DashboardSimpleStartGuideSummary(
        title=guide.title,
        message=guide.message,
        recommended_commands=tuple(step.command for step in guide.recommended_path),
        outcomes=guide.outcomes,
    )


def _sdlc_receipt_summary(receipt: Mapping[str, Any]) -> DashboardSdlcReceiptSummary:
    """Project one SDLC validation receipt into dashboard display state."""

    if not isinstance(receipt, Mapping):
        raise RuntimeCoreInvariantError("dashboard SDLC receipt must be a mapping")
    receipt_id = _required_text(receipt, "receipt_id")
    status = _required_text(receipt, "status")
    valid = _required_bool(receipt, "valid")
    check_count = _required_int(receipt, "check_count")
    error_count = _required_int(receipt, "error_count")
    terminal_closure_required = _required_bool(receipt, "terminal_closure_required")
    receipt_is_not_terminal_closure = _required_bool(receipt, "receipt_is_not_terminal_closure")
    checks = receipt.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        raise RuntimeCoreInvariantError("dashboard SDLC receipt checks must be a sequence")
    errors = receipt.get("errors")
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes)):
        raise RuntimeCoreInvariantError("dashboard SDLC receipt errors must be a sequence")
    if error_count != len(errors):
        raise RuntimeCoreInvariantError("dashboard SDLC receipt error count must match errors")
    passed_check_names: list[str] = []
    failed_check_names: list[str] = []
    for index, check in enumerate(checks):
        if not isinstance(check, Mapping):
            raise RuntimeCoreInvariantError("dashboard SDLC receipt check must be a mapping")
        check_name = _required_text(check, "name")
        check_passed = _required_bool(check, "passed")
        if check_passed:
            passed_check_names.append(check_name)
        else:
            failed_check_names.append(check_name)
        if check_name.strip() != check_name:
            raise RuntimeCoreInvariantError(f"dashboard SDLC receipt check {index} name must be trimmed")
    receipt_ref = stable_identifier(
        "dashboard-sdlc-receipt",
        {
            "receipt_id": receipt_id,
            "status": status,
            "valid": valid,
            "check_count": check_count,
            "error_count": error_count,
            "passed_check_names": tuple(passed_check_names),
            "failed_check_names": tuple(failed_check_names),
        },
    )
    return DashboardSdlcReceiptSummary(
        receipt_ref=receipt_ref,
        receipt_id=receipt_id,
        status=status,
        valid=valid,
        check_count=check_count,
        passed_check_names=tuple(passed_check_names),
        failed_check_names=tuple(failed_check_names),
        error_count=error_count,
        terminal_closure_required=terminal_closure_required,
        receipt_is_not_terminal_closure=receipt_is_not_terminal_closure,
    )


def _simple_home_summary(
    *,
    simple_workflow_summaries: Sequence[DashboardSimpleWorkflowSummary],
    simple_start_guide: DashboardSimpleStartGuideSummary | None,
) -> DashboardSimpleHomeSummary | None:
    """Build a compact dashboard home summary from simple projections."""

    if not simple_workflow_summaries and simple_start_guide is None:
        return None
    ready_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "ready")
    review_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "needs_review")
    blocked_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "blocked")
    primary_command = (
        simple_start_guide.recommended_commands[0]
        if simple_start_guide and simple_start_guide.recommended_commands
        else "mullu start"
    )
    command_guidance = _home_command_guidance(primary_command, simple_start_guide)
    if blocked_count:
        action_items = _home_action_items(
            title="Blocked",
            primary_command=primary_command,
            simple_workflow_summaries=simple_workflow_summaries,
            simple_start_guide=simple_start_guide,
        )
        return DashboardSimpleHomeSummary(
            title="Blocked",
            message="Some workflows need a narrower target before users continue.",
            primary_command=primary_command,
            ready_workflow_count=ready_count,
            review_workflow_count=review_count,
            blocked_workflow_count=blocked_count,
            status_label="Blocked",
            count_summary=_home_count_summary(
                ready_count=ready_count,
                review_count=review_count,
                blocked_count=blocked_count,
            ),
            next_action=_home_next_action("Blocked", primary_command),
            action_items=action_items,
            command_guidance=command_guidance,
        )
    if review_count:
        action_items = _home_action_items(
            title="Needs approval",
            primary_command=primary_command,
            simple_workflow_summaries=simple_workflow_summaries,
            simple_start_guide=simple_start_guide,
        )
        return DashboardSimpleHomeSummary(
            title="Needs approval",
            message="Some workflows need approval before users continue.",
            primary_command=primary_command,
            ready_workflow_count=ready_count,
            review_workflow_count=review_count,
            blocked_workflow_count=blocked_count,
            status_label="Needs approval",
            count_summary=_home_count_summary(
                ready_count=ready_count,
                review_count=review_count,
                blocked_count=blocked_count,
            ),
            next_action=_home_next_action("Needs approval", primary_command),
            action_items=action_items,
            command_guidance=command_guidance,
        )
    action_items = _home_action_items(
        title="Ready",
        primary_command=primary_command,
        simple_workflow_summaries=simple_workflow_summaries,
        simple_start_guide=simple_start_guide,
    )
    return DashboardSimpleHomeSummary(
        title="Ready",
        message="Users can start with the recommended simple workflow path.",
        primary_command=primary_command,
        ready_workflow_count=ready_count,
        review_workflow_count=review_count,
        blocked_workflow_count=blocked_count,
        status_label="Ready",
        count_summary=_home_count_summary(
            ready_count=ready_count,
            review_count=review_count,
            blocked_count=blocked_count,
        ),
        next_action=_home_next_action("Ready", primary_command),
        action_items=action_items,
        command_guidance=command_guidance,
    )


def _home_count_summary(*, ready_count: int, review_count: int, blocked_count: int) -> str:
    """Return compact count text for dashboard home cards."""

    return f"{ready_count} ready, {review_count} need approval, {blocked_count} blocked"


def _home_next_action(title: str, primary_command: str) -> str:
    """Return the next plain user action for the dashboard home card."""

    if title == "Blocked":
        return "Open the blocked workflows and choose a narrower target."
    if title == "Needs approval":
        return "Review the workflows that need approval before continuing."
    return f"Start with `{primary_command}`."


def _home_action_items(
    *,
    title: str,
    primary_command: str,
    simple_workflow_summaries: Sequence[DashboardSimpleWorkflowSummary],
    simple_start_guide: DashboardSimpleStartGuideSummary | None,
) -> tuple[DashboardSimpleHomeAction, ...]:
    """Return a bounded plain action list for the dashboard home."""

    if title == "Blocked":
        selected_workflows = tuple(summary for summary in simple_workflow_summaries if summary.outcome == "blocked")
        return tuple(
            _home_workflow_action(summary, label_prefix="Fix", command=primary_command)
            for summary in selected_workflows[:3]
        )
    if title == "Needs approval":
        selected_workflows = tuple(summary for summary in simple_workflow_summaries if summary.outcome == "needs_review")
        return tuple(
            _home_workflow_action(summary, label_prefix="Review", command=primary_command)
            for summary in selected_workflows[:3]
        )
    selected_workflows = tuple(summary for summary in simple_workflow_summaries if summary.outcome == "ready")
    if selected_workflows:
        return tuple(
            _home_workflow_action(summary, label_prefix="Start", command=primary_command)
            for summary in selected_workflows[:3]
        )
    if simple_start_guide is None:
        return ()
    return (
        DashboardSimpleHomeAction(
            action_ref=stable_identifier(
                "dashboard-home-action",
                {"command": primary_command, "outcome": "choose"},
            ),
            label="Open the simple menu",
            command=primary_command,
            reason=simple_start_guide.message,
            outcome="choose",
        ),
    )


def _home_command_guidance(
    primary_command: str,
    simple_start_guide: DashboardSimpleStartGuideSummary | None,
) -> tuple[str, ...]:
    """Return a short command path for the dashboard start-here block."""

    commands: list[str] = [primary_command]
    if simple_start_guide is not None:
        for command in simple_start_guide.recommended_commands:
            if command not in commands:
                commands.append(command)
            if len(commands) == 3:
                break
    return tuple(commands[:3])


def _home_workflow_action(
    summary: DashboardSimpleWorkflowSummary,
    *,
    label_prefix: str,
    command: str,
) -> DashboardSimpleHomeAction:
    """Project one workflow summary into a plain home action item."""

    return DashboardSimpleHomeAction(
        action_ref=stable_identifier(
            "dashboard-home-action",
            {"workflow_ref": summary.workflow_ref, "outcome": summary.outcome},
        ),
        label=f"{label_prefix} {summary.label}",
        command=command,
        reason=summary.next_step,
        outcome=summary.outcome,
    )


def _workflow_health(
    projection: NoteMemoryProjection,
    repair_items: Sequence[MemoryRepairItem],
    blocked_action_ids: Sequence[str],
) -> WorkflowHealth:
    if projection.conflict_clusters or repair_items:
        return WorkflowHealth.REPAIR_REQUIRED
    if projection.blockers or blocked_action_ids:
        return WorkflowHealth.BLOCKED
    if projection.fracture_delta_ids:
        return WorkflowHealth.DEGRADED
    return WorkflowHealth.READY


def _execution_readiness(
    workflow_health: WorkflowHealth,
    ready_action_ids: Sequence[str],
    blocked_action_ids: Sequence[str],
) -> str:
    if workflow_health in {WorkflowHealth.REPAIR_REQUIRED, WorkflowHealth.BLOCKED}:
        return "not_ready_governance_review_required"
    if ready_action_ids and not blocked_action_ids:
        return "candidate_ready_for_mullu_governance_verdict"
    return "no_action_candidate_ready"


def _required_text(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"dashboard SDLC receipt {field_name} must be a non-empty string")
    if value.strip() != value:
        raise RuntimeCoreInvariantError(f"dashboard SDLC receipt {field_name} must be trimmed")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise RuntimeCoreInvariantError(f"dashboard SDLC receipt {field_name} must be a boolean")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeCoreInvariantError(f"dashboard SDLC receipt {field_name} must be an integer")
    return value


def _active_note_ids(projection: NoteMemoryProjection) -> set[str]:
    return {claim.note_id for claim in projection.active_claims}
