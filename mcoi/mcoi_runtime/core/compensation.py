"""Purpose: compensation assurance runtime for unresolved effect gaps.
Governance scope: plan admission, injected dispatch, observation, verification,
reconciliation, and graph anchoring for recovery effects.
Dependencies: compensation contracts, effect assurance, execution contracts,
operational graph.
Invariants:
  - Compensation requires an unresolved original reconciliation.
  - Compensation dispatch is injected; this runtime performs no provider IO.
  - Compensation succeeds only when its own effect reconciliation is MATCH.
  - Every compensation outcome carries evidence references.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from mcoi_runtime.contracts.compensation import (
    CompensationAttempt,
    CompensationKind,
    CompensationOutcome,
    CompensationPlan,
    CompensationStatus,
)
from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.graph import EdgeType, NodeType

from .effect_assurance import EffectAssuranceGate
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .operational_graph import OperationalGraph


class CompensationDispatcher(Protocol):
    """Callable protocol for side-effecting compensation providers."""

    def __call__(self, plan: CompensationPlan) -> ExecutionResult:
        """Dispatch compensation and return observed execution effects."""
        ...


_UNRESOLVED_STATUSES = (
    ReconciliationStatus.PARTIAL_MATCH,
    ReconciliationStatus.MISMATCH,
    ReconciliationStatus.UNKNOWN,
)


class CompensationAssuranceGate:
    """Create and verify compensation for unresolved reality changes."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        effect_gate: EffectAssuranceGate,
        graph: OperationalGraph | None = None,
    ) -> None:
        self._clock = clock
        self._effect_gate = effect_gate
        self._graph = graph
        self._plans: dict[str, CompensationPlan] = {}
        self._attempts: dict[str, CompensationAttempt] = {}
        self._outcomes: dict[str, CompensationOutcome] = {}

    @property
    def outcome_count(self) -> int:
        """Return total compensation outcomes."""
        return len(self._outcomes)

    def get_outcome(self, outcome_id: str) -> CompensationOutcome | None:
        """Return one compensation outcome."""
        ensure_non_empty_text("outcome_id", outcome_id)
        return self._outcomes.get(outcome_id)

    def create_plan(
        self,
        *,
        original_plan: EffectPlan,
        original_reconciliation: EffectReconciliation,
        capability_id: str,
        approval_id: str,
        expected_effects: tuple[str, ...],
        forbidden_effects: tuple[str, ...],
        evidence_required: tuple[str, ...],
        kind: CompensationKind = CompensationKind.COMPENSATION,
        case_id: str | None = None,
    ) -> CompensationPlan:
        """Create an approved compensation plan for an unresolved reconciliation."""
        if original_reconciliation.command_id != original_plan.command_id:
            raise RuntimeCoreInvariantError("compensation requires matching command identity")
        if original_reconciliation.effect_plan_id != original_plan.effect_plan_id:
            raise RuntimeCoreInvariantError("compensation requires matching effect plan identity")
        if original_reconciliation.status not in _UNRESOLVED_STATUSES:
            raise RuntimeCoreInvariantError("compensation requires unresolved reconciliation")
        effective_case_id = case_id or original_reconciliation.case_id
        if not effective_case_id:
            raise RuntimeCoreInvariantError("compensation requires a case_id")
        now = self._clock()
        plan = CompensationPlan(
            compensation_plan_id=stable_identifier(
                "compensation-plan",
                {
                    "command_id": original_plan.command_id,
                    "reconciliation_id": original_reconciliation.reconciliation_id,
                    "capability_id": capability_id,
                    "created_at": now,
                },
            ),
            command_id=original_plan.command_id,
            effect_plan_id=original_plan.effect_plan_id,
            reconciliation_id=original_reconciliation.reconciliation_id,
            case_id=effective_case_id,
            capability_id=capability_id,
            kind=kind,
            approval_id=approval_id,
            expected_effects=expected_effects,
            forbidden_effects=forbidden_effects,
            evidence_required=evidence_required,
            created_at=now,
            metadata={"original_status": original_reconciliation.status.value},
        )
        self._plans[plan.compensation_plan_id] = plan
        return plan

    def execute(
        self,
        plan: CompensationPlan,
        *,
        dispatch: CompensationDispatcher,
    ) -> tuple[CompensationAttempt, CompensationOutcome]:
        """Dispatch compensation through an injected provider and verify effects."""
        started_at = self._clock()
        execution_result = dispatch(plan)
        observed = self._effect_gate.observe(execution_result)
        compensation_effect_plan = self._effect_gate.create_plan(
            command_id=plan.command_id,
            tenant_id=str(execution_result.metadata.get("tenant_id", "compensation")),
            capability_id=plan.capability_id,
            expected_effects=tuple(
                ExpectedEffect(
                    effect_id=effect_name,
                    name=effect_name,
                    target_ref=f"compensation:{plan.compensation_plan_id}",
                    required=True,
                    verification_method="compensation_observation",
                )
                for effect_name in plan.expected_effects
            ),
            forbidden_effects=plan.forbidden_effects,
            compensation_plan_id=plan.compensation_plan_id,
            graph_node_refs=(
                f"command:{plan.command_id}",
                f"compensation:{plan.compensation_plan_id}",
            ),
            graph_edge_refs=("command produced compensation",),
        )
        verification = self._effect_gate.verify(
            plan=compensation_effect_plan,
            execution_result=execution_result,
            observed_effects=observed,
        )
        reconciliation = self._effect_gate.reconcile(
            plan=compensation_effect_plan,
            observed_effects=observed,
            verification_result=verification,
            case_id=plan.case_id,
        )
        evidence_refs = tuple(effect.evidence_ref for effect in observed)
        finished_at = self._clock()
        attempt = CompensationAttempt(
            attempt_id=stable_identifier(
                "compensation-attempt",
                {
                    "plan": plan.compensation_plan_id,
                    "execution": execution_result.execution_id,
                    "finished_at": finished_at,
                },
            ),
            compensation_plan_id=plan.compensation_plan_id,
            command_id=plan.command_id,
            execution_id=execution_result.execution_id,
            started_at=started_at,
            finished_at=finished_at,
            evidence_refs=evidence_refs,
            metadata={"verification_result_id": verification.verification_id},
        )
        status = (
            CompensationStatus.SUCCEEDED
            if reconciliation.status is ReconciliationStatus.MATCH
            else CompensationStatus.REQUIRES_REVIEW
        )
        outcome = CompensationOutcome(
            outcome_id=stable_identifier(
                "compensation-outcome",
                {
                    "attempt": attempt.attempt_id,
                    "status": status.value,
                    "decided_at": finished_at,
                },
            ),
            compensation_plan_id=plan.compensation_plan_id,
            attempt_id=attempt.attempt_id,
            command_id=plan.command_id,
            status=status,
            verification_result_id=verification.verification_id,
            reconciliation_id=reconciliation.reconciliation_id,
            evidence_refs=evidence_refs,
            decided_at=finished_at,
            case_id=None if status is CompensationStatus.SUCCEEDED else plan.case_id,
            metadata={
                "compensation_reconciliation_status": reconciliation.status.value,
                "approval_id": plan.approval_id,
            },
        )
        self._attempts[attempt.attempt_id] = attempt
        self._outcomes[outcome.outcome_id] = outcome
        if self._graph is not None:
            self.anchor_to_graph(plan=plan, attempt=attempt, outcome=outcome)
        return attempt, outcome

    def anchor_to_graph(
        self,
        *,
        plan: CompensationPlan,
        attempt: CompensationAttempt,
        outcome: CompensationOutcome,
    ) -> None:
        """Anchor compensation plan, attempt, outcome, and evidence to graph."""
        if self._graph is None:
            raise RuntimeCoreInvariantError("compensation graph anchoring requires graph")
        command_node = self._graph.ensure_node(
            f"command:{plan.command_id}",
            NodeType.JOB,
            f"Command {plan.command_id}",
        )
        plan_node = self._graph.ensure_node(
            f"compensation_plan:{plan.compensation_plan_id}",
            NodeType.RUNBOOK,
            f"Compensation plan {plan.compensation_plan_id}",
        )
        attempt_node = self._graph.ensure_node(
            f"compensation_attempt:{attempt.attempt_id}",
            NodeType.PROVIDER_ACTION,
            f"Compensation attempt {attempt.attempt_id}",
        )
        outcome_node = self._graph.ensure_node(
            f"compensation_outcome:{outcome.outcome_id}",
            NodeType.VERIFICATION,
            f"Compensation outcome {outcome.status.value}",
        )
        approval_node = self._graph.ensure_node(
            f"approval:{plan.approval_id}",
            NodeType.APPROVAL,
            f"Compensation approval {plan.approval_id}",
        )
        self._graph.add_edge(EdgeType.DECIDED_BY, plan_node.node_id, approval_node.node_id)
        self._graph.add_edge(EdgeType.PRODUCED, command_node.node_id, plan_node.node_id)
        self._graph.add_edge(EdgeType.PRODUCED, plan_node.node_id, attempt_node.node_id)
        self._graph.add_edge(EdgeType.VERIFIED_BY, attempt_node.node_id, outcome_node.node_id)
        for evidence_ref in outcome.evidence_refs:
            evidence_node = self._graph.ensure_node(
                f"evidence:{evidence_ref}",
                NodeType.DOCUMENT,
                f"Compensation evidence {evidence_ref}",
            )
            self._graph.add_evidence_link(outcome_node.node_id, evidence_node.node_id, "compensation", 1.0)
