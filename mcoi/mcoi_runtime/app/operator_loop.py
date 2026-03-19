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
from mcoi_runtime.contracts.policy import PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.verification import VerificationResult
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
            return OperatorRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                policy_decision_id=policy_decision.decision_id,
                execution_id=None,
                verification_id=None,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_passed=False,
                validation_error="planning_rejected_inadmissible_knowledge",
                execution_result=None,
                verification_closed=False,
                completed=False,
                verification_error=None,
                dispatched=False,
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
                world_state_hash=_rsf["world_state_hash"],
                world_state_entity_count=_rsf["world_state_entity_count"],
                world_state_contradiction_count=_rsf["world_state_contradiction_count"],
                degraded_capabilities=_rsf["degraded_capabilities"],
                escalation_recommendations=_rsf["escalation_recommendations"],
                provider_count=_rsf["provider_count"],
                unhealthy_providers=_rsf["unhealthy_providers"],
            )

        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return OperatorRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                policy_decision_id=policy_decision.decision_id,
                execution_id=None,
                verification_id=None,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_passed=False,
                validation_error="policy_denied_or_escalated",
                execution_result=None,
                verification_closed=False,
                completed=False,
                verification_error=None,
                dispatched=False,
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
                world_state_hash=_rsf["world_state_hash"],
                world_state_entity_count=_rsf["world_state_entity_count"],
                world_state_contradiction_count=_rsf["world_state_contradiction_count"],
                degraded_capabilities=_rsf["degraded_capabilities"],
                escalation_recommendations=_rsf["escalation_recommendations"],
                provider_count=_rsf["provider_count"],
                unhealthy_providers=_rsf["unhealthy_providers"],
            )

        try:
            self.runtime.template_validator.validate(request.template, request.bindings)
        except TemplateValidationError as exc:
            return OperatorRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                policy_decision_id=policy_decision.decision_id,
                execution_id=None,
                verification_id=None,
                observation_reports=tuple(observation_reports),
                merged_state=merged_state,
                planning_result=planning_result,
                policy_decision=policy_decision,
                validation_passed=False,
                validation_error=f"{exc.code}:{exc}",
                execution_result=None,
                verification_closed=False,
                completed=False,
                verification_error=None,
                dispatched=False,
                structured_errors=(
                    validation_error(
                        error_code=exc.code,
                        message=str(exc),
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                world_state_hash=_rsf["world_state_hash"],
                world_state_entity_count=_rsf["world_state_entity_count"],
                world_state_contradiction_count=_rsf["world_state_contradiction_count"],
                degraded_capabilities=_rsf["degraded_capabilities"],
                escalation_recommendations=_rsf["escalation_recommendations"],
                provider_count=_rsf["provider_count"],
                unhealthy_providers=_rsf["unhealthy_providers"],
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
        self._register_execution_entity(request, execution_result, route)

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
        )

    def run_skill(self, request: SkillRequest) -> SkillRunReport:
        """Execute a skill through the governed runtime path.

        1. Resolve skill (by ID or select from registry)
        2. Check policy for the skill
        3. Execute through SkillExecutor with a governed step executor
        4. Update capability confidence from outcome
        5. Return structured report
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

        # Step 2: execute with governed step executor
        governed_executor = _GovernedStepExecutor(runtime=self.runtime)
        record = executor.execute(
            skill,
            step_executor=governed_executor,
            input_context=dict(request.input_context) if request.input_context else None,
        )

        # Step 3: update skill confidence
        succeeded = record.outcome.status is SkillOutcomeStatus.SUCCEEDED
        existing = skill.confidence
        new_confidence = min(1.0, existing + 0.1) if succeeded else max(0.0, existing - 0.1)
        registry.update_confidence(skill.skill_id, round(new_confidence, 4))

        # Step 4: lifecycle promotion on first success
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
        }

    def _register_execution_entity(
        self,
        request: OperatorRequest,
        execution_result: ExecutionResult,
        route: str,
    ) -> None:
        """Register the execution outcome as a world-state entity."""
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
        except (RuntimeCoreInvariantError, ValueError):
            pass  # Entity registration is best-effort — duplicate or validation errors are expected

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
        except Exception as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"dispatch_error:{exc}",
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
