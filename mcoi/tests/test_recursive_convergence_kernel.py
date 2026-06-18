"""End-to-end verification for the CDG-RCCM reference runtime.

The suite covers recursive dependency settlement, continuation-local waiting,
shared providers, exact projections, causal invalidation, active closure,
semantic feedback, oscillation, persistence, effect barriers, SNet adaptation,
and Universal Action handoff.
"""

from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, Callable, Mapping

import pytest

from mcoi_runtime.contracts.snet import SNetInquiryBudget, SNetWHType
from mcoi_runtime.snet.engine import SNetRecursiveMesh
from mcoi_runtime.convergence import (
    BaseConvergentComponent,
    Candidate,
    ClosureGatedEffectCommitter,
    ComponentContract,
    ComponentProjectionRequest,
    ContainmentGraph,
    ContinuationFrame,
    ConvergenceMode,
    ConvergencePolicy,
    DependencyGate,
    DependencyRelation,
    EffectPlan,
    EffectStatus,
    EvidenceScope,
    Need,
    OutcomeCode,
    ProjectionCertificate,
    RecursiveConvergenceOrchestrationKernel,
    SettlementLevel,
    Unknown,
    WorldObservation,
    dump_kernel_snapshot,
    issue_world_verified_certificate,
    restore_kernel_snapshot,
    stable_hash,
)
from mcoi_runtime.convergence.adapters.snet import (
    SNET_COMPONENT_PREFIX,
    run_dependency_gated_snet,
)
from mcoi_runtime.convergence.adapters.universal_action import (
    UniversalActionClosureAdapter,
)


EPOCH = "epoch:test:1"


def _contract(
    component_id: str,
    *,
    outputs: tuple[str, ...] = ("value",),
    mode: ConvergenceMode = ConvergenceMode.BOUNDED_SEARCH,
    maximum_iterations: int = 32,
) -> ComponentContract:
    return ComponentContract(
        component_id=component_id,
        purpose=f"Test component {component_id}",
        schema_version="test-component.v1",
        rule_version="test-rules.v1",
        output_projections=outputs,
        immutable_invariants=("identity_stable",),
        local_invariants=("candidate_valid",),
        boundary_contracts=("dependency_certificates_current",),
        convergence_policy=ConvergencePolicy(
            mode=mode,
            maximum_iterations=maximum_iterations,
            oscillation_detection=True,
        ),
    )


class StaticProjectionComponent(BaseConvergentComponent):
    def __init__(self, component_id: str, values: Mapping[str, Any]) -> None:
        self.contract = _contract(component_id, outputs=tuple(values))
        self.values = dict(values)
        self.calls = 0
        self.seen_targets: list[tuple[str, ...]] = []

    def step(self, frame: ContinuationFrame, dependency_view):
        del dependency_view
        self.calls += 1
        self.seen_targets.append(frame.target_projections)
        return Candidate(
            projections={name: self.values[name] for name in frame.target_projections},
            state={"calls": self.calls},
            evidence_refs=(f"evidence:{self.contract.component_id}",),
        )


class DependencyComponent(BaseConvergentComponent):
    def __init__(
        self,
        component_id: str,
        dependencies: tuple[tuple[str, str], ...],
        combine: Callable[[tuple[Any, ...]], Any],
        *,
        output_projection: str = "value",
        spawned_component: BaseConvergentComponent | None = None,
    ) -> None:
        self.contract = _contract(component_id, outputs=(output_projection,))
        self.dependencies = dependencies
        self.combine = combine
        self.output_projection = output_projection
        self.spawned_component = spawned_component
        self.calls = 0
        self.views: list[tuple[str, ...]] = []

    def step(self, frame: ContinuationFrame, dependency_view):
        self.calls += 1
        self.views.append(tuple(sorted(dependency_view)))
        if frame.phase == "start":
            requests = tuple(
                ComponentProjectionRequest(
                    request_id=stable_hash(
                        "test-request",
                        {
                            "consumer": self.contract.component_id,
                            "provider": provider,
                            "projection": projection,
                            "epoch": frame.epoch_id,
                        },
                    ),
                    consumer_component_id=self.contract.component_id,
                    provider_component_id=provider,
                    projection_name=projection,
                    minimum_level=SettlementLevel.BOUNDARY_RECONCILED,
                    gate=DependencyGate.HARD,
                    epoch_id=frame.epoch_id,
                    relation=DependencyRelation.REQUIRES,
                )
                for provider, projection in self.dependencies
            )
            continuation = replace(
                frame,
                phase="integrate",
                resume_token="after_dependencies",
                generation=frame.generation + 1,
            )
            spawned_frames = ()
            if self.spawned_component is not None:
                spawned_frames = (
                    self.spawned_component.initial_frame(
                        epoch_id=frame.epoch_id,
                        root_component_id=frame.root_component_id,
                        target_projections=(
                            self.spawned_component.contract.output_projections[0],
                        ),
                        depth=frame.depth,
                        parent_frame_id=frame.frame_id,
                    ),
                )
            return Need(
                requests=requests,
                continuation=continuation,
                spawned_frames=spawned_frames,
            )

        values = tuple(
            dependency_view[f"{provider}/{projection}"].value
            for provider, projection in self.dependencies
        )
        return Candidate(
            projections={self.output_projection: self.combine(values)},
            state={"dependency_values": values},
            evidence_refs=(f"evidence:{self.contract.component_id}",),
        )


class FeedbackComponent(BaseConvergentComponent):
    def __init__(self, component_id: str, peer_id: str, *, oscillating: bool = False) -> None:
        self.contract = _contract(
            component_id,
            mode=ConvergenceMode.FINITE_MONOTONE,
            maximum_iterations=12,
        )
        self.peer_id = peer_id
        self.oscillating = oscillating

    def step(self, frame: ContinuationFrame, dependency_view):
        if frame.phase == "start":
            request = ComponentProjectionRequest(
                request_id=stable_hash(
                    "feedback-request",
                    {
                        "consumer": self.contract.component_id,
                        "provider": self.peer_id,
                        "epoch": frame.epoch_id,
                    },
                ),
                consumer_component_id=self.contract.component_id,
                provider_component_id=self.peer_id,
                projection_name="value",
                minimum_level=SettlementLevel.BOUNDARY_RECONCILED,
                gate=DependencyGate.HARD,
                epoch_id=frame.epoch_id,
                relation=DependencyRelation.CONSTRAINS,
            )
            return Need(
                requests=(request,),
                continuation=replace(
                    frame,
                    phase="integrate",
                    resume_token="after_feedback_region",
                    generation=frame.generation + 1,
                ),
            )
        value = dependency_view[f"{self.peer_id}/value"].value
        return Candidate(
            projections={"value": value},
            state={"peer_value": value},
            evidence_refs=(f"feedback:{self.contract.component_id}",),
        )

    def region_seed(self, projection_name: str) -> int:
        assert projection_name == "value"
        return 0

    def region_step(self, values: Mapping[str, Any], generation: int) -> Candidate:
        del generation
        peer_value = int(values[f"{self.peer_id}/value"])
        value = 1 - peer_value if self.oscillating else min(2, peer_value + 1)
        return Candidate(
            projections={"value": value},
            state={"peer_value": peer_value},
            evidence_refs=(f"feedback:{self.contract.component_id}",),
        )


def _closure_certificate(
    *,
    component_id: str = "root",
    projection_name: str = "value",
    value: Any = 1,
    level: SettlementLevel = SettlementLevel.CLOSURE_CERTIFIED,
) -> ProjectionCertificate:
    payload = {
        "component_id": component_id,
        "projection_name": projection_name,
        "value": value,
        "level": int(level),
    }
    return ProjectionCertificate(
        certificate_id=stable_hash("test-certificate", payload),
        component_id=component_id,
        projection_name=projection_name,
        level=level,
        epoch_id=EPOCH,
        state_hash=stable_hash("test-state", value),
        rule_hash=stable_hash("test-rule", "v1"),
        input_hash=stable_hash("test-input", "v1"),
        dependency_certificate_ids=(),
        assumptions=(),
        evidence_refs=("evidence:test",),
        evidence_scope=EvidenceScope.MODEL_ONLY,
        confidence=1.0,
        value=value,
        audit_digest=stable_hash("test-audit", payload),
    )


def test_deep_recursive_dependencies_certify_children_before_parent() -> None:
    leaf = StaticProjectionComponent("leaf", {"value": 2})
    middle = DependencyComponent("middle", (("leaf", "value"),), lambda values: values[0] + 1)
    root = DependencyComponent("root", (("middle", "value"),), lambda values: values[0] + 1)
    kernel = RecursiveConvergenceOrchestrationKernel()
    for component in (root, middle, leaf):
        kernel.register_component(component)

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    closure = kernel.certificates[judgment.certificate_ids[0]]
    assert closure.level is SettlementLevel.CLOSURE_CERTIFIED
    assert closure.value == 4
    assert kernel.active_required_closure() == ("leaf", "middle", "root")
    certified_events = [
        event
        for event in kernel.audit_events
        if event.event_type == "frame_candidate_certified"
    ]
    certified_order = [event.component_id for event in certified_events]
    assert certified_order.index("leaf") < certified_order.index("middle") < certified_order.index("root")


def test_blocked_frame_does_not_prevent_independent_spawned_work() -> None:
    leaf = StaticProjectionComponent("leaf", {"value": 3})
    side = StaticProjectionComponent("side", {"value": 99})
    root = DependencyComponent(
        "root",
        (("leaf", "value"),),
        lambda values: values[0],
        spawned_component=side,
    )
    kernel = RecursiveConvergenceOrchestrationKernel()
    for component in (root, leaf, side):
        kernel.register_component(component)

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    assert side.calls == 1
    side_event = next(
        event for event in kernel.audit_events
        if event.component_id == "side" and event.event_type == "frame_candidate_certified"
    )
    root_resume = next(
        event for event in kernel.audit_events
        if event.component_id == "root" and event.event_type == "frame_resumed"
    )
    assert side_event.sequence < root_resume.sequence


def test_exact_projection_request_does_not_require_unrelated_projection() -> None:
    provider = StaticProjectionComponent("provider", {"needed": 7, "unrelated": 100})
    root = DependencyComponent(
        "root",
        (("provider", "needed"),),
        lambda values: values[0],
    )
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(root)
    kernel.register_component(provider)

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    assert provider.seen_targets == [("needed",)]
    assert root.views[-1] == ("provider/needed",)
    assert kernel.current_certificate("provider", "unrelated") is None


def test_shared_dependency_is_executed_once_and_reused() -> None:
    shared = StaticProjectionComponent("shared", {"value": 5})
    left = DependencyComponent("left", (("shared", "value"),), lambda values: values[0] + 1)
    right = DependencyComponent("right", (("shared", "value"),), lambda values: values[0] + 2)
    root = DependencyComponent(
        "root",
        (("left", "value"), ("right", "value")),
        lambda values: sum(values),
    )
    kernel = RecursiveConvergenceOrchestrationKernel()
    for component in (root, left, right, shared):
        kernel.register_component(component)

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    assert kernel.certificates[judgment.certificate_ids[0]].value == 13
    assert shared.calls == 1


def test_changed_projection_invalidates_and_reopens_only_causal_consumers() -> None:
    leaf = StaticProjectionComponent("leaf", {"value": 2})
    unrelated = StaticProjectionComponent("unrelated", {"value": 50})
    root = DependencyComponent("root", (("leaf", "value"),), lambda values: values[0] + 1)
    kernel = RecursiveConvergenceOrchestrationKernel()
    for component in (root, leaf, unrelated):
        kernel.register_component(component)

    first = kernel.run(root_component_id="root", epoch_id=EPOCH)
    first_root_id = first.certificate_ids[0]
    old_leaf = kernel.current_certificate("leaf", "value")
    assert old_leaf is not None

    new_leaf = replace(
        old_leaf,
        certificate_id=stable_hash("test-certificate", {"leaf": 9}),
        state_hash=stable_hash("test-state", 9),
        value=9,
        audit_digest=stable_hash("test-audit", {"leaf": 9}),
    )
    kernel.inject_certificate(new_leaf)

    assert kernel.certificates[old_leaf.certificate_id].valid is False
    assert kernel.certificates[first_root_id].valid is False
    assert unrelated.calls == 0

    second = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert second.outcome is OutcomeCode.CERTIFIED
    assert kernel.certificates[second.certificate_ids[0]].value == 10
    assert unrelated.calls == 0
    assert any(
        "root" in record.reactivated_frame_ids[0]
        for record in kernel.invalidation_records
        if record.reactivated_frame_ids
    )


def test_incremental_recomputation_matches_from_scratch_result() -> None:
    leaf = StaticProjectionComponent("leaf", {"value": 2})
    root = DependencyComponent("root", (("leaf", "value"),), lambda values: values[0] * 3)
    incremental = RecursiveConvergenceOrchestrationKernel()
    incremental.register_component(root)
    incremental.register_component(leaf)
    incremental.run(root_component_id="root", epoch_id=EPOCH)
    old_leaf = incremental.current_certificate("leaf", "value")
    assert old_leaf is not None
    incremental.inject_certificate(
        replace(
            old_leaf,
            certificate_id=stable_hash("test-certificate", {"leaf": 4}),
            state_hash=stable_hash("test-state", 4),
            value=4,
            audit_digest=stable_hash("test-audit", {"leaf": 4}),
        )
    )
    incremental_result = incremental.run(root_component_id="root", epoch_id=EPOCH)

    fresh_leaf = StaticProjectionComponent("leaf", {"value": 4})
    fresh_root = DependencyComponent("root", (("leaf", "value"),), lambda values: values[0] * 3)
    fresh = RecursiveConvergenceOrchestrationKernel()
    fresh.register_component(fresh_root)
    fresh.register_component(fresh_leaf)
    fresh_result = fresh.run(root_component_id="root", epoch_id=EPOCH)

    assert incremental.certificates[incremental_result.certificate_ids[0]].value == 12
    assert fresh.certificates[fresh_result.certificate_ids[0]].value == 12


def test_unrelated_registered_components_do_not_block_active_closure() -> None:
    root = StaticProjectionComponent("root", {"value": 1})
    unrelated = StaticProjectionComponent("unrelated", {"value": 2})
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(root)
    kernel.register_component(unrelated)

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    assert kernel.active_required_closure() == ("root",)
    assert unrelated.calls == 0


def test_semantic_feedback_cycle_converges_jointly() -> None:
    first = FeedbackComponent("first", "second")
    second = FeedbackComponent("second", "first")
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(first)
    kernel.register_component(second)

    judgment = kernel.run(root_component_id="first", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.CERTIFIED
    assert kernel.certificates[judgment.certificate_ids[0]].value == 2
    regions = kernel.dependencies.cyclic_regions({"first", "second"})
    assert len(regions) == 1
    assert regions[0].cycle_class.value == "semantic_feedback"


def test_oscillating_feedback_cycle_returns_unknown() -> None:
    first = FeedbackComponent("first", "second", oscillating=True)
    second = FeedbackComponent("second", "first", oscillating=True)
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(first)
    kernel.register_component(second)

    judgment = kernel.run(root_component_id="first", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.UNKNOWN
    assert any("semantic_cycle_not_solved" in reason for reason in judgment.reasons)


def test_containment_cycle_is_rejected() -> None:
    graph = ContainmentGraph()
    graph.add("root", "child")
    graph.add("child", "grandchild")

    with pytest.raises(ValueError, match="containment_cycle"):
        graph.add("grandchild", "root")


def test_suspended_runtime_snapshot_restores_exact_continuation() -> None:
    leaf = StaticProjectionComponent("leaf", {"value": 4})
    root = DependencyComponent("root", (("leaf", "value"),), lambda values: values[0] + 1)
    kernel = RecursiveConvergenceOrchestrationKernel(maximum_global_steps=1)
    kernel.register_component(root)
    kernel.register_component(leaf)

    interrupted = kernel.run(root_component_id="root", epoch_id=EPOCH)
    assert interrupted.outcome is OutcomeCode.UNKNOWN
    assert any(frame.status.value == "suspended" for frame in kernel.frames.values())

    payload = json.loads(dump_kernel_snapshot(kernel))
    payload["maximum_global_steps"] = 100
    restored = restore_kernel_snapshot(
        json.dumps(payload, sort_keys=True),
        components=(root, leaf),
    )
    resumed = restored.run(root_component_id="root", epoch_id=EPOCH)

    assert resumed.outcome is OutcomeCode.CERTIFIED
    assert restored.certificates[resumed.certificate_ids[0]].value == 5
    assert any(
        event.event_type == "frame_resumed" and event.component_id == "root"
        for event in restored.audit_events
    )


def test_kernel_rejects_cross_epoch_reuse() -> None:
    root = StaticProjectionComponent("root", {"value": 1})
    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(root)
    kernel.run(root_component_id="root", epoch_id=EPOCH)

    with pytest.raises(ValueError, match="different active epoch"):
        kernel.run(root_component_id="root", epoch_id="epoch:test:2")


def test_effect_committer_blocks_before_closure_without_calling_executor() -> None:
    committer = ClosureGatedEffectCommitter()
    plan = EffectPlan(
        effect_id="effect:1",
        idempotency_key="idempotency:1",
        action_name="test_action",
        payload={"value": 1},
        authority_refs=("authority:test",),
    )
    called = 0

    def executor(_plan):
        nonlocal called
        called += 1
        return "executed"

    receipt = committer.commit(
        plan=plan,
        closure_certificate=_closure_certificate(level=SettlementLevel.BOUNDARY_RECONCILED),
        executor=executor,
        verifier=lambda _plan, _result: (True, "verified"),
    )

    assert receipt.status is EffectStatus.BLOCKED
    assert receipt.reason == "closure_certificate_level_insufficient"
    assert called == 0


def test_effect_committer_is_idempotent_and_verifies_execution() -> None:
    committer = ClosureGatedEffectCommitter()
    plan = EffectPlan(
        effect_id="effect:2",
        idempotency_key="idempotency:2",
        action_name="test_action",
        payload={"value": 2},
        authority_refs=("authority:test",),
    )
    calls = 0

    def executor(_plan):
        nonlocal calls
        calls += 1
        return {"applied": True}

    first = committer.commit(
        plan=plan,
        closure_certificate=_closure_certificate(),
        executor=executor,
        verifier=lambda _plan, result: (result["applied"], "observed"),
    )
    second = committer.commit(
        plan=plan,
        closure_certificate=_closure_certificate(),
        executor=executor,
        verifier=lambda _plan, result: (result["applied"], "observed"),
    )

    assert first.status is EffectStatus.VERIFIED
    assert second == first
    assert calls == 1


def test_failed_verification_uses_compensation_or_requires_recovery() -> None:
    committer = ClosureGatedEffectCommitter()
    plan = EffectPlan(
        effect_id="effect:3",
        idempotency_key="idempotency:3",
        action_name="test_action",
        payload={},
        authority_refs=("authority:test",),
        compensation_name="undo_test_action",
    )
    compensated = committer.commit(
        plan=plan,
        closure_certificate=_closure_certificate(),
        executor=lambda _plan: "applied",
        verifier=lambda _plan, _result: (False, "mismatch"),
        compensator=lambda _plan, _result: "reverted",
    )

    assert compensated.status is EffectStatus.COMPENSATED

    second_plan = replace(plan, effect_id="effect:4", idempotency_key="idempotency:4")

    def broken_compensator(_plan, _result):
        raise RuntimeError("broken")

    recovery = committer.commit(
        plan=second_plan,
        closure_certificate=_closure_certificate(),
        executor=lambda _plan: "applied",
        verifier=lambda _plan, _result: (False, "mismatch"),
        compensator=broken_compensator,
    )
    assert recovery.status is EffectStatus.RECOVERY_REQUIRED


def test_world_verification_requires_physical_observation() -> None:
    closure = _closure_certificate(value={"expected": 1})
    observation = WorldObservation(
        observation_id="observation:1",
        observed_value={"observed": 1},
        evidence_refs=("sensor:test:1",),
        evidence_scope=EvidenceScope.PHYSICALLY_VERIFIED,
        confidence=0.95,
    )

    world = issue_world_verified_certificate(
        closure_certificate=closure,
        observation=observation,
    )

    assert world.level is SettlementLevel.WORLD_VERIFIED
    assert world.evidence_scope is EvidenceScope.PHYSICALLY_VERIFIED
    assert closure.certificate_id in world.dependency_certificate_ids

    with pytest.raises(ValueError, match="physically verified"):
        WorldObservation(
            observation_id="observation:2",
            observed_value=1,
            evidence_refs=("simulation:test",),
            evidence_scope=EvidenceScope.SIMULATED,
        )


def test_dependency_gated_snet_certifies_promoted_children_before_parent() -> None:
    mesh = SNetRecursiveMesh(SNetInquiryBudget(max_depth=3))
    root = mesh.add_symbol("Seed", symbol_type="physical_biological_object")

    def answers(symbol):
        if symbol.label == "Seed":
            return {SNetWHType.DEPENDS_ON: "Water"}
        if symbol.label == "water":
            return {SNetWHType.DEPENDS_ON: "Molecule"}
        return {}

    kernel, judgment = run_dependency_gated_snet(
        mesh=mesh,
        root_symbol_id=root.symbol_id,
        answer_provider=answers,
        epoch_id=EPOCH,
    )

    assert judgment.outcome is OutcomeCode.CERTIFIED
    certifications = [
        event
        for event in kernel.audit_events
        if event.event_type == "frame_candidate_certified"
    ]
    root_component_id = f"{SNET_COMPONENT_PREFIX}{root.symbol_id}"
    root_sequence = next(
        event.sequence for event in certifications if event.component_id == root_component_id
    )
    child_sequences = [
        event.sequence for event in certifications if event.component_id != root_component_id
    ]
    assert len(child_sequences) == 2
    assert max(child_sequences) < root_sequence
    assert kernel.certificates[judgment.certificate_ids[0]].value["child_certificate_ids"]


def test_universal_action_adapter_requires_closure_and_authority() -> None:
    class FakeUniversalActionKernel:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, request):
            self.calls += 1
            return {"request": request, "status": "ran"}

    fake = FakeUniversalActionKernel()
    adapter = UniversalActionClosureAdapter(fake)

    with pytest.raises(ValueError, match="level_insufficient"):
        adapter.dispatch(
            closure_certificate=_closure_certificate(level=SettlementLevel.BOUNDARY_RECONCILED),
            request={"action": "x"},
            authority_check=lambda _request: True,
        )
    with pytest.raises(ValueError, match="authority_rejected"):
        adapter.dispatch(
            closure_certificate=_closure_certificate(),
            request={"action": "x"},
            authority_check=lambda _request: False,
        )

    result = adapter.dispatch(
        closure_certificate=_closure_certificate(),
        request={"action": "x"},
        authority_check=lambda _request: True,
    )
    assert result["status"] == "ran"
    assert fake.calls == 1


def test_unknown_component_outcome_is_not_silently_certified() -> None:
    class UnknownComponent(BaseConvergentComponent):
        contract = _contract("root")

        def step(self, frame, dependency_view):
            del frame, dependency_view
            return Unknown("evidence_not_available")

    kernel = RecursiveConvergenceOrchestrationKernel()
    kernel.register_component(UnknownComponent())

    judgment = kernel.run(root_component_id="root", epoch_id=EPOCH)

    assert judgment.outcome is OutcomeCode.UNKNOWN
    assert judgment.certificate_ids == ()
    assert any("evidence_not_available" in reason for reason in judgment.reasons)
