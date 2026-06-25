"""Purpose: compose operator requests into one governed autonomous request episode.
Governance scope: repository-local request orchestration and request-level receipts.
Dependencies: operator loop, autonomy contracts, solver outcome taxonomy, invariant helpers.
Invariants: every effect-bearing step is autonomy-admitted before dispatch; blocked
boundary actions emit receipt evidence instead of silent skips.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping

from mcoi_runtime.contracts.autonomy import (
    ActionClass,
    AutonomyDecision,
    AutonomyDecisionStatus,
)
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)

from .operator_models import OperatorRequest, OperatorRunReport


class RequestActionBoundary(StrEnum):
    """Boundary class for one request action inside an autonomous episode."""

    LOCAL_REVERSIBLE = "local_reversible"
    EXTERNAL_COMMUNICATION = "external_communication"
    APPROVAL_AUTHORITY = "approval_authority"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AutonomousRequestEpisode:
    """Input envelope for one user request mapped to governed operator steps."""

    episode_id: str
    subject_id: str
    goal_id: str
    requests: tuple[OperatorRequest, ...]
    has_approval: bool = False
    max_local_retries: int = 0
    retry_requests: Mapping[str, tuple[OperatorRequest, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_id", ensure_non_empty_text("episode_id", self.episode_id))
        object.__setattr__(self, "subject_id", ensure_non_empty_text("subject_id", self.subject_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        if not isinstance(self.requests, tuple) or not self.requests:
            raise RuntimeCoreInvariantError("requests must be a non-empty tuple")
        for request in self.requests:
            if not isinstance(request, OperatorRequest):
                raise RuntimeCoreInvariantError("requests must contain OperatorRequest values")
            if request.subject_id != self.subject_id:
                raise RuntimeCoreInvariantError("request subject_id must match episode subject_id")
            if request.goal_id != self.goal_id:
                raise RuntimeCoreInvariantError("request goal_id must match episode goal_id")
        if not isinstance(self.has_approval, bool):
            raise RuntimeCoreInvariantError("has_approval must be a bool")
        if not isinstance(self.max_local_retries, int) or self.max_local_retries < 0:
            raise RuntimeCoreInvariantError("max_local_retries must be a non-negative int")
        if not isinstance(self.retry_requests, Mapping):
            raise RuntimeCoreInvariantError("retry_requests must be a mapping")
        object.__setattr__(
            self,
            "retry_requests",
            {
                ensure_non_empty_text("request_id", request_id): _validated_retry_requests(
                    request_id=request_id,
                    retries=retries,
                    subject_id=self.subject_id,
                    goal_id=self.goal_id,
                )
                for request_id, retries in self.retry_requests.items()
            },
        )


@dataclass(frozen=True, slots=True)
class AutonomousRequestRepairReceipt:
    """Receipt for one bounded local retry or repair candidate."""

    request_id: str
    attempt_index: int
    trigger: str
    autonomy_decision_id: str
    autonomy_status: str
    dispatched: bool
    execution_id: str | None
    validation_error: str | None
    structured_error_codes: tuple[str, ...]
    receipt_ref: str

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "trigger",
            "autonomy_decision_id",
            "autonomy_status",
            "receipt_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        if not isinstance(self.attempt_index, int) or self.attempt_index < 1:
            raise RuntimeCoreInvariantError("attempt_index must be a positive int")
        if not isinstance(self.dispatched, bool):
            raise RuntimeCoreInvariantError("dispatched must be a bool")
        if self.execution_id is not None:
            object.__setattr__(
                self,
                "execution_id",
                ensure_non_empty_text("execution_id", self.execution_id),
            )
        if self.validation_error is not None:
            object.__setattr__(
                self,
                "validation_error",
                ensure_non_empty_text("validation_error", self.validation_error),
            )
        object.__setattr__(
            self,
            "structured_error_codes",
            tuple(ensure_non_empty_text("structured_error_code", code) for code in self.structured_error_codes),
        )


@dataclass(frozen=True, slots=True)
class AutonomousRequestStepReceipt:
    """Receipt for one admitted or blocked step in an autonomous request episode."""

    request_id: str
    action_class: str
    boundary: str
    autonomy_decision_id: str
    autonomy_status: str
    autonomy_reason: str
    dispatched: bool
    execution_id: str | None
    validation_error: str | None
    structured_error_codes: tuple[str, ...]
    receipt_ref: str
    attempt_count: int = 1
    retry_count: int = 0
    repair_receipts: tuple[AutonomousRequestRepairReceipt, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "action_class",
            "boundary",
            "autonomy_decision_id",
            "autonomy_status",
            "autonomy_reason",
            "receipt_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        if not isinstance(self.dispatched, bool):
            raise RuntimeCoreInvariantError("dispatched must be a bool")
        if self.execution_id is not None:
            object.__setattr__(
                self,
                "execution_id",
                ensure_non_empty_text("execution_id", self.execution_id),
            )
        if self.validation_error is not None:
            object.__setattr__(
                self,
                "validation_error",
                ensure_non_empty_text("validation_error", self.validation_error),
            )
        object.__setattr__(
            self,
            "structured_error_codes",
            tuple(ensure_non_empty_text("structured_error_code", code) for code in self.structured_error_codes),
        )
        if not isinstance(self.attempt_count, int) or self.attempt_count < 1:
            raise RuntimeCoreInvariantError("attempt_count must be a positive int")
        if not isinstance(self.retry_count, int) or self.retry_count < 0:
            raise RuntimeCoreInvariantError("retry_count must be a non-negative int")
        object.__setattr__(self, "repair_receipts", tuple(self.repair_receipts))
        if len(self.repair_receipts) != self.retry_count:
            raise RuntimeCoreInvariantError("repair_receipts length must match retry_count")


@dataclass(frozen=True, slots=True)
class AutonomousRequestEpisodeReceipt:
    """Request-level receipt emitted after all admitted steps settle or block."""

    receipt_id: str
    episode_id: str
    subject_id: str
    goal_id: str
    autonomy_mode: str
    started_at: str
    finished_at: str
    action_count: int
    dispatched_count: int
    completed_count: int
    blocked_count: int
    pending_approval_count: int
    prompt_count: int
    step_receipts: tuple[AutonomousRequestStepReceipt, ...]
    receipt_refs: tuple[str, ...]
    execution_ids: tuple[str, ...]
    validation_errors: tuple[str, ...]
    repair_attempt_count: int
    repaired_step_count: int
    repair_receipt_refs: tuple[str, ...]
    solver_outcome: str
    rollback_ref: str
    no_bypass: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "episode_id",
            "subject_id",
            "goal_id",
            "autonomy_mode",
            "started_at",
            "finished_at",
            "solver_outcome",
            "rollback_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        for field_name in (
            "action_count",
            "dispatched_count",
            "completed_count",
            "blocked_count",
            "pending_approval_count",
            "prompt_count",
            "repair_attempt_count",
            "repaired_step_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-negative int")
        if not isinstance(self.no_bypass, bool):
            raise RuntimeCoreInvariantError("no_bypass must be a bool")
        object.__setattr__(self, "step_receipts", tuple(self.step_receipts))
        if len(self.step_receipts) != self.action_count:
            raise RuntimeCoreInvariantError("step_receipts length must match action_count")
        object.__setattr__(
            self,
            "receipt_refs",
            tuple(ensure_non_empty_text("receipt_ref", ref) for ref in self.receipt_refs),
        )
        object.__setattr__(
            self,
            "execution_ids",
            tuple(ensure_non_empty_text("execution_id", value) for value in self.execution_ids),
        )
        object.__setattr__(
            self,
            "validation_errors",
            tuple(ensure_non_empty_text("validation_error", value) for value in self.validation_errors),
        )
        object.__setattr__(
            self,
            "repair_receipt_refs",
            tuple(ensure_non_empty_text("receipt_ref", value) for value in self.repair_receipt_refs),
        )


class AutonomousRequestExecutor:
    """Runs an autonomous request episode through an existing operator loop."""

    def __init__(self, operator_loop: object) -> None:
        if not hasattr(operator_loop, "run_step") or not hasattr(operator_loop, "runtime"):
            raise RuntimeCoreInvariantError("operator_loop must expose run_step and runtime")
        self._operator_loop = operator_loop

    def run_episode(self, episode: AutonomousRequestEpisode) -> AutonomousRequestEpisodeReceipt:
        """Run all admitted local steps and emit one request-level receipt."""

        started_at = self._operator_loop.runtime.clock()
        step_receipts: list[AutonomousRequestStepReceipt] = []
        run_reports: list[OperatorRunReport] = []

        for request in episode.requests:
            action_class = _action_class_for_request(request)
            boundary = _boundary_for_action_class(action_class)
            decision = self._operator_loop.runtime.autonomy.evaluate(
                action_class,
                has_approval=episode.has_approval,
                action_description=str(request.template.get("action_type", action_class.value)),
            )
            if decision.status is AutonomyDecisionStatus.ALLOWED:
                report, repair_receipts = self._run_with_local_retries(
                    request=request,
                    action_class=action_class,
                    boundary=boundary,
                    episode=episode,
                )
                run_reports.append(report)
                step_receipts.append(
                    _step_receipt_from_report(
                        request=request,
                        action_class=action_class,
                        boundary=boundary,
                        decision=decision,
                        report=report,
                        repair_receipts=repair_receipts,
                    )
                )
            else:
                step_receipts.append(
                    _blocked_step_receipt(
                        request=request,
                        action_class=action_class,
                        boundary=boundary,
                        decision=decision,
                    )
                )

        finished_at = self._operator_loop.runtime.clock()
        return _episode_receipt(
            episode=episode,
            autonomy_mode=self._operator_loop.runtime.autonomy.mode.value,
            started_at=started_at,
            finished_at=finished_at,
            step_receipts=tuple(step_receipts),
            run_reports=tuple(run_reports),
        )

    def _run_with_local_retries(
        self,
        *,
        request: OperatorRequest,
        action_class: ActionClass,
        boundary: RequestActionBoundary,
        episode: AutonomousRequestEpisode,
    ) -> tuple[OperatorRunReport, tuple[AutonomousRequestRepairReceipt, ...]]:
        report = self._operator_loop.run_step(_dispatchable_request(request))
        if not _local_retry_allowed(boundary=boundary, report=report, episode=episode):
            return report, ()

        repair_receipts: list[AutonomousRequestRepairReceipt] = []
        retry_candidates = episode.retry_requests.get(request.request_id, ())
        for retry_request in retry_candidates[: episode.max_local_retries]:
            retry_action_class = _action_class_for_request(retry_request)
            retry_boundary = _boundary_for_action_class(retry_action_class)
            retry_decision = self._operator_loop.runtime.autonomy.evaluate(
                retry_action_class,
                has_approval=episode.has_approval,
                action_description=str(retry_request.template.get("action_type", retry_action_class.value)),
            )
            if (
                retry_decision.status is not AutonomyDecisionStatus.ALLOWED
                or retry_boundary is not RequestActionBoundary.LOCAL_REVERSIBLE
            ):
                repair_receipts.append(
                    _repair_receipt_from_blocked_retry(
                        request=retry_request,
                        attempt_index=len(repair_receipts) + 1,
                        trigger=_retry_trigger(report),
                        decision=retry_decision,
                    )
                )
                break

            retry_report = self._operator_loop.run_step(_dispatchable_request(retry_request))
            repair_receipts.append(
                _repair_receipt_from_report(
                    request=retry_request,
                    attempt_index=len(repair_receipts) + 1,
                    trigger=_retry_trigger(report),
                    decision=retry_decision,
                    report=retry_report,
                )
            )
            report = retry_report
            if report.dispatched and report.validation_error is None:
                break

        return report, tuple(repair_receipts)


def run_autonomous_request_episode(
    operator_loop: object,
    episode: AutonomousRequestEpisode,
) -> AutonomousRequestEpisodeReceipt:
    """Convenience entry point for request-episode execution."""

    return AutonomousRequestExecutor(operator_loop).run_episode(episode)


def _validated_retry_requests(
    *,
    request_id: str,
    retries: tuple[OperatorRequest, ...],
    subject_id: str,
    goal_id: str,
) -> tuple[OperatorRequest, ...]:
    if not isinstance(retries, tuple):
        raise RuntimeCoreInvariantError("retry request values must be tuples")
    for retry in retries:
        if not isinstance(retry, OperatorRequest):
            raise RuntimeCoreInvariantError("retry request values must contain OperatorRequest values")
        if retry.request_id == request_id:
            raise RuntimeCoreInvariantError("retry request_id must differ from source request_id")
        if retry.subject_id != subject_id:
            raise RuntimeCoreInvariantError("retry subject_id must match episode subject_id")
        if retry.goal_id != goal_id:
            raise RuntimeCoreInvariantError("retry goal_id must match episode goal_id")
    return retries


def _action_class_for_request(request: OperatorRequest) -> ActionClass:
    explicit = request.template.get("action_class")
    if explicit is not None:
        try:
            return ActionClass(str(explicit))
        except ValueError as exc:
            raise RuntimeCoreInvariantError("action_class must be a known ActionClass value") from exc

    action_type = str(request.template.get("action_type", "")).strip().lower()
    if not action_type and request.observation_requests:
        return ActionClass.OBSERVE
    if "approve" in action_type or "approval" in action_type:
        return ActionClass.APPROVE
    if _looks_like_external_communication(action_type):
        return ActionClass.COMMUNICATE
    if action_type.endswith("_read") or action_type.startswith("read_"):
        return ActionClass.EXECUTE_READ
    return ActionClass.EXECUTE_WRITE


def _looks_like_external_communication(action_type: str) -> bool:
    markers = ("communicate", "communication", "email", "mail", "slack", "smtp", "send", "webhook")
    return any(marker in action_type for marker in markers)


def _dispatchable_request(request: OperatorRequest) -> OperatorRequest:
    if "action_class" not in request.template:
        return request
    template = dict(request.template)
    template.pop("action_class", None)
    return replace(request, template=template)


def _boundary_for_action_class(action_class: ActionClass) -> RequestActionBoundary:
    if action_class in {
        ActionClass.OBSERVE,
        ActionClass.ANALYZE,
        ActionClass.SUGGEST,
        ActionClass.PLAN,
        ActionClass.EXECUTE_READ,
        ActionClass.EXECUTE_WRITE,
    }:
        return RequestActionBoundary.LOCAL_REVERSIBLE
    if action_class is ActionClass.COMMUNICATE:
        return RequestActionBoundary.EXTERNAL_COMMUNICATION
    if action_class is ActionClass.APPROVE:
        return RequestActionBoundary.APPROVAL_AUTHORITY
    return RequestActionBoundary.REJECTED


def _step_receipt_from_report(
    *,
    request: OperatorRequest,
    action_class: ActionClass,
    boundary: RequestActionBoundary,
    decision: AutonomyDecision,
    report: OperatorRunReport,
    repair_receipts: tuple[AutonomousRequestRepairReceipt, ...],
) -> AutonomousRequestStepReceipt:
    receipt_ref = stable_identifier(
        "request-step-receipt",
        {
            "request_id": request.request_id,
            "decision_id": decision.decision_id,
            "execution_id": report.execution_id,
        },
    )
    return AutonomousRequestStepReceipt(
        request_id=request.request_id,
        action_class=action_class.value,
        boundary=boundary.value,
        autonomy_decision_id=decision.decision_id,
        autonomy_status=decision.status.value,
        autonomy_reason=decision.reason,
        dispatched=report.dispatched,
        execution_id=report.execution_id,
        validation_error=report.validation_error,
        structured_error_codes=tuple(error.error_code for error in report.structured_errors),
        receipt_ref=f"receipt://{receipt_ref}",
        attempt_count=1 + len(repair_receipts),
        retry_count=len(repair_receipts),
        repair_receipts=repair_receipts,
    )


def _local_retry_allowed(
    *,
    boundary: RequestActionBoundary,
    report: OperatorRunReport,
    episode: AutonomousRequestEpisode,
) -> bool:
    if episode.max_local_retries == 0:
        return False
    if boundary is not RequestActionBoundary.LOCAL_REVERSIBLE:
        return False
    return (not report.dispatched) or report.validation_error is not None


def _retry_trigger(report: OperatorRunReport) -> str:
    if report.validation_error:
        return report.validation_error
    if not report.dispatched:
        return "local_step_not_dispatched"
    return "local_step_requires_repair"


def _repair_receipt_from_report(
    *,
    request: OperatorRequest,
    attempt_index: int,
    trigger: str,
    decision: AutonomyDecision,
    report: OperatorRunReport,
) -> AutonomousRequestRepairReceipt:
    receipt_ref = stable_identifier(
        "request-repair-receipt",
        {
            "request_id": request.request_id,
            "attempt_index": attempt_index,
            "decision_id": decision.decision_id,
            "execution_id": report.execution_id,
            "validation_error": report.validation_error,
        },
    )
    return AutonomousRequestRepairReceipt(
        request_id=request.request_id,
        attempt_index=attempt_index,
        trigger=trigger,
        autonomy_decision_id=decision.decision_id,
        autonomy_status=decision.status.value,
        dispatched=report.dispatched,
        execution_id=report.execution_id,
        validation_error=report.validation_error,
        structured_error_codes=tuple(error.error_code for error in report.structured_errors),
        receipt_ref=f"receipt://{receipt_ref}",
    )


def _repair_receipt_from_blocked_retry(
    *,
    request: OperatorRequest,
    attempt_index: int,
    trigger: str,
    decision: AutonomyDecision,
) -> AutonomousRequestRepairReceipt:
    receipt_ref = stable_identifier(
        "request-repair-receipt",
        {
            "request_id": request.request_id,
            "attempt_index": attempt_index,
            "decision_id": decision.decision_id,
            "status": decision.status.value,
        },
    )
    return AutonomousRequestRepairReceipt(
        request_id=request.request_id,
        attempt_index=attempt_index,
        trigger=trigger,
        autonomy_decision_id=decision.decision_id,
        autonomy_status=decision.status.value,
        dispatched=False,
        execution_id=None,
        validation_error=None,
        structured_error_codes=(),
        receipt_ref=f"receipt://{receipt_ref}",
    )


def _blocked_step_receipt(
    *,
    request: OperatorRequest,
    action_class: ActionClass,
    boundary: RequestActionBoundary,
    decision: AutonomyDecision,
) -> AutonomousRequestStepReceipt:
    receipt_ref = stable_identifier(
        "request-step-receipt",
        {
            "request_id": request.request_id,
            "decision_id": decision.decision_id,
            "status": decision.status.value,
        },
    )
    return AutonomousRequestStepReceipt(
        request_id=request.request_id,
        action_class=action_class.value,
        boundary=boundary.value,
        autonomy_decision_id=decision.decision_id,
        autonomy_status=decision.status.value,
        autonomy_reason=decision.reason,
        dispatched=False,
        execution_id=None,
        validation_error=None,
        structured_error_codes=(),
        receipt_ref=f"receipt://{receipt_ref}",
    )


def _episode_receipt(
    *,
    episode: AutonomousRequestEpisode,
    autonomy_mode: str,
    started_at: str,
    finished_at: str,
    step_receipts: tuple[AutonomousRequestStepReceipt, ...],
    run_reports: tuple[OperatorRunReport, ...],
) -> AutonomousRequestEpisodeReceipt:
    pending_count = sum(
        1
        for step in step_receipts
        if step.autonomy_status == AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL.value
    )
    rejected_count = sum(
        1
        for step in step_receipts
        if step.autonomy_status == AutonomyDecisionStatus.REJECTED.value
    )
    dispatched_count = sum(1 for step in step_receipts if step.dispatched)
    completed_count = sum(1 for report in run_reports if report.completed)
    execution_ids = tuple(
        step.execution_id for step in step_receipts if step.execution_id is not None
    )
    validation_errors = tuple(
        step.validation_error for step in step_receipts if step.validation_error is not None
    )
    repair_receipt_refs = tuple(
        repair.receipt_ref
        for step in step_receipts
        for repair in step.repair_receipts
    )
    repaired_step_count = sum(
        1
        for step in step_receipts
        if step.retry_count > 0 and step.dispatched and step.validation_error is None
    )
    receipt_refs = tuple(step.receipt_ref for step in step_receipts)
    solver_outcome = _solver_outcome(
        action_count=len(step_receipts),
        dispatched_count=dispatched_count,
        completed_count=completed_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        validation_errors=validation_errors,
    )
    receipt_id = stable_identifier(
        "autonomous-request-receipt",
        {
            "episode_id": episode.episode_id,
            "receipt_refs": receipt_refs,
            "solver_outcome": solver_outcome.value,
        },
    )
    rollback_ref = (
        f"rollback://autonomous-request/{episode.episode_id}/local-effects"
        if execution_ids
        else f"rollback://autonomous-request/{episode.episode_id}/no-effects"
    )
    return AutonomousRequestEpisodeReceipt(
        receipt_id=receipt_id,
        episode_id=episode.episode_id,
        subject_id=episode.subject_id,
        goal_id=episode.goal_id,
        autonomy_mode=autonomy_mode,
        started_at=started_at,
        finished_at=finished_at,
        action_count=len(step_receipts),
        dispatched_count=dispatched_count,
        completed_count=completed_count,
        blocked_count=pending_count + rejected_count,
        pending_approval_count=pending_count,
        prompt_count=pending_count,
        step_receipts=step_receipts,
        receipt_refs=receipt_refs,
        execution_ids=execution_ids,
        validation_errors=validation_errors,
        repair_attempt_count=len(repair_receipt_refs),
        repaired_step_count=repaired_step_count,
        repair_receipt_refs=repair_receipt_refs,
        solver_outcome=solver_outcome.value,
        rollback_ref=rollback_ref,
    )


def _solver_outcome(
    *,
    action_count: int,
    dispatched_count: int,
    completed_count: int,
    pending_count: int,
    rejected_count: int,
    validation_errors: tuple[str, ...],
) -> SolverOutcome:
    if rejected_count > 0:
        return SolverOutcome.GOVERNANCE_BLOCKED
    if pending_count > 0:
        return SolverOutcome.AWAITING_EVIDENCE
    if validation_errors:
        return SolverOutcome.GOVERNANCE_BLOCKED
    if action_count > 0 and completed_count == action_count:
        return SolverOutcome.SOLVED_VERIFIED
    if dispatched_count == action_count:
        return SolverOutcome.SOLVED_UNVERIFIED
    return SolverOutcome.AWAITING_EVIDENCE


__all__ = [
    "AutonomousRequestEpisode",
    "AutonomousRequestEpisodeReceipt",
    "AutonomousRequestExecutor",
    "AutonomousRequestRepairReceipt",
    "AutonomousRequestStepReceipt",
    "RequestActionBoundary",
    "run_autonomous_request_episode",
]
