"""Purpose: effect assurance gate for governed reality-changing execution.
Governance scope: pre-dispatch effect planning, simulation request creation,
post-dispatch observation, verification, reconciliation, and graph commit.
Dependencies: effect assurance contracts, execution contracts, verification
contracts, simulation engine, operational graph.
Invariants:
  - No effect-bearing action is committed without reconciliation MATCH.
  - Actual effects are derived from ExecutionResult.actual_effects only.
  - Assumed effects are never promoted into observed effects.
  - Simulation is read-only and never grants execution by itself.
  - Graph commit requires evidence-bearing observed effects.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ObservedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionResult
from mcoi_runtime.contracts.graph import EdgeType, NodeType
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
)
from mcoi_runtime.contracts.verification import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)

from .invariants import RuntimeCoreInvariantError, stable_identifier
from .operational_graph import OperationalGraph
from .simulation import SimulationEngine


_RISK_COST: dict[RiskLevel, float] = {
    RiskLevel.MINIMAL: 0.0,
    RiskLevel.LOW: 100.0,
    RiskLevel.MODERATE: 500.0,
    RiskLevel.HIGH: 2500.0,
    RiskLevel.CRITICAL: 10000.0,
}

_RISK_SUCCESS: dict[RiskLevel, float] = {
    RiskLevel.MINIMAL: 0.98,
    RiskLevel.LOW: 0.9,
    RiskLevel.MODERATE: 0.75,
    RiskLevel.HIGH: 0.55,
    RiskLevel.CRITICAL: 0.25,
}


class EffectAssuranceGate:
    """Mandatory bridge from approved action to evidence-backed commit."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        graph: OperationalGraph | None = None,
        simulation_engine: SimulationEngine | None = None,
    ) -> None:
        self._clock = clock
        self._graph = graph
        self._simulation_engine = simulation_engine

    def create_plan(
        self,
        *,
        command_id: str,
        tenant_id: str,
        capability_id: str,
        expected_effects: tuple[ExpectedEffect, ...],
        forbidden_effects: tuple[str, ...],
        rollback_plan_id: str | None = None,
        compensation_plan_id: str | None = None,
        graph_node_refs: tuple[str, ...] = (),
        graph_edge_refs: tuple[str, ...] = (),
    ) -> EffectPlan:
        """Create an effect plan before dispatch."""
        now = self._clock()
        effect_plan_id = stable_identifier(
            "effect-plan",
            {
                "command_id": command_id,
                "tenant_id": tenant_id,
                "capability_id": capability_id,
                "created_at": now,
            },
        )
        if not graph_node_refs:
            graph_node_refs = (
                f"command:{command_id}",
                f"capability:{capability_id}",
                f"effect_plan:{effect_plan_id}",
            )
        if not graph_edge_refs:
            graph_edge_refs = (
                "command depends_on capability",
                "command produced effect_plan",
            )
        return EffectPlan(
            effect_plan_id=effect_plan_id,
            command_id=command_id,
            tenant_id=tenant_id,
            capability_id=capability_id,
            expected_effects=expected_effects,
            forbidden_effects=forbidden_effects,
            rollback_plan_id=rollback_plan_id,
            compensation_plan_id=compensation_plan_id,
            graph_node_refs=graph_node_refs,
            graph_edge_refs=graph_edge_refs,
            created_at=now,
        )

    def build_simulation_request(
        self,
        plan: EffectPlan,
        *,
        risk_level: RiskLevel,
        estimated_duration_seconds: float = 60.0,
    ) -> SimulationRequest:
        """Project an effect plan into a read-only simulation request."""
        option = SimulationOption(
            option_id=f"effect-option:{plan.effect_plan_id}",
            label=f"dispatch {plan.capability_id}",
            risk_level=risk_level,
            estimated_cost=_RISK_COST[risk_level],
            estimated_duration_seconds=estimated_duration_seconds,
            success_probability=_RISK_SUCCESS[risk_level],
        )
        return SimulationRequest(
            request_id=f"simreq:{plan.effect_plan_id}",
            context_type="command",
            context_id=plan.command_id,
            description="Effect assurance simulation for governed capability dispatch",
            options=(option,),
        )

    def simulate(
        self,
        plan: EffectPlan,
        *,
        risk_level: RiskLevel,
        estimated_duration_seconds: float = 60.0,
    ) -> SimulationVerdict:
        """Run read-only consequence simulation for a planned effect."""
        engine = self._simulation_engine
        if engine is None:
            if self._graph is None:
                raise RuntimeCoreInvariantError("simulation requires a graph or simulation_engine")
            engine = SimulationEngine(graph=self._graph, clock=self._clock)
        request = self.build_simulation_request(
            plan,
            risk_level=risk_level,
            estimated_duration_seconds=estimated_duration_seconds,
        )
        _, verdict = engine.full_simulation(request)
        return verdict

    def observe(self, execution_result: ExecutionResult) -> tuple[ObservedEffect, ...]:
        """Collect observed effects from execution actual_effects only."""
        if not execution_result.actual_effects:
            raise RuntimeCoreInvariantError("actual_effects required for observation")
        observed_at = self._clock()
        observed: list[ObservedEffect] = []
        for index, effect in enumerate(execution_result.actual_effects):
            if not isinstance(effect, EffectRecord):
                raise RuntimeCoreInvariantError("actual_effects must contain EffectRecord values")
            details = _mapping_or_empty(effect.details)
            evidence_ref = str(details.get("evidence_ref") or f"{execution_result.execution_id}:{effect.name}:{index}")
            effect_id = str(details.get("effect_id") or effect.name)
            source = str(details.get("source") or execution_result.execution_id)
            observed_value = details.get("observed_value", effect.details)
            observed.append(
                ObservedEffect(
                    effect_id=effect_id,
                    name=effect.name,
                    source=source,
                    observed_value=observed_value,
                    evidence_ref=evidence_ref,
                    observed_at=observed_at,
                )
            )
        return tuple(observed)

    def verify(
        self,
        *,
        plan: EffectPlan,
        execution_result: ExecutionResult,
        observed_effects: tuple[ObservedEffect, ...],
    ) -> VerificationResult:
        """Verify required expected effects and forbidden effect absence."""
        observed_ids = {effect.effect_id for effect in observed_effects}
        observed_names = {effect.name for effect in observed_effects}
        checks: list[VerificationCheck] = []
        for expected in plan.expected_effects:
            passed = expected.effect_id in observed_ids or expected.name in observed_names
            status = VerificationStatus.PASS if passed or not expected.required else VerificationStatus.FAIL
            checks.append(
                VerificationCheck(
                    name=f"expected:{expected.effect_id}",
                    status=status,
                    details={
                        "effect_id": expected.effect_id,
                        "required": expected.required,
                        "verification_method": expected.verification_method,
                    },
                )
            )
        for forbidden in plan.forbidden_effects:
            absent = forbidden not in observed_ids and forbidden not in observed_names
            checks.append(
                VerificationCheck(
                    name=f"forbidden:{forbidden}",
                    status=VerificationStatus.PASS if absent else VerificationStatus.FAIL,
                    details={"forbidden_effect": forbidden},
                )
            )
        overall = VerificationStatus.PASS
        if any(check.status is VerificationStatus.FAIL for check in checks):
            overall = VerificationStatus.FAIL
        evidence = tuple(
            EvidenceRecord(
                description="Observed effect evidence",
                uri=effect.evidence_ref,
                details={
                    "effect_id": effect.effect_id,
                    "source": effect.source,
                    "observed_at": effect.observed_at,
                },
            )
            for effect in observed_effects
        )
        if not evidence:
            evidence = (
                EvidenceRecord(
                    description="No observed effects available",
                    uri=f"execution:{execution_result.execution_id}",
                    details={"effect_plan_id": plan.effect_plan_id},
                ),
            )
        return VerificationResult(
            verification_id=stable_identifier(
                "effect-verification",
                {
                    "plan": plan.effect_plan_id,
                    "execution": execution_result.execution_id,
                    "closed_at": self._clock(),
                },
            ),
            execution_id=execution_result.execution_id,
            status=overall,
            checks=tuple(checks),
            evidence=evidence,
            closed_at=self._clock(),
            metadata={
                "command_id": plan.command_id,
                "effect_plan_id": plan.effect_plan_id,
            },
        )

    def reconcile(
        self,
        *,
        plan: EffectPlan,
        observed_effects: tuple[ObservedEffect, ...],
        verification_result: VerificationResult | None,
        case_id: str | None = None,
    ) -> EffectReconciliation:
        """Compare planned and observed effects into a terminal status."""
        observed_keys = {effect.effect_id for effect in observed_effects} | {effect.name for effect in observed_effects}
        required = tuple(effect for effect in plan.expected_effects if effect.required)
        matched = tuple(
            effect.effect_id
            for effect in plan.expected_effects
            if effect.effect_id in observed_keys or effect.name in observed_keys
        )
        missing = tuple(
            effect.effect_id
            for effect in required
            if effect.effect_id not in observed_keys and effect.name not in observed_keys
        )
        forbidden = set(plan.forbidden_effects)
        unexpected = tuple(
            sorted(
                effect.effect_id
                for effect in observed_effects
                if effect.effect_id in forbidden or effect.name in forbidden
            )
        )
        if not observed_effects:
            status = ReconciliationStatus.UNKNOWN
        elif unexpected:
            status = ReconciliationStatus.MISMATCH
        elif missing:
            status = ReconciliationStatus.PARTIAL_MATCH if matched else ReconciliationStatus.MISMATCH
        elif verification_result is not None and verification_result.status is VerificationStatus.FAIL:
            status = ReconciliationStatus.MISMATCH
        else:
            status = ReconciliationStatus.MATCH
        decided_at = self._clock()
        return EffectReconciliation(
            reconciliation_id=stable_identifier(
                "effect-reconciliation",
                {
                    "plan": plan.effect_plan_id,
                    "status": status.value,
                    "decided_at": decided_at,
                },
            ),
            command_id=plan.command_id,
            effect_plan_id=plan.effect_plan_id,
            status=status,
            matched_effects=matched,
            missing_effects=missing,
            unexpected_effects=unexpected,
            verification_result_id=(
                verification_result.verification_id if verification_result is not None else None
            ),
            case_id=case_id,
            decided_at=decided_at,
        )

    def commit_graph(
        self,
        *,
        plan: EffectPlan,
        observed_effects: tuple[ObservedEffect, ...],
        reconciliation: EffectReconciliation,
    ) -> None:
        """Commit a reconciled action to the operational graph."""
        if self._graph is None:
            raise RuntimeCoreInvariantError("graph commit requires graph")
        if reconciliation.status is not ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("graph commit requires reconciliation MATCH")
        if not observed_effects:
            raise RuntimeCoreInvariantError("graph commit requires observed effects")

        command_node = self._graph.ensure_node(
            f"command:{plan.command_id}",
            NodeType.JOB,
            f"Command {plan.command_id}",
        )
        capability_node = self._graph.ensure_node(
            f"capability:{plan.capability_id}",
            NodeType.FUNCTION,
            f"Capability {plan.capability_id}",
        )
        verification_node = self._graph.ensure_node(
            f"verification:{reconciliation.verification_result_id}",
            NodeType.VERIFICATION,
            f"Effect verification {reconciliation.verification_result_id}",
        )
        self._graph.add_edge(EdgeType.DEPENDS_ON, command_node.node_id, capability_node.node_id)
        self._graph.add_edge(EdgeType.VERIFIED_BY, command_node.node_id, verification_node.node_id)
        for effect in observed_effects:
            evidence_node = self._graph.ensure_node(
                f"evidence:{effect.evidence_ref}",
                NodeType.DOCUMENT,
                f"Evidence {effect.evidence_ref}",
            )
            provider_node = self._graph.ensure_node(
                f"provider_action:{effect.effect_id}",
                NodeType.PROVIDER_ACTION,
                f"Observed effect {effect.name}",
            )
            self._graph.add_edge(EdgeType.PRODUCED, command_node.node_id, provider_node.node_id)
            self._graph.add_evidence_link(provider_node.node_id, evidence_node.node_id, "observed_effect", 1.0)
            self._graph.add_edge(EdgeType.VERIFIED_BY, provider_node.node_id, verification_node.node_id)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
