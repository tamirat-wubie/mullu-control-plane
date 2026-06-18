"""Dependency-gated adapter for the existing SNet recursive inquiry prototype.

The existing SNet symbol settlement remains a local inquiry status. This adapter
issues no component certificate until every promoted child required by the
current tick has produced a boundary-reconciled projection certificate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from ..contracts import (
    Candidate,
    ComponentContract,
    ComponentProjectionRequest,
    ConvergenceMode,
    ConvergencePolicy,
    DependencyGate,
    DependencyRelation,
    EvidenceScope,
    Need,
    SettlementLevel,
    ValidationJudgment,
    stable_hash,
)
from ..kernel import BaseConvergentComponent, RecursiveConvergenceOrchestrationKernel


SNET_COMPONENT_PREFIX = "snet-symbol:"
SNET_SYMBOL_PROJECTION = "symbol_projection"


class SNetDependencyGatedComponent(BaseConvergentComponent):
    """Expose one SNet symbol as a recursively settled convergence component."""

    def __init__(
        self,
        *,
        mesh: Any,
        symbol_id: str,
        answer_provider: Callable[[Any], Mapping[Any, str]],
        perspective: str = "general",
        context: str = "general",
    ) -> None:
        if symbol_id not in mesh.symbols:
            raise ValueError(f"unknown SNet symbol_id: {symbol_id}")
        self.mesh = mesh
        self.symbol_id = symbol_id
        self.answer_provider = answer_provider
        self.perspective = perspective
        self.context = context
        self.contract = ComponentContract(
            component_id=f"{SNET_COMPONENT_PREFIX}{symbol_id}",
            purpose="Recursively settle one SNet symbol after required promoted children settle",
            schema_version="snet-dependency-gated.v1",
            rule_version=str(getattr(mesh, "semantics_hash", "snet-runtime")),
            output_projections=(SNET_SYMBOL_PROJECTION,),
            immutable_invariants=(
                "symbol_identity_is_stable",
                "raw_answers_are_not_exposed_by_projection",
            ),
            local_invariants=(
                "unknowns_remain_first_class",
                "contradictions_are_not_silently_deleted",
            ),
            boundary_contracts=(
                "required_promoted_children_are_boundary_reconciled",
            ),
            convergence_policy=ConvergencePolicy(
                mode=ConvergenceMode.BOUNDED_SEARCH,
                maximum_iterations=max(1, int(getattr(mesh.budget, "max_depth", 3)) + 1),
            ),
            maximum_depth=max(0, int(getattr(mesh.budget, "max_depth", 3))),
            evidence_scope=EvidenceScope.MODEL_ONLY,
        )

    def step(self, frame, dependency_view):
        if frame.phase == "start":
            symbol = self.mesh.symbols[self.symbol_id]
            answer_map = self.answer_provider(symbol)
            tick = self.mesh.run_tick_with_answers(
                self.symbol_id,
                answer_map,
                perspective=self.perspective,
                context=self.context,
            )
            promoted_ids = tuple(tick.promoted_symbol_ids)
            state = {
                "tick_id": tick.tick_id,
                "promoted_symbol_ids": promoted_ids,
                "unknown_ids": tuple(tick.unknown_ids),
                "contradiction_ids": tuple(tick.contradiction_ids),
            }
            if promoted_ids:
                requests = tuple(
                    ComponentProjectionRequest(
                        request_id=stable_hash(
                            "snet-child-request",
                            {
                                "parent_symbol_id": self.symbol_id,
                                "child_symbol_id": child_symbol_id,
                                "epoch_id": frame.epoch_id,
                            },
                        ),
                        consumer_component_id=self.contract.component_id,
                        provider_component_id=f"{SNET_COMPONENT_PREFIX}{child_symbol_id}",
                        projection_name=SNET_SYMBOL_PROJECTION,
                        minimum_level=SettlementLevel.BOUNDARY_RECONCILED,
                        gate=DependencyGate.HARD,
                        epoch_id=frame.epoch_id,
                        relation=DependencyRelation.REQUIRES,
                    )
                    for child_symbol_id in promoted_ids
                )
                continuation = replace(
                    frame,
                    phase="integrate_children",
                    resume_token="after_promoted_children",
                    partial_state=state,
                    generation=frame.generation + 1,
                )
                return Need(requests=requests, continuation=continuation)
            return self._candidate(state, dependency_view)

        if frame.phase == "integrate_children":
            expected_ids = tuple(frame.partial_state.get("promoted_symbol_ids", ()))
            for child_symbol_id in expected_ids:
                path = f"{SNET_COMPONENT_PREFIX}{child_symbol_id}/{SNET_SYMBOL_PROJECTION}"
                if path not in dependency_view:
                    raise ValueError("required promoted child certificate is unavailable")
            return self._candidate(dict(frame.partial_state), dependency_view)

        raise ValueError(f"unsupported SNet convergence phase: {frame.phase}")

    def validate_candidate(self, candidate, dependency_view):
        del candidate, dependency_view
        symbol = self.mesh.symbols[self.symbol_id]
        settlement_state = str(getattr(symbol.settlement_state, "value", symbol.settlement_state))
        if settlement_state == "contradictory":
            return ValidationJudgment(
                passed=False,
                reasons=("snet_symbol_contains_open_contradiction",),
            )
        return ValidationJudgment(
            passed=True,
            evidence_refs=(f"snet:symbol:{self.symbol_id}",),
        )

    def reconcile_candidate(self, candidate, dependency_view):
        del candidate
        expected_children = tuple(
            self.mesh.symbols[self.symbol_id].metadata.get("required_child_ids", ())
            if hasattr(self.mesh.symbols[self.symbol_id], "metadata")
            else ()
        )
        # The actual dependency set is the certificates supplied by the kernel.
        # Optional metadata can only strengthen, never weaken, that requirement.
        missing = tuple(
            child_id
            for child_id in expected_children
            if f"{SNET_COMPONENT_PREFIX}{child_id}/{SNET_SYMBOL_PROJECTION}" not in dependency_view
        )
        if missing:
            return ValidationJudgment(
                passed=False,
                reasons=("snet_required_child_boundary_missing",),
            )
        return ValidationJudgment(passed=True)

    def _candidate(self, state: Mapping[str, Any], dependency_view):
        symbol = self.mesh.symbols[self.symbol_id]
        child_certificate_ids = tuple(
            certificate.certificate_id
            for _, certificate in sorted(dependency_view.items())
        )
        projection = {
            "symbol_id": symbol.symbol_id,
            "label": symbol.label,
            "symbol_type": symbol.symbol_type,
            "sense_id": symbol.sense_id,
            "depth": symbol.depth,
            "settlement_state": str(getattr(symbol.settlement_state, "value", symbol.settlement_state)),
            "metadata_ref_count": len(symbol.metadata_refs),
            "relation_ref_count": len(symbol.relation_refs),
            "child_certificate_ids": child_certificate_ids,
        }
        return Candidate(
            projections={SNET_SYMBOL_PROJECTION: projection},
            state=state,
            evidence_refs=(f"snet:symbol:{self.symbol_id}",),
            confidence=1.0,
            evidence_scope=EvidenceScope.MODEL_ONLY,
        )


class SNetDependencyGatedComponentFactory:
    """Create SNet component adapters on demand for promoted symbols."""

    def __init__(
        self,
        *,
        mesh: Any,
        answer_provider: Callable[[Any], Mapping[Any, str]],
        perspective: str = "general",
        context: str = "general",
    ) -> None:
        self.mesh = mesh
        self.answer_provider = answer_provider
        self.perspective = perspective
        self.context = context

    def __call__(self, component_id: str, request) -> SNetDependencyGatedComponent:
        del request
        if not component_id.startswith(SNET_COMPONENT_PREFIX):
            raise ValueError("component_id is outside the SNet adapter namespace")
        symbol_id = component_id[len(SNET_COMPONENT_PREFIX) :]
        return SNetDependencyGatedComponent(
            mesh=self.mesh,
            symbol_id=symbol_id,
            answer_provider=self.answer_provider,
            perspective=self.perspective,
            context=self.context,
        )


def run_dependency_gated_snet(
    *,
    mesh: Any,
    root_symbol_id: str,
    answer_provider: Callable[[Any], Mapping[Any, str]],
    epoch_id: str,
    perspective: str = "general",
    context: str = "general",
):
    """Run SNet with parent certificates gated by recursive child settlement."""

    factory = SNetDependencyGatedComponentFactory(
        mesh=mesh,
        answer_provider=answer_provider,
        perspective=perspective,
        context=context,
    )
    root_component_id = f"{SNET_COMPONENT_PREFIX}{root_symbol_id}"
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component_factory(SNET_COMPONENT_PREFIX, factory)
    kernel.register_component(factory(root_component_id, None))
    judgment = kernel.run(
        root_component_id=root_component_id,
        epoch_id=epoch_id,
        root_projections=(SNET_SYMBOL_PROJECTION,),
    )
    return kernel, judgment
