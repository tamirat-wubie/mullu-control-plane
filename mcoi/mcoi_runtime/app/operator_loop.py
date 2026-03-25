"""Purpose: run one explicit operator request through the MCOI runtime boundaries.
Governance scope: operator-loop single-step orchestration only.
Dependencies: local bootstrap wiring, execution-slice observers and dispatcher, and runtime-core boundaries.
Invariants: request handling is single-step, ordered, deterministic, and never marks execution complete without explicit verification closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.adapters.filesystem_observer import FilesystemObservationRequest
from mcoi_runtime.adapters.observer_base import ObservationResult, ObservationStatus
from mcoi_runtime.adapters.process_observer import ProcessObservationRequest
from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.goal import (
    GoalDescriptor,
    GoalExecutionState,
    GoalPlan,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)
from mcoi_runtime.contracts.policy import PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.verification import VerificationResult
from mcoi_runtime.contracts.autonomy import ActionClass, AutonomyDecisionStatus
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStatus,
)
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.provider import ProviderHealthStatus
from mcoi_runtime.contracts.world_state import StateEntity
from mcoi_runtime.core.errors import (
    ErrorFamily,
    Recoverability,
    SourcePlane,
    StructuredError,
    admissibility_error,
    execution_error,
    observation_error,
    policy_error,
    validation_error,
    verification_error,
)
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceState, EvidenceStateCategory
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.planning_boundary import PlanningBoundaryResult, PlanningKnowledge
from mcoi_runtime.core.policy_engine import PolicyInput
from mcoi_runtime.adapters.executor_base import ExecutionAdapterError
from mcoi_runtime.core.skills import StepExecutor
from mcoi_runtime.core.template_validator import TemplateValidationError
from mcoi_runtime.contracts.skill import (
    SkillDescriptor,
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcome,
    SkillOutcomeStatus,
    SkillSelectionDecision,
    SkillStepOutcome,
)
from mcoi_runtime.persistence.errors import PersistenceError

from .bootstrap import BootstrappedRuntime, build_policy_decision


ObservationRequestT = FilesystemObservationRequest | ProcessObservationRequest


@dataclass(frozen=True, slots=True)
class ObservationDirective:
    observer_route: str
    request: ObservationRequestT
    state_key: str
    category: EvidenceStateCategory = EvidenceStateCategory.OBSERVED

    def __post_init__(self) -> None:
        if not isinstance(self.observer_route, str) or not self.observer_route.strip():
            raise RuntimeCoreInvariantError("observer_route must be a non-empty string")
        if not isinstance(self.state_key, str) or not self.state_key.strip():
            raise RuntimeCoreInvariantError("state_key must be a non-empty string")
        if not isinstance(self.category, EvidenceStateCategory):
            raise RuntimeCoreInvariantError("category must be an EvidenceStateCategory value")


@dataclass(frozen=True, slots=True)
class OperatorRequest:
    request_id: str
    subject_id: str
    goal_id: str
    template: Mapping[str, Any]
    bindings: Mapping[str, str]
    knowledge_entries: tuple[PlanningKnowledge, ...] = ()
    evidence_entries: tuple[EvidenceInput, ...] = ()
    observation_requests: tuple[ObservationDirective, ...] = ()
    blocked_knowledge_ids: tuple[str, ...] = ()
    missing_capability_ids: tuple[str, ...] = ()
    requires_operator_review: bool = False
    verification_result: VerificationResult | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.template, Mapping):
            raise RuntimeCoreInvariantError("template must be a mapping")
        if not isinstance(self.bindings, Mapping):
            raise RuntimeCoreInvariantError("bindings must be a mapping")
        for key, value in self.bindings.items():
            if not isinstance(key, str) or not key.strip():
                raise RuntimeCoreInvariantError("binding names must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("binding values must be non-empty strings")
        for value in self.blocked_knowledge_ids:
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("blocked_knowledge_ids must contain non-empty strings")
        for value in self.missing_capability_ids:
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("missing_capability_ids must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class SkillRequest:
    """Request to execute a skill through the governed runtime."""

    request_id: str
    subject_id: str
    goal_id: str
    skill_id: str | None = None
    input_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SkillRunReport:
    """Report from a skill execution through the operator loop."""

    request_id: str
    goal_id: str
    skill_id: str | None
    selection: SkillSelectionDecision | None
    execution_record: SkillExecutionRecord | None
    status: SkillOutcomeStatus
    completed: bool
    structured_errors: tuple[StructuredError, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status is SkillOutcomeStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class WorkflowRunReport:
    """Report from a workflow execution through the operator loop."""

    workflow_id: str
    execution_id: str
    status: WorkflowStatus
    stage_summaries: tuple[StageExecutionResult, ...]
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class GoalRunReport:
    """Report from a goal execution through the operator loop."""

    goal_id: str
    status: GoalStatus
    plan_id: str | None
    completed_sub_goals: tuple[str, ...] = ()
    failed_sub_goals: tuple[str, ...] = ()
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class ObservationReport:
    observer_route: str
    status: ObservationStatus
    state_key: str
    evidence_count: int
    failure_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperatorRunReport:
    request_id: str
    goal_id: str
    policy_decision_id: str
    execution_id: str | None
    verification_id: str | None
    observation_reports: tuple[ObservationReport, ...]
    merged_state: EvidenceState
    planning_result: PlanningBoundaryResult
    policy_decision: PolicyDecision
    validation_passed: bool
    validation_error: str | None
    execution_result: ExecutionResult | None
    verification_closed: bool
    completed: bool
    verification_error: str | None
    dispatched: bool
    structured_errors: tuple[StructuredError, ...] = ()
    world_state_hash: str | None = None
    world_state_entity_count: int = 0
    world_state_contradiction_count: int = 0
    degraded_capabilities: tuple[str, ...] = ()
    escalation_recommendations: tuple[str, ...] = ()
    provider_count: int = 0
    unhealthy_providers: tuple[str, ...] = ()
    execution_route: str | None = None
    integration_provider_id: str | None = None
    communication_provider_id: str | None = None
    model_provider_id: str | None = None
    autonomy_mode: str | None = None
    autonomy_decision: str | None = None


@dataclass(slots=True)
class OperatorLoop:
    runtime: BootstrappedRuntime

    def run_step(self, request: OperatorRequest) -> OperatorRunReport:
        observation_reports: list[ObservationReport] = []
        observed_evidence: list[EvidenceInput] = []

        for directive in request.observation_requests:
            observer = self.runtime.observers.get(directive.observer_route)
            if observer is None:
                observation_reports.append(
                    ObservationReport(
                        observer_route=directive.observer_route,
                        status=ObservationStatus.UNSUPPORTED,
                        state_key=directive.state_key,
                        evidence_count=0,
                        failure_codes=("observer_not_registered",),
                    )
                )
                continue

            result = observer.observe(directive.request)
            observation_reports.append(
                ObservationReport(
                    observer_route=directive.observer_route,
                    status=result.status,
                    state_key=directive.state_key,
                    evidence_count=len(result.evidence),
                    failure_codes=tuple(failure.code for failure in result.failures),
                )
            )
            observed_evidence.extend(self._evidence_from_observation(directive, result))

        merged_state = self.runtime.runtime_kernel.merge_evidence(
            EvidenceState(),
            request.evidence_entries + tuple(observed_evidence),
        )
        planning_result = self.runtime.runtime_kernel.evaluate_planning(
            request.knowledge_entries,
            admitted_classes=self.runtime.config.allowed_planning_classes,
        )
        policy_decision = self.runtime.runtime_kernel.evaluate_policy(
            PolicyInput(
                subject_id=request.subject_id,
                goal_id=request.goal_id,
                issued_at=self.runtime.clock(),
                blocked_knowledge_ids=request.blocked_knowledge_ids,
                missing_capability_ids=request.missing_capability_ids,
                requires_operator_review=request.requires_operator_review,
            ),
            build_policy_decision,
        )

        # Capture runtime state once for all return paths
        _rsf = self._runtime_state_fields()

        if planning_result.rejected:
            rejected_ids = tuple(r.knowledge_id for r in planning_result.rejected)
            return self._blocked_run_report(
                request=request,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_error_text="planning_rejected_inadmissible_knowledge",
                structured_errors=(
                    admissibility_error(
                        error_code="planning_rejected_inadmissible_knowledge",
                        message="planning boundary rejected inadmissible knowledge",
                        related_ids=rejected_ids,
                        context={
                            "rejected_reasons": {
                                r.knowledge_id: str(r.reason) for r in planning_result.rejected
                            },
                        },
                    ),
                ),
                runtime_state_fields=_rsf,
            )

        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return self._blocked_run_report(
                request=request,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_error_text="policy_denied_or_escalated",
                structured_errors=(
                    policy_error(
                        error_code=f"policy_{policy_decision.status.value}",
                        message=f"policy gate returned {policy_decision.status.value}",
                        recoverability=(
                            Recoverability.APPROVAL_REQUIRED
                            if policy_decision.status is PolicyDecisionStatus.ESCALATE
                            else Recoverability.FATAL_FOR_RUN
                        ),
                        related_ids=(policy_decision.decision_id,),
                        context={"policy_status": policy_decision.status.value},
                    ),
                ),
                runtime_state_fields=_rsf,
            )

        try:
            self.runtime.template_validator.validate(request.template, request.bindings)
        except TemplateValidationError as exc:
            return self._blocked_run_report(
                request=request,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_error_text=f"{exc.code}:{exc}",
                structured_errors=(
                    validation_error(
                        error_code=exc.code,
                        message=str(exc),
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                runtime_state_fields=_rsf,
            )

        execution_result = self.runtime.dispatcher.dispatch(
            DispatchRequest(
                goal_id=request.goal_id,
                route=str(request.template.get("action_type", "")),
                template=request.template,
                bindings=request.bindings,
            )
        )
        verification_closure = self.runtime.verification_engine.evaluate(
            verification_result=request.verification_result,
            execution_result=execution_result,
        )

        errors: list[StructuredError] = []
        if verification_closure.error is not None:
            errors.append(
                verification_error(
                    error_code="verification_closure_error",
                    message=verification_closure.error,
                    related_ids=(execution_result.execution_id,),
                )
            )

        # World-state: register execution outcome as entity
        route = str(request.template.get("action_type", "unknown"))
        entity_reg_error = self._register_execution_entity(request, execution_result, route)
        if entity_reg_error is not None:
            errors.append(entity_reg_error)

        # Meta-reasoning: update capability confidence from execution outcome
        self._update_capability_confidence(route, execution_result, verification_closure)

        ws = self.runtime.world_state
        mr = self.runtime.meta_reasoning

        return OperatorRunReport(
            request_id=request.request_id,
            goal_id=request.goal_id,
            policy_decision_id=policy_decision.decision_id,
            execution_id=execution_result.execution_id,
            verification_id=(
                request.verification_result.verification_id
                if request.verification_result is not None
                else None
            ),
            observation_reports=tuple(observation_reports),
            merged_state=merged_state,
            planning_result=planning_result,
            policy_decision=policy_decision,
            validation_passed=True,
            validation_error=None,
            execution_result=execution_result,
            verification_closed=verification_closure.verification_closed,
            completed=verification_closure.completed,
            verification_error=verification_closure.error,
            dispatched=True,
            structured_errors=tuple(errors),
            world_state_hash=ws.snapshot_hash(),
            world_state_entity_count=ws.entity_count,
            world_state_contradiction_count=len(ws.list_unresolved_contradictions()),
            degraded_capabilities=tuple(d.capability_id for d in mr.list_degraded()),
            escalation_recommendations=tuple(
                r.reason for r in mr.list_escalation_recommendations()
            ),
            provider_count=len(self.runtime.provider_registry.list_providers()),
            unhealthy_providers=tuple(
                p.provider_id for p in self.runtime.provider_registry.list_providers()
                if (h := self.runtime.provider_registry.get_health(p.provider_id)) is not None
                and h.status in (ProviderHealthStatus.DEGRADED, ProviderHealthStatus.UNAVAILABLE)
            ),
            execution_route=route,
            autonomy_mode=self.runtime.autonomy.mode.value,
            **self._resolve_provider_ids(),
        )

    def _blocked_run_report(
        self,
        *,
        request: OperatorRequest,
        observation_reports: tuple[ObservationReport, ...],
        merged_state: EvidenceState,
        planning_result: PlanningBoundaryResult,
        policy_decision: PolicyDecision,
        validation_error_text: str,
        structured_errors: tuple[StructuredError, ...],
        runtime_state_fields: Mapping[str, object],
    ) -> OperatorRunReport:
        """Construct a deterministic blocked-run report.

        Centralizes the non-dispatched report shape so admissibility, policy,
        and validation failures cannot drift apart silently.
        """
        return OperatorRunReport(
            request_id=request.request_id,
            goal_id=request.goal_id,
            policy_decision_id=policy_decision.decision_id,
            execution_id=None,
            verification_id=None,
            observation_reports=observation_reports,
            merged_state=merged_state,
            planning_result=planning_result,
            policy_decision=policy_decision,
            validation_passed=False,
            validation_error=validation_error_text,
            execution_result=None,
            verification_closed=False,
            completed=False,
            verification_error=None,
            dispatched=False,
            structured_errors=structured_errors,
            world_state_hash=runtime_state_fields["world_state_hash"],
            world_state_entity_count=runtime_state_fields["world_state_entity_count"],
            world_state_contradiction_count=runtime_state_fields["world_state_contradiction_count"],
            degraded_capabilities=runtime_state_fields["degraded_capabilities"],
            escalation_recommendations=runtime_state_fields["escalation_recommendations"],
            provider_count=runtime_state_fields["provider_count"],
            unhealthy_providers=runtime_state_fields["unhealthy_providers"],
            autonomy_mode=runtime_state_fields.get("autonomy_mode"),
            integration_provider_id=runtime_state_fields.get("integration_provider_id"),
            communication_provider_id=runtime_state_fields.get("communication_provider_id"),
            model_provider_id=runtime_state_fields.get("model_provider_id"),
        )

    def run_skill(self, request: SkillRequest) -> SkillRunReport:
        """Execute a skill through the governed runtime path.

        1. Resolve skill (by ID or select from registry)
        2. Check autonomy mode — block if mode does not permit execution
        3. Evaluate policy — block if policy denies
        4. Execute through SkillExecutor with a governed step executor
        5. Update capability confidence from outcome
        6. Lifecycle promotion on first success
        """
        registry = self.runtime.skill_registry
        selector = self.runtime.skill_selector
        executor = self.runtime.skill_executor

        # Step 1: resolve skill
        skill: SkillDescriptor | None = None
        selection: SkillSelectionDecision | None = None

        if request.skill_id:
            skill = registry.get(request.skill_id)
            if skill is None:
                return SkillRunReport(
                    request_id=request.request_id,
                    goal_id=request.goal_id,
                    skill_id=request.skill_id,
                    selection=None,
                    execution_record=None,
                    status=SkillOutcomeStatus.FAILED,
                    completed=False,
                    structured_errors=(
                        execution_error(
                            error_code="skill_not_found",
                            message=f"skill not found: {request.skill_id}",
                        ),
                    ),
                )
            if skill.lifecycle is SkillLifecycle.BLOCKED:
                return SkillRunReport(
                    request_id=request.request_id,
                    goal_id=request.goal_id,
                    skill_id=request.skill_id,
                    selection=None,
                    execution_record=None,
                    status=SkillOutcomeStatus.POLICY_DENIED,
                    completed=False,
                    structured_errors=(
                        policy_error(
                            error_code="skill_blocked",
                            message=f"skill is blocked: {request.skill_id}",
                            recoverability=Recoverability.FATAL_FOR_RUN,
                        ),
                    ),
                )
        else:
            # Select from all registered skills
            candidates = registry.list_skills(exclude_blocked=True)
            selection = selector.select(candidates)
            if selection is None:
                return SkillRunReport(
                    request_id=request.request_id,
                    goal_id=request.goal_id,
                    skill_id=None,
                    selection=None,
                    execution_record=None,
                    status=SkillOutcomeStatus.FAILED,
                    completed=False,
                    structured_errors=(
                        execution_error(
                            error_code="no_skill_available",
                            message="no suitable skill found in registry",
                        ),
                    ),
                )
            skill = registry.get(selection.selected_skill_id)

        # Step 2: autonomy mode check — block execution in non-executing modes
        autonomy_decision = self.runtime.autonomy.evaluate(
            ActionClass.EXECUTE_WRITE,
            action_description=f"skill_execution:{skill.skill_id}",
        )
        if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
            return SkillRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                skill_id=skill.skill_id,
                selection=selection,
                execution_record=None,
                status=SkillOutcomeStatus.POLICY_DENIED,
                completed=False,
                structured_errors=(
                    policy_error(
                        error_code="autonomy_blocked",
                        message=(
                            f"autonomy mode {self.runtime.autonomy.mode.value} "
                            f"blocked skill execution: {autonomy_decision.reason}"
                        ),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=(autonomy_decision.decision_id,),
                        context={
                            "autonomy_mode": self.runtime.autonomy.mode.value,
                            "autonomy_status": autonomy_decision.status.value,
                        },
                    ),
                ),
            )

        # Step 3: policy evaluation — block if policy denies
        policy_decision = self.runtime.runtime_kernel.evaluate_policy(
            PolicyInput(
                subject_id=request.subject_id,
                goal_id=request.goal_id,
                issued_at=self.runtime.clock(),
            ),
            build_policy_decision,
        )
        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return SkillRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                skill_id=skill.skill_id,
                selection=selection,
                execution_record=None,
                status=SkillOutcomeStatus.POLICY_DENIED,
                completed=False,
                structured_errors=(
                    policy_error(
                        error_code=f"policy_{policy_decision.status.value}",
                        message=f"policy gate returned {policy_decision.status.value} for skill execution",
                        recoverability=(
                            Recoverability.APPROVAL_REQUIRED
                            if policy_decision.status is PolicyDecisionStatus.ESCALATE
                            else Recoverability.FATAL_FOR_RUN
                        ),
                        related_ids=(policy_decision.decision_id,),
                        context={"policy_status": policy_decision.status.value},
                    ),
                ),
            )

        # Step 4: execute with governed step executor
        governed_executor = _GovernedStepExecutor(runtime=self.runtime)
        record = executor.execute(
            skill,
            step_executor=governed_executor,
            input_context=dict(request.input_context) if request.input_context else None,
        )

        # Step 5: update skill confidence
        succeeded = record.outcome.status is SkillOutcomeStatus.SUCCEEDED
        existing = skill.confidence
        new_confidence = min(1.0, existing + 0.1) if succeeded else max(0.0, existing - 0.1)
        registry.update_confidence(skill.skill_id, round(new_confidence, 4))

        # Step 6: lifecycle promotion on first success
        if succeeded and skill.lifecycle is SkillLifecycle.CANDIDATE:
            try:
                registry.transition(skill.skill_id, SkillLifecycle.PROVISIONAL)
            except RuntimeCoreInvariantError:
                pass

        return SkillRunReport(
            request_id=request.request_id,
            goal_id=request.goal_id,
            skill_id=skill.skill_id,
            selection=selection,
            execution_record=record,
            status=record.outcome.status,
            completed=succeeded,
        )

    def run_workflow(
        self,
        request: SkillRequest,
        workflow_descriptor: WorkflowDescriptor,
    ) -> WorkflowRunReport:
        """Execute a workflow through the governed runtime path.

        1. Validate workflow structure
        2. Check autonomy mode
        3. Evaluate policy
        4. Execute stages sequentially using topological order
        5. Return structured report with stage results
        """
        workflow_engine = self.runtime.workflow_engine
        started_at = self.runtime.clock()

        # Step 1: validate workflow
        validation_errors = workflow_engine.validate_workflow(workflow_descriptor)
        if validation_errors:
            return WorkflowRunReport(
                workflow_id=workflow_descriptor.workflow_id,
                execution_id="",
                status=WorkflowStatus.FAILED,
                stage_summaries=(),
                errors=(
                    validation_error(
                        error_code="workflow_validation_failed",
                        message=f"workflow validation failed: {'; '.join(validation_errors)}",
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        # Step 2: autonomy mode check
        autonomy_decision = self.runtime.autonomy.evaluate(
            ActionClass.EXECUTE_WRITE,
            action_description=f"workflow_execution:{workflow_descriptor.workflow_id}",
        )
        if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
            return WorkflowRunReport(
                workflow_id=workflow_descriptor.workflow_id,
                execution_id="",
                status=WorkflowStatus.FAILED,
                stage_summaries=(),
                errors=(
                    policy_error(
                        error_code="autonomy_blocked",
                        message=(
                            f"autonomy mode {self.runtime.autonomy.mode.value} "
                            f"blocked workflow execution: {autonomy_decision.reason}"
                        ),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=(autonomy_decision.decision_id,),
                        context={
                            "autonomy_mode": self.runtime.autonomy.mode.value,
                            "autonomy_status": autonomy_decision.status.value,
                        },
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        # Step 3: policy evaluation
        policy_decision = self.runtime.runtime_kernel.evaluate_policy(
            PolicyInput(
                subject_id=request.subject_id,
                goal_id=request.goal_id,
                issued_at=self.runtime.clock(),
            ),
            build_policy_decision,
        )
        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return WorkflowRunReport(
                workflow_id=workflow_descriptor.workflow_id,
                execution_id="",
                status=WorkflowStatus.FAILED,
                stage_summaries=(),
                errors=(
                    policy_error(
                        error_code=f"policy_{policy_decision.status.value}",
                        message=f"policy gate returned {policy_decision.status.value} for workflow execution",
                        recoverability=(
                            Recoverability.APPROVAL_REQUIRED
                            if policy_decision.status is PolicyDecisionStatus.ESCALATE
                            else Recoverability.FATAL_FOR_RUN
                        ),
                        related_ids=(policy_decision.decision_id,),
                        context={"policy_status": policy_decision.status.value},
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        # Step 4: start workflow and execute all stages
        workflow_context = dict(request.input_context) if request.input_context else None
        record = workflow_engine.start_workflow(workflow_descriptor, context=workflow_context)
        stage_executor = _WorkflowStageExecutor(loop=self, request=request)

        # Execute stages one-by-one until completion or failure
        while record.status is WorkflowStatus.RUNNING:
            new_record = workflow_engine.execute_next_stage(
                workflow_descriptor,
                record,
                stage_executor,
                context=workflow_context,
            )
            if new_record is record:
                # No progress — stuck: mark as FAILED
                record = WorkflowExecutionRecord(
                    workflow_id=record.workflow_id,
                    execution_id=record.execution_id,
                    status=WorkflowStatus.FAILED,
                    stage_results=record.stage_results,
                    started_at=record.started_at,
                    completed_at=self.runtime.clock(),
                )
                break
            record = new_record

        # Persist if store is available
        if self.runtime.workflow_store is not None:
            self.runtime.workflow_store.save_execution_record(record)

        errors: list[StructuredError] = []
        if record.status is WorkflowStatus.FAILED:
            stage_has_error = False
            for stage_result in record.stage_results:
                if stage_result.status is StageStatus.FAILED and stage_result.error is not None:
                    errors.append(stage_result.error)
                    stage_has_error = True
            if not stage_has_error:
                # Stuck detection — no stage reported a failure but workflow is FAILED
                errors.append(
                    execution_error(
                        error_code="workflow_stuck_no_progress",
                        message="workflow execution made no progress — stages are blocked",
                    )
                )

        return WorkflowRunReport(
            workflow_id=workflow_descriptor.workflow_id,
            execution_id=record.execution_id,
            status=record.status,
            stage_summaries=record.stage_results,
            errors=tuple(errors),
            started_at=record.started_at,
            completed_at=record.completed_at or self.runtime.clock(),
        )

    def run_goal(
        self,
        request: SkillRequest,
        goal_descriptor: GoalDescriptor,
    ) -> GoalRunReport:
        """Execute a goal through the governed runtime path.

        1. Accept goal
        2. Check autonomy mode
        3. Evaluate policy
        4. Create plan from sub-goals (using goal reasoning engine)
        5. Execute sub-goals through run_skill or run_workflow
        6. On failure: mark goal as failed (replanning is manual/future)
        7. Return structured report with goal state
        """
        goal_engine = self.runtime.goal_reasoning_engine
        started_at = self.runtime.clock()

        # Step 1: accept goal
        state = goal_engine.accept_goal(goal_descriptor)

        # Step 2: autonomy mode check
        autonomy_decision = self.runtime.autonomy.evaluate(
            ActionClass.EXECUTE_WRITE,
            action_description=f"goal_execution:{goal_descriptor.goal_id}",
        )
        if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
            return GoalRunReport(
                goal_id=goal_descriptor.goal_id,
                status=GoalStatus.FAILED,
                plan_id=None,
                errors=(
                    policy_error(
                        error_code="autonomy_blocked",
                        message=(
                            f"autonomy mode {self.runtime.autonomy.mode.value} "
                            f"blocked goal execution: {autonomy_decision.reason}"
                        ),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=(autonomy_decision.decision_id,),
                        context={
                            "autonomy_mode": self.runtime.autonomy.mode.value,
                            "autonomy_status": autonomy_decision.status.value,
                        },
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        # Step 3: policy evaluation
        policy_decision = self.runtime.runtime_kernel.evaluate_policy(
            PolicyInput(
                subject_id=request.subject_id,
                goal_id=request.goal_id,
                issued_at=self.runtime.clock(),
            ),
            build_policy_decision,
        )
        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return GoalRunReport(
                goal_id=goal_descriptor.goal_id,
                status=GoalStatus.FAILED,
                plan_id=None,
                errors=(
                    policy_error(
                        error_code=f"policy_{policy_decision.status.value}",
                        message=f"policy gate returned {policy_decision.status.value} for goal execution",
                        recoverability=(
                            Recoverability.APPROVAL_REQUIRED
                            if policy_decision.status is PolicyDecisionStatus.ESCALATE
                            else Recoverability.FATAL_FOR_RUN
                        ),
                        related_ids=(policy_decision.decision_id,),
                        context={"policy_status": policy_decision.status.value},
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        # Step 4: create plan — the caller must provide explicit executable
        # sub-goals in descriptor.metadata["sub_goals"].
        raw_sub_goals = goal_descriptor.metadata.get("sub_goals")
        if raw_sub_goals is None:
            return GoalRunReport(
                goal_id=goal_descriptor.goal_id,
                status=GoalStatus.FAILED,
                plan_id=None,
                errors=(
                    validation_error(
                        error_code="goal_missing_sub_goals",
                        message="goal execution requires explicit sub-goals in metadata['sub_goals']",
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        sub_goals_list: list[SubGoal] = []
        for sg in raw_sub_goals:
            if isinstance(sg, SubGoal):
                sub_goals_list.append(sg)
        raw_sub_goals = tuple(sub_goals_list)

        # Guard: if all sub-goals were filtered out, return a validation error
        if not raw_sub_goals:
            return GoalRunReport(
                goal_id=goal_descriptor.goal_id,
                status=GoalStatus.FAILED,
                plan_id=None,
                errors=(
                    validation_error(
                        error_code="goal_empty_sub_goals",
                        message="all sub-goals were filtered out — none are valid SubGoal instances",
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                started_at=started_at,
                completed_at=self.runtime.clock(),
            )

        plan = goal_engine.create_plan(goal_descriptor, raw_sub_goals)
        state = GoalExecutionState(
            goal_id=state.goal_id,
            status=GoalStatus.EXECUTING,
            current_plan_id=plan.plan_id,
            updated_at=self.runtime.clock(),
        )

        # Persist plan and initial state
        if self.runtime.goal_store is not None:
            self.runtime.goal_store.save_plan(plan)
            self.runtime.goal_store.save_goal_state(state)

        # Step 5: execute sub-goals
        sub_goal_executor = _GoalSubGoalExecutor(loop=self, request=request)

        while state.status is GoalStatus.EXECUTING:
            new_state = goal_engine.execute_next_sub_goal(state, plan, sub_goal_executor)
            if new_state is state:
                # No progress — stuck: mark as FAILED
                state = GoalExecutionState(
                    goal_id=state.goal_id,
                    status=GoalStatus.FAILED,
                    current_plan_id=state.current_plan_id,
                    updated_at=self.runtime.clock(),
                    completed_sub_goals=state.completed_sub_goals,
                    failed_sub_goals=state.failed_sub_goals,
                )
                break
            state = new_state
            # Persist updated state
            if self.runtime.goal_store is not None:
                self.runtime.goal_store.save_goal_state(state)

        errors: list[StructuredError] = []
        if state.status is GoalStatus.FAILED:
            if state.failed_sub_goals:
                errors.append(
                    execution_error(
                        error_code="goal_sub_goal_failed",
                        message=f"goal failed: sub-goals {', '.join(state.failed_sub_goals)} failed",
                        related_ids=state.failed_sub_goals,
                    )
                )
            else:
                # Stuck detection — no sub-goal reported failure but goal is FAILED
                errors.append(
                    execution_error(
                        error_code="goal_stuck_no_progress",
                        message="goal execution made no progress — sub-goals are blocked",
                    )
                )

        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=state.status,
            plan_id=plan.plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=tuple(errors),
            started_at=started_at,
            completed_at=self.runtime.clock(),
        )

    def _runtime_state_fields(self) -> dict:
        """Capture current world-state, meta-reasoning, and provider state for reports."""
        ws = self.runtime.world_state
        mr = self.runtime.meta_reasoning
        pr = self.runtime.provider_registry
        return {
            "world_state_hash": ws.snapshot_hash() if ws.entity_count > 0 else None,
            "world_state_entity_count": ws.entity_count,
            "world_state_contradiction_count": len(ws.list_unresolved_contradictions()),
            "degraded_capabilities": tuple(d.capability_id for d in mr.list_degraded()),
            "escalation_recommendations": tuple(r.reason for r in mr.list_escalation_recommendations()),
            "provider_count": len(pr.list_providers()),
            "unhealthy_providers": tuple(
                p.provider_id for p in pr.list_providers()
                if (h := pr.get_health(p.provider_id)) is not None
                and h.status in (ProviderHealthStatus.DEGRADED, ProviderHealthStatus.UNAVAILABLE)
            ),
            "autonomy_mode": self.runtime.autonomy.mode.value,
            **self._resolve_provider_ids(),
        }

    def _resolve_provider_ids(self) -> dict[str, str | None]:
        """Resolve first healthy provider ID per class for run reports."""
        from mcoi_runtime.contracts.provider import ProviderClass
        pr = self.runtime.provider_registry
        result: dict[str, str | None] = {
            "integration_provider_id": None,
            "communication_provider_id": None,
            "model_provider_id": None,
        }
        field_map = {
            ProviderClass.INTEGRATION: "integration_provider_id",
            ProviderClass.COMMUNICATION: "communication_provider_id",
            ProviderClass.MODEL: "model_provider_id",
        }
        for pc, field_name in field_map.items():
            providers = pr.list_providers(provider_class=pc, enabled_only=True)
            if providers:
                result[field_name] = providers[0].provider_id
        return result

    def _register_execution_entity(
        self,
        request: OperatorRequest,
        execution_result: ExecutionResult,
        route: str,
    ) -> StructuredError | None:
        """Register the execution outcome as a world-state entity.

        Returns a StructuredError if registration fails (best-effort), None on success.
        """
        entity_id = stable_identifier("entity", {
            "execution_id": execution_result.execution_id,
            "goal_id": request.goal_id,
        })
        try:
            self.runtime.world_state.add_entity(StateEntity(
                entity_id=entity_id,
                entity_type="execution_outcome",
                attributes={
                    "execution_id": execution_result.execution_id,
                    "goal_id": execution_result.goal_id,
                    "status": execution_result.status.value,
                    "route": route,
                    "effect_count": len(execution_result.actual_effects),
                },
                evidence_ids=(execution_result.execution_id,),
                confidence=1.0 if execution_result.status is ExecutionOutcome.SUCCEEDED else 0.5,
                created_at=execution_result.finished_at,
            ))
            return None
        except (RuntimeCoreInvariantError, ValueError) as exc:
            # Entity registration is best-effort — duplicate or validation errors are
            # expected but should be visible in the operator report for diagnostics.
            return execution_error(
                error_code="entity_registration_warning",
                message=f"best-effort entity registration failed: {type(exc).__name__}: {exc}",
                recoverability=Recoverability.RETRYABLE,
                related_ids=(execution_result.execution_id,),
                context={"entity_id": entity_id, "exception_type": type(exc).__name__},
            )

    def _update_capability_confidence(
        self,
        capability_id: str,
        execution_result: ExecutionResult,
        verification_closure: object,
    ) -> None:
        """Update meta-reasoning capability confidence from execution + verification."""
        existing = self.runtime.meta_reasoning.get_confidence(capability_id)
        sample_count = (existing.sample_count + 1) if existing else 1
        old_success = existing.success_rate if existing else 0.0
        old_verify = existing.verification_pass_rate if existing else 0.0
        old_error = existing.error_rate if existing else 0.0

        succeeded = execution_result.status is ExecutionOutcome.SUCCEEDED
        verified = getattr(verification_closure, "verification_closed", False) and getattr(verification_closure, "completed", False)
        errored = execution_result.status is ExecutionOutcome.FAILED

        # Running average
        weight = 1.0 / sample_count
        new_success = old_success * (1 - weight) + (1.0 if succeeded else 0.0) * weight
        new_verify = old_verify * (1 - weight) + (1.0 if verified else 0.0) * weight
        new_error = old_error * (1 - weight) + (1.0 if errored else 0.0) * weight

        self.runtime.meta_reasoning.update_confidence(CapabilityConfidence(
            capability_id=capability_id,
            success_rate=round(new_success, 4),
            verification_pass_rate=round(new_verify, 4),
            timeout_rate=0.0,
            error_rate=round(new_error, 4),
            sample_count=sample_count,
            assessed_at=self.runtime.clock(),
        ))

    @staticmethod
    def _evidence_from_observation(
        directive: ObservationDirective,
        result: ObservationResult,
    ) -> tuple[EvidenceInput, ...]:
        if result.status is not ObservationStatus.SUCCEEDED:
            return ()
        return tuple(
            EvidenceInput(
                evidence_id=stable_identifier(
                    "evidence",
                    {
                        "observer_route": directive.observer_route,
                        "state_key": directive.state_key,
                        "description": evidence.description,
                        "uri": evidence.uri,
                    },
                ),
                state_key=directive.state_key,
                value=thaw_value(evidence.details),
                category=directive.category,
            )
            for evidence in result.evidence
        )


class _GovernedStepExecutor:
    """Step executor that dispatches through the governed runtime path."""

    def __init__(self, *, runtime: BootstrappedRuntime) -> None:
        self._runtime = runtime

    def execute_step(
        self,
        step_id: str,
        action_type: str,
        input_bindings: Mapping[str, Any],
    ) -> SkillStepOutcome:
        """Execute one skill step through the dispatcher."""
        template = {"action_type": action_type, **{k: v for k, v in input_bindings.items()}}
        bindings = {k: str(v) for k, v in input_bindings.items() if isinstance(v, str)}

        try:
            self._runtime.template_validator.validate(template, bindings)
        except TemplateValidationError as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"validation:{exc.code}:{exc}",
            )

        try:
            result = self._runtime.dispatcher.dispatch(
                DispatchRequest(
                    goal_id=step_id,
                    route=action_type,
                    template=template,
                    bindings=bindings,
                )
            )
        except ExecutionAdapterError as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"dispatch_error:{type(exc).__name__}:{exc}",
            )

        if result.status is ExecutionOutcome.SUCCEEDED:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.SUCCEEDED,
                execution_id=result.execution_id,
                outputs={"execution_id": result.execution_id, "status": result.status.value},
            )
        return SkillStepOutcome(
            step_id=step_id,
            status=SkillOutcomeStatus.FAILED,
            execution_id=result.execution_id,
            error_message=f"execution_{result.status.value}",
        )


class _WorkflowStageExecutor:
    """Stage executor that dispatches through run_skill for skill_execution stages."""

    def __init__(self, *, loop: OperatorLoop, request: SkillRequest) -> None:
        self._loop = loop
        self._request = request

    def execute_stage(
        self,
        stage_id: str,
        stage_type: str,
        skill_id: str | None,
        inputs: Mapping[str, Any],
    ) -> StageExecutionResult:
        """Execute one workflow stage through the governed skill path."""
        started_at = self._loop.runtime.clock()

        if skill_id is not None:
            report = self._loop.run_skill(SkillRequest(
                request_id=f"{self._request.request_id}-{stage_id}",
                subject_id=self._request.subject_id,
                goal_id=self._request.goal_id,
                skill_id=skill_id,
                input_context=inputs,
            ))

            if report.succeeded:
                return StageExecutionResult(
                    stage_id=stage_id,
                    status=StageStatus.COMPLETED,
                    output={"skill_id": skill_id, "status": "succeeded"},
                    started_at=started_at,
                    completed_at=self._loop.runtime.clock(),
                )
            else:
                error = report.structured_errors[0] if report.structured_errors else None
                return StageExecutionResult(
                    stage_id=stage_id,
                    status=StageStatus.FAILED,
                    error=error,
                    started_at=started_at,
                    completed_at=self._loop.runtime.clock(),
                )

        # Fail closed until non-skill workflow stages have explicit handlers.
        return StageExecutionResult(
            stage_id=stage_id,
            status=StageStatus.FAILED,
            error=execution_error(
                error_code="workflow_stage_handler_missing",
                message=f"workflow stage type {stage_type} has no governed runtime handler",
                recoverability=Recoverability.FATAL_FOR_RUN,
                context={"stage_type": stage_type},
            ),
            started_at=started_at,
            completed_at=self._loop.runtime.clock(),
        )


class _GoalSubGoalExecutor:
    """Sub-goal executor that dispatches through run_skill."""

    def __init__(self, *, loop: OperatorLoop, request: SkillRequest) -> None:
        self._loop = loop
        self._request = request

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal:
        """Execute a sub-goal by dispatching to run_skill or run_workflow."""
        # Recheck autonomy before each sub-goal execution
        autonomy_decision = self._loop.runtime.autonomy.evaluate(
            ActionClass.EXECUTE_WRITE,
            action_description=f"sub_goal_execution:{sub_goal.sub_goal_id}",
        )
        if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
            return SubGoal(
                sub_goal_id=sub_goal.sub_goal_id,
                goal_id=sub_goal.goal_id,
                description=sub_goal.description,
                status=SubGoalStatus.FAILED,
                skill_id=sub_goal.skill_id,
                workflow_id=sub_goal.workflow_id,
                predecessors=sub_goal.predecessors,
            )

        if sub_goal.skill_id is not None:
            report = self._loop.run_skill(SkillRequest(
                request_id=f"{self._request.request_id}-{sub_goal.sub_goal_id}",
                subject_id=self._request.subject_id,
                goal_id=self._request.goal_id,
                skill_id=sub_goal.skill_id,
                input_context=self._request.input_context,
            ))
            new_status = SubGoalStatus.COMPLETED if report.succeeded else SubGoalStatus.FAILED
        elif sub_goal.workflow_id is not None:
            workflow_store = self._loop.runtime.workflow_store
            if workflow_store is None:
                new_status = SubGoalStatus.FAILED
            else:
                try:
                    descriptor = workflow_store.load_descriptor(sub_goal.workflow_id)
                except PersistenceError:
                    new_status = SubGoalStatus.FAILED
                else:
                    report = self._loop.run_workflow(
                        SkillRequest(
                            request_id=f"{self._request.request_id}-{sub_goal.sub_goal_id}",
                            subject_id=self._request.subject_id,
                            goal_id=self._request.goal_id,
                            input_context=self._request.input_context,
                        ),
                        descriptor,
                    )
                    new_status = (
                        SubGoalStatus.COMPLETED
                        if report.status is WorkflowStatus.COMPLETED
                        else SubGoalStatus.FAILED
                    )
        else:
            # Fail closed until bare sub-goals have an explicit executable handler.
            new_status = SubGoalStatus.FAILED

        return SubGoal(
            sub_goal_id=sub_goal.sub_goal_id,
            goal_id=sub_goal.goal_id,
            description=sub_goal.description,
            status=new_status,
            skill_id=sub_goal.skill_id,
            workflow_id=sub_goal.workflow_id,
            predecessors=sub_goal.predecessors,
        )
