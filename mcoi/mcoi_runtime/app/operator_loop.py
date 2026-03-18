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
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceState, EvidenceStateCategory
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.planning_boundary import PlanningBoundaryResult, PlanningKnowledge
from mcoi_runtime.core.policy_engine import PolicyInput
from mcoi_runtime.core.template_validator import TemplateValidationError

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
class ObservationReport:
    observer_route: str
    status: ObservationStatus
    state_key: str
    evidence_count: int
    failure_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperatorRunReport:
    request_id: str
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

        if planning_result.rejected:
            return OperatorRunReport(
                request_id=request.request_id,
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
            )

        if policy_decision.status is not PolicyDecisionStatus.ALLOW:
            return OperatorRunReport(
                request_id=request.request_id,
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
            )

        try:
            self.runtime.template_validator.validate(request.template, request.bindings)
        except TemplateValidationError as exc:
            return OperatorRunReport(
                request_id=request.request_id,
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
        return OperatorRunReport(
            request_id=request.request_id,
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
