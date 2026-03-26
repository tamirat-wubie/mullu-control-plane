"""Purpose: run one explicit operator request through the MCOI runtime boundaries.
Governance scope: operator-loop single-step orchestration only.
Dependencies: local bootstrap wiring, observer adapters, runtime-core boundaries, and governed entry helpers.
Invariants: request handling is single-step, ordered, deterministic, and never marks execution complete without explicit verification closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.adapters.observer_base import ObservationResult, ObservationStatus
from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.goal import GoalDescriptor
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.policy import PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.provider import ProviderClass, ProviderHealthStatus
from mcoi_runtime.contracts.world_state import StateEntity
from mcoi_runtime.contracts.workflow import WorkflowDescriptor
from mcoi_runtime.core.errors import (
    Recoverability,
    SourcePlane,
    StructuredError,
    admissibility_error,
    execution_error,
    policy_error,
    validation_error,
    verification_error,
)
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceState
from mcoi_runtime.app.governed_execution import governed_operator_dispatch
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.planning_boundary import PlanningBoundaryResult
from mcoi_runtime.core.policy_engine import PolicyInput
from mcoi_runtime.core.template_validator import TemplateValidationError

from .bootstrap import BootstrappedRuntime, build_policy_decision
from .operator_models import (
    GoalRunReport,
    ObservationDirective,
    ObservationReport,
    OperatorRequest,
    OperatorRunReport,
    SkillRequest,
    SkillRunReport,
    WorkflowRunReport,
)
from .operator_runners import run_goal, run_skill, run_workflow


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

        runtime_state_fields = self._runtime_state_fields()

        if planning_result.rejected:
            rejected_ids = tuple(result.knowledge_id for result in planning_result.rejected)
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
                                result.knowledge_id: str(result.reason)
                                for result in planning_result.rejected
                            },
                        },
                    ),
                ),
                runtime_state_fields=runtime_state_fields,
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
                runtime_state_fields=runtime_state_fields,
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
                runtime_state_fields=runtime_state_fields,
            )

        if hasattr(self.runtime, 'governed_dispatcher') and self.runtime.governed_dispatcher is not None:
            execution_result = governed_operator_dispatch(
                self.runtime.governed_dispatcher,
                DispatchRequest(
                    goal_id=request.goal_id,
                    route=str(request.template.get("action_type", "")),
                    template=request.template,
                    bindings=request.bindings,
                ),
                actor_id="operator_main",
            )
        else:
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

        route = str(request.template.get("action_type", "unknown"))
        entity_registration_error = self._register_execution_entity(
            request,
            execution_result,
            route,
        )
        if entity_registration_error is not None:
            errors.append(entity_registration_error)

        self._update_capability_confidence(route, execution_result, verification_closure)

        world_state = self.runtime.world_state
        meta_reasoning = self.runtime.meta_reasoning

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
            world_state_hash=world_state.snapshot_hash(),
            world_state_entity_count=world_state.entity_count,
            world_state_contradiction_count=len(world_state.list_unresolved_contradictions()),
            degraded_capabilities=tuple(
                degradation.capability_id for degradation in meta_reasoning.list_degraded()
            ),
            escalation_recommendations=tuple(
                recommendation.reason
                for recommendation in meta_reasoning.list_escalation_recommendations()
            ),
            provider_count=len(self.runtime.provider_registry.list_providers()),
            unhealthy_providers=tuple(
                provider.provider_id
                for provider in self.runtime.provider_registry.list_providers()
                if (
                    health := self.runtime.provider_registry.get_health(provider.provider_id)
                ) is not None
                and health.status
                in (ProviderHealthStatus.DEGRADED, ProviderHealthStatus.UNAVAILABLE)
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
        """Construct a deterministic blocked-run report."""
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
        return run_skill(self, request)

    def run_workflow(
        self,
        request: SkillRequest,
        workflow_descriptor: WorkflowDescriptor,
    ) -> WorkflowRunReport:
        return run_workflow(self, request, workflow_descriptor)

    def run_goal(
        self,
        request: SkillRequest,
        goal_descriptor: GoalDescriptor,
    ) -> GoalRunReport:
        return run_goal(self, request, goal_descriptor)

    def _runtime_state_fields(self) -> dict[str, object]:
        """Capture current world-state, meta-reasoning, and provider state for reports."""
        world_state = self.runtime.world_state
        meta_reasoning = self.runtime.meta_reasoning
        provider_registry = self.runtime.provider_registry
        return {
            "world_state_hash": world_state.snapshot_hash() if world_state.entity_count > 0 else None,
            "world_state_entity_count": world_state.entity_count,
            "world_state_contradiction_count": len(world_state.list_unresolved_contradictions()),
            "degraded_capabilities": tuple(
                degradation.capability_id for degradation in meta_reasoning.list_degraded()
            ),
            "escalation_recommendations": tuple(
                recommendation.reason
                for recommendation in meta_reasoning.list_escalation_recommendations()
            ),
            "provider_count": len(provider_registry.list_providers()),
            "unhealthy_providers": tuple(
                provider.provider_id
                for provider in provider_registry.list_providers()
                if (
                    health := provider_registry.get_health(provider.provider_id)
                ) is not None
                and health.status
                in (ProviderHealthStatus.DEGRADED, ProviderHealthStatus.UNAVAILABLE)
            ),
            "autonomy_mode": self.runtime.autonomy.mode.value,
            **self._resolve_provider_ids(),
        }

    def _resolve_provider_ids(self) -> dict[str, str | None]:
        """Resolve the first healthy provider ID per class for run reports."""
        provider_registry = self.runtime.provider_registry
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
        for provider_class, field_name in field_map.items():
            providers = provider_registry.list_providers(
                provider_class=provider_class,
                enabled_only=True,
            )
            for provider in providers:
                health = provider_registry.get_health(provider.provider_id)
                if health is not None and health.status is ProviderHealthStatus.HEALTHY:
                    result[field_name] = provider.provider_id
                    break
        return result

    def _register_execution_entity(
        self,
        request: OperatorRequest,
        execution_result: ExecutionResult,
        route: str,
    ) -> StructuredError | None:
        """Register the execution outcome as a world-state entity."""
        entity_id = stable_identifier(
            "entity",
            {
                "execution_id": execution_result.execution_id,
                "goal_id": request.goal_id,
            },
        )
        try:
            self.runtime.world_state.add_entity(
                StateEntity(
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
                    confidence=1.0
                    if execution_result.status is ExecutionOutcome.SUCCEEDED
                    else 0.5,
                    created_at=execution_result.finished_at,
                )
            )
            return None
        except (RuntimeCoreInvariantError, ValueError) as exc:
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
        """Update meta-reasoning capability confidence from execution and verification."""
        existing = self.runtime.meta_reasoning.get_confidence(capability_id)
        sample_count = (existing.sample_count + 1) if existing else 1
        old_success = existing.success_rate if existing else 0.0
        old_verify = existing.verification_pass_rate if existing else 0.0
        old_error = existing.error_rate if existing else 0.0

        succeeded = execution_result.status is ExecutionOutcome.SUCCEEDED
        verified = getattr(verification_closure, "verification_closed", False) and getattr(
            verification_closure,
            "completed",
            False,
        )
        errored = execution_result.status is ExecutionOutcome.FAILED

        weight = 1.0 / sample_count
        new_success = old_success * (1 - weight) + (1.0 if succeeded else 0.0) * weight
        new_verify = old_verify * (1 - weight) + (1.0 if verified else 0.0) * weight
        new_error = old_error * (1 - weight) + (1.0 if errored else 0.0) * weight

        self.runtime.meta_reasoning.update_confidence(
            CapabilityConfidence(
                capability_id=capability_id,
                success_rate=round(new_success, 4),
                verification_pass_rate=round(new_verify, 4),
                timeout_rate=0.0,
                error_rate=round(new_error, 4),
                sample_count=sample_count,
                assessed_at=self.runtime.clock(),
            )
        )

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


__all__ = [
    "GoalRunReport",
    "ObservationDirective",
    "ObservationReport",
    "OperatorLoop",
    "OperatorRequest",
    "OperatorRunReport",
    "SkillRequest",
    "SkillRunReport",
    "WorkflowRunReport",
]
