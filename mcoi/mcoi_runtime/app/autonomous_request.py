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
from mcoi_runtime.core.planning_boundary import PlanningKnowledge

from .operator_models import OperatorRequest, OperatorRunReport


class RequestActionBoundary(StrEnum):
    """Boundary class for one request action inside an autonomous episode."""

    LOCAL_REVERSIBLE = "local_reversible"
    EXTERNAL_COMMUNICATION = "external_communication"
    APPROVAL_AUTHORITY = "approval_authority"
    REJECTED = "rejected"


class AutonomousRequestAutomationState(StrEnum):
    """Continuation state derived from an autonomous request episode receipt."""

    SETTLED_WITHOUT_PROMPT = "settled_without_prompt"
    AWAITING_APPROVAL = "awaiting_approval"
    GOVERNANCE_BLOCKED = "governance_blocked"
    AWAITING_EVIDENCE = "awaiting_evidence"


@dataclass(frozen=True, slots=True)
class AutonomousRequestPlanStep:
    """One planned request stage inside an autonomous request episode."""

    stage_id: str
    request: OperatorRequest
    predecessors: tuple[str, ...] = ()
    verification_keys: tuple[str, ...] = ("operator_run_report",)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", ensure_non_empty_text("stage_id", self.stage_id))
        if not isinstance(self.request, OperatorRequest):
            raise RuntimeCoreInvariantError("plan step request must be an OperatorRequest")
        object.__setattr__(
            self,
            "predecessors",
            tuple(ensure_non_empty_text("predecessor", value) for value in self.predecessors),
        )
        if self.stage_id in self.predecessors:
            raise RuntimeCoreInvariantError("plan step cannot depend on itself")
        object.__setattr__(
            self,
            "verification_keys",
            tuple(ensure_non_empty_text("verification_key", value) for value in self.verification_keys),
        )
        if not self.verification_keys:
            raise RuntimeCoreInvariantError("plan step verification_keys must be non-empty")


@dataclass(frozen=True, slots=True)
class AutonomousRequestPlan:
    """Validated directed acyclic plan over local operator requests."""

    plan_id: str
    steps: tuple[AutonomousRequestPlanStep, ...]
    terminal_condition: str = "all planned stages settled or blocked with receipts"

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", ensure_non_empty_text("plan_id", self.plan_id))
        if not isinstance(self.steps, tuple) or not self.steps:
            raise RuntimeCoreInvariantError("plan steps must be a non-empty tuple")
        for step in self.steps:
            if not isinstance(step, AutonomousRequestPlanStep):
                raise RuntimeCoreInvariantError("plan steps must contain AutonomousRequestPlanStep values")
        object.__setattr__(
            self,
            "terminal_condition",
            ensure_non_empty_text("terminal_condition", self.terminal_condition),
        )
        object.__setattr__(self, "steps", _ordered_plan_steps(self.steps))

    @property
    def requests(self) -> tuple[OperatorRequest, ...]:
        """Return planned requests in validated execution order."""

        return tuple(step.request for step in self.steps)


@dataclass(frozen=True, slots=True)
class AutonomousRequestCapabilityMetadata:
    """Capability metadata used to compile request plans deterministically."""

    capability_id: str
    template: Mapping[str, object]
    default_bindings: Mapping[str, str] = field(default_factory=dict)
    predecessor_capability_ids: tuple[str, ...] = ()
    verification_keys: tuple[str, ...] = ("operator_run_report",)
    knowledge_entries: tuple[PlanningKnowledge, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not isinstance(self.template, Mapping):
            raise RuntimeCoreInvariantError("capability template must be a mapping")
        for field_name in ("template_id", "action_type"):
            ensure_non_empty_text(field_name, self.template.get(field_name, ""))
        object.__setattr__(
            self,
            "default_bindings",
            _validated_text_mapping("default_bindings", self.default_bindings),
        )
        object.__setattr__(
            self,
            "predecessor_capability_ids",
            tuple(
                ensure_non_empty_text("predecessor_capability_id", value)
                for value in self.predecessor_capability_ids
            ),
        )
        if self.capability_id in self.predecessor_capability_ids:
            raise RuntimeCoreInvariantError("capability cannot depend on itself")
        object.__setattr__(
            self,
            "verification_keys",
            tuple(ensure_non_empty_text("verification_key", value) for value in self.verification_keys),
        )
        if not self.verification_keys:
            raise RuntimeCoreInvariantError("capability verification_keys must be non-empty")
        if not isinstance(self.knowledge_entries, tuple):
            raise RuntimeCoreInvariantError("capability knowledge_entries must be a tuple")
        for entry in self.knowledge_entries:
            if not isinstance(entry, PlanningKnowledge):
                raise RuntimeCoreInvariantError("capability knowledge_entries must contain PlanningKnowledge values")


@dataclass(frozen=True, slots=True)
class AutonomousRequestIntent:
    """Raw operator intent for deterministic capability-plan compilation."""

    episode_id: str
    subject_id: str
    goal_id: str
    capability_ids: tuple[str, ...]
    bindings: Mapping[str, str] = field(default_factory=dict)
    has_approval: bool = False
    max_local_retries: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_id", ensure_non_empty_text("episode_id", self.episode_id))
        object.__setattr__(self, "subject_id", ensure_non_empty_text("subject_id", self.subject_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        if not isinstance(self.capability_ids, tuple) or not self.capability_ids:
            raise RuntimeCoreInvariantError("intent capability_ids must be a non-empty tuple")
        normalized_capability_ids = tuple(
            ensure_non_empty_text("capability_id", capability_id)
            for capability_id in self.capability_ids
        )
        if len(set(normalized_capability_ids)) != len(normalized_capability_ids):
            raise RuntimeCoreInvariantError("intent capability_ids must be unique")
        object.__setattr__(self, "capability_ids", normalized_capability_ids)
        object.__setattr__(self, "bindings", _validated_text_mapping("bindings", self.bindings))
        if not isinstance(self.has_approval, bool):
            raise RuntimeCoreInvariantError("has_approval must be a bool")
        if not isinstance(self.max_local_retries, int) or self.max_local_retries < 0:
            raise RuntimeCoreInvariantError("max_local_retries must be a non-negative int")


class AutonomousRequestPlanCompiler:
    """Compiles capability metadata and raw intent into an executable episode."""

    def __init__(self, capability_catalog: Mapping[str, AutonomousRequestCapabilityMetadata]) -> None:
        if not isinstance(capability_catalog, Mapping) or not capability_catalog:
            raise RuntimeCoreInvariantError("capability_catalog must be a non-empty mapping")
        normalized_catalog: dict[str, AutonomousRequestCapabilityMetadata] = {}
        for capability_id, metadata in capability_catalog.items():
            normalized_capability_id = ensure_non_empty_text("capability_id", capability_id)
            if not isinstance(metadata, AutonomousRequestCapabilityMetadata):
                raise RuntimeCoreInvariantError(
                    "capability_catalog values must be AutonomousRequestCapabilityMetadata"
                )
            if metadata.capability_id != normalized_capability_id:
                raise RuntimeCoreInvariantError("capability_catalog key must match metadata capability_id")
            normalized_catalog[normalized_capability_id] = metadata
        self._capability_catalog = normalized_catalog

    def compile_episode(self, intent: AutonomousRequestIntent) -> AutonomousRequestEpisode:
        """Compile an intent to a validated episode with expanded dependencies."""

        if not isinstance(intent, AutonomousRequestIntent):
            raise RuntimeCoreInvariantError("intent must be an AutonomousRequestIntent")
        ordered_capability_ids = self._expanded_capability_ids(intent.capability_ids)
        plan = AutonomousRequestPlan(
            plan_id=stable_identifier(
                "autonomous-request-plan",
                {
                    "episode_id": intent.episode_id,
                    "capability_ids": ordered_capability_ids,
                },
            ),
            steps=tuple(
                self._plan_step_for_capability(
                    capability_id=capability_id,
                    intent=intent,
                )
                for capability_id in ordered_capability_ids
            ),
        )
        return AutonomousRequestEpisode.from_plan(
            episode_id=intent.episode_id,
            subject_id=intent.subject_id,
            goal_id=intent.goal_id,
            plan=plan,
            has_approval=intent.has_approval,
            max_local_retries=intent.max_local_retries,
        )

    def _expanded_capability_ids(
        self,
        requested_capability_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(capability_id: str) -> None:
            metadata = self._capability_catalog.get(capability_id)
            if metadata is None:
                raise RuntimeCoreInvariantError("requested capability is not registered")
            if capability_id in visited:
                return
            if capability_id in visiting:
                raise RuntimeCoreInvariantError("capability dependency graph must not contain cycles")
            visiting.add(capability_id)
            for predecessor_id in metadata.predecessor_capability_ids:
                if predecessor_id not in self._capability_catalog:
                    raise RuntimeCoreInvariantError("capability predecessor is not registered")
                visit(predecessor_id)
            visiting.remove(capability_id)
            visited.add(capability_id)
            ordered.append(capability_id)

        for capability_id in requested_capability_ids:
            visit(capability_id)
        return tuple(ordered)

    def _plan_step_for_capability(
        self,
        *,
        capability_id: str,
        intent: AutonomousRequestIntent,
    ) -> AutonomousRequestPlanStep:
        metadata = self._capability_catalog[capability_id]
        required_parameters = _required_parameter_names(metadata.template)
        bindings = dict(metadata.default_bindings)
        for parameter in required_parameters:
            if parameter in intent.bindings:
                bindings[parameter] = intent.bindings[parameter]
        missing_bindings = tuple(
            parameter
            for parameter in required_parameters
            if parameter not in bindings
        )
        if missing_bindings:
            raise RuntimeCoreInvariantError("capability required bindings are missing")
        request = OperatorRequest(
            request_id=stable_identifier(
                "autonomous-request",
                {
                    "episode_id": intent.episode_id,
                    "capability_id": capability_id,
                },
            ),
            subject_id=intent.subject_id,
            goal_id=intent.goal_id,
            template=dict(metadata.template),
            bindings=bindings,
            knowledge_entries=metadata.knowledge_entries,
        )
        _action_class_for_request(request)
        return AutonomousRequestPlanStep(
            stage_id=_stage_id_for_capability(capability_id),
            request=request,
            predecessors=tuple(
                _stage_id_for_capability(predecessor_id)
                for predecessor_id in metadata.predecessor_capability_ids
            ),
            verification_keys=metadata.verification_keys,
        )


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
    plan: AutonomousRequestPlan | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_id", ensure_non_empty_text("episode_id", self.episode_id))
        object.__setattr__(self, "subject_id", ensure_non_empty_text("subject_id", self.subject_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        if not isinstance(self.requests, tuple) or not self.requests:
            raise RuntimeCoreInvariantError("requests must be a non-empty tuple")
        if self.plan is not None:
            if not isinstance(self.plan, AutonomousRequestPlan):
                raise RuntimeCoreInvariantError("plan must be an AutonomousRequestPlan")
            if self.requests != self.plan.requests:
                raise RuntimeCoreInvariantError("episode requests must match plan execution order")
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

    @classmethod
    def from_plan(
        cls,
        *,
        episode_id: str,
        subject_id: str,
        goal_id: str,
        plan: AutonomousRequestPlan,
        has_approval: bool = False,
        max_local_retries: int = 0,
        retry_requests: Mapping[str, tuple[OperatorRequest, ...]] | None = None,
    ) -> "AutonomousRequestEpisode":
        """Build an episode from a validated plan without duplicating request order."""

        return cls(
            episode_id=episode_id,
            subject_id=subject_id,
            goal_id=goal_id,
            requests=plan.requests,
            plan=plan,
            has_approval=has_approval,
            max_local_retries=max_local_retries,
            retry_requests={} if retry_requests is None else retry_requests,
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
    plan_id: str | None = None
    plan_stage_id: str | None = None
    plan_predecessors: tuple[str, ...] = ()

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
        if self.plan_id is not None:
            object.__setattr__(self, "plan_id", ensure_non_empty_text("plan_id", self.plan_id))
        if self.plan_stage_id is not None:
            object.__setattr__(
                self,
                "plan_stage_id",
                ensure_non_empty_text("plan_stage_id", self.plan_stage_id),
            )
        object.__setattr__(
            self,
            "plan_predecessors",
            tuple(ensure_non_empty_text("plan_predecessor", value) for value in self.plan_predecessors),
        )


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
    plan_id: str | None = None
    planned_stage_count: int = 0
    blocked_dependency_count: int = 0
    plan_receipt_ref: str | None = None
    automation_state: str = AutonomousRequestAutomationState.AWAITING_EVIDENCE.value

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
            "automation_state",
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
            "planned_stage_count",
            "blocked_dependency_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-negative int")
        if self.plan_id is not None:
            object.__setattr__(self, "plan_id", ensure_non_empty_text("plan_id", self.plan_id))
        if self.plan_receipt_ref is not None:
            object.__setattr__(
                self,
                "plan_receipt_ref",
                ensure_non_empty_text("plan_receipt_ref", self.plan_receipt_ref),
            )
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
        settled_stage_ids: set[str] = set()

        for plan_step, request in _episode_execution_steps(episode):
            failed_predecessors = _failed_predecessors(plan_step, settled_stage_ids)
            if failed_predecessors:
                step_receipts.append(
                    _blocked_dependency_step_receipt(
                        request=request,
                        plan=episode.plan,
                        plan_step=plan_step,
                        failed_predecessors=failed_predecessors,
                    )
                )
                continue

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
                        plan=episode.plan,
                        plan_step=plan_step,
                    )
                )
                if _step_settled(step_receipts[-1], report):
                    settled_stage_ids.add(plan_step.stage_id)
            else:
                step_receipts.append(
                    _blocked_step_receipt(
                        request=request,
                        action_class=action_class,
                        boundary=boundary,
                        decision=decision,
                        plan=episode.plan,
                        plan_step=plan_step,
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


def _validated_text_mapping(field_name: str, values: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise RuntimeCoreInvariantError(f"{field_name} must be a mapping")
    return {
        ensure_non_empty_text("binding_name", key): ensure_non_empty_text("binding_value", value)
        for key, value in values.items()
    }


def _required_parameter_names(template: Mapping[str, object]) -> tuple[str, ...]:
    required_parameters = template.get("required_parameters", ())
    if required_parameters is None:
        return ()
    if isinstance(required_parameters, (str, bytes)) or not isinstance(required_parameters, (tuple, list)):
        raise RuntimeCoreInvariantError("required_parameters must be an array")
    return tuple(
        ensure_non_empty_text("required_parameter", parameter)
        for parameter in required_parameters
    )


def _stage_id_for_capability(capability_id: str) -> str:
    return f"stage-{ensure_non_empty_text('capability_id', capability_id)}"


def _ordered_plan_steps(
    steps: tuple[AutonomousRequestPlanStep, ...],
) -> tuple[AutonomousRequestPlanStep, ...]:
    stage_by_id: dict[str, AutonomousRequestPlanStep] = {}
    request_ids: set[str] = set()
    for step in steps:
        if step.stage_id in stage_by_id:
            raise RuntimeCoreInvariantError("plan steps must declare unique stage_id values")
        if step.request.request_id in request_ids:
            raise RuntimeCoreInvariantError("plan step requests must declare unique request_id values")
        stage_by_id[step.stage_id] = step
        request_ids.add(step.request.request_id)

    for step in steps:
        for predecessor_id in step.predecessors:
            if predecessor_id not in stage_by_id:
                raise RuntimeCoreInvariantError("plan predecessors must reference declared stage_id values")

    ordered: list[AutonomousRequestPlanStep] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visited:
            return
        if stage_id in visiting:
            raise RuntimeCoreInvariantError("plan stage graph must not contain cycles")
        visiting.add(stage_id)
        for predecessor_id in stage_by_id[stage_id].predecessors:
            visit(predecessor_id)
        visiting.remove(stage_id)
        visited.add(stage_id)
        ordered.append(stage_by_id[stage_id])

    for step in steps:
        visit(step.stage_id)
    return tuple(ordered)


def _episode_execution_steps(
    episode: AutonomousRequestEpisode,
) -> tuple[tuple[AutonomousRequestPlanStep, OperatorRequest], ...]:
    if episode.plan is not None:
        return tuple((step, step.request) for step in episode.plan.steps)
    return tuple(
        (
            AutonomousRequestPlanStep(stage_id=request.request_id, request=request),
            request,
        )
        for request in episode.requests
    )


def _failed_predecessors(
    plan_step: AutonomousRequestPlanStep,
    settled_stage_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        predecessor_id
        for predecessor_id in plan_step.predecessors
        if predecessor_id not in settled_stage_ids
    )


def _step_settled(step_receipt: AutonomousRequestStepReceipt, report: OperatorRunReport) -> bool:
    return (
        step_receipt.dispatched
        and report.validation_error is None
        and step_receipt.validation_error is None
        and step_receipt.autonomy_status == AutonomyDecisionStatus.ALLOWED.value
    )


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
    plan: AutonomousRequestPlan | None,
    plan_step: AutonomousRequestPlanStep,
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
        plan_id=None if plan is None else plan.plan_id,
        plan_stage_id=None if plan is None else plan_step.stage_id,
        plan_predecessors=() if plan is None else plan_step.predecessors,
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
    plan: AutonomousRequestPlan | None = None,
    plan_step: AutonomousRequestPlanStep | None = None,
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
        plan_id=None if plan is None else plan.plan_id,
        plan_stage_id=None if plan is None or plan_step is None else plan_step.stage_id,
        plan_predecessors=() if plan is None or plan_step is None else plan_step.predecessors,
    )


def _blocked_dependency_step_receipt(
    *,
    request: OperatorRequest,
    plan: AutonomousRequestPlan | None,
    plan_step: AutonomousRequestPlanStep,
    failed_predecessors: tuple[str, ...],
) -> AutonomousRequestStepReceipt:
    action_class = _action_class_for_request(request)
    boundary = _boundary_for_action_class(action_class)
    receipt_ref = stable_identifier(
        "request-step-receipt",
        {
            "request_id": request.request_id,
            "stage_id": plan_step.stage_id,
            "failed_predecessors": failed_predecessors,
        },
    )
    return AutonomousRequestStepReceipt(
        request_id=request.request_id,
        action_class=action_class.value,
        boundary=boundary.value,
        autonomy_decision_id=f"dependency-blocked:{plan_step.stage_id}",
        autonomy_status=AutonomyDecisionStatus.REJECTED.value,
        autonomy_reason="predecessor stage did not settle",
        dispatched=False,
        execution_id=None,
        validation_error="dependency_blocked:" + ",".join(failed_predecessors),
        structured_error_codes=("dependency_blocked",),
        receipt_ref=f"receipt://{receipt_ref}",
        plan_id=None if plan is None else plan.plan_id,
        plan_stage_id=plan_step.stage_id,
        plan_predecessors=plan_step.predecessors,
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
    blocked_dependency_count = sum(
        1
        for step in step_receipts
        if "dependency_blocked" in step.structured_error_codes
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
    plan_receipt_ref = _plan_receipt_ref(episode=episode, step_receipts=step_receipts)
    automation_state = _automation_state(
        action_count=len(step_receipts),
        dispatched_count=dispatched_count,
        completed_count=completed_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        validation_errors=validation_errors,
        blocked_dependency_count=blocked_dependency_count,
    )
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
        plan_id=None if episode.plan is None else episode.plan.plan_id,
        planned_stage_count=0 if episode.plan is None else len(episode.plan.steps),
        blocked_dependency_count=blocked_dependency_count,
        plan_receipt_ref=plan_receipt_ref,
        automation_state=automation_state.value,
        solver_outcome=solver_outcome.value,
        rollback_ref=rollback_ref,
    )


def _plan_receipt_ref(
    *,
    episode: AutonomousRequestEpisode,
    step_receipts: tuple[AutonomousRequestStepReceipt, ...],
) -> str | None:
    if episode.plan is None:
        return None
    plan_ref = stable_identifier(
        "autonomous-request-plan-receipt",
        {
            "episode_id": episode.episode_id,
            "plan_id": episode.plan.plan_id,
            "stages": tuple(step.plan_stage_id for step in step_receipts),
            "receipts": tuple(step.receipt_ref for step in step_receipts),
        },
    )
    return f"receipt://{plan_ref}"


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


def _automation_state(
    *,
    action_count: int,
    dispatched_count: int,
    completed_count: int,
    pending_count: int,
    rejected_count: int,
    validation_errors: tuple[str, ...],
    blocked_dependency_count: int,
) -> AutonomousRequestAutomationState:
    if pending_count > 0:
        return AutonomousRequestAutomationState.AWAITING_APPROVAL
    if rejected_count > 0 or validation_errors or blocked_dependency_count > 0:
        return AutonomousRequestAutomationState.GOVERNANCE_BLOCKED
    if action_count > 0 and (completed_count == action_count or dispatched_count == action_count):
        return AutonomousRequestAutomationState.SETTLED_WITHOUT_PROMPT
    return AutonomousRequestAutomationState.AWAITING_EVIDENCE


__all__ = [
    "AutonomousRequestAutomationState",
    "AutonomousRequestCapabilityMetadata",
    "AutonomousRequestEpisode",
    "AutonomousRequestEpisodeReceipt",
    "AutonomousRequestExecutor",
    "AutonomousRequestIntent",
    "AutonomousRequestPlan",
    "AutonomousRequestPlanCompiler",
    "AutonomousRequestPlanStep",
    "AutonomousRequestRepairReceipt",
    "AutonomousRequestStepReceipt",
    "RequestActionBoundary",
    "run_autonomous_request_episode",
]
